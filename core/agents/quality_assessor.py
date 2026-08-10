# Quality Assessment Agent - Evaluates generated CAD script quality
import json
import logging
from typing import Dict, List, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from models import ValidationResult, ValidationCategory, DETAIL_REQUIREMENTS
from utils import ultra_robust_json_parse

logger = logging.getLogger(__name__)


class QualityAssessmentAgent:
    def __init__(self, llm: ChatOpenAI):
        self.name = "QualityAssessor"
        self.llm = llm
        self.quality_assessment_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert CAD quality assessor. You evaluate FreeCAD Python scripts for engineering correctness and design quality.

CRITICAL: Respond with EXACTLY this JSON structure (no markdown, no explanations):
{{"overall_score": 0.85, "category_scores": {{"technical_correctness": 0.9, "completeness": 0.8, "code_quality": 0.85, "requirements_fulfillment": 0.9, "structural_realism": 0.8, "physics_validity": 0.75}}, "strengths": ["str1", "str2"], "weaknesses": ["w1", "w2"], "refinement_suggestions": ["s1", "s2"], "missing_requirements": ["m1"], "requirements_analysis": {{"dimensions_met": true, "features_implemented": ["f1"], "features_missing": ["f2"], "materials_specified": true}}, "component_checklist": {{"foundation": "present", "walls": "present", "windows": "missing", "roof": "partial"}}}}

EVALUATION CRITERIA (weighted):

1. REQUIREMENTS FULFILLMENT (30%):
   - Does the script create EVERY component mentioned in the prompt?
   - Are dimensions realistic for the design type?
   - Are specified features (windows, doors, balconies, etc.) actually implemented?
   - Check the component_plan if provided — are ALL planned components in the script?

2. TECHNICAL CORRECTNESS (20%):
   - Valid FreeCAD API usage (Part.makeBox, doc.addObject, etc.)
   - Proper document lifecycle (newDocument → addObject → recompute)
   - No GUI-only calls (ViewObject, FreeCADGui) in headless scripts
   - Error handling around complex operations

3. STRUCTURAL REALISM (15%):
   - Are wall thicknesses realistic (200-300mm for load-bearing)?
   - Are floor heights realistic (3000-4000mm)?
   - Are column sizes proportional to building height?
   - Would this structure be physically stable?

4. CODE QUALITY (15%):
   - Well-organized with functions for repeated patterns
   - Clear comments explaining design intent
   - Consistent naming conventions
   - No redundant/dead code

5. COMPLETENESS (10%):
   - Has proper imports, document creation, and recompute
   - Line count meets difficulty requirements
   - All logical parts of the design are included

6. PHYSICS VALIDITY (10%):
   - No floating elements (everything connected or supported)
   - Proper load paths (columns under beams, beams under slabs)
   - Realistic proportions for the design type
   - No impossibly thin or thick elements

SCORING RULES:
- overall_score = weighted average of all categories
- Be STRICT: a script that creates just boxes for "modern hospital" should score < 0.5
- Detail matters: a 100-line script for an "advanced" design should be penalized
- Missing components from the prompt: each missing component reduces score by 0.05-0.1"""),
            ("human", """Evaluate this FreeCAD script against ALL requirements:

ORIGINAL PROMPT: {original_prompt}
ENHANCED PROMPT: {enhanced_prompt}
REQUIREMENTS: {requirements}
CATEGORY: {category} | DIFFICULTY: {difficulty}
MINIMUM LINES FOR THIS DIFFICULTY: {min_lines}

FULL SCRIPT ({script_lines} lines):
{script}

VISUAL ASSESSMENT (from rendered 3D views):
- Visual Score: {visual_score}
- Visual Description: {visual_description}
- Present Components: {present_components}
- Missing Components: {missing_components}
- Structural Concerns: {structural_concerns}
- Geometry Issues: {geometry_issues}

EXECUTION STATUS: {execution_success}

PREVIOUS QUALITY HISTORY:
{quality_history}

