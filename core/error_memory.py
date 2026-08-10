# Error Memory System - Cross-session learning from FreeCAD errors
import os
import re
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorMemory:
    """Persistent error→solution memory that learns across sessions.
    
    Stores error patterns, their solutions, and prevention prompts.
    Injects top-N most relevant prevention prompts into the CAD generator context.
    """

    def __init__(self, memory_path: str = "error_memory.json"):
        self.memory_path = memory_path
        self.patterns: List[Dict] = []
        self.success_patterns: List[Dict] = []
        self._load()

    # ---- Persistence ----

    def _load(self):
        """Load error memory from disk."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.patterns = data.get("patterns", [])
                self.success_patterns = data.get("success_patterns", [])
                logger.info(f"Loaded error memory: {len(self.patterns)} error patterns, {len(self.success_patterns)} success patterns")
            except Exception as e:
                logger.warning(f"Failed to load error memory: {e}")
                self.patterns = []
                self.success_patterns = []
        else:
            logger.info("No error memory found — starting fresh")
            self._seed_default_patterns()

    def _save(self):
        """Persist error memory to disk."""
        try:
            data = {
                "patterns": self.patterns,
                "success_patterns": self.success_patterns,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved error memory: {len(self.patterns)} patterns")
        except Exception as e:
            logger.error(f"Failed to save error memory: {e}")

    def _seed_default_patterns(self):
        """Seed with known common FreeCAD errors."""
        self.patterns = [
            {
                "id": "err_001",
                "pattern_regex": r"ViewObject|ShapeColor|\.ViewObject\.",
                "error_type": "headless_gui_reference",
                "frequency": 10,
                "last_seen": datetime.now().isoformat(),
                "root_cause": "LLM uses GUI-mode API in headless FreeCADCmd context",
                "solution": "Remove all ViewObject, ShapeColor, and visual property references",
                "prevention_prompt": "CRITICAL: This runs in headless mode (FreeCADCmd.exe). NEVER use obj.ViewObject, obj.ViewObject.ShapeColor, or any visual/display properties. They are None in headless mode and WILL crash.",
                "verified": True
            },
            {
                "id": "err_002",
                "pattern_regex": r"FreeCADGui|import Gui|Gui\.",
                "error_type": "gui_import",
                "frequency": 8,
                "last_seen": datetime.now().isoformat(),
                "root_cause": "LLM imports GUI module which doesn't exist in headless mode",
                "solution": "Remove all FreeCADGui/Gui imports and references",
                "prevention_prompt": "NEVER import or use FreeCADGui or Gui module. They do not exist in headless mode.",
                "verified": True
            },
            {
                "id": "err_003",
                "pattern_regex": r"Part\.show|Part\.Show",
                "error_type": "gui_show_call",
                "frequency": 5,
                "last_seen": datetime.now().isoformat(),
                "root_cause": "Part.show() is a GUI function that fails in headless mode",
                "solution": "Use doc.addObject('Part::Feature', name) instead of Part.show()",
                "prevention_prompt": "Do NOT use Part.show(). Instead, add shapes to the document: obj = doc.addObject('Part::Feature', 'Name'); obj.Shape = your_shape",
                "verified": True
            },
            {
                "id": "err_004",
                "pattern_regex": r"ActiveDocument.*None|NoneType.*has no attribute",
                "error_type": "null_document",
                "frequency": 3,
                "last_seen": datetime.now().isoformat(),
                "root_cause": "Script accesses App.ActiveDocument before creating one",
                "solution": "Always create document first: doc = App.newDocument('Name')",
                "prevention_prompt": "Always create the document at the top: doc = App.newDocument('ModelName'). Never rely on App.ActiveDocument being set automatically.",
                "verified": True
            },
            {
                "id": "err_005",
                "pattern_regex": r"fuse.*fuse.*fuse|\.fuse\(.*\.fuse\(",
                "error_type": "excessive_boolean_chain",
                "frequency": 4,
                "last_seen": datetime.now().isoformat(),
                "root_cause": "Chaining too many boolean fuse/cut operations causes slowdown or crashes",
                "solution": "Use Part.Compound for non-intersecting shapes, batch fuse operations",
                "prevention_prompt": "AVOID chaining .fuse() calls (e.g. a.fuse(b).fuse(c).fuse(d)...). For non-intersecting shapes use Part.Compound([shapes]). For intersecting shapes, fuse in batches of 5-10.",
                "verified": True
            }
        ]
        self._save()

    # ---- Recording errors ----

    def record_error(self, error_message: str, script: str = "", category: str = ""):
        """Record an error from a failed generation attempt."""
        # Check if this matches an existing pattern
        for pattern in self.patterns:
            try:
                if re.search(pattern["pattern_regex"], error_message, re.IGNORECASE):
                    pattern["frequency"] = pattern.get("frequency", 0) + 1
                    pattern["last_seen"] = datetime.now().isoformat()
                    logger.info(f"Known error pattern matched: {pattern['error_type']} (freq: {pattern['frequency']})")
                    self._save()
                    return
            except re.error:
                continue

        # Check against the script itself for patterns
        for pattern in self.patterns:
            try:
                if re.search(pattern["pattern_regex"], script, re.IGNORECASE):
                    pattern["frequency"] = pattern.get("frequency", 0) + 1
                    pattern["last_seen"] = datetime.now().isoformat()
                    logger.info(f"Known error pattern found in script: {pattern['error_type']} (freq: {pattern['frequency']})")
                    self._save()
                    return
            except re.error:
                continue

        # New unknown error — store it
        new_id = f"err_{len(self.patterns) + 1:03d}"
        new_pattern = {
            "id": new_id,
            "pattern_regex": re.escape(error_message[:100]),
            "error_type": "runtime_error",
            "frequency": 1,
            "last_seen": datetime.now().isoformat(),
            "root_cause": error_message[:200],
            "solution": f"Fix: {error_message[:150]}",
            "prevention_prompt": f"AVOID this error: {error_message[:150]}",
            "verified": False,
            "category": category
        }
        self.patterns.append(new_pattern)
        logger.info(f"New error pattern recorded: {new_id}")
        self._save()

    def record_success(self, script: str, prompt: str, category: str = ""):
        """Record a successful generation pattern."""
        # Extract key API patterns from successful script
        api_calls = set()
        for api in ["Part.makeBox", "Part.makeCylinder", "Part.makeCone", "Part.makeSphere",
                     "Part.Compound", "Part.Wire", "Part.Face", "Part.BSplineCurve",
                     "doc.addObject", ".fuse(", ".cut(", ".translate(",
                     "Draft.make", "Part.makePolygon", "Part.makeTorus"]:
            if api in script:
                api_calls.add(api)

        if api_calls:
            self.success_patterns.append({
                "prompt_snippet": prompt[:100],
                "api_patterns": list(api_calls),
                "category": category,
                "line_count": len(script.split("\n")),
                "timestamp": datetime.now().isoformat()
            })
            # Keep only last 100 success patterns
            if len(self.success_patterns) > 100:
                self.success_patterns = self.success_patterns[-100:]
            self._save()

    # ---- Retrieval for injection ----

    def get_prevention_prompts(self, category: str = "", components: List[str] = None, top_n: int = 5) -> str:
        """Get top-N most relevant prevention prompts for injection into the generator."""
        if not self.patterns:
            return ""

        # Sort by frequency (most common errors first)
        sorted_patterns = sorted(self.patterns, key=lambda p: p.get("frequency", 0), reverse=True)

        # DEFECT 9 FIX: only inject unverified patterns once they've been seen 3+ times.
        # Raw exception text from a single failure is meaningless to an LLM.
        verified   = [p for p in sorted_patterns if p.get("verified", False)]
        unverified = [p for p in sorted_patterns
                      if not p.get("verified", False) and p.get("frequency", 0) >= 3]

        selected = (verified + unverified)[:top_n]

        if not selected:
            return ""

        lines = ["ERROR PREVENTION (from previous sessions — DO NOT repeat these mistakes):"]
        for i, pattern in enumerate(selected, 1):
            lines.append(f"{i}. [{pattern.get('error_type', 'unknown')}] {pattern['prevention_prompt']}")

        return "\n".join(lines)

    def get_success_context(self, category: str = "", top_n: int = 3) -> str:
        """Get successful patterns for positive reinforcement."""
        if not self.success_patterns:
            return ""

        # Filter by category if provided
        relevant = self.success_patterns
        if category:
            cat_matches = [p for p in self.success_patterns if p.get("category", "").lower() == category.lower()]
            if cat_matches:
                relevant = cat_matches

        recent = relevant[-top_n:]
        if not recent:
            return ""

        lines = ["PROVEN SUCCESSFUL PATTERNS:"]
        for p in recent:
            apis = ", ".join(p.get("api_patterns", [])[:5])
            lines.append(f"- {p.get('prompt_snippet', '?')} → Used: {apis} ({p.get('line_count', '?')} lines)")

        return "\n".join(lines)
