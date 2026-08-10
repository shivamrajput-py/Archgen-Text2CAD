"""
WebSocket Manager for ArchgenCAD
=================================
Handles real-time progress updates during CAD generation.
"""

from typing import Dict, List, Set
from fastapi import WebSocket
import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class GenerationStage(str, Enum):
    """Stages of the CAD generation pipeline."""
    QUEUED = "queued"
    VALIDATING_PROMPT = "validating_prompt"
    RETRIEVING_EXAMPLES = "retrieving_examples"
    GENERATING_SCRIPT = "generating_script"
    VALIDATING_SYNTAX = "validating_syntax"
    EXECUTING_ENGINE = "executing_engine"
    VALIDATING_GEOMETRY = "validating_geometry"
    REFINING = "refining"
    EXPORTING_MODEL = "exporting_model"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProgressUpdate:
    """Progress update data structure."""
    stage: GenerationStage
    progress: float  # 0.0 to 1.0
    message: str
    iteration: int = 0
    max_iterations: int = 5
    details: dict = None
    
    def to_dict(self) -> dict:
        return {
            "type": "progress",
            "stage": self.stage.value,
            "progress": self.progress,
            "message": self.message,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "details": self.details or {},
            "timestamp": datetime.now().isoformat()
        }


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    Supports multiple clients per session.
    """
    
    def __init__(self):
        # session_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # session_id -> latest progress
        self.session_progress: Dict[str, ProgressUpdate] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a new WebSocket connection for a session."""
        await websocket.accept()
        
        async with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = set()
            self.active_connections[session_id].add(websocket)
        
        logger.info(f"WebSocket connected for session {session_id}")
        
        # Send current progress if available
        if session_id in self.session_progress:
            await self.send_to_client(
                websocket, 
                self.session_progress[session_id].to_dict()
            )
    
    async def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if session_id in self.active_connections:
                self.active_connections[session_id].discard(websocket)
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_to_client(self, websocket: WebSocket, data: dict):
        """Send data to a specific client."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")
    
    async def broadcast_to_session(self, session_id: str, data: dict):
        """Broadcast data to all clients connected to a session."""
        if session_id not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self.active_connections[session_id].discard(ws)
    
    async def send_progress(self, session_id: str, update: ProgressUpdate):
        """Send a progress update to all clients in a session."""
        self.session_progress[session_id] = update
        await self.broadcast_to_session(session_id, update.to_dict())
    
    async def send_model_ready(self, session_id: str, model_data: dict):
        """Notify clients that the model is ready for viewing."""
        message = {
            "type": "model_ready",
            "session_id": session_id,
            "stl_url": model_data.get("stl_url"),
            "fcstd_url": model_data.get("fcstd_url"),
            "preview_images": model_data.get("preview_images", []),
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_session(session_id, message)
    
    async def send_generation_complete(self, session_id: str, result: dict):
        """Notify clients that generation is complete."""
        message = {
            "type": "generation_complete",
            "session_id": session_id,
            "success": result.get("success", False),
            "final_score": result.get("final_score", 0),
            "iterations": result.get("iterations", 0),
            "message": result.get("message", ""),
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_session(session_id, message)
    
    async def send_error(self, session_id: str, error: str):
        """Send an error message to all clients in a session."""
        message = {
            "type": "error",
            "session_id": session_id,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_session(session_id, message)
    
    def get_connection_count(self, session_id: str = None) -> int:
        """Get the number of active connections."""
        if session_id:
            return len(self.active_connections.get(session_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())
    
    def clear_session(self, session_id: str):
        """Clean up session data."""
        if session_id in self.session_progress:
            del self.session_progress[session_id]


# Global connection manager instance
ws_manager = ConnectionManager()


# Progress calculation helpers
STAGE_PROGRESS = {
    GenerationStage.QUEUED: (0.0, 0.05),
    GenerationStage.VALIDATING_PROMPT: (0.05, 0.10),
    GenerationStage.RETRIEVING_EXAMPLES: (0.10, 0.15),
    GenerationStage.GENERATING_SCRIPT: (0.15, 0.40),
    GenerationStage.VALIDATING_SYNTAX: (0.40, 0.45),
    GenerationStage.EXECUTING_ENGINE: (0.45, 0.70),
    GenerationStage.VALIDATING_GEOMETRY: (0.70, 0.75),
    GenerationStage.REFINING: (0.75, 0.90),
    GenerationStage.EXPORTING_MODEL: (0.90, 0.98),
    GenerationStage.COMPLETED: (1.0, 1.0),
    GenerationStage.FAILED: (0.0, 0.0),
}


def calculate_progress(stage: GenerationStage, stage_progress: float = 0.5) -> float:
    """
    Calculate overall progress based on stage and intra-stage progress.
    
    Args:
        stage: Current generation stage
        stage_progress: Progress within the current stage (0.0 to 1.0)
    
    Returns:
        Overall progress (0.0 to 1.0)
    """
    start, end = STAGE_PROGRESS.get(stage, (0.0, 1.0))
    return start + (end - start) * stage_progress
