# Execution Validation Agent - Tests FreeCAD script execution
# Now with pre-execution sanitization (AST-based) and proper error handling
import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from models import ValidationResult, ValidationCategory
from execution import FreeCADExecutionTool
from script_sanitizer import ScriptSanitizer, SanitizeResult

logger = logging.getLogger(__name__)


class ExecutionValidationAgent:
    def __init__(self, llm: ChatOpenAI, timeout: int = 120, enable_execution: bool = False):
        self.name = "ExecutionValidator"
        self.llm = llm
        self.enable_execution = enable_execution
        self.executor_tool = FreeCADExecutionTool(timeout=timeout)
        self.sanitizer = ScriptSanitizer()

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        script = input_data.get("generated_script", "")
        output_dir = input_data.get("output_dir")

        # ============================================================
        # LAYER 1: Pre-Execution Sanitization (instant, no FreeCAD)
        # ============================================================
        sanitize_result = self.sanitizer.sanitize(script)
        
        if sanitize_result.gui_removals:
            logger.info(
                f"Sanitizer stripped {len(sanitize_result.gui_removals)} GUI references: "
                f"{', '.join(sanitize_result.gui_removals[:5])}"
            )
        
        # If syntax errors found, fail immediately (no need to waste FreeCAD execution)
        if not sanitize_result.success:
            logger.warning(
                f"Sanitizer found syntax errors: {sanitize_result.syntax_errors}"
            )
            val_result = ValidationResult(
                is_valid=False,
                score=0.0,
                errors=sanitize_result.syntax_errors,
                suggestions=[
                    "Fix the syntax errors before execution. "
                    "Check indentation, brackets, and string quotes."
                ],
                category=ValidationCategory.EXECUTION.value
            )
            return {
                "validation_result": val_result,
                "success": False,
                "score": 0.0,
                "execution_logs": "Pre-execution sanitization failed",
                "error": sanitize_result.syntax_errors[0] if sanitize_result.syntax_errors else "Syntax error",
                "feedback": sanitize_result.syntax_errors,
                "execution_status": "failed",
                "fcstd_path": None,
                "validation_results": {
                    "execution_success": False,
                    "sanitizer_errors": sanitize_result.syntax_errors,
                }
            }
        
        # Use the cleaned script (GUI calls stripped) for execution
        cleaned_script = sanitize_result.cleaned_script
        
        # Log sanitization warnings
        if sanitize_result.warnings:
            for w in sanitize_result.warnings:
                logger.info(f"Sanitizer warning: {w}")

        # ============================================================
        # LAYER 2: Actual FreeCAD Execution (if enabled)
        # ============================================================
        if self.enable_execution:
            logger.info(
                f"Executing FreeCAD script "
                f"(complexity={sanitize_result.complexity}, "
                f"timeout={sanitize_result.suggested_timeout}s, "
                f"lines={sanitize_result.estimated_line_count})"
            )
            
            # Use sanitizer's dynamic timeout
            execution_result = self.executor_tool.execute_with_metrics(
                cleaned_script, 
                output_dir,
                timeout_override=sanitize_result.suggested_timeout
            )
            
            return self._process_execution_result(execution_result, sanitize_result)

        # ============================================================
        # LAYER 2b: Simulated Execution (LLM analysis when FreeCAD unavailable)
        # ============================================================
        else:
            logger.info("Simulating execution with LLM Logic Analysis...")
            return await self._simulate_execution_with_llm(cleaned_script)

    def _process_execution_result(
        self, execution_result: Dict[str, Any], sanitize_result: SanitizeResult
    ) -> Dict[str, Any]:
        """Process the execution result and build the validation response."""
        errors = []
        score = 1.0
        execution_status = execution_result.get("execution_status", "failed")
        
        for err in execution_result.get("errors", []):
            if isinstance(err, dict):
                line_info = f" (line {err['line']})" if err.get('line') else ""
                error_type = err.get('type', 'Error')
                msg = f"{error_type}{line_info}: {err.get('message', 'Unknown error')}"
                if err.get('fix'):
                    msg += f" | Fix: {err['fix']}"
                errors.append(msg)
            else:
                errors.append(str(err))
        
        # Add sanitizer warnings as informational
        if sanitize_result.warnings:
            for w in sanitize_result.warnings:
                errors.append(f"[Sanitizer Warning] {w}")
        
        # Score based on execution status
        if execution_status == "success":
            score = 1.0
            logger.info("Execution successful!")
        elif execution_status == "partial":
            score = 0.4  # Partial: model created but execution didn't complete cleanly
            logger.warning("Execution partial: model file exists but execution had issues")
        elif execution_status == "skipped":
            score = 0.3  # FreeCAD not found — can't validate at all
            logger.warning("Execution skipped: FreeCAD not available")
        else:  # "failed"
            score = 0.0
            logger.error(f"Execution failed with {len(errors)} errors")
        
        is_valid = execution_status in ("success", "partial")
        
        val_result = ValidationResult(
            is_valid=is_valid,
            score=score,
            errors=errors,
            suggestions=["Fix the errors listed above"] if errors else [],
            category=ValidationCategory.EXECUTION.value
        )

        return {
            "validation_result": val_result,
            "success": execution_status == "success",
            "score": score,
            "execution_logs": str(execution_result.get("raw_stdout", "")),
            "error": errors[0] if errors else None,
            "feedback": errors,
            "metrics": execution_result.get("metrics"),
            "fcstd_path": execution_result.get("fcstd_path"),
            "execution_status": execution_status,
            "validation_results": {
                "execution_success": execution_status == "success",
                "execution_status": execution_status,
                "metrics": execution_result.get("metrics"),
                "complexity": sanitize_result.complexity,
                "gui_removals": len(sanitize_result.gui_removals),
            }
        }

    async def _simulate_execution_with_llm(self, script: str) -> Dict[str, Any]:
        """Use LLM to statically analyze the code for runtime errors."""
        system_prompt = """You are a Python Interpreter for FreeCAD. 
        Analyze the following code for:
        1. Syntax errors
        2. Unused imports or undefined variables
        3. Logical errors (e.g. creating objects but not adding them to document)
        4. Misuse of FreeCAD API
        
        STRICT RULES:
        - DO NOT suggest design improvements.
        - DO NOT complain about missing comments.
        - ONLY report blocking errors that would cause a crash or empty output.
        - If the code looks runnable, return success=true.
        
        Return JSON format:
        {
            "success": boolean,
            "error": "description of fatal error or null",
            "logs": "Simulated execution log [OK]..."
        }
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"CODE TO ANALYZE:\n```python\n{script}\n```")
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            result = json.loads(content)
            
            success = result.get("success", False)
            error_msg = result.get("error")
            
            val_result = ValidationResult(
                is_valid=success,
                score=1.0 if success else 0.0,
                errors=[error_msg] if error_msg else [],
                suggestions=["Fix logic errors identified by simulation"] if not success else [],
                category=ValidationCategory.EXECUTION.value
            )
            
            return {
                "validation_result": val_result,
                "success": success,
                "score": 1.0 if success else 0.0,
                "execution_logs": result.get("logs", "Simulated Check Complete"),
                "error": error_msg,
                "feedback": [error_msg] if error_msg else [],
                "execution_status": "success" if success else "failed",
                "fcstd_path": None,
                "validation_results": {
                    "execution_success": success,
                    "simulated": True
                }
            }
        except Exception as e:
            logger.warning(f"Simulated execution analysis failed: {e} — marking as uncertain")
            val_result = ValidationResult(
                is_valid=False,
                score=0.5,
                errors=[f"Simulated execution analysis failed: {str(e)} — script may have issues"],
                suggestions=["Re-run with real FreeCAD execution for definitive validation"],
                category=ValidationCategory.EXECUTION.value
            )
            
            return {
                "validation_result": val_result,
                "success": False, 
                "score": 0.5,
                "execution_logs": f"Simulated check failed: {str(e)}", 
                "error": str(e),
                "feedback": [f"Simulation analysis error: {str(e)}"],
                "execution_status": "failed",
                "fcstd_path": None,
                "validation_results": {"execution_success": False, "simulated": True, "error": str(e)}
            }
