# Visual Quality Assessor - Renders CAD model and assesses with VLM
import os
import sys
import json
import asyncio
import subprocess
import tempfile
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class VisualQualityAssessor:
    """
    Renders CAD model from multiple angles and uses VLM to assess visual quality.
    Returns detailed visual feedback for refinement.
    """
    
    def __init__(self, api_key: str = None, vlm_model: str = "google/gemini-2.0-pro-exp-02-05:free"):
        self.name = "VisualQualityAssessor"
        self.vlm_model = vlm_model
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.render_timeout = 120  # seconds
        
    def render_model(self, fcstd_path: str, output_dir: str) -> Dict[str, Any]:
        """
        Render model from multiple angles using PyVista (headless).
        Two-step process:
        1. Export FCStd to STL using FreeCADCmd
        2. Render STL using PyVista
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: Export FCStd to STL using FreeCADCmd
        stl_path = os.path.join(output_dir, "model.stl")
        
        # Find FreeCADCmd.exe
        freecad_paths = [
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
        ]
        
        freecad_cmd = None
        for path in freecad_paths:
            if os.path.exists(path):
                freecad_cmd = path
                break
        
        if freecad_cmd is None:
            return {"success": False, "images": [], "errors": ["FreeCADCmd.exe not found"]}
        
        # Create export script
        step_path = os.path.join(output_dir, "model.step")
        
        export_script = f'''
import FreeCAD
import Part
import Mesh

try:
    doc = FreeCAD.openDocument(r"{fcstd_path}")
    
    # Collect all shapes
    shapes = []
    for obj in doc.Objects:
        if hasattr(obj, 'Shape') and obj.Shape:
            shapes.append(obj.Shape)
    
    if shapes:
        # Create compound of all shapes
        if len(shapes) == 1:
            compound = shapes[0]
        else:
            compound = Part.makeCompound(shapes)
        
        # === HIGH-QUALITY STL EXPORT ===
        # Use MeshPart for fine tessellation with angular deflection control
        # LinearDeflection=0.05mm = fine enough mesh for small features
        # AngularDeflection=0.1 rad (~5.7°) = smooth curves (prevents diamond-bore artifacts)
        try:
            import MeshPart
            mesh = Mesh.Mesh()
            for shape in shapes:
                try:
                    mesh.addMesh(MeshPart.meshFromShape(
                        Shape=shape,
                        LinearDeflection=0.05,
                        AngularDeflection=0.1,
                        Relative=False
                    ))
                except:
                    try:
                        mesh.addMesh(MeshPart.meshFromShape(
                            Shape=shape,
                            LinearDeflection=0.2,
                            AngularDeflection=0.3,
                            Relative=False
                        ))
                    except:
                        mesh.addMesh(Mesh.Mesh(shape.tessellate(0.05)))
        except ImportError:
            # Fallback if MeshPart not available
            mesh = Mesh.Mesh()
            for shape in shapes:
                try:
                    mesh.addMesh(Mesh.Mesh(shape.tessellate(0.05)))
                except:
                    pass
        
        # Export to STL
        mesh.write(r"{stl_path}")
        print("STL_EXPORT_SUCCESS")
        
        # === STEP EXPORT (B-rep format) ===
        try:
            compound.exportStep(r"{step_path}")
            print("STEP_EXPORT_SUCCESS")
        except Exception as step_err:
            print(f"STEP_EXPORT_FAILED: {{step_err}}")
    else:
        print("STL_EXPORT_FAILED: No shapes found")
    
    FreeCAD.closeDocument(doc.Name)
except Exception as e:
    print(f"STL_EXPORT_FAILED: {{e}}")
'''
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(export_script)
                export_script_path = f.name
            
            result = subprocess.run(
                [freecad_cmd, export_script_path],
                capture_output=True, text=True,
                timeout=120, encoding='utf-8', errors='ignore'
            )
            
            try:
                os.unlink(export_script_path)
            except:
                pass
            
            if not os.path.exists(stl_path):
                logger.warning(f"STL export failed. stdout: {result.stdout}, stderr: {result.stderr}")
                return {"success": False, "images": [], "errors": ["STL export failed"]}
            
            logger.info(f"STL exported successfully: {stl_path}")
            
            if os.path.exists(step_path):
                logger.info(f"STEP exported successfully: {step_path}")
            else:
                logger.warning("STEP export was not generated")
            
        except subprocess.TimeoutExpired:
            return {"success": False, "images": [], "errors": ["STL export timed out"]}
        except Exception as e:
            return {"success": False, "images": [], "errors": [f"STL export error: {e}"]}
        
        # Step 2: Render STL using PyVista
        try:
            from pyvista_renderer import render_stl_views
            render_result = render_stl_views(stl_path, output_dir)
            
            if render_result["success"]:
                logger.info(f"PyVista rendered {len(render_result['images'])} images")
            else:
                logger.warning(f"PyVista rendering issues: {render_result['errors']}")
            
            return render_result
            
        except ImportError:
            renderer_path = os.path.join(os.path.dirname(__file__), "..", "pyvista_renderer.py")
            
            try:
                result = subprocess.run(
                    [sys.executable, renderer_path, stl_path, output_dir],
                    capture_output=True, text=True,
                    timeout=self.render_timeout, encoding='utf-8', errors='ignore'
                )
                
                stdout = result.stdout
                if "===RENDERER_RESULT_START===" in stdout:
                    json_start = stdout.find("===RENDERER_RESULT_START===") + len("===RENDERER_RESULT_START===")
                    json_end = stdout.find("===RENDERER_RESULT_END===")
                    if json_end > json_start:
                        try:
                            return json.loads(stdout[json_start:json_end].strip())
                        except json.JSONDecodeError:
                            pass
                
                return {"success": False, "images": [], "errors": [result.stderr or "PyVista render failed"]}
                
            except subprocess.TimeoutExpired:
                return {"success": False, "images": [], "errors": ["PyVista rendering timed out"]}
            except Exception as e:
                return {"success": False, "images": [], "errors": [f"PyVista error: {e}"]}
    
    def encode_image_base64(self, image_path: str) -> str:
        """Encode image to base64 for VLM API."""
        import base64
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return ""
    
    async def assess_visual_quality(
        self, 
        image_paths: List[str], 
        original_prompt: str,
        requirements: Dict = None
    ) -> Dict[str, Any]:
        """Send rendered images to VLM for structured visual quality assessment."""
        import httpx
        
        if not self.api_key:
            logger.warning("No OpenRouter API key for VLM, using fallback assessment")
            return self._fallback_assessment()
        
        # Priority: isometric gives best overall view, front/top for structural validation
        priority_order = ['isometric', 'front', 'top', 'left', 'right', 'back']
        
        def get_priority(path):
            for i, key in enumerate(priority_order):
                if key in path.lower():
                    return i
            return len(priority_order)
        
        sorted_paths = sorted(image_paths, key=get_priority)
        
        # Send up to 4 images (isometric + front + top + one side) for comprehensive assessment
        image_contents = []
        view_labels = []
        for img_path in sorted_paths[:4]:
            if os.path.exists(img_path):
                b64 = self.encode_image_base64(img_path)
                if b64:
                    # Extract view name from filename
                    view_name = os.path.basename(img_path).replace("render_", "").replace(".png", "").upper()
                    view_labels.append(view_name)
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"}
                    })
        
        if not image_contents:
            return self._fallback_assessment()
        
        views_description = ", ".join(view_labels)
        
        # Extract expected components from requirements for structured comparison
        expected_features = requirements.get("features", []) if requirements else []
        expected_dims = requirements.get("dimensions", {}) if requirements else {}
        
        vlm_prompt = f"""You are a professional CAD design quality assessor for FreeCAD 3D models.
