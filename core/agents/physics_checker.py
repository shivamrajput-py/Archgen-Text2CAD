# Physics Check Agent — Deterministic Engineering Rule Validation
# No LLM dependency. Parses FreeCAD script dimensions and validates
# them against domain-specific engineering rules of thumb.
#
# Runs in <100ms. Zero external dependencies.
import ast
import re
import math
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ENGINEERING RULES DATABASE
# ══════════════════════════════════════════════════════════════════════════════
# Each rule is a dict:
#   id          — unique key (for deduplication across iterations)
#   domain      — which categories it applies to (list)
#   severity    — "critical" | "warning" | "info"
#   check(dims) — returns (passed: bool, message: str, fix: str) or None to skip

ENGINEERING_RULES: List[Dict] = []


def _rule(rule_id: str, domains: List[str], severity: str = "warning"):
    """Decorator to register a rule function."""
    def decorator(fn):
        ENGINEERING_RULES.append({
            "id": rule_id,
            "domains": domains,
            "severity": severity,
            "check": fn,
        })
        return fn
    return decorator


# ── Structural / Architectural Rules ─────────────────────────────────────────

@_rule("WALL_MIN_THICKNESS", ["architectural", "structural"], "critical")
def _wall_min_thickness(dims, ctx):
    """Load-bearing walls must be ≥ 100mm thick."""
    walls = [d for d in dims if d["type"] == "box" and _is_wall(d)]
    violations = []
    for w in walls:
        thickness = min(w["length"], w["width"])  # thinnest dimension = thickness
        if thickness < 80:  # mm
            violations.append((
                f"Wall '{w.get('name', '?')}' is {thickness:.0f}mm thick — too thin for load-bearing",
                f"Increase wall thickness to at least 150mm (200mm recommended)"
            ))
    return violations


@_rule("FLOOR_HEIGHT_RANGE", ["architectural", "structural"], "warning")
def _floor_height_range(dims, ctx):
    """Floor-to-floor height should be 2500-5000mm."""
    violations = []
    boxes = [d for d in dims if d["type"] == "box"]
    for b in boxes:
        h = b["height"]
        # Only check items that look like floor-height elements (tall, wide)
        if h > 1500 and b["length"] > 2000 and b["width"] > 2000:
            continue  # This is a slab/floor, not a room-height element
        if _is_floor_height(b, h):
            if h < 2500:
                violations.append((
                    f"Floor height {h:.0f}mm is below minimum (2500mm)",
                    f"Set floor-to-floor height to 3000mm (standard residential/commercial)"
                ))
            elif h > 6000:
                violations.append((
                    f"Floor height {h:.0f}mm is unusually tall (max 5000mm typical)",
                    f"Reduce floor height to 3000-4500mm unless it's an atrium"
                ))
    return violations


@_rule("SLAB_THICKNESS", ["architectural", "structural"], "warning")
def _slab_thickness(dims, ctx):
    """Floor slabs should be 100-400mm thick."""
    violations = []
    slabs = [d for d in dims if d["type"] == "box" and _is_slab(d)]
    for s in slabs:
        thickness = s["height"]  # slabs are usually flat boxes
        if thickness < 100:
            violations.append((
                f"Slab thickness {thickness:.0f}mm is too thin (min 100mm)",
                f"Increase slab thickness to 150-200mm for residential, 200-300mm for commercial"
            ))
        elif thickness > 500:
            violations.append((
                f"Slab thickness {thickness:.0f}mm is unusually thick (max ~400mm)",
                f"Reduce slab thickness to 200-300mm unless it's a transfer slab"
            ))
    return violations


@_rule("COLUMN_MIN_SIZE", ["architectural", "structural"], "warning")
def _column_min_size(dims, ctx):
    """Columns should be ≥ 200mm in cross-section."""
    violations = []
    columns = [d for d in dims if _is_column(d)]
    for c in columns:
        if c["type"] == "cylinder":
            size = c["radius"] * 2
            if size < 200:
                violations.append((
                    f"Column diameter {size:.0f}mm is too small (min 200mm)",
                    f"Increase column diameter to at least 300mm"
                ))
        elif c["type"] == "box":
            size = min(c["length"], c["width"])
            if size < 200:
                violations.append((
                    f"Column cross-section {size:.0f}mm is too small (min 200mm)",
                    f"Increase column size to at least 300x300mm"
                ))
    return violations


