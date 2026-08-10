# ============================================================================
# app.py — Backward-compatible re-export layer
# ============================================================================
# This file used to be the monolithic 2800-line codebase.
# Phase C split it into focused modules under core/.
#
# All public symbols are re-exported here so that existing code like
#   ``from app import TextToCADOrchestrator, ValidationResult, ...``
# continues to work without any import changes.
# ============================================================================

import os, sys

# Ensure both the core/ directory and its parent are on sys.path
# so that imports work whether run from core/ or the project root.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
for _p in (_this_dir, _parent_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------- Data Models, Enums & Constants ----------
from models import (
    ValidationResult,
    CADGenerationResult,
    ValidationCategory,
    AgentState,
    DOMAIN_RULES,
    DETAIL_REQUIREMENTS,
    most_common_Freecad_errors,
    FREECAD_PERFORMANCE_TIPS,
    FREECAD_CHEAT_SHEET,
    word_count,
)

# ---------- Utilities ----------
from utils import ultra_robust_json_parse

# ---------- RAG ----------
from rag import HybridRAG

# ---------- Execution Tool ----------
from execution import FreeCADExecutionTool

# ---------- Error Memory ----------
from error_memory import ErrorMemory

# ---------- Orchestrator ----------
from orchestrator import TextToCADOrchestrator

# ---------- Public API ----------
__all__ = [
    # Models & Enums
    "ValidationResult",
    "CADGenerationResult",
    "ValidationCategory",
    "AgentState",
    # Constants
    "DOMAIN_RULES",
    "DETAIL_REQUIREMENTS",
    "most_common_Freecad_errors",
    "FREECAD_PERFORMANCE_TIPS",
    "FREECAD_CHEAT_SHEET",
    # Utilities
    "ultra_robust_json_parse",
    "word_count",
    # Core Systems
    "HybridRAG",
    "FreeCADExecutionTool",
    "ErrorMemory",
    # Orchestrator
    "TextToCADOrchestrator",
]