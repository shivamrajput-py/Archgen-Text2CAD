# Load environment variables from .env file automatically
# This allows the server to work without manually exporting env vars
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import uuid
import logging
import json
import shutil
import asyncio
from datetime import datetime, timedelta
import os
import sqlite3
from pathlib import Path

# Load .env file before any API clients initialize
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=False)
    if _env_path.exists():
        logging.getLogger(__name__).info(f"Loaded environment from {_env_path}")
except ImportError:
    pass  # python-dotenv not installed; rely on shell env vars

from drawing_generator import generate_2d_drawing


# WebSocket manager for real-time updates
from websocket_manager import (
    ws_manager, 
    GenerationStage, 
    ProgressUpdate, 
    calculate_progress
)

# Import all the classes from your workflow
# (Assuming they're in the same file or properly importable)
from app import (
    TextToCADOrchestrator,
    HybridRAG,
    CADGenerationResult,
    ValidationResult,
    ValidationCategory,
    AgentState
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Enhanced Text-to-CAD Workflow API",
    description="Professional Text-to-CAD system with multi-agent workflow, RAG, and conversational memory",
    version="2.0.0"
)

# Add CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== CONFIGURATION ====================
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DEFAULT_MODEL = "qwen/qwen3.5-plus-02-15"
JSON_EXAMPLES_PATH = "dataset.json"
SESSION_TIMEOUT_HOURS = 24
MAX_SESSIONS = 100
FREECAD_TIMEOUT_SECONDS = 600  # 10 minutes timeout for generation + execution
ENABLE_FREECAD_EXECUTION = True # Set to True to enable actual FreeCAD execution

# Model storage paths
MODELS_DIR = Path(__file__).parent / "generated_models"
MODELS_DIR.mkdir(exist_ok=True)
MODEL_REGISTRY = MODELS_DIR / "model_registry.json"

def _load_model_registry() -> dict:
    """Load persisted model metadata from disk."""
    if MODEL_REGISTRY.exists():
        try:
            with open(MODEL_REGISTRY, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def _save_model_registry():
    """Persist current model metadata to disk."""
    try:
        with open(MODEL_REGISTRY, 'w') as f:
            json.dump(generated_models, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save model registry: {e}")

# Mount static files for model downloads
app.mount("/models", StaticFiles(directory=str(MODELS_DIR)), name="models")

# ==================== DATA MODELS ====================

class CADGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Text description of the CAD model to generate")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    new_session: bool = Field(False, description="Force create new session")
    model_name: str = Field(DEFAULT_MODEL, description="LLM model to use")
    max_iterations: int = Field(5, description="Maximum refinement iterations")
    min_quality_score: float = Field(0.7, description="Minimum quality threshold")
    temperature: float = Field(0.1, description="LLM temperature parameter")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds")

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    limit: int
    username: str
    company: Optional[str] = None

class UserSessions(BaseModel):
    sessions_json: str

class SessionInfo(BaseModel):
    session_id: str
    created_at: datetime
    last_used: datetime
    prompt_count: int
    status: str

class CADGenerationResponse(BaseModel):
    session_id: str
    model_id: Optional[str] = None
    success: bool
    script: str
    final_score: float
    iterations: int
    message: str
    validation_results: Dict[str, Dict]
    generation_time_seconds: float
    prompt_count: int
    error_summary: Optional[str] = None
    svg_path: Optional[str] = None

class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}

class ConversationHistory(BaseModel):
    session_id: str
    messages: List[ConversationMessage]
    total_messages: int
    created_at: datetime
    last_used: datetime

# ==================== GLOBAL STATE ====================

class GlobalCADSystem:
    def __init__(self):
        self.orchestrator: Optional[TextToCADOrchestrator] = None
        self.rag_system: Optional[HybridRAG] = None
        self.conversations: Dict[str, List[ConversationMessage]] = {}
        self.session_metadata: Dict[str, SessionInfo] = {}
        self.initialized = False
        self.initialization_error = None
        
    async def initialize(self):
        """Initialize the CAD system and RAG once at startup"""
        try:
            logger.info("Initializing Enhanced Text-to-CAD System...")
            
            # Verify API key
            if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "paste-your-api-key-here":
                raise ValueError("OpenRouter API key is required")
            
            # Initialize RAG system (loaded once)
            logger.info("Loading RAG system...")
            self.rag_system = HybridRAG(JSON_EXAMPLES_PATH)
            logger.info(f"RAG system loaded with {len(self.rag_system.local_examples)} examples")
            
            # Initialize orchestrator with pre-loaded RAG
            logger.info("Initializing orchestrator...")
            self.orchestrator = TextToCADOrchestrator(
                openrouter_api_key=OPENROUTER_API_KEY,
                model_name=DEFAULT_MODEL,
                json_examples_path=JSON_EXAMPLES_PATH,
                max_iterations=5,
                min_quality_score=0.7,
                execution_timeout=FREECAD_TIMEOUT_SECONDS,
                enable_execution=ENABLE_FREECAD_EXECUTION
            )
            
            self.initialized = True
            logger.info("Enhanced Text-to-CAD System initialized successfully!")
            
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"Failed to initialize system: {e}")
            raise e
    
    def create_session(self, force_new: bool = False, session_id: Optional[str] = None) -> str:
        """Create or get session ID"""
        if not force_new and session_id and session_id in self.conversations:
            # Update last used time
            self.session_metadata[session_id].last_used = datetime.now()
            return session_id
        
        # Create new session - use provided session_id if given, else generate new
        new_session_id = session_id if (session_id and not force_new) else str(uuid.uuid4())
        self.conversations[new_session_id] = []
        self.session_metadata[new_session_id] = SessionInfo(
            session_id=new_session_id,
            created_at=datetime.now(),
            last_used=datetime.now(),
            prompt_count=0,
            status="active"
        )
        
        # Clean up old sessions if needed
        self._cleanup_old_sessions()
        
        logger.info(f"Created new session: {new_session_id}")
        return new_session_id
    
    def _cleanup_old_sessions(self):
        """Remove old sessions to prevent memory bloat"""
        if len(self.conversations) <= MAX_SESSIONS:
            return
        
        # Remove oldest sessions
        cutoff_time = datetime.now() - timedelta(hours=SESSION_TIMEOUT_HOURS)
        sessions_to_remove = [
            sid for sid, meta in self.session_metadata.items()
            if meta.last_used < cutoff_time
        ]
        
        for sid in sessions_to_remove:
            self.conversations.pop(sid, None)
            self.session_metadata.pop(sid, None)
            
        logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
    
    def add_conversation_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
            
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.conversations[session_id].append(message)
        
        if session_id in self.session_metadata:
            self.session_metadata[session_id].last_used = datetime.now()
            if role == "user":
                self.session_metadata[session_id].prompt_count += 1
    
    def get_conversation_context(self, session_id: str, max_exchanges: int = 3) -> str:
        """Get conversation context for the LLM"""
        if session_id not in self.conversations or not self.conversations[session_id]:
            return ""
        
        messages = self.conversations[session_id]
        recent_messages = messages[-(max_exchanges * 2):]  # Last N exchanges
        
        context_parts = []
        for msg in recent_messages:
            if msg.role == "user":
                context_parts.append(f"Previous User Request: {msg.content}")
            elif msg.role == "assistant":
                # Include summary of previous generation
                metadata = msg.metadata
                if metadata.get("success"):
                    context_parts.append(f"Previous Generation: Success (Score: {metadata.get('final_score', 'N/A')}, Iterations: {metadata.get('iterations', 'N/A')})")
                    if metadata.get("validation_summary"):
                        context_parts.append(f"Previous Validation: {metadata.get('validation_summary')}")
                else:
                    context_parts.append(f"Previous Generation: Failed - {metadata.get('error_summary', 'Unknown error')}")
        
        return "\n".join(context_parts)