@_rule("BEAM_DEPTH_RATIO", ["architectural", "structural"], "warning")
def _beam_depth_ratio(dims, ctx):
    """Beam depth should be ≥ span/20 (concrete) or span/25 (steel)."""
    violations = []
    beams = [d for d in dims if d["type"] == "box" and _is_beam(d)]
    for b in beams:
        span = max(b["length"], b["width"])
        depth = b["height"]
        if span > 1000 and depth > 0:  # only for meaningful spans
            ratio = span / depth
            if ratio > 25:
                violations.append((
                    f"Beam span/depth ratio is {ratio:.0f}:1 (span={span:.0f}mm, depth={depth:.0f}mm) — too shallow",
                    f"Increase beam depth to at least {span/20:.0f}mm (concrete) or {span/25:.0f}mm (steel)"
                ))
    return violations


@_rule("FOUNDATION_EXISTS", ["architectural", "structural"], "critical")
def _foundation_exists(dims, ctx):
    """Multi-story structures should have a foundation element."""
    script = ctx.get("script", "")
    category = ctx.get("category", "")
    if category not in ("architectural", "structural"):
        return []
    
    # Check if the script mentions foundation-related terms
    has_foundation = any(kw in script.lower() for kw in 
                        ["foundation", "footing", "ground_slab", "base_slab", "plinth"])
    
    # Check if there are elements at or below z=0
    has_ground_element = any(
        d.get("z", 0) <= 0 and d.get("type") == "box" 
        and min(d.get("length", 0), d.get("width", 0)) > 1000
        for d in dims
    )
    
    if not has_foundation and not has_ground_element:
        # Only flag if this looks like a building (has multiple tall elements)
        tall_elements = [d for d in dims if d.get("height", 0) > 2000]
        if len(tall_elements) >= 2:
            return [(
                "No foundation detected for a multi-element structure",
                "Add a foundation/ground slab at z=0 using Part.makeBox(length, width, 500, App.Vector(x, y, -500))"
            )]
    return []


@_rule("WINDOW_PROPORTIONS", ["architectural"], "info")
def _window_proportions(dims, ctx):
    """Window openings should have reasonable aspect ratios (1:1 to 1:3)."""
    violations = []
    script = ctx.get("script", "")
    # Look for cut operations that might be windows
    windows = [d for d in dims if d.get("is_cut", False) and d["type"] == "box"]
    for w in windows:
        width = min(w["length"], w["width"])
        height = w["height"]
        if width > 200 and height > 200:  # actual window-sized, not a slot
            ratio = height / width if width > 0 else 0
            if ratio > 4:
                violations.append((
                    f"Window aspect ratio {ratio:.1f}:1 is too narrow (max 3:1)",
                    f"Adjust window width to at least {height/3:.0f}mm"
                ))
    return violations


# ── Civil / Bridge Rules ─────────────────────────────────────────────────────

@_rule("BRIDGE_DECK_DEPTH", ["civil", "structural"], "critical")
def _bridge_deck_depth(dims, ctx):
    """Bridge deck depth should be ≥ span/30 (steel) or span/25 (concrete)."""
    violations = []
    script = ctx.get("script", "")
    if "bridge" not in script.lower() and "deck" not in script.lower():
        return []
    
    decks = [d for d in dims if d["type"] == "box" and _is_deck(d)]
    for deck in decks:
        span = max(deck["length"], deck["width"])
        depth = deck["height"]
        if span > 5000 and depth > 0:
            ratio = span / depth
            if ratio > 30:
                violations.append((
                    f"Bridge deck span/depth ratio is {ratio:.0f}:1 — too shallow for safety",
                    f"Increase deck depth to at least {span/25:.0f}mm (concrete) or {span/30:.0f}mm (steel)"
                ))
    return violations


