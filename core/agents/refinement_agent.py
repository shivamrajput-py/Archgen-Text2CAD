# Refinement Agent - Analyzes failures and suggests improvements
import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from utils import ultra_robust_json_parse

logger = logging.getLogger(__name__)


class RefinementAgent:
    def __init__(self, llm: ChatOpenAI):
        self.name = "RefinementAgent"
        self.llm = llm
        self.refinement_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert FreeCAD script refinement specialist. Your job is to analyze why the current design scored low and produce a COMPREHENSIVE refined prompt that will generate a better script on the next iteration.

CRITICAL: Respond with EXACTLY this JSON structure (no markdown, no explanations):
{{"primary_issues": ["critical issue 1", "design flaw 2"], "enhanced_prompt_suggestions": "COMPLETE STANDALONE PROMPT for the next iteration...", "should_continue": true, "confidence_score": 0.8, "specific_fixes": ["Fix: Change X to Y", "Fix: Import module Z"], "visual_improvements": ["Add windows using Part.cut operations", "Increase wall thickness to 200mm"], "focus_areas": ["structural_realism", "component_completeness"]}}

KEY RULES:
1. 'enhanced_prompt_suggestions' IS the actual prompt for the next iteration. Make it STANDALONE and COMPREHENSIVE:
   - Start with the original design request
   - Add EXPLICIT FIX INSTRUCTIONS for every error found
   - For execution errors: give exact code patterns to use instead
   - For missing components: describe exactly what to add with dimensions
   - For visual issues: describe what the rendered view showed was wrong
   - For structural issues: specify realistic dimensions and placement
   
2. NEVER give vague suggestions like "improve the design" — be SPECIFIC:
   ❌ "Add windows" 
   ✅ "Add rectangular window openings (1200x1500mm) on each floor using Part.makeBox for the opening shape and Part.cut to subtract from walls. Place windows at 900mm from floor level, spacing 2000mm apart."

3. Use 'visual_improvements' for issues visible in the rendered 3D views
4. Use 'focus_areas' to tell the next iteration what to prioritize
5. Set 'should_continue' to false ONLY if the design is fundamentally wrong and a restart would be better
6. OVER-ENGINEERING CHECK: If the script creates objects, features, or geometry NOT requested in the ORIGINAL USER REQUEST, list them as primary_issues and instruct the next iteration to REMOVE them. Only the explicitly requested components should be built. Extra decorative features (unrequested chamfers, grooves, markers, helper geometry, countersinks, ribs) decrease quality scores."""),
            ("human", """Iteration {iteration_count}/{max_iterations} — Analyze and suggest improvements:

ORIGINAL USER REQUEST:
"{original_prompt}"

CURRENT ENHANCED PROMPT:
{enhanced_prompt}

CATEGORY SCORES:
{category_scores}

SCRIPT OVERVIEW ({script_lines} lines):
{script_snippet}

EXECUTION ERRORS (if any):
{execution_errors}

VALIDATION RESULTS:
{validation_summary}

VISUAL ASSESSMENT (from rendered 3D model views):
- Visual Score: {visual_score}
- Visual Description: {visual_description}
- Present Components: {present_components}
- Missing Components: {missing_components}
- Structural Concerns: {structural_concerns}
- Geometry Issues: {geometry_issues}
- Completeness Issues: {completeness_issues}
- Visual Suggestions: {visual_suggestions}

QUALITY ASSESSMENT:
- Overall Score: {quality_score}
- Weaknesses: {weaknesses}
- Missing Requirements: {missing_requirements}
- Component Checklist: {component_checklist}

ITERATION HISTORY (score trend):
{iteration_trend}

PREVIOUS ERRORS IN THIS SESSION:
{previous_errors}

PHYSICS ENGINEERING CHECK:
- Physics Score: {physics_score}
- Violations: {physics_violations}
- Fix Suggestions: {physics_fixes}