# Global system instance
cad_system = GlobalCADSystem()

# ==================== GENERATION QUEUE (SEMAPHORE) ====================
# Only ONE FreeCAD subprocess runs at a time to prevent OOM on the server.
# Additional requests wait in a queue. If already 3 requests waiting, reject immediately.
GENERATION_SEMAPHORE = asyncio.Semaphore(1)   # 1 concurrent FreeCAD execution
MAX_QUEUE_SIZE = 3                             # Max requests allowed to wait
_queue_size = 0                                # Current number of requests waiting


# ==================== AUTH & QUOTA MANAGEMENT ====================
CLIENTS_DB_PATH = Path("clients.json")

def _load_clients() -> List[Dict[str, Any]]:
    if not CLIENTS_DB_PATH.exists():
        return []
    with open(CLIENTS_DB_PATH, "r") as f:
        return json.load(f)

def _save_clients(clients: List[Dict[str, Any]]):
    with open(CLIENTS_DB_PATH, "w") as f:
        json.dump(clients, f, indent=2)

def get_current_user(authorization: str = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split("Bearer ")[1]
    clients = _load_clients()
    for c in clients:
        if c.get("token") == token:
            return c
    raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    clients = _load_clients()
    for c in clients:
        if c.get("username") == request.username and c.get("password") == request.password:
            return LoginResponse(
                token=c.get("token", ""),
                limit=c.get("limit", 0),
                username=c.get("username", ""),
                company=c.get("company", "")
            )
    raise HTTPException(status_code=401, detail="Invalid username or password")

# ==================== CLOUD SESSIONS ====================
DB_PATH = "archgen_db.sqlite"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/user/sessions")
async def get_user_sessions(current_user: Dict[str, Any] = Depends(get_current_user)):
    username = current_user.get("username")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT sessions_json FROM user_sessions WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"sessions_json": row["sessions_json"]}
    return {"sessions_json": "[]"}