SPECIFIC EVALUATION FOCUS:
{evaluation_focus}""")
        ])

    def _check_requirements_fulfillment(self, script: str, requirements: Dict) -> float:
        """Check how well script fulfills specified requirements"""
        if not requirements:
            return 0.8

        fulfillment_score = 0.0
        total_requirements = 0

        if "dimensions" in requirements:
            total_requirements += 1
            dims = requirements["dimensions"]
            dim_found = any(str(val).replace("mm", "") in script for val in dims.values())
            if dim_found:
                fulfillment_score += 1

        if "features" in requirements:
            features = requirements["features"]
            total_requirements += len(features)
            for feature in features:
                if feature.lower() in script.lower():
                    fulfillment_score += 1

        if "materials" in requirements:
            materials = requirements["materials"]
            total_requirements += len(materials)
            for material in materials:
                if material.lower() in script.lower():
                    fulfillment_score += 1

        return fulfillment_score / max(1, total_requirements)

    def _assess_code_quality(self, script: str) -> float:
        """Assess general code quality"""
        score = 0.5
        if "import" in script: score += 0.1
        if "newDocument" in script: score += 0.1
        if "recompute" in script: score += 0.1
        if len(script.split('\n')) > 10: score += 0.1
        if "def " in script: score += 0.1
        return min(1.0, score)

    def _assess_completeness(self, script: str, requirements: Dict) -> float:
        """Assess how complete the script is"""
        score = 0.6
        if "import" in script and "newDocument" in script and "recompute" in script:
            score += 0.2
        if requirements.get("features"):
            feature_count = len(requirements["features"])
            complexity_bonus = min(0.2, feature_count * 0.05)
            score += complexity_bonus
        return min(1.0, score)

    def _build_evaluation_focus(self, input_data: Dict) -> str:
        """Build specific evaluation focus based on iteration history"""
        focus_areas = []

        if "iteration_history" in input_data:
            recent_issues = []
            for iteration in input_data["iteration_history"][-2:]:
                recent_issues.extend(iteration.get("primary_issues", []))
            if recent_issues:
                focus_areas.append(f"Pay special attention to: {', '.join(set(recent_issues[:3]))}")

        if "validation_results" in input_data:
            failed_categories = [cat for cat, result in input_data["validation_results"].items()
                                 if not result.is_valid]
            if failed_categories:
                focus_areas.append(f"Focus on issues in: {', '.join(failed_categories)}")

        return "\n".join(focus_areas) if focus_areas else "Perform comprehensive evaluation across all criteria"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        script = input_data.get("generated_script", "")
        requirements = input_data.get("requirements", {})
        original_prompt = input_data.get("original_prompt", "")
        enhanced_prompt = input_data.get("enhanced_prompt", "")
        domain = input_data.get("domain", "mechanical")
        difficulty = input_data.get("difficulty", "intermediate")
        category = input_data.get("category", "architectural")
        execution_success = input_data.get("execution_success", False)

        # Get visual assessment context
        visual_assessment = input_data.get("visual_assessment", {})
        visual_score = visual_assessment.get("visual_score", "N/A")
        visual_description = visual_assessment.get("visual_description", "No visual assessment available")
        present_components = ", ".join(visual_assessment.get("present_components", [])) or "Unknown"
        missing_components = ", ".join(visual_assessment.get("missing_components", [])) or "None identified"
        structural_concerns = ", ".join(visual_assessment.get("structural_concerns", [])) or "None identified"
        geometry_issues = ", ".join(visual_assessment.get("geometry_issues", [])) or "None identified"

        # Get difficulty requirements
        detail_requirements = DETAIL_REQUIREMENTS.get(difficulty, DETAIL_REQUIREMENTS["intermediate"])
        min_lines = detail_requirements.get("min_lines", 100)
        script_lines = len(script.split('\n'))

        logger.info(f"Assessing quality: {script_lines} lines, difficulty={difficulty}, min_lines={min_lines}")

        try:
            quality_history = self._build_quality_history_context(input_data)
            evaluation_focus = self._build_evaluation_focus(input_data)

            response = await self.llm.ainvoke(
                self.quality_assessment_prompt.format_messages(
                    original_prompt=original_prompt,
                    enhanced_prompt=enhanced_prompt,
                    requirements=json.dumps(requirements, indent=1),
                    category=category,
                    difficulty=difficulty,
                    min_lines=min_lines,
                    script=script,
                    script_lines=script_lines,
                    quality_history=quality_history,
                    execution_success=execution_success,
                    evaluation_focus=evaluation_focus,
                    visual_score=visual_score,
                    visual_description=visual_description,
                    present_components=present_components,
                    missing_components=missing_components,
                    structural_concerns=structural_concerns,
                    geometry_issues=geometry_issues
                )
            )

            fallback_data = {
                "overall_score": 0.6,
                "category_scores": {
                    "technical_correctness": 0.7,
                    "completeness": 0.5,
                    "code_quality": 0.6,
                    "requirements_fulfillment": self._check_requirements_fulfillment(script, requirements),
                    "structural_realism": 0.5,
                    "physics_validity": 0.5
                },
                "strengths": ["Script generated successfully"],
                "weaknesses": ["Quality assessment parsing failed"],
                "refinement_suggestions": ["Manual code review recommended"],
                "missing_requirements": [],
                "requirements_analysis": {
                    "dimensions_met": "dimensions" in requirements,
                    "features_implemented": [],
                    "features_missing": [],
                    "materials_specified": "materials" in requirements
                },
                "component_checklist": {}
            }

            assessment_result = ultra_robust_json_parse(response.content, fallback_data, "quality_assessment")
            llm_score = assessment_result.get("overall_score", 0.6)

            # Apply deterministic penalties/bonuses on top of LLM score
            adjusted_score = llm_score

            # Penalty: script too short for difficulty
            if script_lines < min_lines:
                line_ratio = script_lines / min_lines
                line_penalty = (1.0 - line_ratio) * 0.15
                adjusted_score -= line_penalty
                logger.warning(f"Line penalty: -{line_penalty:.3f} ({script_lines}/{min_lines} lines)")

            # Penalty: missing doc lifecycle
            if "newDocument" not in script:
                adjusted_score -= 0.05
            if "recompute" not in script:
                adjusted_score -= 0.03

            # Penalty: GUI calls in headless script (minor — doesn't break anything)
            if "ViewObject" in script or "FreeCADGui" in script:
                adjusted_score -= 0.03
                logger.warning("GUI call penalty: -0.03")

            # Bonus: strong visual score (validates that the script actually produces good output)
            if isinstance(visual_score, (int, float)) and visual_score > 0.7:
                adjusted_score += 0.05

            # Penalty: physics violations (from PhysicsCheckAgent)
            # Each CRITICAL violation costs 0.06, each WARNING costs 0.02
            # Cap at 0.25 to avoid over-penalizing
            try:
                physics_result = input_data.get("physics_result", {})
                physics_score_val = physics_result.get("physics_score", 1.0)
                if physics_score_val < 1.0:
                    critical_count = physics_result.get("critical_count", 0)
                    warning_count = physics_result.get("warning_count", 0)
                    physics_penalty = min(0.25, critical_count * 0.06 + warning_count * 0.02)
                    adjusted_score -= physics_penalty
                    logger.warning(f"Physics penalty: -{physics_penalty:.3f} ({critical_count} critical, {warning_count} warnings)")
            except Exception:
                pass  # Never crash quality assessment over physics integration

            # Penalty: FEM structural failures (from FEMValidator, Phase 3)
            try:
                fem_result = input_data.get("fem_result", {})
                fem_score_val = fem_result.get("fem_score", 1.0)
                if fem_score_val < 1.0 and not fem_result.get("fem_error"):
                    # Only penalize if FEM actually ran (not skipped)
                    fem_penalty = min(0.08, (1.0 - fem_score_val) * 0.12)
                    adjusted_score -= fem_penalty
                    logger.warning(f"FEM penalty: -{fem_penalty:.3f} (safety_factor={fem_result.get('safety_factor', 'N/A')})")
            except Exception:
                pass  # Never crash quality assessment over FEM integration

            # Penalty: over-engineering detected via geometry health check
            # If the script created way more objects than the expected component count,
            # it's adding unrequested features (the #1 failure mode from our audit).
            try:
                geometry_health = input_data.get("geometry_health") or {}
                if not geometry_health:
                    # The execution engine returns health data under 'metrics' key
                    geometry_health = input_data.get("metrics") or {}
                if not geometry_health:
                    # Legacy fallback
                    exec_metrics = input_data.get("execution_metrics") or {}
                    geometry_health = exec_metrics if isinstance(exec_metrics, dict) else {}
                
                actual_objects = geometry_health.get("objects", 0)
                expected_components = len(input_data.get("components", []))
                
                if actual_objects > 0 and expected_components > 0:
                    # Allow up to 2x the expected count (for sub-components, assemblies)
                    # Penalize beyond that — each excess object costs 0.02, capped at 0.15
                    excess = max(0, actual_objects - expected_components * 2)
                    if excess > 0:
                        overeng_penalty = min(0.15, excess * 0.02)
                        adjusted_score -= overeng_penalty
                        logger.warning(
                            f"Over-engineering penalty: -{overeng_penalty:.3f} "
                            f"({actual_objects} objects vs {expected_components} expected components)"
                        )
                
                # Penalty: invalid topology detected
                invalid_count = geometry_health.get("invalid", 0)
                if isinstance(invalid_count, int) and invalid_count > 0:
                    topo_penalty = min(0.10, invalid_count * 0.04)
                    adjusted_score -= topo_penalty
                    logger.warning(
                        f"Topology penalty: -{topo_penalty:.3f} "
                        f"({invalid_count} invalid shapes detected)"
                    )
            except Exception:
                pass  # Never crash quality assessment over geometry health integration

            adjusted_score = max(0.0, min(1.0, adjusted_score))
            
            logger.info(f"Quality: LLM={llm_score:.2f} → Adjusted={adjusted_score:.2f}")

            quality_validation = ValidationResult(
                is_valid=adjusted_score >= 0.75,
                score=adjusted_score,
                errors=assessment_result.get("missing_requirements", []),
                suggestions=assessment_result.get("refinement_suggestions", []),
                category=ValidationCategory.VISUAL.value
            )

            return {
                "quality_validation": quality_validation,
                "overall_score": adjusted_score,
                "llm_raw_score": llm_score,
                "detailed_assessment": assessment_result,
                "category_scores": assessment_result.get("category_scores", {}),
                "strengths": assessment_result.get("strengths", []),
                "weaknesses": assessment_result.get("weaknesses", []),
                "refinement_suggestions": assessment_result.get("refinement_suggestions", []),
                "missing_requirements": assessment_result.get("missing_requirements", []),
                "requirements_analysis": assessment_result.get("requirements_analysis", {}),
                "component_checklist": assessment_result.get("component_checklist", {})
            }

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return self._create_fallback_assessment(script, requirements)

    def _build_quality_history_context(self, input_data: Dict) -> str:
        """Build quality history context for assessment"""
        history = []
        if "iteration_history" in input_data:
            for iteration in input_data["iteration_history"][-3:]:
                score = iteration.get("validation_scores", {}).get("quality", 0)
                issues = iteration.get("primary_issues", [])
                improvements = iteration.get("improvements_made", [])
                history.append(
                    f"Iteration {iteration.get('iteration', 0)}: Score={score:.2f}, Issues=[{', '.join(issues[:2])}], Improvements=[{', '.join(improvements[:2])}]")
        return "\n".join(history) if history else "No previous quality history available"

    def _create_fallback_assessment(self, script: str, requirements: Dict) -> Dict[str, Any]:
        """Create a basic fallback assessment when LLM evaluation fails"""
        score = 0.5
        issues = []

        if not script:
            score = 0.0
            issues.append("No script generated")
        else:
            if "import FreeCAD" in script or "import App" in script:
                score += 0.1
            if "newDocument" in script:
                score += 0.1
            if "recompute" in script:
                score += 0.1
            if len(script.split('\n')) > 5:
                score += 0.1

        score = min(1.0, max(0.0, score))

        quality_validation = ValidationResult(
            is_valid=score >= 0.8,
            score=score,
            errors=issues,
            suggestions=[],
            category=ValidationCategory.VISUAL.value
        )

        return {
            "quality_validation": quality_validation,
            "overall_score": score,
            "llm_raw_score": 0.0,
            "detailed_assessment": {"overall_score": score},
            "category_scores": {"fallback_assessment": score},
            "strengths": ["Basic script structure present"] if script else [],
            "weaknesses": issues,
            "refinement_suggestions": [],
            "missing_requirements": [],
            "requirements_analysis": {},
            "component_checklist": {}
        }
