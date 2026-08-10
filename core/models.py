# Data models, enums, and constants for ArchGen Text-to-CAD system
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum


# ==================== DATA MODELS ====================

@dataclass
class ValidationResult:
    is_valid: bool
    score: float
    errors: List[str]
    suggestions: List[str]
    category: str


@dataclass
class CADGenerationResult:
    script: str
    success: bool
    validation_results: Dict[str, 'ValidationResult']
    iterations: int
    final_score: float
    error_summary: Optional[str] = None
    fcstd_path: Optional[str] = None  # Path to generated FreeCAD file
    stl_path: Optional[str] = None    # Path to exported STL file
    svg_path: Optional[str] = None    # Path to exported TechDraw SVG file


# ==================== ENUMS ====================

class ValidationCategory(Enum):
    SYNTAX = "syntax"
    EXECUTION = "execution"
    GEOMETRIC = "geometric"
    VISUAL = "visual"
    SEMANTIC = "semantic"
    PHYSICS = "physics"


class AgentState(Enum):
    PROMPT_VALIDATION = "prompt_validation"
    CAD_GENERATION = "cad_generation"
    EXECUTION_VALIDATION = "execution_validation"
    QUALITY_ASSESSMENT = "quality_assessment"
    REFINEMENT = "refinement"
    COMPLETED = "completed"
    FAILED = "failed"



# ==================== PYDANTIC MODELS (Structured LLM Output) ====================

try:
    from pydantic import BaseModel, Field as PydanticField
    
    class GuardrailResult(BaseModel):
        """Output of the Guardrail Gate — determines if a prompt should proceed."""
        is_allowed: bool = PydanticField(description="Whether the prompt is allowed to proceed to CAD generation")
        rejection_reason: Optional[str] = PydanticField(default=None, description="Human-readable reason for rejection, if is_allowed=False")
        confidence: float = PydanticField(ge=0.0, le=1.0, description="Confidence that this classification is correct")
        is_cad_related: bool = PydanticField(description="Whether the prompt is related to CAD/engineering/design")
        is_appropriate: bool = PydanticField(description="Whether the prompt contains appropriate content")
        is_specific_enough: bool = PydanticField(description="Whether the prompt has enough detail to generate a CAD model")
        needs_clarification: bool = PydanticField(default=False, description="Whether we should ask the user for more details before proceeding")
        clarification_prompt: Optional[str] = PydanticField(default=None, description="Question to ask the user if needs_clarification=True")
    
    class ComponentSpec(BaseModel):
        """Specification for a single design component in the component plan."""
        name: str = PydanticField(description="Component name (e.g., 'Foundation', 'Roof_Structure')")
        description: str = PydanticField(description="What this component is and its purpose")
        material: str = PydanticField(description="Primary material (e.g., 'Concrete', 'Steel', 'Timber')")
        dimensions_mm: Dict[str, float] = PydanticField(description="Key dimensions in millimeters (e.g., {'length': 10000, 'width': 8000, 'height': 300})")
        freecad_approach: str = PydanticField(description="How to build this in FreeCAD (e.g., 'Part.makeBox for main slab, Part.makeCylinder for piles')")
        construction_order: int = PydanticField(ge=1, description="Build priority (1=first, foundation before walls before roof)")
        depends_on: List[str] = PydanticField(default_factory=list, description="Component names this depends on")
    
    class RequirementsSpec(BaseModel):
        """Extracted engineering requirements from the prompt."""
        dimensions: Dict[str, str] = PydanticField(default_factory=dict, description="Overall dimensions in mm (e.g., {'length': '50000mm', 'width': '30000mm'})")
        features: List[str] = PydanticField(default_factory=list, description="Requested features (e.g., 'windows', 'balconies', 'parking')")
        materials: List[str] = PydanticField(default_factory=list, description="Materials mentioned (e.g., 'concrete', 'glass', 'steel')")
        load_cases: List[Dict[str, Any]] = PydanticField(default_factory=list, description="Structural load cases for FEM")
    
    class PromptAnalysis(BaseModel):
        """Complete structured output from prompt analysis — replaces the old freeform JSON."""
        is_valid: bool = PydanticField(default=True, description="Whether the prompt is a valid CAD request")
        difficulty: str = PydanticField(description="'simple', 'intermediate', or 'advanced'")
        category: str = PydanticField(description="'architectural', 'structural', 'civil', 'mechanical_engineering', or 'industrial'")
        components: List[str] = PydanticField(description="List of design components extracted from the prompt")
        tags: List[str] = PydanticField(description="Keywords describing the design")
        enhanced_prompt: str = PydanticField(description="Improved technical prompt with specific dimensions and parameters")
        domain: str = PydanticField(description="Engineering domain for rule lookup")
        complexity_score: float = PydanticField(ge=0.0, le=1.0, description="Estimated complexity (0=trivial, 1=extremely complex)")
        component_plan: List[ComponentSpec] = PydanticField(description="Ordered component specifications for the CAD generator")
        requirements: RequirementsSpec = PydanticField(default_factory=RequirementsSpec, description="Extracted engineering requirements")