@app.post("/user/sessions")
async def save_user_sessions(data: UserSessions, current_user: Dict[str, Any] = Depends(get_current_user)):
    username = current_user.get("username")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_sessions (username, sessions_json) VALUES (?, ?)", 
        (username, data.sessions_json)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}

# ==================== API ENDPOINTS ====================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    # Create User Sessions Table if not exists
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS user_sessions (username TEXT PRIMARY KEY, sessions_json TEXT)")
    conn.commit()
    conn.close()
    
    try:
        await cad_system.initialize()
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Don't crash the server, let health check handle it

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "service": "Enhanced Text-to-CAD Workflow API",
        "version": "2.0.0",
        "status": "initialized" if cad_system.initialized else "initializing",
        "features": [
            "Multi-agent CAD generation workflow",
            "RAG-enhanced generation",
            "Conversational memory",
            "Session management", 
            "Quality validation",
            "Iterative refinement",
            "Comprehensive error handling"
        ],
        "endpoints": {
            "generate": "/generate-cad",
            "sessions": "/sessions",
            "conversation": "/conversation/{session_id}",
            "health": "/health"
        }
    }

@app.post("/generate-cad", response_model=CADGenerationResponse)
async def generate_cad(request: CADGenerationRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Generate CAD script using the enhanced workflow and evaluate quotas."""
    start_time = datetime.now()
    
    # ── Check quota limit ──
    clients = _load_clients()
    client_idx = next((i for i, c in enumerate(clients) if c.get("username") == current_user["username"]), None)
    if client_idx is None or clients[client_idx].get("limit", 0) <= 0:
        raise HTTPException(status_code=403, detail="Quota exceeded. Please contact support to increase your limit.")
    
    # Check system initialization
    if not cad_system.initialized:
        raise HTTPException(
            status_code=503,
            detail=f"System not initialized. Error: {cad_system.initialization_error or 'Unknown error'}"
        )
    
    # Handle session management
    session_id = cad_system.create_session(
        force_new=request.new_session,
        session_id=request.session_id
    )

    # ── Generation queue guard ──
    # Reject immediately if too many requests are already waiting
    global _queue_size
    if _queue_size >= MAX_QUEUE_SIZE:
        raise HTTPException(
            status_code=503,
            detail=f"Server is busy — {_queue_size} request(s) already queued. Please try again in a few minutes."
        )

    # Increment queue counter BEFORE acquiring semaphore
    _queue_size += 1

    try:
        # Notify user of queue position while waiting
        await ws_manager.send_progress(session_id, ProgressUpdate(
            stage=GenerationStage.QUEUED,
            progress=0.0,
            message=(
                f"Queued \u2014 waiting for current generation to finish..."
                if _queue_size > 1 else "Starting CAD generation..."
            )
        ))

        # Block until no other FreeCAD subprocess is running.
        # Semaphore(1): only ONE generation at a time; others wait in async queue.
        async with GENERATION_SEMAPHORE:
            _queue_size -= 1  # acquired lock, no longer waiting

            await ws_manager.send_progress(session_id, ProgressUpdate(
                stage=GenerationStage.QUEUED,
                progress=0.01,
                message="Your turn \u2014 starting generation..."
            ))

            # Add user message to conversation
            cad_system.add_conversation_message(
                session_id, "user", request.prompt,
                {"model_name": request.model_name, "parameters": request.model_dump()}
            )

            await ws_manager.send_progress(session_id, ProgressUpdate(
                stage=GenerationStage.VALIDATING_PROMPT,
                progress=0.05,
                message="Analyzing your prompt..."
            ))

            conversation_context = cad_system.get_conversation_context(session_id)

            enhanced_user_prompt = request.prompt
            if conversation_context:
                enhanced_user_prompt = conversation_context + "\n\nCurrent Request: " + request.prompt

            await ws_manager.send_progress(session_id, ProgressUpdate(
                stage=GenerationStage.RETRIEVING_EXAMPLES,
                progress=0.10,
                message="Finding similar CAD examples..."
            ))

            cad_system.orchestrator.max_iterations = request.max_iterations
            cad_system.orchestrator.min_quality_score = request.min_quality_score

            if request.model_name != cad_system.orchestrator.cadgen_llm.model_name:
                from langchain_openai import ChatOpenAI
                cad_system.orchestrator.cadgen_llm = ChatOpenAI(
                    openai_api_key=OPENROUTER_API_KEY,
                    openai_api_base="https://openrouter.ai/api/v1",
                    model_name=request.model_name,
                    temperature=request.temperature,
                    timeout=180,
                    max_retries=2
                )
                cad_system.orchestrator.cad_generator.llm = cad_system.orchestrator.cadgen_llm

            logger.info(f"Starting CAD generation for session {session_id}")

            async def _ws_progress(stage, progress, message, iteration=0, max_iter=0):
                stage_map = {
                    "validating_prompt": GenerationStage.VALIDATING_PROMPT,
                    "retrieving_examples": GenerationStage.RETRIEVING_EXAMPLES,
                    "generating_script": GenerationStage.GENERATING_SCRIPT,
                    "executing_engine": GenerationStage.EXECUTING_ENGINE,
                    "validating_geometry": GenerationStage.VALIDATING_GEOMETRY,
                    "refining": GenerationStage.REFINING,
                    "exporting_model": GenerationStage.EXPORTING_MODEL,
                }
                ws_stage = stage_map.get(stage, GenerationStage.GENERATING_SCRIPT)
                await ws_manager.send_progress(session_id, ProgressUpdate(
                    stage=ws_stage,
                    progress=min(progress, 0.98),
                    message=message,
                    iteration=iteration,
                    max_iterations=max_iter,
                ))

            result: CADGenerationResult = await cad_system.orchestrator.generate_cad(
                enhanced_user_prompt, progress_callback=_ws_progress
            )

            generation_time = (datetime.now() - start_time).total_seconds()

            validation_dict = {}
            for category, validation in result.validation_results.items():
                validation_dict[category] = {
                    "is_valid": validation.is_valid,
                    "score": validation.score,
                    "errors": validation.errors,
                    "suggestions": validation.suggestions,
                    "category": validation.category
                }

            valid_count = sum(1 for v in result.validation_results.values() if v.is_valid)
            total_count = len(result.validation_results)
            validation_summary = f"Valid: {valid_count}/{total_count}"

            model_id = None
            if result.success:
                stl_path = result.stl_path
                fcstd_path = result.fcstd_path

                logger.info(f"Model files - STL: {stl_path}, FCSTD: {fcstd_path}")

                model_id = f"{session_id}_{uuid.uuid4().hex[:8]}"

                perm_dir = MODELS_DIR / model_id
                perm_dir.mkdir(parents=True, exist_ok=True)

                perm_stl = None
                perm_step = None
                perm_fcstd = None

                if stl_path and Path(stl_path).exists():
                    perm_stl = str(perm_dir / "model.stl")
                    shutil.copy2(stl_path, perm_stl)
                    logger.info(f"Copied STL to permanent: {perm_stl}")

                if fcstd_path and Path(fcstd_path).exists():
                    perm_fcstd = str(perm_dir / "model.FCStd")
                    shutil.copy2(fcstd_path, perm_fcstd)
                    logger.info(f"Copied FCStd to permanent: {perm_fcstd}")

                    temp_step = Path(fcstd_path).parent / "renders" / "model.step"
                    if temp_step.exists():
                        perm_step = str(perm_dir / "model.step")
                        shutil.copy2(str(temp_step), perm_step)
                        logger.info(f"Copied STEP to permanent: {perm_step}")

                perm_svg = None
                if perm_stl and Path(perm_stl).exists():
                    svg_out = str(perm_dir / "drawing.svg")
                    await ws_manager.send_progress(session_id, ProgressUpdate(
                        stage=GenerationStage.EXPORTING_MODEL,
                        progress=0.97,
                        message="Generating 2D engineering drawing..."
                    ))
                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        ok = await loop.run_in_executor(
                            None,
                            generate_2d_drawing,
                            perm_stl, svg_out, request.prompt
                        )
                        if ok and Path(svg_out).exists():
                            perm_svg = svg_out
                            logger.info(f"2D drawing generated: {perm_svg}")
                        else:
                            logger.warning("2D drawing generation returned False \u2014 skipping")
                    except Exception as svg_err:
                        logger.warning(f"2D drawing generation failed (non-fatal): {svg_err}")

                model_data = {
                    "session_id": session_id,
                    "stl_path": perm_stl,
                    "fcstd_path": perm_fcstd,
                    "step_path": perm_step,
                    "svg_path": perm_svg,
                    "created_at": datetime.now().isoformat(),
                    "generation_time": generation_time
                }
                session_models[session_id] = model_data
                generated_models[model_id] = model_data
                _save_model_registry()

                if client_idx is not None:
                    clients[client_idx]["limit"] -= 1
                    _save_clients(clients)
                    uname = clients[client_idx]["username"]
                    rem = clients[client_idx]["limit"]
                    logger.info(f"Deducted 1 prompt from {uname}. Remaining limit: {rem}")

                await ws_manager.send_model_ready(session_id, {
                    "model_id": model_id,
                    "stl_url": f"/download/model/{model_id}/stl" if stl_path else None,
                    "fcstd_url": f"/download/model/{model_id}/fcstd" if fcstd_path else None,
                    "step_url": f"/download/model/{model_id}/step" if fcstd_path else None,
                    "svg_url": f"/download/model/{model_id}/svg" if perm_svg else None
                })

            await ws_manager.send_progress(session_id, ProgressUpdate(
                stage=GenerationStage.COMPLETED,
                progress=1.0,
                message="CAD generation complete!",
                iteration=result.iterations,
                max_iterations=request.max_iterations
            ))

            cad_system.add_conversation_message(
                session_id, "assistant", result.script,
                {
                    "success": result.success,
                    "final_score": result.final_score,
                    "iterations": result.iterations,
                    "validation_results": validation_dict,
                    "validation_summary": validation_summary,
                    "error_summary": result.error_summary,
                    "generation_time": generation_time
                }
            )

            prompt_count = cad_system.session_metadata[session_id].prompt_count

            logger.info(
                f"CAD generation completed for session {session_id} "
                f"- Success: {result.success}, Score: {result.final_score:.2f}"
            )

            await ws_manager.send_generation_complete(session_id, {
                "success": result.success,
                "final_score": result.final_score,
                "iterations": result.iterations,
                "message": "CAD generation completed successfully" if result.success else "CAD generation failed"
            })

            return CADGenerationResponse(
                session_id=session_id,
                model_id=model_id,
                success=result.success,
                script=result.script,
                final_score=result.final_score,
                iterations=result.iterations,
                message="CAD generation completed successfully" if result.success else "CAD generation failed",
                validation_results=validation_dict,
                generation_time_seconds=generation_time,
                prompt_count=prompt_count,
                error_summary=result.error_summary
            )

    except Exception as e:
        # Always restore queue counter on any failure path
        if _queue_size > 0:
            _queue_size -= 1
        logger.error(f"Generation error for session {session_id}: {e}")

        await ws_manager.send_error(session_id, str(e))
        await ws_manager.send_progress(session_id, ProgressUpdate(
            stage=GenerationStage.FAILED,
            progress=0.0,
            message=f"Generation failed: {str(e)}"
        ))

        cad_system.add_conversation_message(
            session_id, "assistant", "",
            {"success": False, "error": str(e), "error_type": type(e).__name__}
        )

        generation_time = (datetime.now() - start_time).total_seconds()
        prompt_count = cad_system.session_metadata.get(session_id, SessionInfo(
            session_id=session_id, created_at=datetime.now(),
            last_used=datetime.now(), prompt_count=0, status="error"
        )).prompt_count

        return CADGenerationResponse(
            session_id=session_id,
            model_id=None,
            success=False,
            script="",
            final_score=0.0,
            iterations=0,
            message=f"Generation failed: {str(e)}",
            validation_results={},
            generation_time_seconds=generation_time,
            prompt_count=prompt_count,
            error_summary=str(e)
        )


@app.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    sessions = []
    for session_id, metadata in cad_system.session_metadata.items():
        sessions.append({
            "session_id": session_id,
            "created_at": metadata.created_at,
            "last_used": metadata.last_used,
            "prompt_count": metadata.prompt_count,
            "message_count": len(cad_system.conversations.get(session_id, [])),
            "status": metadata.status
        })
    
    return {
        "active_sessions": len(sessions),
        "sessions": sorted(sessions, key=lambda x: x["last_used"], reverse=True),
        "system_stats": {
            "total_conversations": len(cad_system.conversations),
            "rag_examples_loaded": len(cad_system.rag_system.local_examples) if cad_system.rag_system else 0,
            "system_initialized": cad_system.initialized
        }
    }

@app.get("/conversation/{session_id}", response_model=ConversationHistory)
async def get_conversation(session_id: str):
    """Get conversation history for a session"""
    if session_id not in cad_system.conversations:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = cad_system.conversations[session_id]
    metadata = cad_system.session_metadata.get(session_id)
    
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages),
        created_at=metadata.created_at if metadata else datetime.now(),
        last_used=metadata.last_used if metadata else datetime.now()
    )

@app.delete("/conversation/{session_id}")
async def clear_conversation(session_id: str):
    """Clear conversation history for a session"""
    if session_id not in cad_system.conversations:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Clear conversation and metadata
    del cad_system.conversations[session_id]
    del cad_system.session_metadata[session_id]
    
    return {"message": f"Conversation {session_id} cleared successfully"}

@app.post("/sessions/cleanup")
async def cleanup_sessions():
    """Manually trigger session cleanup"""
    initial_count = len(cad_system.conversations)
    cad_system._cleanup_old_sessions()
    final_count = len(cad_system.conversations)
    
    return {
        "message": "Session cleanup completed",
        "sessions_removed": initial_count - final_count,
        "active_sessions": final_count
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_info = {
        "status": "healthy" if cad_system.initialized else "unhealthy",
        "system_initialized": cad_system.initialized,
        "active_sessions": len(cad_system.conversations),
        "rag_system_loaded": cad_system.rag_system is not None,
        "orchestrator_ready": cad_system.orchestrator is not None,
        "components": {
            "rag_examples_count": len(cad_system.rag_system.local_examples) if cad_system.rag_system else 0,
            "embeddings_ready": cad_system.rag_system.embeddings is not None if cad_system.rag_system else False,
            "conversation_memory": len(cad_system.conversations) > 0
        }
    }
    
    if cad_system.initialization_error:
        health_info["error"] = cad_system.initialization_error
    
    return health_info

@app.get("/rag/stats")
async def rag_statistics():
    """Get RAG system statistics"""
    if not cad_system.rag_system:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    
    return {
        "examples_loaded": len(cad_system.rag_system.local_examples),
        "embeddings_created": cad_system.rag_system.embeddings is not None,
        "embedding_dimensions": cad_system.rag_system.embeddings.shape if cad_system.rag_system.embeddings is not None else None,
        "json_file_path": cad_system.rag_system.json_file_path,
        "embedding_model": cad_system.rag_system.embedding_model.get_sentence_embedding_dimension() if hasattr(cad_system.rag_system.embedding_model, 'get_sentence_embedding_dimension') else "unknown"
    }

# ==================== WEBSOCKET ENDPOINTS ====================

# Track session model files
session_models: Dict[str, Dict[str, str]] = {}
generated_models: Dict[str, Dict[str, str]] = _load_model_registry()

# NOTE: Defect 11 fixed — the duplicate /download/{session_id}/stl route that
# existed here (lines 676-690) was removed. The authoritative implementation
# is in the FILE DOWNLOAD ENDPOINTS section below (after the WebSocket endpoint).
@app.get("/download/model/{model_id}/stl")
async def download_model_stl(model_id: str):
    if model_id not in generated_models:
        raise HTTPException(status_code=404, detail="Model not found")
    stl_path = generated_models[model_id].get("stl_path")
    if not stl_path or not Path(stl_path).exists():
        raise HTTPException(status_code=404, detail="STL file not found")
    return FileResponse(path=stl_path, filename=f"model_{model_id[:8]}.stl", media_type="application/octet-stream")

@app.get("/download/model/{model_id}/step")
async def download_model_step(model_id: str):
    if model_id not in generated_models:
        raise HTTPException(status_code=404, detail="Model not found")
    step_path_str = generated_models[model_id].get("step_path")
    if step_path_str and Path(step_path_str).exists():
        return FileResponse(path=step_path_str, filename=f"model_{model_id[:8]}.step", media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="STEP file not available")

@app.get("/download/model/{model_id}/fcstd")
async def download_model_fcstd(model_id: str):
    if model_id not in generated_models:
        raise HTTPException(status_code=404, detail="Model not found")
    fcstd_path = generated_models[model_id].get("fcstd_path")
    if fcstd_path and Path(fcstd_path).exists():
        return FileResponse(path=fcstd_path, filename=f"model_{model_id[:8]}.fcstd", media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="FCStd file not available")

@app.get("/download/{session_id}/svg")
async def download_svg(session_id: str):
    """Download generated SVG TechDraw for a session."""
    files = _get_session_files(session_id)
    if not files:
        raise HTTPException(status_code=404, detail="No model found for this session")
    
    svg_path = files.get("svg_path")
    if not svg_path or not os.path.exists(svg_path):
        raise HTTPException(status_code=404, detail="SVG file not found")
    
    return FileResponse(
        svg_path,
        media_type="image/svg+xml",
        filename=f"archgen_model_{session_id[:8]}_blueprint.svg"
    )

@app.get("/download/model/{model_id}/svg")
async def download_model_svg(model_id: str):
    if model_id not in generated_models:
        raise HTTPException(status_code=404, detail="Model not found")
    svg_path = generated_models[model_id].get("svg_path")
    if svg_path and Path(svg_path).exists():
        return FileResponse(path=svg_path, filename=f"blueprint_{model_id[:8]}.svg", media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="SVG file not available")

@app.get("/download/model/{model_id}/obj")
async def download_model_obj(model_id: str):
    """Download OBJ file - converted on-the-fly from STL using trimesh."""
    if model_id not in generated_models:
        raise HTTPException(status_code=404, detail="Model not found")
    stl_path = generated_models[model_id].get("stl_path")
    if not stl_path or not Path(stl_path).exists():
        raise HTTPException(status_code=404, detail="Source STL file not found")
    try:
        import trimesh
        mesh = trimesh.load(stl_path)
        obj_path = Path(stl_path).with_suffix(".obj")
        mesh.export(str(obj_path), file_type="obj")
        return FileResponse(path=str(obj_path), filename=f"model_{model_id[:8]}.obj", media_type="application/octet-stream")
    except Exception as e:
        logger.error(f"OBJ conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"OBJ conversion failed: {str(e)}")

@app.get("/models/{session_id}/model.stl")
async def get_model_stl(session_id: str):
    """Get STL model file (alias for download endpoint)"""
    return await download_stl(session_id)

@app.get("/models/{session_id}/model.step")
async def get_model_step(session_id: str):
    """Get STEP model file (alias for download endpoint)"""
    return await download_step(session_id)

@app.get("/models/{session_id}/{view}.png")
async def get_model_image(session_id: str, view: str):
    """Get rendered PNG image for a specific view"""
    if session_id not in session_models:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get the render directory from the STL path
    stl_path = session_models[session_id].get("stl_path")
    if not stl_path:
        raise HTTPException(status_code=404, detail="Model not generated")
    
    # Images are in the same directory as STL (renders folder)
    render_dir = Path(stl_path).parent
    image_path = render_dir / f"{view}.png"
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail=f"Image view '{view}' not found")
    
    return FileResponse(
        path=str(image_path),
        media_type="image/png"
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time progress updates.
    Connect to receive progress events during CAD generation.
    """
    await ws_manager.connect(websocket, session_id)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to ArchgenCAD WebSocket"
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping/pong for connection keepalive
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    # Echo back any other messages (for debugging)
                    await websocket.send_json({
                        "type": "echo",
                        "data": data
                    })
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket, session_id)

