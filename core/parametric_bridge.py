import FreeCAD as App
import Part
from FreeCAD import Vector
import math

# ==============================================================================
# PARAMETRIC HYBRID BRIDGE GENERATOR for FreeCAD
# ==============================================================================
# This script procedurally generates a complex hybrid suspension-arch bridge 
# reflecting the provided blueprint, including the structural grid, load paths, 
# parametric constraints, and clearance zones.
#
# Usage: Open FreeCAD, open the Python Console (View -> Panels -> Python Console),
# and copy-paste this script, or load it as a Macro.
# ==============================================================================

DOC_NAME = "Parametric_Hybrid_Bridge"
doc = App.getDocument(DOC_NAME)
if not doc:
    doc = App.newDocument(DOC_NAME)

# ------------------------------------------------------------------------------
# 1. PARAMETRIC CONSTRAINTS
# Adjust these values to parametrically control the entire bridge design.
# ------------------------------------------------------------------------------
MAIN_SPAN       = 200.0   # Length of the central suspension + arch span
SIDE_SPAN       = 80.0    # Length of the side spans
DECK_WIDTH      = 24.0    # Total width of the bridge deck
DECK_THICKNESS  = 1.5     # Vertical thickness of the deck slab
PIER_HEIGHT     = 50.0    # Height from ground level (Clearance Zone) to the deck
TOWER_HEIGHT    = 80.0    # Height of the suspension towers above the deck
ARCH_RISE       = 35.0    # The upward rise of the supporting arch underneath
CABLE_SAG       = 55.0    # Sag of the main suspension cable

TOWER_WIDTH     = 6.0     # Width of individual tower columns
TOWER_DEPTH     = 10.0    # Depth (along the bridge) of tower columns

TRUSS_HEIGHT    = 6.0     # Depth of the under-deck structural grid
PANEL_LENGTH    = 10.0    # Longitudinal subdivision step for structural grid

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS FOR GEOMETRY PROCESSING
# ------------------------------------------------------------------------------
shapes = []

def add_box(l, w, h, pos):
    box = Part.makeBox(l, w, h)
    box.translate(pos)
    shapes.append(box)

def add_line_strut(p1, p2, radius=0.5):
    """Creates a cylindrical structural member representing a load path/strut."""
    v = p2.sub(p1)
    length = v.Length
    if length > 0.001:
        cyl = Part.makeCylinder(radius, length, p1, v)
        shapes.append(cyl)

def add_arch(start_pos, end_pos, rise, thickness):
    """Creates a parabolic arch for underneath support."""
    steps = int(MAIN_SPAN / (PANEL_LENGTH / 2))
    span = end_pos.x - start_pos.x
    for i in range(steps):
        t1 = i / steps
        t2 = (i + 1) / steps
        
        x1 = start_pos.x + t1 * span
        x2 = start_pos.x + t2 * span
        
        loc_x1 = x1 - (start_pos.x + span/2)
        loc_x2 = x2 - (start_pos.x + span/2)
        
        # Parabolic equation centered at mid-span
        z1 = start_pos.z + rise - (4 * rise / (span * span)) * (loc_x1 * loc_x1)
        z2 = start_pos.z + rise - (4 * rise / (span * span)) * (loc_x2 * loc_x2)
        
        pt1 = Vector(x1, start_pos.y, z1)
        pt2 = Vector(x2, end_pos.y, z2)
        add_line_strut(pt1, pt2, radius=thickness)

# ------------------------------------------------------------------------------
# 2. CLEARANCE ZONES & FOUNDATIONS (PIERS)
# ------------------------------------------------------------------------------
pier_x_coords = [-MAIN_SPAN/2, MAIN_SPAN/2]

for px in pier_x_coords:
    # Base foundation in water/ground
    add_box(TOWER_DEPTH*2, DECK_WIDTH + 14, PIER_HEIGHT/3, Vector(px - TOWER_DEPTH, -(DECK_WIDTH+14)/2, 0))
    # Vertical supports up to the deck
    add_box(TOWER_DEPTH, TOWER_WIDTH*1.5, PIER_HEIGHT*2/3, Vector(px - TOWER_DEPTH/2, -DECK_WIDTH/2 - 2, PIER_HEIGHT/3))
    add_box(TOWER_DEPTH, TOWER_WIDTH*1.5, PIER_HEIGHT*2/3, Vector(px - TOWER_DEPTH/2, DECK_WIDTH/2 - TOWER_WIDTH*1.5 + 2, PIER_HEIGHT/3))

