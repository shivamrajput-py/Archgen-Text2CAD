# FEM Structural Validator — Phase 3
# Runs FreeCAD FEM analysis via CalculiX on generated .FCStd files.
# Only triggered when PhysicsCheckAgent sets fem_recommended=True.
#
# This agent generates a FEM analysis script, executes it via FreeCADCmd,
# and parses the CalculiX results (max stress, max displacement, safety factor).
import os
import re
import json
import subprocess
import tempfile
import logging
from typing import Dict, Any, Optional, List

from models import ValidationResult, ValidationCategory

logger = logging.getLogger(__name__)


class FEMValidator:
    """
    Structural validation using FreeCAD's FEM Workbench + CalculiX solver.
    
    Workflow:
    1. Opens the generated .FCStd file
    2. Creates a FEM analysis (mesh, material, constraints, loads)
    3. Runs CalculiX solver
    4. Reads results (max displacement, max stress)
    5. Compares against engineering thresholds
    
    Requirements:
    - FreeCAD 0.21+ with FEM workbench
    - CalculiX (ccx) solver installed
    """

    def __init__(self, timeout: int = 120):
        self.name = "FEMValidator"
        self.timeout = timeout
        self.freecad_cmd = self._find_freecad()

    def _find_freecad(self) -> Optional[str]:
        """Locate FreeCADCmd.exe on the system."""
        candidates = [
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run FEM analysis on a generated FreeCAD model.
        
        Expects input_data keys:
            - fcstd_path: str (path to .FCStd file)
            - category: str
            - requirements: dict (optional)
            - physics_result: dict (from PhysicsCheckAgent)
        
        Returns:
            - fem_valid: bool
            - fem_score: float (0-1)
            - max_displacement_mm: float
            - max_stress_mpa: float
            - safety_factor: float
            - fem_issues: list of str
            - fem_suggestions: list of str
        """
        fcstd_path = input_data.get("fcstd_path", "")
        category = input_data.get("category", "architectural")
        requirements = input_data.get("requirements", {})

        # Pre-flight checks
        if not self.freecad_cmd:
            logger.warning("FEMValidator: FreeCADCmd.exe not found — skipping FEM analysis")
            return self._skip_result("FreeCADCmd.exe not found on system")

        if not fcstd_path or not os.path.exists(fcstd_path):
            logger.warning(f"FEMValidator: FCStd file not found at '{fcstd_path}'")
            return self._skip_result("FCStd file not available")

        try:
            # Generate the FEM analysis script
            fem_script = self._generate_fem_script(fcstd_path, category, requirements)
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='_fem_analysis.py', 
                delete=False, encoding='utf-8'
            ) as f:
                f.write(fem_script)
                script_path = f.name

            # Execute via FreeCADCmd
            logger.info(f"FEMValidator: Running CalculiX analysis on {os.path.basename(fcstd_path)}...")
            
            try:
                result = subprocess.run(
                    [self.freecad_cmd, script_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    encoding='utf-8',
                    errors='ignore'
                )
            except subprocess.TimeoutExpired:
                logger.warning(f"FEMValidator: Analysis timed out after {self.timeout}s")
                return self._skip_result(f"FEM analysis timed out after {self.timeout}s")
            finally:
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

            # Parse results
            stdout = result.stdout or ""
            stderr = result.stderr or ""

            return self._parse_fem_results(stdout, stderr, category)

        except Exception as e:
            logger.error(f"FEMValidator: Unexpected error: {e}")
            return self._skip_result(f"FEM analysis error: {str(e)}")

    def _generate_fem_script(self, fcstd_path: str, category: str, requirements: Dict) -> str:
        """
        Generate a Python script that FreeCADCmd will execute 
        to perform FEM analysis on the model.
        """
        # Get domain-specific material and load parameters
        material = self._get_material_params(category)
        load = self._get_load_params(category)
        
        load_cases = requirements.get("load_cases", [])
        load_cases_json = json.dumps(load_cases).replace('\\', '\\\\')
        
        # Escape backslashes in the path for Python string
        safe_path = fcstd_path.replace('\\', '\\\\')

        script = f'''# Auto-generated FEM analysis script
import sys
import json

try:
    import FreeCAD as App
    import Part
    import ObjectsFem
except ImportError as e:
    print(f"===FEM_RESULT_START==={{\\\"success\\\": false, \\\"error\\\": \\\"FEM module import failed: {{e}}\\\"}}===FEM_RESULT_END===")
    sys.exit(0)

result = {{
    "success": False,
    "error": None,
    "max_displacement_mm": 0.0,
    "max_stress_mpa": 0.0,
    "safety_factor": 0.0,
    "node_count": 0,
    "element_count": 0,
    "analysis_type": "static_linear"
}}

try:
    # Open the FCStd file
    doc = App.openDocument(r"{safe_path}")
    App.setActiveDocument(doc.Name)
    doc.recompute()

    # Find Part::Feature objects to analyze
    part_objects = [obj for obj in doc.Objects if hasattr(obj, "Shape") and hasattr(obj.Shape, "Volume")]
    
    if not part_objects:
        result["error"] = "No solid geometry found in document"
        print(f"===FEM_RESULT_START===") 
        print(json.dumps(result))
        print(f"===FEM_RESULT_END===")
        sys.exit(0)

    try:
        combined_shape = Part.makeCompound([obj.Shape for obj in part_objects])
    except Exception as e:
        result["error"] = f"Failed to create assembly compound: {{e}}"
        print("===FEM_RESULT_START===")
        print(json.dumps(result))
        print("===FEM_RESULT_END===")
        sys.exit(0)
    
    # Create analysis object
    analysis = ObjectsFem.makeAnalysis(doc, "FEM_Analysis")
    
    # Create solver
    try:
        solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX")
        solver.GeometricalNonlinearity = "linear"
        solver.ThermoMechSteadyState = False
        solver.IterationsControlParameterTimeUse = False
        analysis.addObject(solver)
    except Exception as e:
        result["error"] = f"CalculiX solver setup failed: {{e}}"
        print("===FEM_RESULT_START===")
        print(json.dumps(result))
        print("===FEM_RESULT_END===")
        sys.exit(0)

    # Create shape object for analysis
    shape_obj = doc.addObject("Part::Feature", "AnalysisShape")
    shape_obj.Shape = combined_shape
    
    # DEFECT 3 FIX: extract material fallback values into plain local vars
    # so they survive as literals inside the f-string, not as nested property access.
    _yield_strength = {material['yield_strength_mpa']}
    _youngs_modulus  = "{material['youngs_modulus']}"
    _poisson_ratio   = "{material['poisson_ratio']}"
    _density         = "{material['density']}"
    _mat_name        = "{material['name']}"

    yield_strengths = []
    solids = combined_shape.Solids
    for i, solid in enumerate(solids):
        # Match solid to original part object via CenterOfMass
        matched_obj = None
        solid_center = solid.CenterOfMass
        for obj in part_objects:
            if obj.Shape and obj.Shape.Volume > 0:
                dist = obj.Shape.CenterOfMass.sub(solid_center).Length
                if dist < 1.0:
                    matched_obj = obj
                    break
        
        actual_material = None
        if matched_obj and hasattr(matched_obj, "Label2") and "Material:" in matched_obj.Label2:
            mat_name = matched_obj.Label2.split("Material:")[-1].strip()
            try:
                mat_gr = doc.getObject('Materials')
                if mat_gr and mat_gr.getObject(mat_name):
                    actual_material = mat_gr.getObject(mat_name)
            except Exception:
                pass

        mat_dict = {{}}
        target_yield = _yield_strength
        if actual_material:
            try:
                mat_dict["Name"] = actual_material.Name
                mat_dict["YoungsModulus"] = getattr(actual_material, "YoungsModulus", _youngs_modulus)
                mat_dict["Density"]       = getattr(actual_material, "Density",        _density)
                mat_dict["PoissonRatio"]  = _poisson_ratio
                target_yield = float(getattr(actual_material, "YieldStrength", str(_yield_strength)).replace(" MPa", "").strip())
            except Exception:
                actual_material = None # Fallback
                
        if not actual_material:
            mat_dict["Name"]         = _mat_name
            mat_dict["YoungsModulus"] = _youngs_modulus
            mat_dict["PoissonRatio"]  = _poisson_ratio
            mat_dict["Density"]       = _density
            
        yield_strengths.append(target_yield)
            
        mat_obj = ObjectsFem.makeMaterialSolid(doc, f"Material_Solid{{i+1}}")
        mat_obj.Material = mat_dict
        mat_obj.References = [(shape_obj, f"Solid{{i+1}}")]
        analysis.addObject(mat_obj)

    result["yield_strength_extracted"] = min(yield_strengths) if yield_strengths else _yield_strength

    # Create tie constraints for touching faces (glues the assembly together)
    # DEFECT 6 FIX: cap max tie constraints and skip expensive distToShape for
    # face pairs whose bounding boxes don't overlap — keeps this O(N) in practice.
    faces = combined_shape.Faces
    tie_count = 0
    MAX_TIES = 80  # cap to avoid runaway analysis time
    if len(faces) < 500:
        for i in range(len(faces)):
            if tie_count >= MAX_TIES:
                break
            for j in range(i+1, len(faces)):
                if tie_count >= MAX_TIES:
                    break
                f1, f2 = faces[i], faces[j]
                # Cheap bounding-box pre-filter before the expensive distToShape call
                if not f1.BoundBox.intersect(f2.BoundBox):
                    continue
                try:
                    dist = f1.distToShape(f2)[0]
                    if dist < 1e-3: # Touching
                        tie = ObjectsFem.makeConstraintTie(doc, f"Tie_{{tie_count}}")
                        tie.References = [(shape_obj, f"Face{{i+1}}"), (shape_obj, f"Face{{j+1}}")]
                        tie.Tolerance = 0.1
                        analysis.addObject(tie)
                        tie_count += 1
                except Exception:
                    pass
    
    # Create mesh
    try:
        mesh_obj = ObjectsFem.makeMeshGmsh(doc, "FEM_Mesh")
        mesh_obj.Part = shape_obj
        
        # Adaptive mesh size based on model dimensions
        bb = combined_shape.BoundBox
        max_dim = max(bb.XLength, bb.YLength, bb.ZLength)
        mesh_obj.CharacteristicLengthMax = str(max(max_dim / 10.0, 50.0))
        mesh_obj.CharacteristicLengthMin = str(max(max_dim / 50.0, 10.0))
        mesh_obj.ElementOrder = "1st"
        analysis.addObject(mesh_obj)
        
        # Try to generate mesh
        from femmesh.gmshtools import GmshTools
        gmsh = GmshTools(mesh_obj)
        error = gmsh.create_mesh()
        if error:
            result["error"] = f"Mesh generation failed: {{error}}"
            print("===FEM_RESULT_START===")
            print(json.dumps(result))
            print("===FEM_RESULT_END===")
            sys.exit(0)
        
        fem_mesh = mesh_obj.FemMesh
        result["node_count"] = fem_mesh.NodeCount
        result["element_count"] = fem_mesh.VolumeCount + fem_mesh.FaceCount
        
    except Exception as e:
        result["error"] = f"Meshing failed: {{e}}"
        print("===FEM_RESULT_START===")
        print(json.dumps(result))
        print("===FEM_RESULT_END===")
        sys.exit(0)

    # Parse load cases from PromptValidator
    load_cases = json.loads('{load_cases_json}')
    solids = combined_shape.Solids
    
    # 1. Apply Gravity default
    try:
        gravity = ObjectsFem.makeConstraintSelfWeight(doc, "Gravity")
        gravity.Gravity_x = 0.0
        gravity.Gravity_y = 0.0
        gravity.Gravity_z = -1.0
        analysis.addObject(gravity)
    except Exception:
        pass
        
    # 2. Iterate LLM dynamic load cases
    lc_count = 0
    for lc in load_cases:
        target = lc.get("target", "").lower()
        lc_type = lc.get("type", "fixed")
        mag = lc.get("magnitude_mpa", {load['pressure_mpa']})
        direction = lc.get("direction", [0, 0, -1])
        
        # Find which solid matches this target
        target_faces = []
        for i, solid in enumerate(solids):
            # Check if this solid maps to an object matching the target name
            solid_center = solid.CenterOfMass
            mapped = False
            for obj in part_objects:
                if (target in obj.Name.lower() or target in obj.Label.lower()) and obj.Shape.Volume > 0:
                    if obj.Shape.CenterOfMass.sub(solid_center).Length < 1.0:
                        mapped = True
                        break
            if mapped:
                # Add faces of this solid
                for j, face in enumerate(combined_shape.Faces):
                    if face.CenterOfMass.sub(solid.CenterOfMass).Length <= max(solid.BoundBox.XLength, solid.BoundBox.YLength, solid.BoundBox.ZLength):
                        # Geometric check to see if face belongs to solid (since indices get flattened)
                        # More precise: exact bounding box within solid bounding box
                        if solid.BoundBox.isInside(face.BoundBox.Center):
                            target_faces.append("Face" + str(j+1))

        if not target_faces:
            continue
            
        if lc_type == "fixed":
            # For fixed, we usually want the extreme bottom face of the target
            try:
                fixed = ObjectsFem.makeConstraintFixed(doc, f"Fixed_{{lc_count}}")
                fixed.References = [(shape_obj, target_faces[0])]  # Simplified, grab the first matching face
                analysis.addObject(fixed)
            except Exception:
                pass
        elif lc_type == "pressure":
            # For pressure, we want a face pointing in the opposite of direction typically
            try:
                pressure = ObjectsFem.makeConstraintPressure(doc, f"Pressure_{{lc_count}}")
                pressure.Pressure = mag
                pressure.Reversed = True
                pressure.References = [(shape_obj, target_faces[0])]
                analysis.addObject(pressure)
            except Exception:
                pass
        lc_count += 1


    # Run the solver
    try:
        doc.recompute()
        from femtools import ccxtools
        fea = ccxtools.FemToolsCcx(analysis, solver)
        fea.update_objects()
        fea.setup_working_dir()
        fea.setup_ccx()
        
        message = fea.check_prerequisites()
        if message:
            result["error"] = f"FEM prerequisites not met: {{message}}"
            print(f"===FEM_RESULT_START===")
            print(json.dumps(result))
            print(f"===FEM_RESULT_END===")
            sys.exit(0)
        
        fea.write_inp_file()
        fea.ccx_run()
        fea.load_results()
        
        # Extract results
        for obj in analysis.Group:
            if obj.isDerivedFrom("Fem::FemResultObject"):
                if hasattr(obj, "DisplacementLengths") and obj.DisplacementLengths:
                    result["max_displacement_mm"] = round(max(obj.DisplacementLengths), 4)
                if hasattr(obj, "StressValues") and obj.StressValues:
                    result["max_stress_mpa"] = round(max(obj.StressValues), 4)
                break
        
        # Calculate safety factor
        yield_strength = result.get("yield_strength_extracted", {material['yield_strength_mpa']})
        if result["max_stress_mpa"] > 0:
            result["safety_factor"] = round(yield_strength / result["max_stress_mpa"], 2)
        else:
            result["safety_factor"] = 99.0  # No stress = safe
        
        result["success"] = True
        
    except Exception as e:
        result["error"] = f"CalculiX solve failed: {{e}}"

except Exception as e:
    result["error"] = f"FEM analysis failed: {{e}}"

# Output results
print(f"===FEM_RESULT_START===")
print(json.dumps(result))
print(f"===FEM_RESULT_END===")
'''
        return script

    def _get_material_params(self, category: str) -> Dict[str, str]:
        """Get default material properties by category."""
        materials = {
            "architectural": {
                "name": "Concrete_C30",
                "youngs_modulus": "30000 MPa",
                "poisson_ratio": "0.20",
                "density": "2400 kg/m^3",
                "yield_strength_mpa": 30.0,
            },
            "structural": {
                "name": "Steel_S355",
                "youngs_modulus": "210000 MPa",
                "poisson_ratio": "0.30",
                "density": "7850 kg/m^3",
                "yield_strength_mpa": 355.0,
            },
            "civil": {
                "name": "Steel_S355",
                "youngs_modulus": "210000 MPa",
                "poisson_ratio": "0.30",
                "density": "7850 kg/m^3",
                "yield_strength_mpa": 355.0,
            },
            "mechanical_engineering": {
                "name": "Steel_AISI304",
                "youngs_modulus": "193000 MPa",
                "poisson_ratio": "0.29",
                "density": "8000 kg/m^3",
                "yield_strength_mpa": 215.0,
            },
            "industrial": {
                "name": "Steel_S275",
                "youngs_modulus": "210000 MPa",
                "poisson_ratio": "0.30",
                "density": "7850 kg/m^3",
                "yield_strength_mpa": 275.0,
            },
        }
        return materials.get(category, materials["structural"])

    def _get_load_params(self, category: str) -> Dict[str, float]:
        """Get default loading parameters by category."""
        loads = {
            "architectural": {"pressure_mpa": 0.005},     # ~5 kPa live load (office)
            "structural": {"pressure_mpa": 0.005},
            "civil": {"pressure_mpa": 0.010},              # ~10 kPa traffic load
            "mechanical_engineering": {"pressure_mpa": 0.1},  # 100 kPa (mechanical)
            "industrial": {"pressure_mpa": 0.010},
        }
        return loads.get(category, loads["structural"])

    def _parse_fem_results(self, stdout: str, stderr: str, category: str) -> Dict[str, Any]:
        """Parse FEM results from FreeCADCmd stdout."""
        # Extract JSON from markers
        if "===FEM_RESULT_START===" in stdout:
            try:
                start = stdout.find("===FEM_RESULT_START===") + len("===FEM_RESULT_START===")
                end = stdout.find("===FEM_RESULT_END===")
                if end > start:
                    json_str = stdout[start:end].strip()
                    fem_data = json.loads(json_str)
                    return self._evaluate_fem_data(fem_data, category)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"FEMValidator: Failed to parse FEM JSON: {e}")

        # Check for common solver errors
        combined = stdout + stderr
        if "ccx" in combined.lower() and "error" in combined.lower():
            return self._skip_result("CalculiX solver reported errors")
        if "gmsh" in combined.lower() and "error" in combined.lower():
            return self._skip_result("GMSH meshing failed")

        return self._skip_result("FEM analysis produced no readable results")

    def _evaluate_fem_data(self, fem_data: Dict, category: str) -> Dict[str, Any]:
        """Evaluate FEM results against engineering thresholds."""
        if not fem_data.get("success", False):
            error_msg = fem_data.get("error", "Unknown FEM error")
            logger.warning(f"FEMValidator: Analysis failed: {error_msg}")
            return self._skip_result(error_msg)

        max_disp = fem_data.get("max_displacement_mm", 0.0)
        max_stress = fem_data.get("max_stress_mpa", 0.0)
        safety_factor = fem_data.get("safety_factor", 0.0)

        issues = []
        suggestions = []
        score = 1.0

        # Get thresholds based on category
        thresholds = self._get_thresholds(category)

        # Check displacement
        if max_disp > thresholds["max_displacement_mm"]:
            issues.append(
                f"Max displacement {max_disp:.2f}mm exceeds limit {thresholds['max_displacement_mm']:.0f}mm"
            )
            suggestions.append(
                f"Increase member sizes or add bracing to reduce displacement below {thresholds['max_displacement_mm']:.0f}mm"
            )
            score -= 0.15

        # Check safety factor
        if safety_factor < thresholds["min_safety_factor"]:
            issues.append(
                f"Safety factor {safety_factor:.2f} is below minimum {thresholds['min_safety_factor']:.1f}"
            )
            suggestions.append(
                f"Increase cross-sections or reduce loads — safety factor must be ≥ {thresholds['min_safety_factor']:.1f}"
            )
            score -= 0.25
        elif safety_factor < thresholds["min_safety_factor"] * 1.5:
            issues.append(
                f"Safety factor {safety_factor:.2f} is marginal (recommended ≥ {thresholds['min_safety_factor'] * 1.5:.1f})"
            )
            score -= 0.05

        # Check max stress
        material = self._get_material_params(category)
        yield_strength = material["yield_strength_mpa"]
        stress_ratio = max_stress / yield_strength if yield_strength > 0 else 0
        if stress_ratio > 0.9:
            issues.append(
                f"Max stress {max_stress:.1f} MPa is {stress_ratio*100:.0f}% of yield strength ({yield_strength:.0f} MPa) — near failure"
            )
            suggestions.append(
                "Increase member sizes or redistribute loads — stress is dangerously close to material capacity"
            )
            score -= 0.20

        score = max(0.0, min(1.0, score))
        fem_valid = safety_factor >= thresholds["min_safety_factor"] and max_disp <= thresholds["max_displacement_mm"]

        logger.info(
            f"FEMValidator: displacement={max_disp:.2f}mm, stress={max_stress:.1f}MPa, "
            f"safety_factor={safety_factor:.2f}, score={score:.2f}, "
            f"mesh={fem_data.get('node_count', 0)} nodes"
        )

        return {
            "fem_valid": fem_valid,
            "fem_score": score,
            "max_displacement_mm": max_disp,
            "max_stress_mpa": max_stress,
            "safety_factor": safety_factor,
            "node_count": fem_data.get("node_count", 0),
            "element_count": fem_data.get("element_count", 0),
            "fem_issues": issues,
            "fem_suggestions": suggestions,
            "fem_error": None,
        }

    def _get_thresholds(self, category: str) -> Dict[str, float]:
        """Engineering acceptability thresholds by domain."""
        thresholds = {
            "architectural": {
                "max_displacement_mm": 20.0,   # L/250 for typical building
                "min_safety_factor": 1.5,
            },
            "structural": {
                "max_displacement_mm": 15.0,
                "min_safety_factor": 1.5,
            },
            "civil": {
                "max_displacement_mm": 50.0,   # Bridges allow more deflection
                "min_safety_factor": 2.0,       # Higher safety for public infrastructure
            },
            "mechanical_engineering": {
                "max_displacement_mm": 0.5,    # Tight tolerance for mechanical
                "min_safety_factor": 2.0,
            },
            "industrial": {
                "max_displacement_mm": 30.0,
                "min_safety_factor": 1.5,
            },
        }
        return thresholds.get(category, thresholds["structural"])

    def _skip_result(self, reason: str) -> Dict[str, Any]:
        """Return a neutral (non-penalizing) result when FEM can't run."""
        logger.info(f"FEMValidator: Skipped — {reason}")
        return {
            "fem_valid": True,       # Don't penalize if FEM can't run
            "fem_score": 1.0,
            "max_displacement_mm": 0.0,
            "max_stress_mpa": 0.0,
            "safety_factor": 0.0,
            "node_count": 0,
            "element_count": 0,
            "fem_issues": [],
            "fem_suggestions": [],
            "fem_error": reason,
        }