# ==================== FILE DOWNLOAD ENDPOINTS ====================

def _get_session_files(session_id: str) -> dict:
    """DEFECT 13 FIX: look up file paths in the in-memory dict first,
    then fall back to the persistent registry so links survive server restarts."""
    if session_id in session_models:
        return session_models[session_id]
    # Try to find by session_id in the persisted generated_models registry
    for model_data in generated_models.values():
        if model_data.get("session_id") == session_id:
            return model_data
    return {}


@app.get("/download/{session_id}/stl")
async def download_stl(session_id: str):
    """Download generated STL file for a session."""
    files = _get_session_files(session_id)
    if not files:
        raise HTTPException(status_code=404, detail="No model found for this session")
    
    stl_path = files.get("stl_path")
    if not stl_path or not os.path.exists(stl_path):
        raise HTTPException(status_code=404, detail="STL file not found")
    
    return FileResponse(
        stl_path,
        media_type="application/octet-stream",
        filename=f"archgen_model_{session_id[:8]}.stl"
    )

@app.get("/download/{session_id}/fcstd")
async def download_fcstd(session_id: str):
    """Download generated FreeCAD file for a session."""
    files = _get_session_files(session_id)
    if not files:
        raise HTTPException(status_code=404, detail="No model found for this session")
    
    fcstd_path = files.get("fcstd_path")
    if not fcstd_path or not os.path.exists(fcstd_path):
        raise HTTPException(status_code=404, detail="FreeCAD file not found")
    
    return FileResponse(
        fcstd_path,
        media_type="application/octet-stream",
        filename=f"archgen_model_{session_id[:8]}.fcstd"
    )

