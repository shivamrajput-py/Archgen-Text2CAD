import os
import tempfile
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TechDrawGenerator:
    """Agent that creates 2D orthographic drawings (TechDraw) from an FCStd file."""

    def __init__(self, freecad_cmd_path: str = None, timeout: int = 45):
        self.name = "TechDrawGenerator"
        self.timeout = timeout
        
        if freecad_cmd_path:
            self.freecad_cmd = freecad_cmd_path
        else:
            self.freecad_cmd = self._find_freecadcmd()

    def _find_freecadcmd(self) -> Optional[str]:
        """Find the FreeCAD command line executable path."""
        # Check environment variable first
        env_path = os.environ.get("FREECAD_BINC_PATH")
        if env_path and os.path.exists(env_path):
            return env_path
            
        common_paths = [
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None

    def execute(self, fcstd_path: str, output_dir: str) -> Dict[str, Any]:
        """Generate TechDraw SVG from the given FCStd document."""
        if not self.freecad_cmd:
            logger.warning("TechDrawGenerator: FreeCADCmd.exe not found.")
            return {"success": False, "error": "FreeCADCmd.exe not found."}

        if not fcstd_path or not os.path.exists(fcstd_path):
            logger.warning(f"TechDrawGenerator: FCStd file not found at '{fcstd_path}'")
            return {"success": False, "error": "FCStd file not available."}

        # Determine SVG output path
        base_name = os.path.splitext(os.path.basename(fcstd_path))[0]
        svg_filename = f"{base_name}_techdraw.svg"
        svg_path = os.path.join(output_dir, svg_filename)
        
        # Prepare script
        script_content = self._generate_techdraw_script(fcstd_path, svg_path)
        
        # DEFECT 2 FIX: initialise before try so finally can safely reference it
        script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='_techdraw.py', delete=False, encoding='utf-8') as f:
                f.write(script_content)
                script_path = f.name
                
            logger.info(f"TechDrawGenerator: Running 2D Draft Generation on {os.path.basename(fcstd_path)}...")
            
            result = subprocess.run(
                [self.freecad_cmd, script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if "TECHDRAW_SUCCESS" in stdout:
                result_success = True
                result_error = None
            else:
                result_success = False
                result_error = "FreeCAD Script failed to signal TECHDRAW_SUCCESS. Check logs."
                if "error" in stdout.lower() or "error" in stderr.lower():
                    result_error = stderr if stderr else stdout

            return {
                "success": result_success,
                "error": result_error,
                "svg_path": svg_path if result_success and os.path.exists(svg_path) else None,
                "logs": stdout + "\n" + stderr
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"TechDrawGenerator: Timed out after {self.timeout}s.")
            return {"success": False, "error": "Timeout generating TechDraw."}
        except Exception as e:
            logger.error(f"TechDrawGenerator: Exception: {e}")
            return {"success": False, "error": str(e)}
        finally:
            # DEFECT 2 FIX: guard against script_path being unset
            if script_path:
                try:
                    os.unlink(script_path)
                except OSError:
                    pass


    def _generate_techdraw_script(self, fcstd_path: str, svg_path: str) -> str:
        # DEFECT 1 FIX: escape single backslashes to double (Windows paths)
        safe_in_path = fcstd_path.replace('\\', '\\\\')
        safe_out_path = svg_path.replace('\\', '\\\\')
        
        return f'''# Auto-generated TechDraw Export Script
import sys
import FreeCAD as App
import TechDraw

def main():
    try:
        # Open Document
        doc = App.openDocument(r"{safe_in_path}")
        App.setActiveDocument(doc.Name)
        
        # Find parts matching solids or App::Part
        target_objs = []
        for obj in doc.Objects:
            if obj.isDerivedFrom("App::Part") or obj.isDerivedFrom("Part::Feature"):
                if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
                    target_objs.append(obj)
        
        if not target_objs:
            print("TECHDRAW_ERROR: No solid geometries found.")
            sys.exit(0)
            
        # Create a drawing page
        page = doc.addObject("TechDraw::DrawPage", "TechDraw_Page")
        
        # We can use a standard template or an empty one. Empty is fine for MVP.
        template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
        # Need to provide a valid template path if we want title blocks, but let's just make views
        # If template is empty, it acts as a blank canvas
        page.Template = template
        
        doc.recompute()
        
        # Create Iso View
        iso_view = doc.addObject("TechDraw::DrawViewPart", "Iso_View")
        iso_view.Source = target_objs
        iso_view.Direction = (1.0, 1.0, 1.0)
        iso_view.X = 150
        iso_view.Y = 150
        iso_view.Scale = 0.5  # Auto-scaling is complex in headless, default 0.5
        page.addView(iso_view)
        
        # Create Top View
        top_view = doc.addObject("TechDraw::DrawViewPart", "Top_View")
        top_view.Source = target_objs
        top_view.Direction = (0.0, 0.0, 1.0)
        top_view.X = 50
        top_view.Y = 150
        top_view.Scale = 0.5
        page.addView(top_view)

        doc.recompute()
        
        # Save as SVG — DEFECT 12 FIX: try importSVG first, fall back to TechDrawGui
        exported = False
        try:
            import importSVG
            importSVG.export([page], r"{safe_out_path}")
            exported = True
        except Exception:
            pass
        if not exported:
            try:
                import TechDrawGui
                TechDrawGui.exportPageAsSvg(page, r"{safe_out_path}")
                exported = True
            except Exception:
                pass
        if not exported:
            print("TECHDRAW_ERROR: Could not export SVG — neither importSVG nor TechDrawGui available")
            return
        print("TECHDRAW_SUCCESS")
        
    except Exception as e:
        print(f"TECHDRAW_ERROR: {{e}}")
        
if __name__ == "__main__":
    main()
'''