You are viewing {len(image_contents)} rendered views ({views_description}) of a 3D model.

ORIGINAL DESIGN REQUEST:
"{original_prompt}"

EXPECTED FEATURES: {', '.join(expected_features) if expected_features else 'See prompt above'}
EXPECTED DIMENSIONS: {json.dumps(expected_dims) if expected_dims else 'See prompt above'}

SCORING SYSTEM — Rate each dimension 0.0 to 1.0:

1. PROMPT FIDELITY (Does the model match what was asked for?)
   - Does the overall shape match the requested design type (building/bridge/etc)?
   - Are the specified components visible (floors, windows, roof, etc)?
   - Does scale/proportion look reasonable for the design type?

2. STRUCTURAL INTEGRITY (Would this design work in the real world?)
   - Are walls/columns/supports properly placed and thick enough?
   - Is the structure physically stable (no floating elements)?
   - Are floor heights, room proportions realistic?

3. GEOMETRIC QUALITY (Is the 3D geometry well-formed?)
   - Are there visible gaps, intersections, or broken surfaces?
   - Are edges clean and shapes properly aligned?
   - Is the model complete (no missing faces/sides)?

4. COMPONENT COMPLETENESS (Are all requested parts present?)
   - List EACH component from the prompt and whether it's visible or missing
   - Check: foundation, walls, floors, windows, doors, roof, stairs, etc.