@app.get("/model/{session_id}/info")
async def get_model_info(session_id: str):
    """Get information about generated model files for a session."""
    model_info = _get_session_files(session_id)
    if not model_info:
        return {
            "session_id": session_id,
            "has_model": False,
            "message": "No model generated yet"
        }
    
    return {
        "session_id": session_id,
        "has_model": True,
        "stl_available": model_info.get("stl_path") is not None and os.path.exists(model_info.get("stl_path", "")),
        "fcstd_available": model_info.get("fcstd_path") is not None and os.path.exists(model_info.get("fcstd_path", "")),
        "svg_available": model_info.get("svg_path") is not None and os.path.exists(model_info.get("svg_path", "")),
        "stl_url": f"/download/{session_id}/stl" if model_info.get("stl_path") else None,
        "fcstd_url": f"/download/{session_id}/fcstd" if model_info.get("fcstd_path") else None,
        "svg_url": f"/download/{session_id}/svg" if model_info.get("svg_path") else None,
        "created_at": model_info.get("created_at"),
        "generation_time": model_info.get("generation_time")
    }



# ==================== FEEDBACK ENDPOINT ====================
FEEDBACK_DIR = Path("feedback")
FEEDBACK_DIR.mkdir(exist_ok=True)

class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Quality rating 1-5")
    comment: Optional[str] = Field(None, description="Optional user comment")
    useful: Optional[bool] = Field(None, description="Was this model useful?")