# Side span supports (End abutments)
side_pier_x = [-MAIN_SPAN/2 - SIDE_SPAN, MAIN_SPAN/2 + SIDE_SPAN]
for px in side_pier_x:
    add_box(TOWER_DEPTH, DECK_WIDTH, PIER_HEIGHT, Vector(px - TOWER_DEPTH/2, -DECK_WIDTH/2, 0))

# ------------------------------------------------------------------------------
# 3. TOWERS
# ------------------------------------------------------------------------------
for px in pier_x_coords:
    # Left and Right tower columns
    add_box(TOWER_DEPTH, TOWER_WIDTH, TOWER_HEIGHT, Vector(px - TOWER_DEPTH/2, -DECK_WIDTH/2, PIER_HEIGHT))
    add_box(TOWER_DEPTH, TOWER_WIDTH, TOWER_HEIGHT, Vector(px - TOWER_DEPTH/2, DECK_WIDTH/2 - TOWER_WIDTH, PIER_HEIGHT))
    
    # Structural Grid (X-Bracing) on Towers
    num_x = 5
    x_h = TOWER_HEIGHT / num_x
    for i in range(num_x):
        z_base = PIER_HEIGHT + i * x_h
        # Corner points of the bracing panel
        p1 = Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH, z_base)
        p2 = Vector(px, DECK_WIDTH/2 - TOWER_WIDTH, z_base + x_h)
        p3 = Vector(px, DECK_WIDTH/2 - TOWER_WIDTH, z_base)
        p4 = Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH, z_base + x_h)
        # Diagonals & cross beams
        add_line_strut(p1, p2, 1.0)
        add_line_strut(p3, p4, 1.0)
        if i > 0:
            add_line_strut(p1, p3, 1.2)
    # Top horizontal beam
    add_line_strut(Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH, PIER_HEIGHT + TOWER_HEIGHT), 
                   Vector(px, DECK_WIDTH/2 - TOWER_WIDTH, PIER_HEIGHT + TOWER_HEIGHT), 1.5)

# ------------------------------------------------------------------------------
# 4. DECK & STRUCTURAL GRID
# ------------------------------------------------------------------------------
total_len = MAIN_SPAN + 2 * SIDE_SPAN
start_x = -total_len / 2

# Main Top Deck Slab
add_box(total_len, DECK_WIDTH, DECK_THICKNESS, Vector(start_x, -DECK_WIDTH/2, PIER_HEIGHT))

# Complex under-deck truss system
num_panels = int(total_len / PANEL_LENGTH)
actual_panel_len = total_len / num_panels

for i in range(num_panels):
    x_curr = start_x + i * actual_panel_len
    x_next = start_x + (i + 1) * actual_panel_len
    
    for y in [-DECK_WIDTH/2 + 1, DECK_WIDTH/2 - 1]:
        # Bottom longitudinal chords
        add_line_strut(Vector(x_curr, y, PIER_HEIGHT - TRUSS_HEIGHT), Vector(x_next, y, PIER_HEIGHT - TRUSS_HEIGHT), 0.8)
        # Vertical struts connecting deck to bottom chord
        add_line_strut(Vector(x_curr, y, PIER_HEIGHT), Vector(x_curr, y, PIER_HEIGHT - TRUSS_HEIGHT), 0.6)
        # Diagonal X struts
        add_line_strut(Vector(x_curr, y, PIER_HEIGHT - TRUSS_HEIGHT), Vector(x_next, y, PIER_HEIGHT), 0.5)
        add_line_strut(Vector(x_curr, y, PIER_HEIGHT), Vector(x_next, y, PIER_HEIGHT - TRUSS_HEIGHT), 0.5)
        
    # Transverse bottom beams
    if i > 0:
        add_line_strut(Vector(x_curr, -DECK_WIDTH/2 + 1, PIER_HEIGHT - TRUSS_HEIGHT),
                       Vector(x_curr, DECK_WIDTH/2 - 1, PIER_HEIGHT - TRUSS_HEIGHT), 0.8)