@_rule("BRIDGE_CLEARANCE", ["civil"], "warning")
def _bridge_clearance(dims, ctx):
    """Bridge vertical clearance should be ≥ 5500mm (AASHTO standard)."""
    script = ctx.get("script", "")
    if "bridge" not in script.lower():
        return []
    
    violations = []
    # Check for clearance-related variables
    clearance_match = re.search(r'clearance\s*=\s*(\d+(?:\.\d+)?)', script, re.IGNORECASE)
    if clearance_match:
        clearance = float(clearance_match.group(1))
        if clearance < 5500:
            violations.append((
                f"Bridge vertical clearance {clearance:.0f}mm is below AASHTO minimum (5500mm)",
                f"Set vertical clearance to at least 5500mm"
            ))
    return violations


@_rule("PYLON_HEIGHT_RATIO", ["civil"], "warning")  
def _pylon_height(dims, ctx):
    """Cable-stayed bridge pylon height should be ~span/4 to span/5."""
    script = ctx.get("script", "")
    if "pylon" not in script.lower() and "tower" not in script.lower():
        return []
    
    violations = []
    pylons = [d for d in dims if d["type"] == "cylinder" and d.get("height", 0) > 10000]
    if not pylons:
        pylons = [d for d in dims if d["type"] == "box" and _is_pylon(d)]
    
    # Find the deck/span length
    span_match = re.search(r'(?:span|main_span|total_length)\s*=\s*(\d+(?:\.\d+)?)', script, re.IGNORECASE)
    if span_match and pylons:
        span = float(span_match.group(1))
        for p in pylons:
            pylon_h = p.get("height", 0)
            if pylon_h > 0 and span > 0:
                ratio = span / pylon_h
                if ratio > 7:
                    violations.append((
                        f"Pylon height {pylon_h:.0f}mm is too short for span {span:.0f}mm (ratio {ratio:.1f}:1)",
                        f"Increase pylon height to {span/5:.0f}mm - {span/4:.0f}mm"
                    ))
                elif ratio < 3:
                    violations.append((
                        f"Pylon height {pylon_h:.0f}mm is excessive for span {span:.0f}mm (ratio {ratio:.1f}:1)",
                        f"Reduce pylon height to {span/5:.0f}mm - {span/4:.0f}mm"
                    ))
    return violations


# ── Mechanical Engineering Rules ─────────────────────────────────────────────

@_rule("GEAR_MIN_TEETH", ["mechanical_engineering"], "warning")
def _gear_min_teeth(dims, ctx):
    """Gears should have ≥ 17 teeth to avoid undercutting."""
    script = ctx.get("script", "")
    violations = []
    teeth_matches = re.findall(r'(?:teeth|num_teeth|tooth_count|n_teeth)\s*=\s*(\d+)', script, re.IGNORECASE)
    for match in teeth_matches:
        teeth = int(match)
        if teeth < 17:
            violations.append((
                f"Gear has {teeth} teeth — below minimum 17 (causes undercutting)",
                f"Increase tooth count to at least 17, or use profile shift correction"
            ))
    return violations


@_rule("SHAFT_PROPORTIONS", ["mechanical_engineering"], "warning")
def _shaft_proportions(dims, ctx):
    """Shaft length-to-diameter ratio should be reasonable (< 20:1 unsupported)."""
    violations = []
    shafts = [d for d in dims if d["type"] == "cylinder" and _is_shaft(d)]
    for s in shafts:
        diameter = s["radius"] * 2
        length = s["height"]
        if diameter > 0 and length > 0:
            ratio = length / diameter
            if ratio > 20:
                violations.append((
                    f"Shaft L/D ratio is {ratio:.0f}:1 (L={length:.0f}mm, D={diameter:.0f}mm) — risk of whip/deflection",
                    f"Add intermediate bearings or increase diameter to {length/15:.0f}mm"
                ))
    return violations


@_rule("BLADE_THICKNESS", ["mechanical_engineering"], "warning")
def _blade_thickness(dims, ctx):
    """Turbine/fan blades should have minimum thickness for structural integrity."""
    script = ctx.get("script", "")
    if "blade" not in script.lower():
        return []
    
    violations = []
    blades = [d for d in dims if d["type"] == "box" and "blade" in d.get("name", "").lower()]
    for b in blades:
        thickness = min(b["length"], b["width"], b["height"])
        span = max(b["length"], b["width"], b["height"])
        if thickness > 0 and span > 0:
            ratio = span / thickness
            if ratio > 50:
                violations.append((
                    f"Blade span/thickness ratio is {ratio:.0f}:1 — too thin for structural loads",
                    f"Increase blade thickness to at least {span/30:.0f}mm"
                ))
    return violations