@app.post("/feedback/{model_id}")
async def submit_feedback(model_id: str, request: FeedbackRequest):
    """Submit user feedback for a generated model."""
    feedback_file = FEEDBACK_DIR / "feedback.json"
    
    # Load existing feedback
    existing = []
    if feedback_file.exists():
        try:
            with open(feedback_file, 'r') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []
    
    # Add new feedback
    entry = {
        "model_id": model_id,
        "rating": request.rating,
        "comment": request.comment,
        "useful": request.useful,
        "timestamp": datetime.now().isoformat(),
    }
    existing.append(entry)
    
    # Save
    with open(feedback_file, 'w') as f:
        json.dump(existing, f, indent=2)
    
    logger.info(f"Feedback received for model {model_id}: rating={request.rating}")
    return {"status": "ok", "message": "Feedback saved. Thank you!"}

@app.get("/feedback/{model_id}")
async def get_feedback(model_id: str):
    """Get feedback for a specific model."""
    feedback_file = FEEDBACK_DIR / "feedback.json"
    if not feedback_file.exists():
        return {"model_id": model_id, "feedback": []}
    
    try:
        with open(feedback_file, 'r') as f:
            all_feedback = json.load(f)
        model_feedback = [fb for fb in all_feedback if fb.get("model_id") == model_id]
        return {"model_id": model_id, "feedback": model_feedback}
    except (json.JSONDecodeError, OSError):
        return {"model_id": model_id, "feedback": []}

