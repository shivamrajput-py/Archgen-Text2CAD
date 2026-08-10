# TextToCADOrchestrator - Main workflow orchestration
# Pipeline: PromptValidator → CADGenerator → ExecutionValidator → PhysicsChecker → VisualAssessor → QualityAssessor → RefinementAgent
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any

from langchain_openai import ChatOpenAI

from models import (
    ValidationResult, CADGenerationResult, ValidationCategory, DOMAIN_RULES
)
from rag import HybridRAG
from error_memory import ErrorMemory
from generation_archive import GenerationArchive
from agents.prompt_validator import PromptValidationAgent
from agents.cad_generator import CADGenerationAgent
from agents.execution_validator import ExecutionValidationAgent
from agents.quality_assessor import QualityAssessmentAgent
from agents.visual_assessor import VisualQualityAssessor
from agents.refinement_agent import RefinementAgent
from agents.physics_checker import PhysicsCheckAgent
from agents.fem_validator import FEMValidator
from agents.techdraw_generator import TechDrawGenerator

logger = logging.getLogger(__name__)

# Default model for fast/best when not explicitly overridden
# NOTE: arcee-ai/trinity-large-preview:free was retired (404). Using reliable alternatives.
DEFAULT_FAST_MODEL = "meta-llama/llama-3.1-8b-instruct:free"  # Fast, free, reliable
DEFAULT_BEST_MODEL = "google/gemini-2.0-pro-exp-02-05:free"  # Best quality free model


