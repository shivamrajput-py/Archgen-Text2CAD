#!/usr/bin/env python3
"""
FreeCAD Executor Script
========================
This script is run by FreeCADCmd.exe to:
1. Execute a generated CAD script
2. Capture any errors with line numbers
3. Extract geometric metrics (volume, bounding box, object count)
4. Save the .FCStd file for rendering

Usage: FreeCADCmd.exe freecad_executor.py <script_path> <output_dir>

Output: JSON to stdout with execution results
"""

import sys
import os
import json
import traceback

# FreeCAD imports (available when run via FreeCADCmd)
try:
    import FreeCAD as App
    import Part
    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False


def extract_metrics(doc):
    """Extract geometric metrics from a FreeCAD document."""
    metrics = {
        "total_objects": 0,
        "part_objects": 0,
        "total_volume": 0.0,
        "total_surface_area": 0.0,
        "bounding_box": None,
        "component_names": [],
        "object_details": []
    }
    
    if doc is None:
        return metrics
    
    # Combined bounding box
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
    
    for obj in doc.Objects:
        metrics["total_objects"] += 1
        metrics["component_names"].append(obj.Name)
        
        obj_detail = {
            "name": obj.Name,
            "type": obj.TypeId,
            "has_shape": False,
            "volume": 0,
            "area": 0
        }
        
        if hasattr(obj, 'Shape') and obj.Shape:
            try:
                shape = obj.Shape
                obj_detail["has_shape"] = True
                metrics["part_objects"] += 1
                
                # Volume
                if hasattr(shape, 'Volume'):
                    vol = shape.Volume
                    if vol > 0:
                        obj_detail["volume"] = vol
                        metrics["total_volume"] += vol
                
                # Surface area
                if hasattr(shape, 'Area'):
                    area = shape.Area
                    if area > 0:
                        obj_detail["area"] = area
                        metrics["total_surface_area"] += area
                
                # Bounding box
                if hasattr(shape, 'BoundBox'):
                    bb = shape.BoundBox
                    min_x = min(min_x, bb.XMin)
                    min_y = min(min_y, bb.YMin)
                    min_z = min(min_z, bb.ZMin)
                    max_x = max(max_x, bb.XMax)
                    max_y = max(max_y, bb.YMax)
                    max_z = max(max_z, bb.ZMax)
            except Exception as e:
                obj_detail["error"] = str(e)
        
        metrics["object_details"].append(obj_detail)
    
    # Set combined bounding box
    if min_x != float('inf'):
        metrics["bounding_box"] = {
            "min": {"x": min_x, "y": min_y, "z": min_z},
            "max": {"x": max_x, "y": max_y, "z": max_z},
            "dimensions": {
                "length": max_x - min_x,
                "width": max_y - min_y,
                "height": max_z - min_z
            }
        }
    
    return metrics


def setup_standard_materials(doc):
    """Inject standard engineering materials into the document if missing."""
    if not doc:
        return
        
    mat_group = doc.getObject('Materials')
    if not mat_group:
        mat_group = doc.addObject('App::DocumentObjectGroup', 'Materials')
        
    # Standard materials dictionary
    std_materials = {
        'Steel': {'Density': '7850 kg/m^3', 'YoungsModulus': '200 GPa', 'YieldStrength': '250 MPa'},
        'Concrete': {'Density': '2400 kg/m^3', 'YoungsModulus': '30 GPa', 'CompressiveStrength': '30 MPa'},
        'Timber': {'Density': '600 kg/m^3', 'YoungsModulus': '11 GPa', 'YieldStrength': '24 MPa'},
        'Aluminum': {'Density': '2700 kg/m^3', 'YoungsModulus': '69 GPa', 'YieldStrength': '276 MPa'}
    }
    
    for mat_name, props in std_materials.items():
        if not mat_group.getObject(mat_name):
            try:
                # Add basic material feature (App::MaterialObjectExt is ideal, but Feature is safe base)
                mat_obj = doc.addObject('App::FeaturePython', mat_name)
                mat_group.addObject(mat_obj)
                # Store properties as custom properties so FEM/LLM can read them
                for k, v in props.items():
                    mat_obj.addProperty("App::PropertyString", k, "Material", f"{mat_name} {k}")
                    setattr(mat_obj, k, v)
            except Exception:
                pass # Fail silently if material creation fails in headless


def execute_script(script_path, output_dir):
    """Execute a FreeCAD script and return results."""
    result = {
        "success": False,
        "errors": [],
        "warnings": [],
        "metrics": None,
        "fcstd_path": None,
        "script_line_count": 0
    }
    
    # Validate inputs
    if not os.path.exists(script_path):
        result["errors"].append({"message": f"Script not found: {script_path}", "line": None})
        return result
    
    # Read script
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        result["script_line_count"] = len(script_content.split('\n'))
    except Exception as e:
        result["errors"].append({"message": f"Cannot read script: {e}", "line": None})
        return result
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Execute the script
    try:
        # Create a namespace for execution
        exec_globals = {
            '__name__': '__main__',
            '__file__': script_path,
            'App': App,
            'FreeCAD': App,
            'Part': Part
        }
        
        # Execute
        exec(compile(script_content, script_path, 'exec'), exec_globals)
        
        # Find the active document
        doc = App.ActiveDocument
        if doc is None:
            # Try to find any open document
            docs = App.listDocuments()
            if docs:
                doc = list(docs.values())[0]
        
        if doc:
            # Recompute to ensure everything is up to date
            doc.recompute()
            
            # Setup standard materials so the script or future steps have access to them
            setup_standard_materials(doc)
            
            # Extract metrics
            result["metrics"] = extract_metrics(doc)
            
            # Save the file
            fcstd_path = os.path.join(output_dir, "output_model.FCStd")
            doc.saveAs(fcstd_path)
            result["fcstd_path"] = fcstd_path
            
            result["success"] = True
        else:
            result["warnings"].append("No document was created by the script")
            result["success"] = True  # Script ran but no document
            
    except SyntaxError as e:
        result["errors"].append({
            "message": f"Syntax Error: {e.msg}",
            "line": e.lineno,
            "offset": e.offset,
            "text": e.text.strip() if e.text else None,
            "type": "SyntaxError"
        })
    except Exception as e:
        # Extract line number from traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        error_line = None
        error_file = None
        
        for frame in reversed(tb):
            if frame.filename == script_path or '<' in frame.filename:
                error_line = frame.lineno
                error_file = frame.filename
                break
        
        result["errors"].append({
            "message": str(e),
            "line": error_line,
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        })
    
    return result


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print(json.dumps({
            "success": False,
            "errors": [{"message": "Usage: freecad_executor.py <script_path> <output_dir>"}]
        }))
        sys.exit(1)
    
    script_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    if not FREECAD_AVAILABLE:
        print(json.dumps({
            "success": False,
            "errors": [{"message": "FreeCAD not available. Run via FreeCADCmd.exe"}]
        }))
        sys.exit(1)
    
    result = execute_script(script_path, output_dir)
    
    # Output JSON result
    print("===EXECUTOR_RESULT_START===")
    print(json.dumps(result, indent=2, default=str))
    print("===EXECUTOR_RESULT_END===")
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