except ImportError:
    # Pydantic v2 not available — these models won't be used
    pass


# ==================== CONSTANTS ====================

# PHASE 4: Domain-Specific Engineering Rules
DOMAIN_RULES = {
    "architectural": {
        "floor_height": "3000mm (standard residential/commercial)",
        "wall_thickness": "200-300mm for load-bearing, 100-150mm for partitions",
        "window_aspect": "1:1.5 to 1:2 (width:height)",
        "door_height": "2100mm standard, 2400mm for main entrances",
        "bay_spacing": "6000-9000mm for column grids",
        "ceiling_height": "2700-3000mm clear height",
        "stair_rise": "150-180mm per step",
        "stair_tread": "280-300mm depth",
        "roof_pitch": "Minimum 10 degrees for drainage.",
        "cantilever_length": "Span/depth ratio should be < 10 for cantilevers.",
        "load_factor": "Safety Factor must be >= 2.0. Max allowable stress: 15 MPa for concrete.",
        "deflection_limit": "span / 240 (max allowed sagging under live load)."
    },
    "structural": {
        "column_spacing": "6000-9000mm typical grid",
        "beam_depth": "span/12 to span/15 for concrete, span/20 for steel",
        "slab_thickness": "150-200mm for residential, 200-300mm for commercial",
        "column_size": "300x300mm minimum for low-rise, 600x600mm for high-rise",
        "foundation_depth": "1000-1500mm below ground level",
        "load_factor": "Safety Factor >= 1.5 for steel yield (355 MPa max).",
        "deflection_limit": "span / 360 for primary structural members.",
        "fatigue": "Consider cyclical load fatigue; ensure smooth fillets at joints to reduce stress concentration."
    },
    "civil": {
        "road_lane_width": "3500mm per lane",
        "sidewalk_width": "1500-2000mm",
        "bridge_deck_ratio": "depth/span = 1:20 for beam bridges",
        "tunnel_clearance": "5000mm height for vehicular",
        "slope_gradient": "1:12 maximum for accessibility ramps",
        "traffic_load": "Must withstand 10 kPa multi-lane vehicle tracking loads.",
        "load_factor": "Safety Factor >= 2.5 for public transit and civil infrastructure.",
        "deflection_limit": "span / 500 for bridge decks."
    },
    "mechanical_engineering": {
        "tolerance": "±0.1mm for precision fits, ±0.5mm for general",
        "thread_pitch": "ISO metric standard (M6=1mm, M10=1.5mm)",
        "shaft_diameter": "Standard series: 10, 12, 16, 20, 25, 30mm",
        "bearing_clearance": "0.02-0.05mm for running fits",
        "gear_module": "1, 1.5, 2, 2.5, 3mm standard",
        "stress_limits": "Max Von Mises Stress < 215 MPa (AISI 304).",
        "fatigue": "Avoid sharp 90-degree internal corners to prevent catastrophic fatigue failure (always chamfer/fillet).",
        "load_factor": "Safety Factor >= 3.0 for dynamic rotating assemblies."
    },
    "industrial": {
        "aisle_width": "3000mm for forklift access",
        "loading_dock_height": "1200mm for trucks",
        "clear_height": "6000-12000mm for warehouses",
        "column_grid": "12000x24000mm for industrial",
        "equipment_load": "Live load capacity >= 15 kPa for heavy machinery.",
        "load_factor": "Safety Factor >= 1.5 for static industrial storage."
    }
}