@_rule("WALL_THICKNESS_MECHANICAL", ["mechanical_engineering", "industrial"], "warning")
def _wall_thickness_mech(dims, ctx):
    """Mechanical enclosures/housings should have ≥ 2mm wall thickness."""
    violations = []
    # Look for thin-walled boxes (likely housings/enclosures)
    for d in dims:
        if d["type"] == "box":
            min_dim = min(d["length"], d["width"], d["height"])
            max_dim = max(d["length"], d["width"], d["height"])
            # Thin-walled if one dimension is much smaller than others
            if max_dim > 50 and min_dim < 2 and min_dim > 0:
                violations.append((
                    f"Wall thickness {min_dim:.1f}mm is below manufacturing minimum (2mm)",
                    f"Increase wall thickness to at least 3mm for casting, 2mm for sheet metal"
                ))
    return violations


@_rule("MIN_ROOF_PITCH", ["architectural"], "warning")
def _min_roof_pitch(dims, ctx):
    """Roof pitch should be reasonable to shed water."""
    script = ctx.get("script", "")
    violations = []
    pitch_match = re.search(r'(?:roof_pitch|pitch|angle)\s*=\s*(\d+(?:\.\d+)?)', script, re.IGNORECASE)
    if pitch_match:
        pitch = float(pitch_match.group(1))
        if 0 < pitch < 10:
            violations.append((
                f"Roof pitch {pitch:.1f}° is very low (minimum 10° recommended for runoff)",
                f"Increase roof pitch to at least 15°"
            ))
    return violations


@_rule("MAX_CANTILEVER_LENGTH", ["architectural", "structural", "civil"], "warning")
def _max_cantilever_length(dims, ctx):
    """Cantilevers should not be excessively long relative to their depth."""
    violations = []
    script = ctx.get("script", "")
    if "cantilever" not in script.lower():
        return []
    
    beams = [d for d in dims if d["type"] == "box" and _is_beam(d)]
    for b in beams:
        if "cantilever" in b.get("name", "").lower():
            span = max(b["length"], b["width"])
            depth = b["height"]
            if span > 0 and depth > 0:
                ratio = span / depth
                if ratio > 10:
                    violations.append((
                        f"Cantilever span/depth ratio is {ratio:.1f}:1 (span={span:.0f}mm, depth={depth:.0f}mm) — unsafe",
                        f"Increase depth to at least {span/10:.0f}mm or reduce span"
                    ))
    return violations


# ── Universal Rules ──────────────────────────────────────────────────────────

@_rule("ZERO_DIMENSION", ["architectural", "structural", "civil", "mechanical_engineering", "industrial"], "critical")
def _zero_dimension(dims, ctx):
    """No geometric dimension should be zero or negative."""
    violations = []
    for d in dims:
        for key in ["length", "width", "height", "radius"]:
            val = d.get(key)
            if val is not None and val <= 0:
                violations.append((
                    f"Element '{d.get('name', '?')}' has {key}={val} — invalid dimension",
                    f"Set {key} to a positive value"
                ))
    return violations


@_rule("EXTREME_ASPECT_RATIO", ["architectural", "structural", "civil", "mechanical_engineering", "industrial"], "warning")
def _extreme_aspect(dims, ctx):
    """Elements with extreme aspect ratios (>100:1) are likely errors."""
    violations = []
    for d in dims:
        if d["type"] == "box":
            values = sorted([d["length"], d["width"], d["height"]])
            if values[0] > 0:
                ratio = values[2] / values[0]
                if ratio > 100:
                    violations.append((
                        f"Element '{d.get('name', '?')}' has extreme aspect ratio {ratio:.0f}:1 ({values[2]:.0f}/{values[0]:.0f}mm)",
                        f"Check dimensions — this may be an error"
                    ))
    return violations


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRY CLASSIFIERS (heuristic — not perfect, but catches obvious patterns)
# ══════════════════════════════════════════════════════════════════════════════

