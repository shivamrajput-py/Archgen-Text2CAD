# FreeCAD Execution Tool - Runs and validates CAD scripts with proper process management
import os
import json
import subprocess
import tempfile
import re
import logging
import time
from typing import Dict, List, Optional, Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)


class FreeCADExecutionTool:
    """Execute FreeCAD scripts with proper process lifecycle management.
    
    Key improvements over the original:
    - Uses subprocess.Popen for process control (not .run)
    - Kills the entire process tree on timeout via psutil
    - Cleans up temp files in finally blocks (no leaks)
    - Separates stdout/stderr analysis (fewer false positives)
    - Uses precise error patterns instead of broad string matching
    """
    
    # FreeCAD installation paths to search (Windows)
    FREECAD_PATHS = [
        r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD 0.19\bin\FreeCADCmd.exe",
        r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
    ]
    
    # Precise error patterns that indicate REAL Python/FreeCAD errors (not normal output)
    # Each pattern is a regex that must match a line start or traceback structure
    FATAL_ERROR_PATTERNS = [
        r"^Traceback \(most recent call last\):",     # Real Python traceback
        r"^\w*Error: .+",                             # NameError: x, TypeError: y, etc.
        r"^\w*Exception: .+",                         # Specific exception messages  
        r"===EXECUTION_ERROR:",                        # Our sentinel marker
    ]
    
    # Compiled for performance
    _fatal_patterns_compiled = None
    
    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        if self._fatal_patterns_compiled is None:
            FreeCADExecutionTool._fatal_patterns_compiled = [
                re.compile(p, re.MULTILINE) for p in self.FATAL_ERROR_PATTERNS
            ]
    
    def find_freecad(self) -> Optional[str]:
        """Locate FreeCADCmd.exe on the system."""
        for path in self.FREECAD_PATHS:
            if os.path.exists(path):
                return path
        return None
    
    def _kill_process_tree(self, pid: int):
        """Kill a process and ALL its children (prevents orphan FreeCAD processes)."""
        if HAS_PSUTIL:
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
                # Wait for processes to actually terminate
                gone, alive = psutil.wait_procs(children + [parent], timeout=5)
                if alive:
                    logger.warning(f"Some processes survived kill: {[p.pid for p in alive]}")
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                logger.warning(f"Error killing process tree: {e}")
        else:
            # Fallback without psutil: use taskkill on Windows
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    capture_output=True, timeout=10
                )
            except Exception as e:
                logger.warning(f"Fallback process kill failed: {e}")
    
    def _clean_script(self, script: str) -> str:
        """Remove markdown code blocks and normalize the script."""
        cleaned = script
        if "```python" in cleaned:
            cleaned = re.sub(r'```python\n?', '', cleaned)
        if "```" in cleaned:
            cleaned = re.sub(r'```\n?', '', cleaned)
        return cleaned.strip()
    
    def _has_save_call(self, script: str) -> bool:
        """Check if the script contains an actual saveAs/saveCopy method call (not in comments)."""
        for line in script.splitlines():
            stripped = line.strip()
            # Skip comments
            if stripped.startswith('#'):
                continue
            # Check for actual method calls
            if re.search(r'\.(saveAs|saveCopy)\s*\(', stripped):
                return True
        return False
    
    def _build_execution_script(self, script: str, output_dir: str) -> str:
        """Build the final script with mandatory imports and save commands."""
        fcstd_path = os.path.join(output_dir, "output_model.FCStd")
        
        # Mandatory imports block
        mandatory_imports = """# === Auto-injected mandatory imports ===
import FreeCAD
import FreeCAD as App
import Part
try:
    import Draft
except ImportError:
    pass

"""
        
        full_script = mandatory_imports + script
        
        # Only inject save command if script doesn't already save
        if not self._has_save_call(script):
            save_command = f'''

# ===== Auto-injected geometry health check =====
try:
    _obj_count = 0
    _total_faces = 0
    _total_edges = 0
    _invalid_shapes = []
    for _obj in App.ActiveDocument.Objects:
        if hasattr(_obj, 'Shape') and _obj.Shape and not _obj.Shape.isNull():
            _obj_count += 1
            _total_faces += len(_obj.Shape.Faces)
            _total_edges += len(_obj.Shape.Edges)
            if not _obj.Shape.isValid():
                _invalid_shapes.append(_obj.Label)
    print(f"===GEOMETRY_HEALTH: objects={{_obj_count}} faces={{_total_faces}} edges={{_total_edges}} invalid={{len(_invalid_shapes)}}===")
    if _invalid_shapes:
        print(f"===TOPOLOGY_WARNING: {{','.join(_invalid_shapes)}}===")
except Exception as _he:
    print(f"===GEOMETRY_HEALTH: error={{_he}}===")

# ===== Auto-added execution validation =====
import sys
try:
    if App.ActiveDocument:
        App.ActiveDocument.recompute()
        App.ActiveDocument.saveAs(r"{fcstd_path}")
        print("===EXECUTION_SUCCESS===")
    else:
        print("===EXECUTION_ERROR: No ActiveDocument created===")
        sys.exit(1)
except Exception as e:
    print(f"===EXECUTION_ERROR: {{str(e)}}===")
    sys.exit(1)
'''
            full_script += save_command
        
        return full_script, fcstd_path
    
    def _analyze_output(self, stdout: str, stderr: str) -> dict:
        """
        Analyze execution output with separated stdout/stderr and precise patterns.
        
        Returns:
            dict with keys: has_error, error_msg, error_type, fix_suggestion, execution_succeeded
        """
        result = {
            "has_error": False,
            "error_msg": "",
            "error_type": "RuntimeError",
            "fix_suggestion": None,
            "execution_succeeded": "===EXECUTION_SUCCESS===" in (stdout or ""),
            "geometry_health": None,
        }
        
        # ── Parse geometry health check metrics ──
        if stdout and "===GEOMETRY_HEALTH:" in stdout:
            try:
                health_line = [l for l in stdout.splitlines() if "===GEOMETRY_HEALTH:" in l][0]
                health_data = health_line.split("===GEOMETRY_HEALTH:")[1].split("===")[0].strip()
                health_metrics = {}
                for pair in health_data.split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        try:
                            health_metrics[k] = int(v)
                        except ValueError:
                            health_metrics[k] = v
                result["geometry_health"] = health_metrics
                
                # Check for topology warnings
                topology_warnings = [l for l in stdout.splitlines() if "===TOPOLOGY_WARNING:" in l]
                if topology_warnings:
                    warning_line = topology_warnings[0]
                    invalid_labels = warning_line.split("===TOPOLOGY_WARNING:")[1].split("===")[0].strip()
                    health_metrics["invalid_labels"] = invalid_labels
                
                logger.info(
                    f"Geometry health: objects={health_metrics.get('objects', '?')}, "
                    f"faces={health_metrics.get('faces', '?')}, "
                    f"invalid={health_metrics.get('invalid', '?')}"
                )
            except Exception as e:
                logger.warning(f"Failed to parse geometry health: {e}")
        
        # Check our execution sentinel first
        if "===EXECUTION_ERROR:" in (stdout or ""):
            result["has_error"] = True
            start = stdout.find("===EXECUTION_ERROR:") + 19
            end = stdout.find("===", start)
            result["error_msg"] = stdout[start:end].strip() if end > start else stdout[start:start+200]
            return result
        
        # Analyze STDOUT for real Python errors (this is where tracebacks appear)
        if stdout:
            for pattern in self._fatal_patterns_compiled:
                match = pattern.search(stdout)
                if match:
                    result["has_error"] = True
                    
                    # Extract the traceback or error context
                    if "Traceback" in stdout:
                        tb_start = stdout.find("Traceback")
                        result["error_msg"] = stdout[tb_start:tb_start+500]
                    else:
                        pos = match.start()
                        result["error_msg"] = stdout[max(0, pos-30):pos+200].strip()
                    break
        
        # Classify specific error types for better fix suggestions
        if result["has_error"]:
            error_msg = result["error_msg"]
            
            if "ShapeColor" in error_msg or "ViewObject" in error_msg:
                result["error_type"] = "HeadlessModeError"
                result["fix_suggestion"] = (
                    "Remove ALL obj.ViewObject and .ShapeColor references — "
                    "they don't work in headless FreeCADCmd mode."
                )
            elif "Gui" in error_msg or "FreeCADGui" in error_msg:
                result["error_type"] = "GUIError"
                result["fix_suggestion"] = (
                    "Remove ALL FreeCADGui, Gui.* and Gui.ActiveView references — "
                    "FreeCADCmd has no GUI."
                )
            elif "NameError" in error_msg:
                result["error_type"] = "NameError"
                result["fix_suggestion"] = (
                    "A variable or function is used before it's defined. "
                    "Check the error message for the undefined name."
                )
            elif "SyntaxError" in error_msg or "IndentationError" in error_msg:
                result["error_type"] = "SyntaxError"
                result["fix_suggestion"] = (
                    "The script has a syntax or indentation error. "
                    "Check the line number in the error message."
                )
        
        # STDERR: Parse FreeCAD's C++ exception format: [Exception message]
        # These appear as: "Exception while processing file: /path/script.py [the error]"
        # They are REAL errors that caused the script to abort silently.
        if stderr and stderr.strip() and not result["execution_succeeded"]:
            stderr_error = self._parse_freecad_stderr(stderr)
            if stderr_error:
                # Only use stderr error if we didn't already find a Python traceback
                if not result["has_error"]:
                    result["has_error"] = True
                    result["error_msg"] = stderr_error["msg"]
                    result["error_type"] = stderr_error["type"]
                    result["fix_suggestion"] = stderr_error["fix"]
                logger.info(f"FreeCAD stderr (parsed exception): {stderr_error['msg']}")
            else:
                logger.info(f"FreeCAD stderr (non-fatal): {stderr[:200]}")
        
        return result
    
    def _parse_freecad_stderr(self, stderr: str) -> Optional[dict]:
        """Parse FreeCAD C++ exceptions from stderr into actionable error dicts."""
        import re
        # Pattern: "Exception while processing file: ... [error message]"
        exc_match = re.search(r'Exception while processing file:.*?\[(.+?)\]', stderr, re.DOTALL)
        if not exc_match:
            return None
        
        raw_error = exc_match.group(1).strip()
        
        # Map known FreeCAD C++ errors to actionable Python fixes
        error_fixes = {
            "type must be 'Shape', not Part.Feature": {
                "type": "ShapeTypeError",
                "fix": "You passed a Part.Feature object where a Shape is needed. Use `obj.Shape` instead of the object directly. Example: `Part.makeSolid(feature.Shape)` not `Part.makeSolid(feature)`."
            },
            "Profile shape is not a single vertex, edge, wire nor face": {
                "type": "SweepProfileError",
                "fix": "The profile for sweep/loft must be a single wire or face. Use `profile.Shape.Wires[0]` or wrap geometry in a wire: `Part.Wire([edge1, edge2])`. Avoid passing compound shapes."
            },
            "Invalid cell address or property": {
                "type": "SpreadsheetError",
                "fix": "Spreadsheet cell reference is invalid. Do not use FreeCAD Spreadsheet objects in headless mode. Use plain Python variables for parameters instead."
            },
            "syntax error": {
                "type": "FreeCADSyntaxError",
                "fix": "FreeCAD reported a syntax error when loading the script. Check for Python syntax issues, especially f-strings, indentation, or unclosed brackets/parentheses."
            },
            "This object is immutable": {
                "type": "ImmutableObjectError",
                "fix": "You are trying to modify an immutable FreeCAD object (likely a shape primitive). Assign it to a document object first using `doc.addObject()`, then modify properties."
            },
            "Shape is null": {
                "type": "NullShapeError",
                "fix": "A shape operation returned a null/empty shape. Check that all geometry operations (makeSolid, fuse, cut, etc.) are valid. Add a check: `if shape.isNull(): raise ValueError('shape is null')`."
            },
        }
        
        for key, fix_info in error_fixes.items():
            if key.lower() in raw_error.lower():
                return {
                    "msg": f"FreeCAD C++ Error: {raw_error}",
                    "type": fix_info["type"],
                    "fix": fix_info["fix"]
                }
        
        # Generic unknown C++ error
        return {
            "msg": f"FreeCAD internal error: {raw_error}",
            "type": "FreeCADInternalError",
            "fix": "The FreeCAD geometry kernel raised an internal exception. Simplify the geometry operation that failed. Try using basic Part primitives (makeBox, makeCylinder, makeCone) and boolean operations instead of advanced sweep/loft operations."
        }
    
    def _find_fcstd(self, expected_path: str, output_dir: str) -> Optional[str]:
        """Find the generated .FCStd file."""
        # Check expected path first
        if os.path.exists(expected_path):
            return expected_path
        
        # Fallback: scan output directory for any .FCStd
        if output_dir and os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith('.FCStd'):
                    return os.path.join(output_dir, f)
        
        return None
    
    def execute_with_metrics(self, script: str, output_dir: str = None, 
                             timeout_override: int = None) -> Dict[str, Any]:
        """
        Execute a FreeCAD script with full process lifecycle management.
        
        Args:
            script: The FreeCAD Python script to execute
            output_dir: Directory for output files (auto-created if None)
            timeout_override: Override the default timeout (from ScriptSanitizer)
        
        Returns:
            dict with: success, errors, metrics, fcstd_path, execution_status,
                       raw_stdout, raw_stderr
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="freecad_output_")
        
        timeout = timeout_override or self.timeout
        
        # Find FreeCAD
        freecad_cmd = self.find_freecad()
        if freecad_cmd is None:
            return {
                "success": False,
                "errors": [{"message": "FreeCADCmd.exe not found in any known location", "line": None, "type": "EnvironmentError"}],
                "metrics": None,
                "fcstd_path": None,
                "execution_status": "skipped",
            }
        
        # Clean and build execution script
        cleaned = self._clean_script(script)
        full_script, expected_fcstd = self._build_execution_script(cleaned, output_dir)
        
        # Write to temp file
        script_path = None
        process = None
        
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
            ) as f:
                f.write(full_script)
                script_path = f.name
            
            # Execute with Popen for process control
            cmd = [freecad_cmd, script_path]
            logger.info(f"Executing FreeCAD: timeout={timeout}s, script_lines={len(full_script.splitlines())}")
            
            start_time = time.time()
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                elapsed = time.time() - start_time
                logger.info(f"FreeCAD execution completed in {elapsed:.1f}s (return code: {process.returncode})")
            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                logger.warning(f"FreeCAD execution timed out after {elapsed:.1f}s — killing process tree")
                
                # CRITICAL: Kill the entire process tree
                self._kill_process_tree(process.pid)
                process.wait(timeout=5)
                
                # Check if a partial .FCStd was created before timeout
                partial_fcstd = self._find_fcstd(expected_fcstd, output_dir)
                
                if partial_fcstd:
                    # Partial success: FreeCAD created a file but timed out during recompute/save
                    return {
                        "success": False,
                        "errors": [{
                            "message": f"Execution timed out after {timeout}s but a partial model was saved",
                            "line": None,
                            "type": "TimeoutPartial"
                        }],
                        "metrics": None,
                        "fcstd_path": partial_fcstd,
                        "execution_status": "partial",
                        "raw_stdout": "",
                        "raw_stderr": "",
                    }
                else:
                    return {
                        "success": False,
                        "errors": [{
                            "message": f"Execution timed out after {timeout}s with no output",
                            "line": None,
                            "type": "TimeoutFailed"
                        }],
                        "metrics": None,
                        "fcstd_path": None,
                        "execution_status": "failed",
                        "raw_stdout": "",
                        "raw_stderr": "",
                    }
            
            # Analyze output
            analysis = self._analyze_output(stdout, stderr)
            found_fcstd = self._find_fcstd(expected_fcstd, output_dir)
            
            success = (
                process.returncode == 0 
                and not analysis["has_error"] 
                and (analysis["execution_succeeded"] or found_fcstd is not None)
            )
            
            # Build error list
            errors = []
            if analysis["has_error"]:
                error_entry = {
                    "message": analysis["error_msg"],
                    "line": None,
                    "type": analysis["error_type"],
                }
                if analysis["fix_suggestion"]:
                    error_entry["fix"] = analysis["fix_suggestion"]
                errors.append(error_entry)
            
            # Check stderr for C++ exceptions if Python execution silently failed
            if not success and not errors and stderr and "<Exception>" in stderr:
                errors.append({
                    "message": f"FreeCAD internal exception: {stderr.strip()}",
                    "line": None,
                    "type": "FreeCADInternalError",
                    "fix": "The geometry operation failed internally. Try simplifying the shape or checking dimensions."
                })
                
            # If still no errors but execution failed, add a generic error
            if not success and not errors:
                errors.append({
                    "message": "Script execution aborted silently without a Python traceback. The script may have crashed FreeCAD or exited early.",
                    "line": None,
                    "type": "SilentCrash"
                })
            
            execution_status = "success" if success else "failed"
            
            return {
                "success": success,
                "errors": errors,
                "metrics": analysis.get("geometry_health"),
                "fcstd_path": found_fcstd,
                "execution_status": execution_status,
                "raw_stdout": stdout,
                "raw_stderr": stderr,
            }
            
        except Exception as e:
            logger.error(f"Execution infrastructure error: {e}", exc_info=True)
            return {
                "success": False,
                "errors": [{"message": f"Execution infrastructure error: {str(e)}", "line": None, "type": "InternalError"}],
                "metrics": None,
                "fcstd_path": None,
                "execution_status": "failed",
            }
        finally:
            # ALWAYS clean up temp files — even on timeout or exception
            if script_path and os.path.exists(script_path):
                try:
                    os.unlink(script_path)
                except Exception:
                    pass