FEM STRUCTURAL ANALYSIS (if available):
- FEM Score: {fem_score}
- Max Displacement: {fem_displacement}
- Max Stress: {fem_stress}
- Safety Factor: {fem_safety_factor}
- FEM Issues: {fem_issues}""")
        ])

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        validation_results = input_data.get("validation_results", {})
        original_script = input_data.get("generated_script", "")
        original_prompt = input_data.get("original_prompt", "")
        enhanced_prompt = input_data.get("enhanced_prompt", "")
        iteration_count = input_data.get("iteration_count", 1)
        max_iterations = input_data.get("max_iterations", 5)

        try:
            # Build validation summary
            validation_summary = {}
            for category, result in validation_results.items():
                validation_summary[category] = {
                    "score": result.score,
                    "errors": result.errors[:5],
                    "valid": result.is_valid
                }
            
            # Extract visual assessment context
            visual_assessment = input_data.get("visual_assessment", {})
            visual_score = visual_assessment.get("visual_score", "N/A")
            visual_description = visual_assessment.get("visual_description", "No visual assessment available")
            missing_components = ", ".join(visual_assessment.get("missing_components", [])) or "None identified"
            present_components = ", ".join(visual_assessment.get("present_components", [])) or "Unknown"
            geometry_issues = ", ".join(visual_assessment.get("geometry_issues", [])) or "None identified"
            completeness_issues = ", ".join(visual_assessment.get("completeness_issues", [])) or "None identified"
            structural_concerns = ", ".join(visual_assessment.get("structural_concerns", [])) or "None identified"
            visual_suggestions = ", ".join(visual_assessment.get("refinement_suggestions", [])) or "None"

            # Quality assessment details
            quality_feedback = input_data.get("previous_quality_feedback", "{}")
            try:
                quality_data = json.loads(quality_feedback) if isinstance(quality_feedback, str) else quality_feedback
            except (json.JSONDecodeError, TypeError):
                quality_data = {}
            
            quality_score = quality_data.get("score", "N/A")
            weaknesses = ", ".join(quality_data.get("weaknesses", [])) or "None identified"
            missing_requirements = ", ".join(quality_data.get("missing", [])) or "None"
            category_scores = json.dumps(quality_data.get("category_scores", {}), indent=1) or "N/A"
            component_checklist = json.dumps(quality_data.get("component_checklist", {}), indent=1) or "N/A"

            # Build iteration trend
            iteration_trend = self._build_iteration_trend(input_data)
            
            # Execution errors
            execution_errors = "\n".join(input_data.get("previous_errors", [])) or "No execution errors"
            
            # Send FULL script — no truncation to avoid losing context
            script_lines_count = len(original_script.split('\n'))

            response = await self.llm.ainvoke(
                self.refinement_prompt.format_messages(
                    original_prompt=original_prompt,
                    enhanced_prompt=enhanced_prompt,
                    iteration_count=iteration_count,
                    max_iterations=max_iterations,
                    script_snippet=original_script,
                    script_lines=script_lines_count,
                    execution_errors=execution_errors,
                    validation_summary=json.dumps(validation_summary, indent=2),
                    visual_score=visual_score,
                    visual_description=visual_description,
                    present_components=present_components,
                    missing_components=missing_components,
                    structural_concerns=structural_concerns,
                    geometry_issues=geometry_issues,
                    completeness_issues=completeness_issues,
                    visual_suggestions=visual_suggestions,
                    quality_score=quality_score,
                    weaknesses=weaknesses,
                    missing_requirements=missing_requirements,
                    category_scores=category_scores,
                    component_checklist=component_checklist,
                    iteration_trend=iteration_trend,
                    previous_errors=execution_errors,
                    physics_score=self._safe_get(input_data, "physics_result", "physics_score", "N/A"),
                    physics_violations=self._format_physics_violations(input_data),
                    physics_fixes=self._format_physics_fixes(input_data),
                    fem_score=self._safe_get(input_data, "fem_result", "fem_score", "N/A"),
                    fem_displacement=self._safe_get(input_data, "fem_result", "max_displacement_mm", "N/A"),
                    fem_stress=self._safe_get(input_data, "fem_result", "max_stress_mpa", "N/A"),
                    fem_safety_factor=self._safe_get(input_data, "fem_result", "safety_factor", "N/A"),
                    fem_issues=", ".join(self._safe_list(input_data, "fem_result", "fem_issues")) or "None"
                )
            )

            fallback_data = {
                "primary_issues": ["Refinement analysis incomplete"],
                "enhanced_prompt_suggestions": f"{enhanced_prompt}\n\nITERATION {iteration_count} FIXES REQUIRED:\n- Fix all execution errors\n- Add all missing components\n- Improve structural realism",
                "should_continue": True,
                "confidence_score": 0.5,
                "specific_fixes": ["Review generated code manually"],
                "visual_improvements": [],
                "focus_areas": ["completeness", "correctness"]
            }

            result = ultra_robust_json_parse(response.content, fallback_data, "refinement_analysis")

            logger.info(f"Refinement: should_continue={result.get('should_continue', True)}, "
                        f"confidence={result.get('confidence_score', 0):.2f}, "
                        f"issues={len(result.get('primary_issues', []))}, "
                        f"fixes={len(result.get('specific_fixes', []))}")

            return {
                "improvement_analysis": result,
                "should_continue": result.get("should_continue", True),
                "enhanced_prompt_suggestion": result.get("enhanced_prompt_suggestions", enhanced_prompt),
                "primary_issues": result.get("primary_issues", ["Unknown issue"]),
                "specific_fixes": result.get("specific_fixes", []),
                "visual_improvements": result.get("visual_improvements", []),
                "focus_areas": result.get("focus_areas", [])
            }

        except Exception as e:
            logger.error(f"Refinement analysis failed: {e}")
            return {
                "should_continue": True,
                "enhanced_prompt_suggestion": f"{enhanced_prompt}\n\nFIX ERRORS AND IMPROVE: {str(e)}",
                "primary_issues": [f"Refinement error: {str(e)}"],
                "specific_fixes": ["Manual review required"],
                "visual_improvements": [],
                "focus_areas": []
            }
    
    def _build_iteration_trend(self, input_data: Dict) -> str:
        """Build a trend summary from iteration history."""
        trend_lines = []
        if "iteration_history" in input_data:
            for entry in input_data["iteration_history"]:
                iteration = entry.get("iteration", "?")
                score = entry.get("overall_score", 0)
                issues = entry.get("primary_issues", [])
                improvements = entry.get("improvements_made", [])
                trend_lines.append(
                    f"  Iter {iteration}: score={score:.2f} | issues: {', '.join(issues[:2])} | improved: {', '.join(improvements[:2])}"
                )
        
        if not trend_lines:
            return "First iteration — no history yet"
        
        # Add trend analysis
        scores = [entry.get("overall_score", 0) for entry in input_data.get("iteration_history", [])]
        if len(scores) >= 2:
            if scores[-1] > scores[-2]:
                trend_lines.append(f"  📈 IMPROVING: {scores[-2]:.2f} → {scores[-1]:.2f}")
            elif scores[-1] < scores[-2]:
                trend_lines.append(f"  📉 DECLINING: {scores[-2]:.2f} → {scores[-1]:.2f} — change approach!")
            else:
                trend_lines.append(f"  ➡️ STAGNANT at {scores[-1]:.2f} — try different technique!")
        
        return "\n".join(trend_lines)

    def _safe_get(self, data: Dict, outer_key: str, inner_key: str, default="N/A"):
        """Safely get a nested value from context data."""
        try:
            outer = data.get(outer_key, {})
            if isinstance(outer, dict):
                return outer.get(inner_key, default)
            return default
        except Exception:
            return default

    def _safe_list(self, data: Dict, outer_key: str, inner_key: str) -> list:
        """Safely get a nested list from context data."""
        try:
            outer = data.get(outer_key, {})
            if isinstance(outer, dict):
                val = outer.get(inner_key, [])
                return val if isinstance(val, list) else []
            return []
        except Exception:
            return []

    def _format_physics_violations(self, data: Dict) -> str:
        """Format physics violations into readable text."""
        try:
            physics = data.get("physics_result", {})
            violations = physics.get("violations", [])
            if not violations:
                return "No physics violations"
            parts = []
            for v in violations[:5]:  # Cap at 5
                severity = v.get("severity", "?").upper()
                msg = v.get("message", "Unknown")
                parts.append(f"[{severity}] {msg}")
            return "; ".join(parts)
        except Exception:
            return "Physics data unavailable"

    def _format_physics_fixes(self, data: Dict) -> str:
        """Format physics fix suggestions into readable text."""
        try:
            physics = data.get("physics_result", {})
            fixes = physics.get("fix_suggestions", [])
            if not fixes:
                return "None needed"
            return "; ".join(fixes[:5])
        except Exception:
            return "Physics data unavailable"