def _is_wall(d: Dict) -> bool:
    """Heuristic: a wall is tall, long, and thin."""
    if d["type"] != "box":
        return False
    dims_sorted = sorted([d["length"], d["width"], d["height"]])
    # Thin dimension < 500, tall dimension > 1000
    return dims_sorted[0] < 500 and dims_sorted[2] > 1000 and dims_sorted[0] < dims_sorted[2] * 0.15


def _is_slab(d: Dict) -> bool:
    """Heuristic: a slab is wide, long, and thin (height is smallest)."""
    if d["type"] != "box":
        return False
    return (d["height"] < d["length"] * 0.15 and 
            d["height"] < d["width"] * 0.15 and
            d["length"] > 1000 and d["width"] > 1000)


def _is_column(d: Dict) -> bool:
    """Heuristic: a column is tall with small cross-section."""
    if d["type"] == "cylinder":
        return d["height"] > d["radius"] * 4
    if d["type"] == "box":
        dims_sorted = sorted([d["length"], d["width"], d["height"]])
        return dims_sorted[2] > dims_sorted[0] * 3 and dims_sorted[0] < 1000
    return False


def _is_beam(d: Dict) -> bool:
    """Heuristic: a beam is long, with moderate depth and width."""
    if d["type"] != "box":
        return False
    dims_sorted = sorted([d["length"], d["width"], d["height"]])
    # Long dimension >> other two, but not as thin as a wall
    return (dims_sorted[2] > dims_sorted[0] * 4 and
            dims_sorted[0] > 50 and dims_sorted[0] < 1000 and
            dims_sorted[2] > 1000)


def _is_deck(d: Dict) -> bool:
    """Heuristic: a bridge deck is very long, wide, and relatively thin."""
    if d["type"] != "box":
        return False
    return (max(d["length"], d["width"]) > 5000 and
            d["height"] < max(d["length"], d["width"]) * 0.1)


def _is_pylon(d: Dict) -> bool:
    """Heuristic: a pylon is very tall with moderate cross-section."""
    if d["type"] == "box":
        return d["height"] > 10000 and min(d["length"], d["width"]) < d["height"] * 0.3
    return False


def _is_shaft(d: Dict) -> bool:
    """Heuristic: a shaft is a cylinder much longer than its diameter."""
    if d["type"] != "cylinder":
        return False
    return d["height"] > d["radius"] * 6


def _is_floor_height(d: Dict, h: float) -> bool:
    """Check if a dimension looks like a floor-to-floor height."""
    if d["type"] != "box":
        return False
    # It's a floor height if H is the dominant dimension and the element is narrow (wall-like)
    return h > max(d["length"], d["width"]) * 0.5 and h > 2000


# ══════════════════════════════════════════════════════════════════════════════
# SCRIPT DIMENSION PARSER
# ══════════════════════════════════════════════════════════════════════════════

