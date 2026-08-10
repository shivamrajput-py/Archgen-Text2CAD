#!/usr/bin/env python3
"""
FreeCAD Renderer Script
========================
This script is run by FreeCADCmd.exe to render a model from multiple angles.

Usage: FreeCADCmd.exe freecad_renderer.py <fcstd_path> <output_dir>

Output: 6 PNG images from different angles + JSON metadata
"""

import sys
import os
import json
import math

# FreeCAD imports
try:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part
    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False


# Camera positions for 6 standard views
# Each tuple: (name, camera_direction, camera_up)
CAMERA_VIEWS = [
    ("front", (0, -1, 0), (0, 0, 1)),      # Looking from -Y towards +Y
    ("back", (0, 1, 0), (0, 0, 1)),        # Looking from +Y towards -Y
    ("left", (-1, 0, 0), (0, 0, 1)),       # Looking from -X towards +X
    ("right", (1, 0, 0), (0, 0, 1)),       # Looking from +X towards -X
    ("top", (0, 0, 1), (0, 1, 0)),         # Looking from +Z towards -Z
    ("isometric", (1, -1, 0.7), (0, 0, 1)) # Isometric view
]

# Image settings
IMAGE_WIDTH = 800
IMAGE_HEIGHT = 600
BACKGROUND_COLOR = "White"


def normalize(vec):
    """Normalize a vector."""
    length = math.sqrt(vec[0]**2 + vec[1]**2 + vec[2]**2)
    if length == 0:
        return vec
    return (vec[0]/length, vec[1]/length, vec[2]/length)


def get_bounding_box(doc):
    """Get combined bounding box of all objects."""
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
    
    for obj in doc.Objects:
        if hasattr(obj, 'Shape') and obj.Shape:
            try:
                bb = obj.Shape.BoundBox
                min_x = min(min_x, bb.XMin)
                min_y = min(min_y, bb.YMin)
                min_z = min(min_z, bb.ZMin)
                max_x = max(max_x, bb.XMax)
                max_y = max(max_y, bb.YMax)
                max_z = max(max_z, bb.ZMax)
            except:
                pass
    
    if min_x == float('inf'):
        return None
    
    return {
        "center": ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2),
        "size": (max_x - min_x, max_y - min_y, max_z - min_z),
        "diagonal": math.sqrt((max_x-min_x)**2 + (max_y-min_y)**2 + (max_z-min_z)**2)
    }


def render_views(fcstd_path, output_dir):
    """Render multiple views of a FreeCAD model."""
    result = {
        "success": False,
        "images": [],
        "errors": []
    }
    
    # Validate inputs
    if not os.path.exists(fcstd_path):
        result["errors"].append(f"File not found: {fcstd_path}")
        return result
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Initialize GUI (required for rendering)
        # Note: This may need adjustment based on FreeCAD version
        try:
            Gui.showMainWindow()
        except:
            pass  # May already be initialized or not needed
        
        # Open document
        doc = App.openDocument(fcstd_path)
        if doc is None:
            result["errors"].append("Failed to open document")
            return result
        
        # Get bounding box for camera positioning
        bbox = get_bounding_box(doc)
        if bbox is None:
            result["errors"].append("No geometry found in document")
            return result
        
        # Calculate camera distance based on model size
        camera_distance = bbox["diagonal"] * 2.0
        center = bbox["center"]
        
        # Get the active view
        try:
            view = Gui.activeDocument().activeView()
        except:
            result["errors"].append("Cannot get active view. GUI may not be available.")
            return result
        
        # Render each view
        for view_name, direction, up in CAMERA_VIEWS:
            try:
                # Normalize direction
                direction = normalize(direction)
                
                # Calculate camera position
                cam_pos = (
                    center[0] + direction[0] * camera_distance,
                    center[1] + direction[1] * camera_distance,
                    center[2] + direction[2] * camera_distance
                )
                
                # Set camera
                view.viewPosition(App.Vector(*cam_pos), App.Vector(*center), App.Vector(*up))
                view.fitAll()
                
                # Save image
                image_path = os.path.join(output_dir, f"render_{view_name}.png")
                view.saveImage(image_path, IMAGE_WIDTH, IMAGE_HEIGHT, BACKGROUND_COLOR)
                
                result["images"].append({
                    "view": view_name,
                    "path": image_path,
                    "width": IMAGE_WIDTH,
                    "height": IMAGE_HEIGHT
                })
                
            except Exception as e:
                result["errors"].append(f"Error rendering {view_name}: {str(e)}")
        
        # Close document
        App.closeDocument(doc.Name)
        
        result["success"] = len(result["images"]) > 0
        
    except Exception as e:
        result["errors"].append(f"Rendering failed: {str(e)}")
    
    return result


def render_simple(fcstd_path, output_dir):
    """
    Simplified rendering using FreeCAD's built-in export.
    Fallback if GUI rendering fails.
    """
    result = {
        "success": False,
        "images": [],
        "errors": []
    }
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        doc = App.openDocument(fcstd_path)
        if doc is None:
            result["errors"].append("Failed to open document")
            return result
        
        # Try to export as image using different methods
        for obj in doc.Objects:
            if hasattr(obj, 'Shape') and obj.Shape:
                try:
                    # Export shape to image using mesh
                    import Mesh
                    mesh = Mesh.Mesh()
                    for o in doc.Objects:
                        if hasattr(o, 'Shape'):
                            try:
                                mesh.addMesh(Mesh.Mesh(o.Shape.tessellate(1)))
                            except:
                                pass
                    
                    # Save as STL (can be rendered externally)
                    stl_path = os.path.join(output_dir, "model.stl")
                    mesh.write(stl_path)
                    result["images"].append({
                        "view": "mesh_export",
                        "path": stl_path,
                        "type": "stl"
                    })
                    result["success"] = True
                    break
                except Exception as e:
                    result["errors"].append(f"Mesh export failed: {e}")
        
        App.closeDocument(doc.Name)
        
    except Exception as e:
        result["errors"].append(f"Simple render failed: {str(e)}")
    
    return result


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print(json.dumps({
            "success": False,
            "errors": ["Usage: freecad_renderer.py <fcstd_path> <output_dir>"]
        }))
        sys.exit(1)
    
    fcstd_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not FREECAD_AVAILABLE:
        print(json.dumps({
            "success": False,
            "errors": ["FreeCAD not available. Run via FreeCADCmd.exe"]
        }))
        sys.exit(1)
    
    # Try full GUI rendering first
    result = render_views(fcstd_path, output_dir)
    
    # If GUI rendering failed, try simple export
    if not result["success"]:
        result = render_simple(fcstd_path, output_dir)
    
    # Output JSON result
    print("===RENDERER_RESULT_START===")
    print(json.dumps(result, indent=2))
    print("===RENDERER_RESULT_END===")
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