# PHASE 5: Detail Level Requirements
DETAIL_REQUIREMENTS = {
    "simple": {
        "min_lines": 50,
        "max_lines": 150,
        "min_components": 1,
        "features": ["basic geometry", "single document"]
    },
    "intermediate": {
        "min_lines": 200,
        "max_lines": 500,
        "min_components": 3,
        "features": ["windows", "doors", "structural elements", "proper scale"]
    },
    "advanced": {
        "min_lines": 500,
        "max_lines": 2000,
        "min_components": 5,
        "features": ["detailed facade", "interiors", "landscaping", "multiple sub-assemblies", "realistic materials"]
    }
}

# Common FreeCAD errors to avoid
most_common_Freecad_errors = """
CRITICAL HEADLESS MODE ERRORS (FreeCADCmd.exe has NO GUI):
1. DO NOT use obj.ViewObject - it is None in headless mode!
2. DO NOT use obj.ViewObject.ShapeColor - causes 'NoneType' error!
3. DO NOT use Gui.ActiveView or Gui.activeDocument() - GUI doesn't exist!
4. DO NOT use FreeCADGui or Gui module at all!
5. Colors/materials are only visual - skip them in headless scripts.

COMMON RUNTIME ERRORS:
- 'NoneType' object has no attribute 'ShapeColor' → Remove all ViewObject references
- Module 'FreeCADGui' not found → Don't import or use Gui module
- 'Gui' is not defined → Remove all Gui references
"""

# FreeCAD Performance, Architecture, and Assembly Tips
FREECAD_PERFORMANCE_TIPS = """
CRITICAL ARCHITECTURE RULES (How to structure models):
1. USE ASSEMBLIES: Create an `App::Part` as the root container (e.g., `bridge = doc.addObject('App::Part', 'Bridge')`).
2. SEPARATE COMPONENTS: Create individual `PartDesign::Body` or `Part::Feature` items for each component and add them to the assembly (e.g., `bridge.addObject(deck_body)`).
3. NAME COMPONENTS EXPLICITLY: Set `obj.Label` or `obj.Name` to match the exact names of the components so that Finite Element constraints (load_cases targets) can find them.
4. AVOID FUSING EVERYTHING: Do NOT use deeply nested `shape1.fuse(shape2)` chains. Only fuse if making a single, unified, homogeneous part.
5. USE PARAMETRICS: Create a `Spreadsheet::Sheet` named 'Parameters', store extracted dimensions there, and bind geometric properties to it using `setExpression(...)`.

CRITICAL BOOLEAN OPERATIONS RULE:
1. NEVER use sequential .fuse() or .cut() in a loop. Sequential boolean chains cause topology corruption (circles become diamonds, faces become polygons).
   WRONG:  for tooth in teeth_list: gear = gear.fuse(tooth)
   RIGHT:  compound = Part.Compound(teeth_list); gear = disk.fuse(compound)
   Always gather all shapes into a Python list, create Part.Compound(list), then do ONE .fuse() or ONE .cut().
2. LIMIT total boolean operations to under 10 per solid body. If you need more, batch them using Part.Compound.
3. After complex boolean chains, validate with: if not shape.isValid(): shape = shape.fix(0.01, 0.01, 0.01)

DEFENSIVE OVERCUT RULE (prevent ghost faces on boolean cuts):
1. When cutting a hole through a solid, extend the cutting tool 1-2mm BEYOND both faces of the target.
   WRONG:  hole = Part.makeCylinder(r, plate_thickness, App.Vector(x, y, 0))
   RIGHT:  hole = Part.makeCylinder(r, plate_thickness + 2.0, App.Vector(x, y, -1.0))
   This prevents zero-thickness residual faces in the B-Rep topology.

PERFORMANCE RULES:
1. LIMIT total object count to ~500 for smooth rendering. Use `Draft.array` for repeating elements.
2. AVOID complex lofts with many sections (>20).
"""