class CADScriptVisitor(ast.NodeVisitor):
    def __init__(self, script: str):
        self.script = script
        self.lines = script.split('\n')
        self.variables = {}
        self.dims = []
        self.current_name = "unknown"

    def _get_is_cut(self, lineno: int) -> bool:
        if lineno is None or lineno < 1:
            return False
        start = max(0, lineno - 3)
        end = min(len(self.lines), lineno + 2)
        chunk = "\n".join(self.lines[start:end])
        return '.cut(' in chunk

    def visit_Assign(self, node):
        if len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                var_name = target.id
                val = self._eval_node(node.value)
                if val is not None:
                    self.variables[var_name] = val
                
                old_name = self.current_name
                self.current_name = var_name
                self.visit(node.value)
                self.current_name = old_name
                return
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                old_name = self.current_name
                self.current_name = target.value.id
                self.visit(node.value)
                self.current_name = old_name
                return

        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == "Part":
                args = [self._eval_node(a) for a in node.args]
                resolved_args = [a if a is not None else 1.0 for a in args]

                if node.func.attr == "makeBox" and len(resolved_args) >= 3:
                    z_val = 0.0
                    if len(node.args) >= 4:
                        arg3 = node.args[3]
                        if isinstance(arg3, ast.Call) and getattr(arg3.func, "attr", "") == "Vector" and len(arg3.args) >= 3:
                            z_eval = self._eval_node(arg3.args[2])
                            if z_eval is not None:
                                z_val = z_eval
                                
                    self.dims.append({
                        "type": "box",
                        "length": abs(resolved_args[0]),
                        "width": abs(resolved_args[1]),
                        "height": abs(resolved_args[2]),
                        "z": z_val,
                        "name": self.current_name,
                        "is_cut": self._get_is_cut(getattr(node, "lineno", 0)),
                        "line": getattr(node, "lineno", 0)
                    })
                elif node.func.attr == "makeCylinder" and len(resolved_args) >= 2:
                    self.dims.append({
                        "type": "cylinder",
                        "radius": abs(resolved_args[0]),
                        "height": abs(resolved_args[1]),
                        "name": self.current_name,
                        "line": getattr(node, "lineno", 0)
                    })
                elif node.func.attr == "makeCone" and len(resolved_args) >= 3:
                    self.dims.append({
                        "type": "cone",
                        "radius": max(abs(resolved_args[0]), abs(resolved_args[1])),
                        "radius_top": min(abs(resolved_args[0]), abs(resolved_args[1])),
                        "height": abs(resolved_args[2]),
                        "name": self.current_name,
                        "line": getattr(node, "lineno", 0)
                    })

        self.generic_visit(node)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        elif isinstance(node, ast.Name):
            return self.variables.get(node.id)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            val = self._eval_node(node.operand)
            return -val if val is not None else None
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if left is not None and right is not None:
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div): return left / right if right != 0 else None
        return None

class ScriptDimensionParser:
    """Extract geometric dimensions from FreeCAD Python scripts using AST."""

    def __init__(self, script: str):
        self.script = script
        self.variables: Dict[str, float] = {}

    def parse(self) -> List[Dict]:
        """Parse all geometry creation calls and return dimension dicts."""
        try:
            tree = ast.parse(self.script)
        except SyntaxError:
            logger.warning("SyntaxError parsing script with AST.")
            return []
            
        visitor = CADScriptVisitor(self.script)
        visitor.visit(tree)
        self.variables = visitor.variables
        return visitor.dims


# ══════════════════════════════════════════════════════════════════════════════
# PHYSICS CHECK AGENT
# ══════════════════════════════════════════════════════════════════════════════

