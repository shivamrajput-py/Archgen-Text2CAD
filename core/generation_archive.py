# ============================================================================
# generation_archive.py — Persists every iteration's data for future use
# ============================================================================
# Saves prompts, scripts, scores, and rendered images into structured folders.
# Each generation call gets a unique folder. Each iteration gets a subfolder.
#
# Structure:
#   core/generation_archive/
#     └── 20260220_023500_a1b2c3/              ← one generation call
#         ├── metadata.json                     ← top-level info
#         ├── iteration_1/
#         │   ├── iteration_data.json           ← prompts, scores, context
#         │   ├── script.py                     ← generated FreeCAD script
#         │   ├── render_isometric.png          ← copied rendered images
#         │   ├── render_front.png
#         │   └── ...
#         ├── iteration_2/
#         │   └── ...
#         └── final_result.json                 ← final outcome
# ============================================================================

import os
import json
import shutil
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class GenerationArchive:
    """Archives every generation call and each iteration's data."""

    def __init__(self, archive_root: str = None):
        if archive_root is None:
            archive_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generation_archive")
        self.archive_root = archive_root
        os.makedirs(self.archive_root, exist_ok=True)
        self._current_session_dir: Optional[str] = None
        self._session_id: Optional[str] = None

    def start_session(self, user_prompt: str, model_name: str = "", category: str = "", difficulty: str = "") -> str:
        """Start a new generation session. Returns the session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:8]
        self._session_id = f"{timestamp}_{short_id}"
        self._current_session_dir = os.path.join(self.archive_root, self._session_id)
        os.makedirs(self._current_session_dir, exist_ok=True)

        metadata = {
            "session_id": self._session_id,
            "timestamp": datetime.now().isoformat(),
            "user_prompt": user_prompt,
            "model_name": model_name,
            "category": category,
            "difficulty": difficulty,
            "iterations": []
        }
        self._write_json(os.path.join(self._current_session_dir, "metadata.json"), metadata)

        logger.info(f"Archive session started: {self._session_id}")
        return self._session_id

    def save_iteration(
        self,
        iteration: int,
        original_prompt: str,
        enhanced_prompt: str,
        script: str,
        execution_score: float = 0.0,
        execution_errors: List[str] = None,
        visual_score: float = 0.0,
        visual_assessment: Dict = None,
        quality_score: float = 0.0,
        quality_assessment: Dict = None,
        overall_score: float = 0.0,
        rendered_images: List[str] = None,
        category: str = "",
        difficulty: str = "",
        component_plan: List = None,
        error_prevention: str = "",
        **extra_context
    ):
        """Save one iteration's complete data."""
        if not self._current_session_dir:
            logger.warning("No archive session active — skipping save")
            return

        iter_dir = os.path.join(self._current_session_dir, f"iteration_{iteration}")
        os.makedirs(iter_dir, exist_ok=True)

        # Save the script as .py
        script_path = os.path.join(iter_dir, "script.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
        except Exception as e:
            logger.error(f"Failed to save script: {e}")

        # Copy rendered images into this iteration's folder
        copied_images = []
        if rendered_images:
            for img_path in rendered_images:
                if os.path.exists(img_path):
                    dest = os.path.join(iter_dir, os.path.basename(img_path))
                    try:
                        shutil.copy2(img_path, dest)
                        copied_images.append(os.path.basename(img_path))
                    except Exception as e:
                        logger.warning(f"Failed to copy image {img_path}: {e}")

        # Build iteration data
        iteration_data = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "original_prompt": original_prompt,
            "enhanced_prompt": enhanced_prompt,
            "category": category,
            "difficulty": difficulty,
            "script_lines": len(script.split("\n")),
            "scores": {
                "execution": execution_score,
                "visual": visual_score,
                "quality": quality_score,
                "overall": overall_score
            },
            "execution_errors": execution_errors or [],
            "visual_assessment": _sanitize_for_json(visual_assessment or {}),
            "quality_assessment": _sanitize_for_json(quality_assessment or {}),
            "component_plan": component_plan or [],
            "error_prevention_used": error_prevention[:500] if error_prevention else "",
            "rendered_images": copied_images
        }

        # Add any extra context
        for k, v in extra_context.items():
            try:
                json.dumps(v)
                iteration_data[k] = v
            except (TypeError, ValueError):
                iteration_data[k] = str(v)

        self._write_json(os.path.join(iter_dir, "iteration_data.json"), iteration_data)

        # Update metadata with iteration reference
        self._append_to_metadata(iteration, overall_score)

        logger.info(f"Archive: iteration {iteration} saved ({len(copied_images)} images, score={overall_score:.2f})")

    def save_final_result(
        self,
        success: bool,
        final_score: float,
        total_iterations: int,
        best_script: str = "",
        fcstd_path: str = None,
        stl_path: str = None,
        error_summary: str = ""
    ):
        """Save the final generation outcome."""
        if not self._current_session_dir:
            return

        final = {
            "success": success,
            "final_score": final_score,
            "total_iterations": total_iterations,
            "error_summary": error_summary,
            "timestamp": datetime.now().isoformat()
        }

        # Copy final FCStd/STL if they exist
        if fcstd_path and os.path.exists(fcstd_path):
            dest = os.path.join(self._current_session_dir, "final_model.FCStd")
            try:
                shutil.copy2(fcstd_path, dest)
                final["fcstd_archived"] = True
            except Exception as e:
                logger.warning(f"Failed to copy FCStd: {e}")

        if stl_path and os.path.exists(stl_path):
            dest = os.path.join(self._current_session_dir, "final_model.stl")
            try:
                shutil.copy2(stl_path, dest)
                final["stl_archived"] = True
            except Exception as e:
                logger.warning(f"Failed to copy STL: {e}")

        # Save best script
        if best_script:
            try:
                with open(os.path.join(self._current_session_dir, "best_script.py"), "w", encoding="utf-8") as f:
                    f.write(best_script)
            except Exception:
                pass

        self._write_json(os.path.join(self._current_session_dir, "final_result.json"), final)
        logger.info(f"Archive: final result saved (success={success}, score={final_score:.2f})")

    def _append_to_metadata(self, iteration: int, score: float):
        """Append iteration summary to session metadata."""
        meta_path = os.path.join(self._current_session_dir, "metadata.json")
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["iterations"].append({"iteration": iteration, "score": score})
            self._write_json(meta_path, meta)
        except Exception as e:
            logger.warning(f"Failed to update metadata: {e}")

    def _write_json(self, path: str, data: dict):
        """Write JSON file safely."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")


def _sanitize_for_json(obj: Any) -> Any:
    """Make sure obj is JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)