class TextToCADOrchestrator:
    def __init__(self,
                 openrouter_api_key: str,
                 model_name: str,
                 json_examples_path: str,
                 max_iterations: int = 5,
                 min_quality_score: float = 0.8,
                 execution_timeout: int = 300,
                 enable_execution: bool = False):

        # ── Multi-model strategy ──
        # cadgen_model: used for CAD generation (user-configurable via model_name)
        # fast_model:   used for PromptValidator, ExecutionValidator (simulated)
        # best_model:   used for QualityAssessor, RefinementAgent
        self.cadgen_llm = ChatOpenAI(
            openai_api_key=openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            model_name=model_name,
            temperature=0.1,
            timeout=180,
            max_retries=2
        )

        self.fast_llm = ChatOpenAI(
            openai_api_key=openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            model_name=DEFAULT_FAST_MODEL,
            temperature=0.1,
            timeout=120,
            max_retries=2
        )

        self.best_llm = ChatOpenAI(
            openai_api_key=openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            model_name=DEFAULT_BEST_MODEL,
            temperature=0.1,
            timeout=120,
            max_retries=2
        )

        self.rag_system = HybridRAG(json_examples_path)

        # ── Error Memory (cross-session learning) ──
        error_memory_path = os.path.join(os.path.dirname(json_examples_path) or ".", "error_memory.json")
        self.error_memory = ErrorMemory(error_memory_path)

        # ── Generation Archive (persists every iteration for data augmentation) ──
        self.archive = GenerationArchive()

        # ── Agents (assigned to appropriate model tiers) ──
        self.prompt_validator = PromptValidationAgent(self.fast_llm)           # fast
        self.cad_generator = CADGenerationAgent(self.cadgen_llm, self.rag_system)  # cadgen (user's chosen model)
        self.execution_validator = ExecutionValidationAgent(self.fast_llm, timeout=execution_timeout, enable_execution=enable_execution)  # fast
        self.quality_assessor = QualityAssessmentAgent(self.best_llm)          # best
        self.visual_assessor = VisualQualityAssessor(api_key=openrouter_api_key)
        self.refinement_agent = RefinementAgent(self.best_llm)                 # best
        self.physics_checker = PhysicsCheckAgent()                              # pure python — no LLM
        self.fem_validator = FEMValidator(timeout=execution_timeout)             # FreeCAD FEM + CalculiX
        self.techdraw_generator = TechDrawGenerator(timeout=execution_timeout)   # FreeCAD TechDraw Auto SVG

        self.max_iterations = max_iterations
        self.min_quality_score = min_quality_score

        self.iteration_count = 0
        self.context = {}

    def _update_iteration_history(self, iteration: int, results: Dict):
        """Maintain structured history of iterations"""
        if "iteration_history" not in self.context:
            self.context["iteration_history"] = []

        validation_scores = {}
        for category, result in results.get("validation_results", {}).items():
            if hasattr(result, 'score'):
                validation_scores[category] = result.score

        iteration_data = {
            "iteration": iteration,
            "timestamp": time.time(),
            "validation_scores": validation_scores,
            "primary_issues": results.get("primary_issues", []),
            "improvements_made": results.get("improvements_made", []),
            "overall_score": results.get("overall_score", 0.0)
        }

        self.context["iteration_history"].append(iteration_data)

        if len(self.context["iteration_history"]) > 1:
            self.context["improvement_trend"] = self._analyze_improvement_trend()

    def _analyze_improvement_trend(self) -> Dict[str, Any]:
        """Analyze improvement trends across iterations"""
        history = self.context["iteration_history"]
        if len(history) < 2:
            return {"trend": "insufficient_data"}

        recent = history[-2:]
        scores = [h.get("overall_score", 0) for h in recent]

        trend_analysis = {
            "trend": "improving" if scores[-1] > scores[0] else "declining" if scores[-1] < scores[0] else "stable",
            "score_change": scores[-1] - scores[0] if len(scores) >= 2 else 0,
            "consistent_issues": self._find_consistent_issues(history[-3:]),
            "successful_patterns": self._find_successful_patterns(history[-3:])
        }

        return trend_analysis

    def _find_consistent_issues(self, recent_history: List[Dict]) -> List[str]:
        """Find issues that appear consistently across iterations"""
        issue_counts = {}
        for iteration in recent_history:
            for issue in iteration.get("primary_issues", []):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        threshold = len(recent_history) / 2
        return [issue for issue, count in issue_counts.items() if count > threshold]

    def _find_successful_patterns(self, recent_history: List[Dict]) -> List[str]:
        """Find patterns that led to improvements"""
        successful_patterns = []
        for iteration in recent_history:
            if iteration.get("overall_score", 0) > 0.7:
                successful_patterns.extend(iteration.get("improvements_made", []))

        return list(set(successful_patterns))

    def get_relevant_insights(self, current_agent: str) -> Dict:
        """Get insights relevant to current agent"""
        insights = self.context.get("agent_insights", {})
        relevant = {}

        if current_agent == "refinement" and "quality_assessor" in insights:
            relevant["quality_feedback"] = insights["quality_assessor"]["insights"]

        return relevant

    def aggregate_validation_results(self, validations: Dict) -> Dict:
        """Aggregate all validation results into summary"""
        total_score = 0
        total_weight = 0
        failed_categories = []

        weights = {
            "execution": 0.25,
            "quality": 0.30,
            "visual": 0.25,
            "physics": 0.15,
            "fem": 0.05
        }

        for category, result in validations.items():
            weight = weights.get(category, 0.1)
            total_score += result.score * weight
            total_weight += weight

            if not result.is_valid:
                failed_categories.append(category)

        return {
            "overall_score": total_score / max(total_weight, 1),
            "failed_categories": failed_categories,
            "pass_rate": len([r for r in validations.values() if r.is_valid]) / max(len(validations), 1)
        }

    async def generate_cad(self, user_prompt: str, progress_callback=None) -> CADGenerationResult:
        logger.info(f"Starting CAD generation for: {user_prompt[:100]}...")

        # Helper to safely call progress callback
        async def _report(stage, progress, message, iteration=0, max_iter=0):
            if progress_callback:
                try:
                    await progress_callback(stage, progress, message, iteration, max_iter)
                except Exception:
                    pass

        self.context = {
            "original_prompt": user_prompt,
            "enhanced_prompt": user_prompt,
            "requirements": {},
            "previous_errors": [],
            "previous_quality_feedback": "None"
        }
        self.iteration_count = 0

        final_validations = {}
        overall_score = 0.0
        model_name = getattr(self.cadgen_llm, 'model_name', '')

        # ── Track best successful result across all iterations ──
        # Even if we never hit the quality threshold, we return the
        # best iteration that actually executed without errors.
        best_result = None  # {score, iteration, script, fcstd_path, stl_path, validations, step_path}

        try:
            # ── Step 1: Validate, enhance prompt, and plan components ──
            try:
                prompt_result = await self.prompt_validator.execute({"prompt": user_prompt})
                
                # ── Handle guardrail rejection ──
                if prompt_result.get("rejected"):
                    rejection_reason = prompt_result.get("rejection_reason", "Prompt rejected by guardrail")
                    logger.warning(f"Prompt rejected: {rejection_reason}")
                    return CADGenerationResult(
                        script="",
                        success=False,
                        validation_results={},
                        iterations=0,
                        final_score=0.0,
                        error_summary=f"Prompt rejected: {rejection_reason}"
                    )
                
                # ── Handle clarification request ──
                if prompt_result.get("needs_clarification"):
                    clarification = prompt_result.get("clarification_prompt", "Could you provide more details?")
                    logger.info(f"Clarification needed: {clarification}")
                    return CADGenerationResult(
                        script="",
                        success=False,
                        validation_results={},
                        iterations=0,
                        final_score=0.0,
                        error_summary=f"Clarification needed: {clarification}"
                    )
                
                self.context.update(prompt_result)
                # DEFECT 5 FIX: explicitly store components so RAG ingestion always has metadata
                self.context["components"] = prompt_result.get("components", [])
                logger.info(f"Prompt: {self.context.get('category')}/{self.context.get('difficulty')} | Components: {len(self.context.get('components', []))} | Plan: {len(self.context.get('component_plan', []))} steps")
            except Exception as e:
                logger.warning(f"Prompt validation failed: {e}")
                self.context.setdefault("components", [])


            # ── Inject error prevention from cross-session memory ──
            await _report("retrieving_examples", 0.10, "Analyzing reference patterns...")
            category = self.context.get("category", "")
            components = self.context.get("components", [])
            self.context["error_prevention"] = self.error_memory.get_prevention_prompts(
                category=category, components=components, top_n=5
            )

            # ── Phase 2: Inject engineering constraints into context ──
            domain_rules = DOMAIN_RULES.get(category, {})
            if domain_rules:
                constraints_text = "\n".join(f"- {k}: {v}" for k, v in domain_rules.items())
                self.context["engineering_constraints"] = (
                    f"ENGINEERING STANDARDS FOR {category.upper()} DESIGNS:\n{constraints_text}"
                )
            else:
                self.context["engineering_constraints"] = ""

            # ── Start archive session ──
            try:
                self.archive.start_session(
                    user_prompt=user_prompt,
                    model_name=model_name,
                    category=category,
                    difficulty=self.context.get("difficulty", "")
                )
            except Exception as e:
                logger.warning(f"Archive session start failed: {e}")

            for iteration in range(self.max_iterations):
                self.iteration_count = iteration + 1
                self.context["iteration_count"] = self.iteration_count
                logger.info(f"Iteration {self.iteration_count}/{self.max_iterations}")
                _max_iter = self.max_iterations
                _iter_base = 0.15 + (iteration / max(_max_iter, 1)) * 0.75
                await _report("generating_script", _iter_base, f"Generating your design...", self.iteration_count, _max_iter)

                # ── Generate CAD script ──
                try:
                    gen_result = await self.cad_generator.execute(self.context)

                    if not gen_result["success"]:
                        logger.error(f"Generation failed: {gen_result.get('error', 'Unknown error')}")
                        self.context["previous_errors"].append(
                            f"Generation failed: {gen_result.get('error', 'Unknown')}")
                        continue

                    self.context.update(gen_result)
                except Exception as e:
                    logger.error(f"Generation error: {e}")
                    self.context["previous_errors"].append(f"Generation error: {str(e)}")
                    continue

                # ── Test execution (real FreeCAD or LLM simulation) ──
                await _report("executing_engine", _iter_base + 0.15, "Building the 3D model...", self.iteration_count, _max_iter)
                try:
                    exec_result = await self.execution_validator.execute(self.context)
                    exec_validation = exec_result["validation_result"]
                    execution_status = exec_result.get("execution_status", "failed")
                    final_validations["execution"] = exec_validation

                    if execution_status == "skipped":
                        # FreeCAD not available — proceed with reduced confidence
                        logger.warning("Execution skipped: FreeCAD not available")
                        exec_validation = ValidationResult(
                            is_valid=True, score=0.3,
                            errors=["FreeCAD not available — execution skipped"],
                            suggestions=["Install FreeCAD for actual execution testing"],
                            category=ValidationCategory.EXECUTION.value
                        )
                        final_validations["execution"] = exec_validation
                    elif execution_status == "partial":
                        # Model was partially created before timeout/error
                        logger.warning("Execution partial: model file exists but execution incomplete")
                        # Still proceed — we have a partial model to assess
                    elif execution_status == "failed":
                        logger.warning(f"Execution failed: {exec_validation.errors}")
                        self.context["previous_errors"].extend(exec_validation.errors)

                        # Record errors in cross-session memory
                        script = self.context.get("generated_script", "")
                        for err in exec_validation.errors:
                            self.error_memory.record_error(err, script=script, category=category)

                        continue
                    # else: "success" — proceed normally

                    self.context.update(exec_result)

                except Exception as e:
                    # NEVER force-pass on exception — fail honestly
                    logger.error(f"Execution validation infrastructure error: {e}")
                    self.context["previous_errors"].append(f"Execution validator error: {str(e)}")
                    continue

                # ── Physics / Engineering Rule Check ──
                await _report("validating_geometry", _iter_base + 0.30, "Running engineering checks...", self.iteration_count, _max_iter)
                try:
                    physics_result = self.physics_checker.execute(self.context)
                    physics_score = physics_result.get("physics_score", 1.0)
                    physics_violations = physics_result.get("violations", [])
                    physics_fixes = physics_result.get("fix_suggestions", [])

                    physics_validation = ValidationResult(
                        is_valid=physics_result.get("physics_valid", True),
                        score=physics_score,
                        errors=[v["message"] for v in physics_violations if v["severity"] == "critical"],
                        suggestions=[v["fix"] for v in physics_violations],
                        category=ValidationCategory.PHYSICS.value
                    )
                    final_validations["physics"] = physics_validation
                    self.context["physics_result"] = physics_result

                    if physics_fixes:
                        self.context["previous_errors"].extend(physics_fixes)
                        logger.warning(f"Physics Score: {physics_score:.2f} — {len(physics_violations)} violations")
                    else:
                        logger.info(f"Physics Score: {physics_score:.2f} — all checks passed")

                    if physics_result.get("fem_recommended", False):
                        logger.info("Physics: FEM analysis recommended for this design (Phase 3)")

                except Exception as e:
                    logger.warning(f"Physics check failed: {e}")
                    final_validations["physics"] = ValidationResult(
                        is_valid=True, score=1.0, errors=[], suggestions=[],
                        category=ValidationCategory.PHYSICS.value
                    )

                # ── Visual Quality Assessment ──
                await _report("validating_geometry", _iter_base + 0.40, "Assessing visual quality...", self.iteration_count, _max_iter)
                visual_result = {"visual_score": 0.5, "visual_assessment": {}}
                try:
                    fcstd_path = exec_result.get("fcstd_path")
                    if fcstd_path and os.path.exists(fcstd_path):
                        output_dir = os.path.dirname(fcstd_path)
                        visual_result = await self.visual_assessor.execute({
                            "fcstd_path": fcstd_path,
                            "output_dir": output_dir,
                            "original_prompt": user_prompt,
                            "requirements": self.context.get("requirements", {})
                        })
                        self.context["visual_assessment"] = visual_result.get("visual_assessment", {})
                        self.context["rendered_images"] = visual_result.get("rendered_images", [])
                        self.context["fcstd_path"] = fcstd_path
                        stl_path = os.path.join(output_dir, "renders", "model.stl")
                        if os.path.exists(stl_path):
                            self.context["stl_path"] = stl_path
                            logger.info(f"STL file found at: {stl_path}")
                        else:
                            logger.warning(f"STL file not found at: {stl_path}")
                        logger.info(f"Visual Score: {visual_result.get('visual_score', 'N/A')}")
                    else:
                        logger.info("No FCStd file available for visual assessment")
                        self.context["visual_assessment"] = {}
                except Exception as e:
                    logger.warning(f"Visual assessment failed: {e}")
                    self.context["visual_assessment"] = {}

                # ── FEM Structural Validation (Phase 3) ──
                # Only runs when physics checker recommends it AND we have a .FCStd file
                fem_result = {"fem_score": 1.0, "fem_valid": True, "fem_issues": [], "fem_suggestions": [], "fem_error": None}
                try:
                    physics_result = self.context.get("physics_result", {})
                    fcstd_for_fem = self.context.get("fcstd_path")
                    
                    if physics_result.get("fem_recommended", False) and fcstd_for_fem and os.path.exists(fcstd_for_fem):
                        logger.info("FEM: Running CalculiX structural analysis (Phase 3)...")
                        fem_result = self.fem_validator.execute({
                            "fcstd_path": fcstd_for_fem,
                            "category": category,
                            "requirements": self.context.get("requirements", {}),
                            "physics_result": physics_result,
                        })
                        self.context["fem_result"] = fem_result

                        # Store FEM validation result
                        fem_validation = ValidationResult(
                            is_valid=fem_result.get("fem_valid", True),
                            score=fem_result.get("fem_score", 1.0),
                            errors=fem_result.get("fem_issues", []),
                            suggestions=fem_result.get("fem_suggestions", []),
                            category=ValidationCategory.PHYSICS.value
                        )
                        final_validations["fem"] = fem_validation

                        # Feed FEM issues into refinement feedback
                        fem_fixes = [
                            f"[FEM] {issue}" for issue in fem_result.get("fem_issues", [])
                        ]
                        if fem_fixes:
                            self.context["previous_errors"].extend(fem_fixes)

                        # Log results
                        if fem_result.get("fem_error"):
                            logger.info(f"FEM: Skipped — {fem_result['fem_error']}")
                        else:
                            logger.info(
                                f"FEM: displacement={fem_result.get('max_displacement_mm', 0):.2f}mm, "
                                f"stress={fem_result.get('max_stress_mpa', 0):.1f}MPa, "
                                f"safety_factor={fem_result.get('safety_factor', 0):.2f}, "
                                f"score={fem_result.get('fem_score', 1.0):.2f}"
                            )
                    else:
                        if not physics_result.get("fem_recommended", False):
                            logger.info("FEM: Not recommended for this design")
                        else:
                            logger.info("FEM: No FCStd file available")
                        self.context["fem_result"] = fem_result

                except Exception as e:
                    logger.warning(f"FEM validation failed (non-blocking): {e}")
                    self.context["fem_result"] = fem_result

                # ── Quality Assessment ──
                await _report("validating_geometry", _iter_base + 0.55, "Quality assessment...", self.iteration_count, _max_iter)
                try:
                    self.context["validation_results"] = final_validations
                    quality_result = await self.quality_assessor.execute(self.context)
                    overall_score = quality_result["overall_score"]
                    quality_validation = quality_result["quality_validation"]

                    final_validations["quality"] = quality_validation

                    logger.info(f"Quality Score: {overall_score:.2f} (Threshold: {self.min_quality_score})")

                    # ── Force Quality Penalty if STL is missing ──
                    if not self.context.get("stl_path"):
                        logger.warning("Empty geometry (no STL). Applying severe quality penalty forcing retry.")
                        overall_score = 0.0
                        if "weaknesses" not in quality_result:
                            quality_result["weaknesses"] = []
                        quality_result["weaknesses"].append("CRITICAL: The script produced no valid 3D shapes. You MUST create a solid geometry (e.g., using Part.makeSolid or Extrude).")

                    iteration_results = {
                        "validation_results": final_validations,
                        "overall_score": overall_score,
                        "primary_issues": quality_result.get("weaknesses", []),
                        "improvements_made": quality_result.get("strengths", [])
                    }
                    self._update_iteration_history(self.iteration_count, iteration_results)

                    # ── Snapshot best result so far ──
                    # Keep the highest-scoring successful iteration so we can
                    # return it even if later iterations regress or error out.
                    if best_result is None or overall_score > best_result["score"]:
                        best_result = {
                            "score": overall_score,
                            "iteration": self.iteration_count,
                            "script": self.context.get("generated_script", ""),
                            "fcstd_path": self.context.get("fcstd_path"),
                            "stl_path": self.context.get("stl_path"),
                            "step_path": self.context.get("step_path"),
                            "validations": dict(final_validations),
                        }
                        logger.info(f"Best result updated: iteration {self.iteration_count}, score {overall_score:.2f}")

                    # ── Archive this iteration ──
                    try:
                        exec_v = final_validations.get("execution")
                        self.archive.save_iteration(
                            iteration=self.iteration_count,
                            original_prompt=user_prompt,
                            enhanced_prompt=self.context.get("enhanced_prompt", ""),
                            script=self.context.get("generated_script", ""),
                            execution_score=exec_v.score if exec_v else 0.0,
                            execution_errors=exec_v.errors if exec_v else [],
                            visual_score=visual_result.get("visual_score", 0.0),
                            visual_assessment=self.context.get("visual_assessment", {}),
                            quality_score=overall_score,
                            quality_assessment=quality_result.get("detailed_assessment", {}),
                            overall_score=overall_score,
                            rendered_images=self.context.get("rendered_images", []),
                            category=category,
                            difficulty=self.context.get("difficulty", ""),
                            component_plan=self.context.get("component_plan", []),
                            error_prevention=self.context.get("error_prevention", "")
                        )
                    except Exception as e:
                        logger.warning(f"Archive save failed: {e}")

                    if overall_score >= self.min_quality_score:
                        logger.info(f"Success! Score: {overall_score:.0%}")

                        # --- TechDraw 2D Generation ---
                        svg_path = None
                        if self.context.get("fcstd_path"):
                            logger.info("Executing TechDraw 2D Draft generation...")
                            td_result = self.techdraw_generator.execute(
                                self.context["fcstd_path"], 
                                os.path.dirname(self.context["fcstd_path"])
                            )
                            if td_result.get("success"):
                                svg_path = td_result.get("svg_path")
                                self.context["svg_path"] = svg_path
                                logger.info(f"TechDraw 2D SVG generated at: {svg_path}")
                            else:
                                logger.warning(f"TechDraw generation failed: {td_result.get('error')}")

                        # Record success in error memory
                        self.error_memory.record_success(
                            script=self.context["generated_script"],
                            prompt=user_prompt,
                            category=category
                        )
                        
                        # Continuous Learning: Save gold generations for manual review
                        if overall_score >= 0.90:
                            logger.info("Gold standard achieved (>0.90). Saving to pending_review for manual review.")
                            try:
                                pending_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_review")
                                os.makedirs(pending_dir, exist_ok=True)
                                
                                # Build filename from timestamp and short prompt
                                short_prompt = user_prompt[:50].replace(' ', '_').replace('/', '_').replace('\\', '_')
                                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                                filename = f"{timestamp}_{short_prompt}.json"
                                filepath = os.path.join(pending_dir, filename)
                                
                                pending_entry = {
                                    "prompt": user_prompt,
                                    "script": self.context["generated_script"],
                                    "category": category,
                                    "components": self.context.get("components", []),
                                    "difficulty": self.context.get("difficulty", "intermediate"),
                                    "score": overall_score,
                                    "timestamp": datetime.now().isoformat(),
                                    "model_name": model_name,
                                    "_note": "Add tags, chain_of_thoughts, freecad_apis, engineering_concepts, validation_criteria before ingesting"
                                }
                                
                                with open(filepath, 'w', encoding='utf-8') as f:
                                    json.dump(pending_entry, f, indent=2, ensure_ascii=False)
                                
                                logger.info(f"Gold generation saved to: {filepath}")
                            except Exception as e:
                                logger.warning(f"Failed to save gold generation for review: {e}")

                        # Archive final success
                        try:
                            self.archive.save_final_result(
                                success=True,
                                final_score=overall_score,
                                total_iterations=self.iteration_count,
                                best_script=self.context["generated_script"],
                                fcstd_path=self.context.get("fcstd_path"),
                                stl_path=self.context.get("stl_path")
                            )
                        except Exception as e:
                            logger.warning(f"Archive final save failed: {e}")

                        return CADGenerationResult(
                            script=self.context["generated_script"],
                            success=True,
                            validation_results=final_validations,
                            iterations=self.iteration_count,
                            final_score=overall_score,
                            fcstd_path=self.context.get("fcstd_path"),
                            stl_path=self.context.get("stl_path"),
                            svg_path=self.context.get("svg_path")
                        )

                    else:
                        weaknesses = quality_result.get("weaknesses", [])
                        refinement_suggestions = quality_result.get("refinement_suggestions", [])
                        missing_requirements = quality_result.get("missing_requirements", [])

                        quality_feedback = {
                            "score": overall_score,
                            "weaknesses": weaknesses,
                            "suggestions": refinement_suggestions,
                            "missing": missing_requirements,
                            "category_scores": quality_result.get("category_scores", {}),
                            "component_checklist": quality_result.get("component_checklist", {})
                        }

                        self.context["previous_quality_feedback"] = json.dumps(quality_feedback, indent=2)

                        quality_issues = weaknesses + missing_requirements
                        self.context["previous_errors"].extend([f"Quality issue: {issue}" for issue in quality_issues])

                        if iteration < self.max_iterations - 1:
                            logger.info("Running refinement...")
                            await _report("refining", _iter_base + 0.70, f"Refining the design (pass {self.iteration_count} of {_max_iter})...", self.iteration_count, _max_iter)

                            try:
                                self.context["validation_results"] = final_validations
                                self.context["max_iterations"] = self.max_iterations
                                refinement_result = await self.refinement_agent.execute(self.context)

                                if refinement_result["should_continue"]:
                                    self.context["enhanced_prompt"] = refinement_result["enhanced_prompt_suggestion"]
                                    continue
                                else:
                                    break
                            except Exception as e:
                                logger.warning(f"Refinement failed: {e}")
                                continue
                        else:
                            break

                except Exception as e:
                    logger.error(f"Quality assessment failed: {e}")
                    overall_score = 0.6
                    quality_validation = ValidationResult(
                        is_valid=False, score=overall_score, errors=[f"Assessment failed: {str(e)}"],
                        suggestions=["Manual review needed"], category=ValidationCategory.VISUAL.value
                    )
                    final_validations["quality"] = quality_validation

            # ── All iterations exhausted ──
            # If ANY iteration produced a successful execution, return it
            # as a success with its best score — never discard working output.
            if best_result is not None:
                logger.info(
                    f"Returning best result from iteration {best_result['iteration']} "
                    f"(score {best_result['score']:.2f}) — threshold not reached but model was valid"
                )

                # Archive as partial success
                try:
                    self.archive.save_final_result(
                        success=True,
                        final_score=best_result["score"],
                        total_iterations=self.iteration_count,
                        best_script=best_result["script"],
                        fcstd_path=best_result.get("fcstd_path"),
                        stl_path=best_result.get("stl_path")
                    )
                except Exception as e:
                    logger.warning(f"Archive final save failed: {e}")

                return CADGenerationResult(
                    script=best_result["script"],
                    success=True,
                    validation_results=best_result.get("validations", final_validations),
                    iterations=self.iteration_count,
                    final_score=best_result["score"],
                    fcstd_path=best_result.get("fcstd_path"),
                    stl_path=best_result.get("stl_path"),
                    svg_path=self.context.get("svg_path")
                )

            # Truly failed — no iteration ever executed successfully
            logger.warning(f"Failed after {self.max_iterations} iterations — no successful execution")

            aggregated_results = self.aggregate_validation_results(final_validations)

            try:
                self.archive.save_final_result(
                    success=False,
                    final_score=aggregated_results.get("overall_score", overall_score),
                    total_iterations=self.iteration_count,
                    best_script=self.context.get("generated_script", ""),
                    fcstd_path=self.context.get("fcstd_path"),
                    stl_path=self.context.get("stl_path"),
                    error_summary=f"All iterations failed execution. No valid model produced."
                )
            except Exception as e:
                logger.warning(f"Archive final save failed: {e}")

            return CADGenerationResult(
                script=self.context.get("generated_script", ""),
                success=False,
                validation_results=final_validations,
                iterations=self.iteration_count,
                final_score=aggregated_results.get("overall_score", overall_score),
                error_summary=f"All {self.max_iterations} iterations failed execution. No valid model was produced.",
                fcstd_path=self.context.get("fcstd_path"),
                stl_path=self.context.get("stl_path")
            )

        except Exception as e:
            logger.error(f"Critical error in orchestrator: {e}")
            return CADGenerationResult(
                script="",
                success=False,
                validation_results=final_validations,
                iterations=self.iteration_count,
                final_score=0.0,
                error_summary=f"Critical orchestrator error: {str(e)}",
                fcstd_path=self.context.get("fcstd_path") if hasattr(self, 'context') else None,
                stl_path=self.context.get("stl_path") if hasattr(self, 'context') else None
            )