class PhysicsCheckAgent:
    """
    Deterministic engineering rule checker. No LLM needed.
    
    Parses the generated FreeCAD script, extracts dimensions from
    Part.makeBox / Part.makeCylinder / Part.makeCone calls, resolves
    variables, and checks them against domain-specific engineering rules.
    """

    def __init__(self):
        self.name = "PhysicsChecker"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run physics/engineering checks on a generated CAD script.
        
        Expects input_data keys:
            - generated_script: str
            - category: str (architectural, structural, civil, mechanical_engineering, industrial)
            - requirements: dict (optional)
            - difficulty: str (optional)
        
        Returns:
            - physics_valid: bool (True if no CRITICAL violations)
            - physics_score: float (0-1)
            - violations: list of {rule_id, severity, message, fix}
            - fix_suggestions: list of str (for refinement agent)
            - fem_recommended: bool (Phase 3 flag)
            - extracted_dimensions: list (debug info)
        """
        script = input_data.get("generated_script", "")
        category = input_data.get("category", "architectural")
        requirements = input_data.get("requirements", {})
        difficulty = input_data.get("difficulty", "intermediate")

        if not script.strip():
            return self._empty_result()

        # ── Parse dimensions ──
        parser = ScriptDimensionParser(script)
        dims = parser.parse()

        if not dims:
            logger.info("PhysicsChecker: No parseable geometry found in script")
            return self._empty_result(note="No geometry calls found to validate")

        logger.info(f"PhysicsChecker: Parsed {len(dims)} geometry elements from script")

        # ── Run domain-specific rules ──
        ctx = {
            "script": script,
            "category": category,
            "requirements": requirements,
            "difficulty": difficulty,
            "variables": parser.variables,
        }

        all_violations = []
        for rule in ENGINEERING_RULES:
            # Only run rules that apply to this domain
            if category not in rule["domains"]:
                continue
            try:
                results = rule["check"](dims, ctx)
                if results:
                    for msg, fix in results:
                        all_violations.append({
                            "rule_id": rule["id"],
                            "severity": rule["severity"],
                            "message": msg,
                            "fix": fix,
                        })
            except Exception as e:
                logger.warning(f"PhysicsChecker rule {rule['id']} failed: {e}")

        # ── Calculate score ──
        critical_count = sum(1 for v in all_violations if v["severity"] == "critical")
        warning_count = sum(1 for v in all_violations if v["severity"] == "warning")
        info_count = sum(1 for v in all_violations if v["severity"] == "info")

        # BUG FIX: The old linear formula (0.15*criticals + 0.05*warnings) collapses
        # to 0.0 whenever a model has >7 criticals or >20 warnings — which happens on
        # any moderately complex building because each *element* may trigger a rule.
        #
        # New formula: cap the contribution from each severity tier independently,
        # then combine. This means a model with many repeated warnings of the same
        # class doesn't score lower than one with just a single critical.
        #
        #   critical penalty: up to 0.50 (harder cap — real structural failures)
        #   warning penalty:  up to 0.30
        #   info penalty:     up to 0.10
        total_dims = max(len(dims), 1)
        critical_ratio = min(critical_count / max(total_dims * 0.5, 3), 1.0)   # normalised
        warning_ratio  = min(warning_count  / max(total_dims * 1.0, 5), 1.0)
        info_ratio     = min(info_count     / max(total_dims * 2.0, 10), 1.0)

        penalty = critical_ratio * 0.50 + warning_ratio * 0.30 + info_ratio * 0.10
        physics_score = max(0.0, min(1.0, 1.0 - penalty))
        physics_valid = critical_count == 0

        # ── Phase 3 flag: recommend FEM for complex structures ──
        fem_recommended = self._should_recommend_fem(dims, category, script)

        # ── Build fix suggestions for refinement agent ──
        fix_suggestions = [
            f"[PHYSICS] {v['message']} → FIX: {v['fix']}"
            for v in all_violations
            if v["severity"] in ("critical", "warning")
        ]

        # Log summary
        if all_violations:
            logger.warning(
                f"PhysicsChecker: {len(all_violations)} violations "
                f"({critical_count} critical, {warning_count} warning, {info_count} info) "
                f"→ score={physics_score:.2f}"
            )
        else:
            logger.info(f"PhysicsChecker: All checks passed → score=1.00")

        return {
            "physics_valid": physics_valid,
            "physics_score": physics_score,
            "violations": all_violations,
            "fix_suggestions": fix_suggestions,
            "fem_recommended": fem_recommended,
            "extracted_dimensions": dims,
            "critical_count": critical_count,
            "warning_count": warning_count,
        }

    def _empty_result(self, note: str = "") -> Dict:
        return {
            "physics_valid": True,
            "physics_score": 1.0,
            "violations": [],
            "fix_suggestions": [note] if note else [],
            "fem_recommended": False,
            "extracted_dimensions": [],
            "critical_count": 0,
            "warning_count": 0,
        }

    def _should_recommend_fem(self, dims: List, category: str, script: str) -> bool:
        """Recommend FEM analysis for designs with significant structural loads."""
        script_lower = script.lower()
        # Multi-story buildings (3+ tall elements)
        tall_elements = [d for d in dims if d.get("height", 0) > 4000]
        if len(tall_elements) >= 3 and category in ("architectural", "structural"):
            return True
        # Bridges — any bridge with a span > 5m gets FEM
        if "bridge" in script_lower and any(
            d.get("type") == "box" and max(d.get("length", 0), d.get("width", 0)) > 5000
            for d in dims
        ):
            return True
        # Any bridge with critical physics violations should also get FEM
        if "bridge" in script_lower and category == "civil":
            return True
        # Pressure vessels
        if "pressure" in script_lower or "vessel" in script_lower:
            return True
        # Towers, pylons, masts
        if any(kw in script_lower for kw in ["tower", "pylon", "mast", "chimney"]):
            very_tall = [d for d in dims if d.get("height", 0) > 8000]
            if very_tall:
                return True
        return False