5. VISUAL COMPLEXITY & DETAIL (Is it detailed enough for the difficulty level?)
   - Does it look like a quick placeholder or a detailed design?
   - Are there architectural details (window frames, eaves, structural elements)?

Respond with ONLY valid JSON:
{{
    "visual_score": 0.75,
    "prompt_fidelity": 0.8,
    "structural_integrity": 0.7,
    "geometric_quality": 0.8,
    "component_completeness": 0.6,
    "visual_complexity": 0.7,
    "visual_description": "Brief description of what the model actually looks like",
    "completeness_issues": ["Missing windows on east facade", "No roof structure visible"],
    "geometry_issues": ["Gap between wall and floor slab on level 3"],
    "structural_concerns": ["Columns appear undersized for building height", "No visible foundation"],
    "visual_strengths": ["Good floor separation", "Correct number of stories"],
    "missing_components": ["balconies", "entrance door", "stairwell"],
    "present_components": ["walls", "floor slabs", "columns"],
    "refinement_suggestions": ["Add window openings using Part.cut", "Add roof slab on top floor"],
    "overall_assessment": "1-2 sentence summary"
}}

IMPORTANT: visual_score should be the weighted average:
  prompt_fidelity(30%) + structural_integrity(20%) + geometric_quality(15%) + component_completeness(25%) + visual_complexity(10%)"""
        
        user_content = [{"type": "text", "text": vlm_prompt}] + image_contents
        
        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.vlm_model,
                            "messages": [{"role": "user", "content": user_content}]
                        }
                    )
                    
                    if response.status_code == 429:
                        wait_time = 2 ** (attempt + 1)
                        logger.warning(f"VLM rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                        
                        content = content.strip()
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        
                        try:
                            assessment = json.loads(content)
                            
                            # Calculate weighted visual_score if sub-scores exist
                            if all(k in assessment for k in ["prompt_fidelity", "structural_integrity", "geometric_quality", "component_completeness", "visual_complexity"]):
                                calculated_score = (
                                    assessment["prompt_fidelity"] * 0.30 +
                                    assessment["structural_integrity"] * 0.20 +
                                    assessment["geometric_quality"] * 0.15 +
                                    assessment["component_completeness"] * 0.25 +
                                    assessment["visual_complexity"] * 0.10
                                )
                                assessment["visual_score"] = round(calculated_score, 3)
                                logger.info(f"VLM Visual Score (calculated): {assessment['visual_score']:.3f} [fidelity={assessment['prompt_fidelity']}, struct={assessment['structural_integrity']}, geo={assessment['geometric_quality']}, complete={assessment['component_completeness']}, detail={assessment['visual_complexity']}]")
                            else:
                                logger.info(f"VLM Visual Score (raw): {assessment.get('visual_score', 0.5)}")
                            
                            return {
                                "success": True,
                                "visual_score": assessment.get("visual_score", 0.5),
                                "prompt_fidelity": assessment.get("prompt_fidelity", 0.5),
                                "structural_integrity": assessment.get("structural_integrity", 0.5),
                                "geometric_quality": assessment.get("geometric_quality", 0.5),
                                "component_completeness": assessment.get("component_completeness", 0.5),
                                "visual_complexity": assessment.get("visual_complexity", 0.5),
                                "visual_description": assessment.get("visual_description", ""),
                                "completeness_issues": assessment.get("completeness_issues", []),
                                "geometry_issues": assessment.get("geometry_issues", []),
                                "structural_concerns": assessment.get("structural_concerns", []),
                                "visual_strengths": assessment.get("visual_strengths", []),
                                "missing_components": assessment.get("missing_components", []),
                                "present_components": assessment.get("present_components", []),
                                "refinement_suggestions": assessment.get("refinement_suggestions", []),
                                "overall_assessment": assessment.get("overall_assessment", "")
                            }
                        except json.JSONDecodeError:
                            logger.error("VLM response was not valid JSON")
                            return self._fallback_assessment()
                    else:
                        logger.error(f"VLM API error: {response.status_code} - {response.text}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** (attempt + 1))
                            continue
                        return self._fallback_assessment()
                        
            except Exception as e:
                logger.error(f"VLM assessment failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                return self._fallback_assessment()
        
        return self._fallback_assessment()
    
    def _fallback_assessment(self) -> Dict[str, Any]:
        """Fallback when VLM is unavailable."""
        return {
            "success": False,
            "visual_score": 0.5,
            "prompt_fidelity": 0.5,
            "structural_integrity": 0.5,
            "geometric_quality": 0.5,
            "component_completeness": 0.5,
            "visual_complexity": 0.5,
            "visual_description": "Visual assessment unavailable — could not assess model visually",
            "completeness_issues": ["VLM assessment unavailable"],
            "geometry_issues": [],
            "structural_concerns": [],
            "visual_strengths": [],
            "missing_components": [],
            "present_components": [],
            "refinement_suggestions": ["Unable to perform visual assessment"],
            "overall_assessment": "Fallback assessment — VLM unavailable"
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution: render and assess."""
        fcstd_path = input_data.get("fcstd_path")
        output_dir = input_data.get("output_dir")
        original_prompt = input_data.get("original_prompt", "")
        requirements = input_data.get("requirements", {})
        
        if not fcstd_path or not os.path.exists(fcstd_path):
            logger.warning(f"No FCStd file available for visual assessment: {fcstd_path}")
            return {
                "success": False,
                "visual_assessment": self._fallback_assessment(),
                "rendered_images": []
            }
        
        if not output_dir:
            output_dir = tempfile.mkdtemp(prefix="freecad_render_")
        
        render_dir = os.path.join(output_dir, "renders")
        os.makedirs(render_dir, exist_ok=True)
        
        logger.info(f"Rendering model from: {fcstd_path}")
        render_result = self.render_model(fcstd_path, render_dir)
        
        if not render_result.get("success") or not render_result.get("images"):
            logger.warning("Rendering failed or no images produced")
            return {
                "success": False,
                "visual_assessment": self._fallback_assessment(),
                "rendered_images": [],
                "render_errors": render_result.get("errors", [])
            }
        
        image_paths = [img["path"] for img in render_result.get("images", []) if os.path.exists(img.get("path", ""))]
        skipped_blank = render_result.get("skipped_blank", [])

        logger.info(f"Assessing {len(image_paths)} rendered images with VLM ({len(skipped_blank)} views skipped as blank)...")
        visual_assessment = await self.assess_visual_quality(image_paths, original_prompt, requirements)

        # Append blank-view diagnostic as geometry issues so downstream agents know
        if skipped_blank:
            extra_geo = [
                f"View '{v}' rendered blank — no visible geometry from this angle (inverted/missing faces)"
                for v in skipped_blank
            ]
            visual_assessment["geometry_issues"] = extra_geo + visual_assessment.get("geometry_issues", [])
            # Penalize geometric_quality (up to -0.20 for many blank views)
            blank_penalty = min(0.20, len(skipped_blank) * 0.05)
            visual_assessment["geometric_quality"] = max(0.10, visual_assessment.get("geometric_quality", 0.5) - blank_penalty)
            # Recalculate weighted visual_score
            visual_assessment["visual_score"] = round(
                visual_assessment.get("prompt_fidelity", 0.5) * 0.30 +
                visual_assessment.get("structural_integrity", 0.5) * 0.20 +
                visual_assessment.get("geometric_quality", 0.5) * 0.15 +
                visual_assessment.get("component_completeness", 0.5) * 0.25 +
                visual_assessment.get("visual_complexity", 0.5) * 0.10,
                3
            )

        return {
            "success": True,
            "visual_assessment": visual_assessment,
            "rendered_images": image_paths,
            "visual_score": visual_assessment.get("visual_score", 0.5),
            "skipped_views": skipped_blank
        }