# ==================== ADMIN: RAG REVIEW QUEUE ====================
# Recommendation 6: Promote auto-ingested RAG entries only after human review.
# These endpoints allow operators to inspect and approve/reject pending entries.

@app.get("/admin/rag/pending")
async def list_pending_rag_entries():
    """List all auto-ingested RAG entries that are awaiting human review.
    
    Returns entries with their dataset index so they can be approved
    via POST /admin/rag/approve/{index}.
    """
    if not cad_system.initialized or cad_system.rag_system is None:
        raise HTTPException(status_code=503, detail="CAD system not initialized")
    
    pending = cad_system.rag_system.get_pending_entries()
    return {
        "total_pending": len(pending),
        "total_dataset": len(cad_system.rag_system.local_examples),
        "entries": [
            {
                "index": e["index"],
                "prompt": e.get("prompt", "")[:120],
                "category": e.get("category", "unknown"),
                "difficulty": e.get("difficulty", "unknown"),
                "components": e.get("components", []),
                "ingested_at": e.get("ingested_at", "unknown"),
            }
            for e in pending
        ]
    }

@app.post("/admin/rag/approve/{index}")
async def approve_rag_entry(index: int):
    """Approve a pending auto-ingested RAG entry by its dataset index.
    
    Clears the review_pending flag and lifts the retrieval score penalty.
    The entry must have auto_ingested=True.
    """
    if not cad_system.initialized or cad_system.rag_system is None:
        raise HTTPException(status_code=503, detail="CAD system not initialized")
    
    ok = cad_system.rag_system.approve_entry(index)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Could not approve entry at index {index}. "
                   "Check that the index is valid and the entry is auto-ingested."
        )
    return {"status": "approved", "index": index, "message": "Entry is now fully promoted in the RAG dataset."}