# FreeCAD Scripting Cheat Sheet for LLM context
FREECAD_CHEAT_SHEET = """
FREECAD API QUICK REFERENCE:

--- 1. SPREADSHEET PARAMETRICS ---
sheet = doc.addObject('Spreadsheet::Sheet', 'Parameters')
sheet.set('A1', '5000'); sheet.setAlias('A1', 'Span')
# Bind geometry:
box.setExpression('Length', 'Parameters.Span')

--- 2. HIERARCHICAL ASSEMBLIES ---
assembly = doc.addObject('App::Part', 'MainAssembly')
part = doc.addObject('Part::Feature', 'Deck')
part.Shape = Part.makeBox(...)
assembly.addObject(part)

--- 3. GEOMETRY & OPERATIONS ---
# Primitives
Box: Part.makeBox(L, W, H, App.Vector(x,y,z))
Cyl: Part.makeCylinder(R, H, App.Vector(x,y,z))
Cone: Part.makeCone(R1, R2, H, App.Vector(x,y,z))
Sphere: Part.makeSphere(R, App.Vector(x,y,z))
# Transforms
shape.translate(App.Vector(dx, dy, dz))
shape.rotate(App.Vector(0,0,0), App.Vector(0,0,1), angle_deg)
# Booleans (Use sparingly — ALWAYS batch via Part.Compound)
union_shape = shape1.fuse(shape2)
cut_shape = shape1.cut(shape2)

--- 4. BATCH BOOLEANS (MANDATORY for >3 boolean operations) ---
# Fusing multiple shapes (e.g., teeth on a gear, fins on a heat sink):
shapes_list = [make_tooth(i) for i in range(12)]
compound = Part.Compound(shapes_list)   # zero Boolean cost — just groups shapes
result = base_disk.fuse(compound)        # ONE Boolean operation, not 12

# Cutting multiple holes:
holes_list = [Part.makeCylinder(r, h+2, App.Vector(x,y,-1)) for x,y in positions]
holes_compound = Part.Compound(holes_list)
result = plate.cut(holes_compound)       # ONE Boolean cut, not N sequential cuts

--- 5. SWEPT PROFILES (for rails, pipes, helical geometry) ---
import math
# Helix (e.g., spiral staircase rail, spring, thread):
helix = Part.makeHelix(pitch_mm, height_mm, radius_mm)
# Swept tube along a path:
profile_wire = Part.Wire(Part.makeCircle(tube_radius))
path_wire = Part.Wire(helix.Edges)
swept_solid = Part.makePipeShell([path_wire], profile_wire, True)

--- 6. TOPOLOGY HEALING (after complex booleans) ---
# Always validate shape after boolean operations:
if not result_shape.isValid():
    result_shape = result_shape.fix(0.01, 0.01, 0.01)
    print('Shape was invalid — applied fix()')

--- 7. DOCUMENT CLEANUP (prevent duplicate geometry) ---
# CRITICAL: Only add the FINAL result to the document.
# Do NOT add intermediate construction shapes as separate Part::Feature objects.
# WRONG (creates overlapping duplicates):
#   doc.addObject('Part::Feature', 'base_plate').Shape = base_plate
#   doc.addObject('Part::Feature', 'flanges').Shape = flanges
#   doc.addObject('Part::Feature', 'final').Shape = base_plate.fuse(flanges)
# RIGHT (only the final result):
#   final_shape = base_plate.fuse(flanges)
#   result_obj = doc.addObject('Part::Feature', 'MotorBracket')
#   result_obj.Shape = final_shape

--- 8. MATERIAL ASSIGNMENT ---
# Always assign simple string labels if real materials are unavailable
part.Label2 = 'Material: Steel'
"""


# ==================== HELPERS ====================

def word_count(text) -> int:
    """Return the number of whitespace-delimited words in text."""
    try:
        if not isinstance(text, str):
            text = str(text)
        return len(text.strip().split())
    except Exception:
        return len(text)