# ------------------------------------------------------------------------------
# 5. THE SUPPORTING ARCH (Hybrid Structural Feature)
# ------------------------------------------------------------------------------
# The arch spans between the inner sides of the main piers
for y in [-DECK_WIDTH/2 + 2, DECK_WIDTH/2 - 2]:
    p_start = Vector(-MAIN_SPAN/2, y, PIER_HEIGHT - ARCH_RISE)
    p_end = Vector(MAIN_SPAN/2, y, PIER_HEIGHT - ARCH_RISE)
    
    # Ensure arch connects up appropriately
    add_arch(p_start, p_end, ARCH_RISE, 1.5)
    
    # Vertical struts from arch up to the deck structural grid
    arch_span = MAIN_SPAN
    arch_steps = int(MAIN_SPAN / PANEL_LENGTH)
    for i in range(1, arch_steps):
        t = i / arch_steps
        px = p_start.x + t * arch_span
        loc_x = px - (p_start.x + arch_span/2)
        pz = p_start.z + ARCH_RISE - (4 * ARCH_RISE / (arch_span * arch_span)) * (loc_x * loc_x)
        
        # Connect arch to the bottom of the deck truss system
        if pz < PIER_HEIGHT - TRUSS_HEIGHT:
            add_line_strut(Vector(px, y, pz), Vector(px, y, PIER_HEIGHT - TRUSS_HEIGHT), 0.8)

# ------------------------------------------------------------------------------
# 6. LOAD PATHS: SUSPENSION CABLES
# ------------------------------------------------------------------------------
cable_pts_main_l = []
cable_pts_main_r = []

span_steps = int(MAIN_SPAN / PANEL_LENGTH)
for i in range(span_steps + 1):
    t = i / span_steps
    px = -MAIN_SPAN/2 + t * MAIN_SPAN
    # Parabolic load path for suspension cable
    pz = PIER_HEIGHT + TOWER_HEIGHT - CABLE_SAG + (4 * CABLE_SAG / (MAIN_SPAN * MAIN_SPAN)) * (px * px)
    
    cable_pts_main_l.append(Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, pz))
    cable_pts_main_r.append(Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, pz))
    
    # Vertical suspenders
    if 0 < i < span_steps:
        add_line_strut(Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, pz), Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, PIER_HEIGHT), 0.3)
        add_line_strut(Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, pz), Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, PIER_HEIGHT), 0.3)

# Draw main cables longitudinally
for pts in [cable_pts_main_l, cable_pts_main_r]:
    for i in range(len(pts)-1):
        add_line_strut(pts[i], pts[i+1], 1.2)

# Side span cables (Straight Anchorages to the side piers)
for side_x_start, side_dir in [(-MAIN_SPAN/2, -1), (MAIN_SPAN/2, 1)]:
    side_pts_l = []
    side_pts_r = []
    side_steps = int(SIDE_SPAN / PANEL_LENGTH)
    for i in range(side_steps + 1):
        t = i / side_steps
        px = side_x_start + side_dir * t * SIDE_SPAN
        # Straight linear descent to ground/side pier
        pz = PIER_HEIGHT + TOWER_HEIGHT - t * TOWER_HEIGHT
        
        side_pts_l.append(Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, pz))
        side_pts_r.append(Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, pz))
        
        # Vertical suspenders for side span
        if 0 < i < side_steps:
            add_line_strut(Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, pz), Vector(px, -DECK_WIDTH/2 + TOWER_WIDTH/2, PIER_HEIGHT), 0.3)
            add_line_strut(Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, pz), Vector(px, DECK_WIDTH/2 - TOWER_WIDTH/2, PIER_HEIGHT), 0.3)
            
    for i in range(len(side_pts_l)-1):
        add_line_strut(side_pts_l[i], side_pts_l[i+1], 1.2)
        add_line_strut(side_pts_r[i], side_pts_r[i+1], 1.2)

# ------------------------------------------------------------------------------
# 7. FINAL ASSEMBLY & DISPLAY
# ------------------------------------------------------------------------------
print(f"Generating CAD model with {len(shapes)} structural elements...")
comp = Part.makeCompound(shapes)

bridge_obj = doc.addObject("Part::Feature", "Hybrid_Suspension_Bridge_Assembly")
bridge_obj.Shape = comp
bridge_obj.ViewObject.ShapeColor = (0.7, 0.7, 0.75) # Cool metallic gray

doc.recompute()
App.Console.PrintMessage("Parametric Hybrid Bridge built successfully!\n")
print("Done! Bridge is generated in the active document.")