@app.delete("/admin/rag/reject/{index}")
async def reject_rag_entry(index: int):
    """Reject and permanently remove a pending auto-ingested RAG entry.
    
    Use this to remove low-quality or hallucinated auto-ingested entries
    before they affect the retrieval system.
    """
    if not cad_system.initialized or cad_system.rag_system is None:
        raise HTTPException(status_code=503, detail="CAD system not initialized")
    
    rag = cad_system.rag_system
    if index < 0 or index >= len(rag.local_examples):
        raise HTTPException(status_code=404, detail=f"Index {index} out of range")
    
    entry = rag.local_examples[index]
    if not entry.get("auto_ingested"):
        raise HTTPException(status_code=400, detail="Can only reject auto-ingested entries")
    
    prompt_preview = entry.get("prompt", "")[:60]
    rag.local_examples.pop(index)
    
    # Persist removal
    with open(rag.json_file_path, "w", encoding="utf-8") as f:
        json.dump(rag.local_examples, f, indent=2)
    
    # Rebuild embeddings after deletion (deletion requires a full rebuild — acceptable since rare)
    rag._create_embeddings()
    
    logger.info(f"RAG reject: entry {index} removed ('{prompt_preview}...')")
    return {
        "status": "rejected",
        "index": index,
        "removed_prompt": prompt_preview,
        "remaining_dataset_size": len(rag.local_examples)
    }

@app.get("/admin/rag/stats")
async def rag_stats():
    """Return high-level statistics about the RAG dataset."""
    if not cad_system.initialized or cad_system.rag_system is None:
        raise HTTPException(status_code=503, detail="CAD system not initialized")
    
    examples = cad_system.rag_system.local_examples
    total = len(examples)
    auto_ingested = sum(1 for e in examples if e.get("auto_ingested"))
    pending = sum(1 for e in examples if e.get("auto_ingested") and e.get("review_pending", False))
    approved = sum(1 for e in examples if e.get("auto_ingested") and not e.get("review_pending", False))
    curated = total - auto_ingested
    
    by_category: dict = {}
    by_difficulty: dict = {}
    for e in examples:
        cat = e.get("category", "unknown")
        diff = e.get("difficulty", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
    
    return {
        "total_entries": total,
        "curated": curated,
        "auto_ingested": auto_ingested,
        "pending_review": pending,
        "approved_auto": approved,
        "by_category": by_category,
        "by_difficulty": by_difficulty,
        "embeddings_shape": list(cad_system.rag_system.embeddings.shape)
            if cad_system.rag_system.embeddings is not None else None
    }

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "paste-your-api-key-here":
        print("[ERROR] Please set your OpenRouter API key in the OPENROUTER_API_KEY variable")
        exit(1)
    
    print("[*] Starting ArchGen CAD Engine API")
    print(f"[*] API Key: {OPENROUTER_API_KEY[:8]}...")
    print(f"[*] RAG Examples: {JSON_EXAMPLES_PATH}")
    print(f"[*] Server: http://0.0.0.0:8000")
    print(f"[*] Docs: http://0.0.0.0:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
