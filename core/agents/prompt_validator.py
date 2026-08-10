# Prompt Validation Agent - 2-Stage Pipeline: Guardrail Gate + Structured Extraction
# Uses LangChain's with_structured_output() for reliable Pydantic model output
import json
import logging
from typing import Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from models import (
    ValidationResult, ValidationCategory,
    GuardrailResult, PromptAnalysis, ComponentSpec, RequirementsSpec
)

logger = logging.getLogger(__name__)


class PromptValidationAgent:
    """Two-stage prompt validation pipeline.
    
    Stage 1: Guardrail Gate (fast_llm)
        - Is this a CAD/engineering request?
        - Is it appropriate content?
        - Is it specific enough to generate a model?
        - Should we ask for clarification?
    
    Stage 2: Structured Extraction (fast_llm + with_structured_output)
        - Category, difficulty, components, tags
        - Enhanced prompt with dimensions
        - Component plan with FreeCAD API hints
        - Requirements (dimensions, materials, load cases)
    """
    
    def __init__(self, llm: ChatOpenAI):
        self.name = "PromptValidator"
        self.llm = llm
        
        # Stage 1: Guardrail Gate — uses structured output for reliable classification
        self.guardrail_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a content classifier for a Text-to-CAD engineering system.

Your job is to determine if a user's prompt should proceed to CAD model generation.

Classify the prompt on these axes:
1. is_cad_related: Is this about designing, building, or engineering a physical object, structure, or mechanism? (buildings, bridges, gears, turbines, furniture, vehicles, etc. are all valid)
2. is_appropriate: Does the prompt contain appropriate content? (reject weapons of mass destruction, explicit content, illegal items)
3. is_specific_enough: Does the prompt have enough detail to generate a 3D model? A prompt like "design something" is too vague. "Design a house" is acceptable (we can infer defaults).
4. needs_clarification: Should we ask the user for more details before proceeding? Set true if the prompt is valid but very vague.
5. clarification_prompt: If needs_clarification is true, write a helpful question to ask the user.

is_allowed should be true ONLY if is_cad_related AND is_appropriate AND is_specific_enough are ALL true.
If is_allowed is false, provide a clear rejection_reason.
Set confidence to how certain you are (0.0 to 1.0)."""),
            ("human", "Classify this prompt: {prompt}")
        ])
        
        # Stage 2: Structured Extraction — comprehensive prompt analysis
        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Text-to-CAD prompt analyzer, enhancer, and component architect.

Analyze the given prompt and produce a comprehensive structured output:

1. difficulty: "simple" (basic shapes, 50-100 lines), "intermediate" (buildings/vehicles, 200-400 lines), or "advanced" (complex assemblies, 500-1000+ lines)
2. category: "architectural", "structural", "civil", "mechanical_engineering", or "industrial"
3. components: List of ALL design elements visible in the prompt
4. tags: Keywords describing the design
5. enhanced_prompt: Improved technical prompt with SPECIFIC dimensions in millimeters, real-world scale
6. domain: Engineering domain for rule lookup (usually same as category)
7. complexity_score: 0.0 (trivial) to 1.0 (extremely complex)
8. component_plan: Ordered list of components to build, each with:
   - name: Component name (e.g., "Foundation", "Roof_Structure")
   - description: What this is and key specs
   - material: Primary material (Concrete, Steel, Timber, Aluminum, Glass, etc.)
   - dimensions_mm: Key dimensions as name:value pairs in millimeters
   - freecad_approach: How to build in FreeCAD (e.g., "Part.makeBox for slab, Part.makeCylinder for columns")
   - construction_order: Build priority (1=first, foundation before walls before roof)
   - depends_on: List of component names this depends on
9. requirements:
   - dimensions: Overall dimensions in mm
   - features: Requested features (windows, balconies, etc.)
   - materials: All materials mentioned or inferred
   - load_cases: Structural loads for FEM validation

RULES:
- Be specific with dimensions (use millimeters, real-world scale)
- component_plan MUST be ordered by construction priority (foundation first, roof last)
- Each component MUST be an independent Part/Body in a hierarchical App::Part assembly
- Each component MUST have a specific material assigned
- Generate structural load_cases (fixed constraints + pressure/force loads)
- Include specific FreeCAD API hints for each component
- For mechanical: use Hub, Blades, Shaft, Housing etc.
- For civil: use Deck, Pylons, Cables, Abutments etc."""),
            ("human", "Analyze and decompose this CAD prompt: {prompt}")
        ])

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the 2-stage prompt validation pipeline."""
        prompt = input_data.get("prompt", "")
        
        # ============================================================
        # STAGE 1: Guardrail Gate
        # ============================================================
        guardrail_result = await self._run_guardrail(prompt)
        
        if guardrail_result is not None:
            # Check if prompt is rejected
            if not guardrail_result.is_allowed:
                logger.warning(
                    f"Prompt rejected by guardrail: {guardrail_result.rejection_reason} "
                    f"(confidence={guardrail_result.confidence:.2f})"
                )
                return self._build_rejection_response(prompt, guardrail_result)
            
            # Check if clarification is needed
            if guardrail_result.needs_clarification:
                logger.info(
                    f"Guardrail requests clarification: {guardrail_result.clarification_prompt}"
                )
                return self._build_clarification_response(prompt, guardrail_result)
            
            logger.info(
                f"Guardrail passed: cad_related={guardrail_result.is_cad_related}, "
                f"appropriate={guardrail_result.is_appropriate}, "
                f"specific={guardrail_result.is_specific_enough}, "
                f"confidence={guardrail_result.confidence:.2f}"
            )
        else:
            # Guardrail failed to run — proceed with caution
            logger.warning("Guardrail gate failed — proceeding with extraction anyway")
        
        # ============================================================
        # STAGE 2: Structured Extraction
        # ============================================================
        analysis = await self._run_extraction(prompt)
        
        if analysis is not None:
            return self._build_success_response(prompt, analysis)
        else:
            # Extraction failed — return fallback
            logger.error("Structured extraction failed — using fallback defaults")
            return self._build_fallback_response(prompt)
    
    async def _run_guardrail(self, prompt: str) -> Optional[GuardrailResult]:
        """Stage 1: Run the guardrail gate with structured output."""
        try:
            # Use with_structured_output for reliable Pydantic model binding
            structured_llm = self.llm.with_structured_output(GuardrailResult)
            result = await structured_llm.ainvoke(
                self.guardrail_prompt.format_messages(prompt=prompt)
            )
            return result
        except Exception as e:
            logger.warning(f"Guardrail structured output failed: {e}")
            # Try manual JSON fallback
            try:
                response = await self.llm.ainvoke(
                    self.guardrail_prompt.format_messages(prompt=prompt)
                )
                content = response.content.strip()
                # Try to parse as JSON and construct GuardrailResult
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                data = json.loads(content)
                return GuardrailResult(**data)
            except Exception as e2:
                logger.warning(f"Guardrail JSON fallback also failed: {e2}")
                return None
    
    async def _run_extraction(self, prompt: str) -> Optional[PromptAnalysis]:
        """Stage 2: Run structured extraction with Pydantic model output."""
        try:
            structured_llm = self.llm.with_structured_output(PromptAnalysis)
            result = await structured_llm.ainvoke(
                self.extraction_prompt.format_messages(prompt=prompt)
            )
            return result
        except Exception as e:
            logger.warning(f"Structured extraction failed: {e}")
            # Try manual JSON fallback
            try:
                response = await self.llm.ainvoke(
                    self.extraction_prompt.format_messages(prompt=prompt)
                )
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                data = json.loads(content)
                return PromptAnalysis(**data)
            except Exception as e2:
                logger.warning(f"Extraction JSON fallback also failed: {e2}")
                return None
    
    def _build_success_response(self, prompt: str, analysis: PromptAnalysis) -> Dict[str, Any]:
        """Build the response dict from a successful PromptAnalysis."""
        # Format component blueprint for the CAD generator
        component_plan_dicts = [
            {
                "name": c.name,
                "description": c.description,
                "material": c.material,
                "dimensions_mm": c.dimensions_mm,
                "freecad_approach": c.freecad_approach,
                "construction_order": c.construction_order,
                "priority": c.construction_order,  # backward compat
                "apis_hint": [c.freecad_approach],
                "depends_on": c.depends_on,
            }
            for c in sorted(analysis.component_plan, key=lambda c: c.construction_order)
        ]
        
        component_blueprint = self._format_component_blueprint(component_plan_dicts)
        
        enhanced_prompt = analysis.enhanced_prompt
        if component_blueprint:
            enhanced_prompt += (
                f"\n\nSTRUCTURED COMPONENT BLUEPRINT "
                f"(generate ALL components in ONE script, in this order):\n"
                f"{component_blueprint}"
            )
        
        # ── Auto-injected Negative Constraints ──
        # The audit proved that explicit "DO NOT ADD" constraints are the single
        # highest-leverage improvement. Prompts with them scored 8.9 avg vs 5.7 without.
        component_names = [c.name for c in analysis.component_plan]
        negative_constraints = (
            "\n\nCRITICAL NEGATIVE CONSTRAINTS (MANDATORY — VIOLATION = FAILURE):\n"
            f"1. Build ONLY the components listed above: {', '.join(component_names)}.\n"
            "2. DO NOT add: reference lines, section planes, bounding boxes, "
            "bolt position markers, center axis lines, BCD circles, or any visualization helpers.\n"
            "3. DO NOT create duplicate geometry — if you fuse parts into a final solid, "
            "do NOT also add the individual sub-parts as separate objects in the document. "
            "Only the FINAL fused/cut result should appear in the document tree.\n"
            "4. DO NOT add decorative or 'professional' features (chamfers, fillets, grooves, "
            "recesses, countersinks, ribs, notches, orientation markers) unless they are "
            "EXPLICITLY listed in the requirements above.\n"
            "5. The output will be automatically validated. Any unrequested object "
            "in the document tree will cause the quality score to decrease.\n"
        )
        enhanced_prompt += negative_constraints
        
        # Build requirements dict
        requirements = {
            "dimensions": analysis.requirements.dimensions,
            "features": analysis.requirements.features,
            "materials": analysis.requirements.materials,
            "load_cases": analysis.requirements.load_cases,
        }
        
        validation_result = ValidationResult(
            is_valid=True,
            score=analysis.complexity_score,
            errors=[],
            suggestions=[analysis.enhanced_prompt],
            category=ValidationCategory.SEMANTIC.value
        )
        
        logger.info(
            f"Prompt Analysis — Difficulty: {analysis.difficulty}, "
            f"Category: {analysis.category}, "
            f"Components: {len(analysis.components)}, "
            f"Plan: {len(component_plan_dicts)} steps"
        )
        
        # Build the full PromptAnalysis JSON for RAG search query
        prompt_analysis_json = analysis.model_dump() if hasattr(analysis, 'model_dump') else {}
        
        return {
            "validation_result": validation_result,
            "enhanced_prompt": enhanced_prompt,
            "requirements": requirements,
            "domain": analysis.domain,
            "difficulty": analysis.difficulty,
            "category": analysis.category,
            "components": analysis.components,
            "tags": analysis.tags,
            "component_plan": component_plan_dicts,
            "prompt_analysis": prompt_analysis_json,  # Full structured analysis for RAG query
        }
    
    def _build_rejection_response(self, prompt: str, guardrail: GuardrailResult) -> Dict[str, Any]:
        """Build response for a rejected prompt."""
        validation_result = ValidationResult(
            is_valid=False,
            score=0.0,
            errors=[guardrail.rejection_reason or "Prompt rejected by guardrail"],
            suggestions=[],
            category=ValidationCategory.SEMANTIC.value
        )
        
        return {
            "validation_result": validation_result,
            "enhanced_prompt": prompt,
            "requirements": {},
            "domain": "unknown",
            "difficulty": "unknown",
            "category": "unknown",
            "components": [],
            "tags": [],
            "component_plan": [],
            "prompt_analysis": {},
            "rejected": True,
            "rejection_reason": guardrail.rejection_reason,
        }
    
    def _build_clarification_response(self, prompt: str, guardrail: GuardrailResult) -> Dict[str, Any]:
        """Build response when clarification is needed."""
        validation_result = ValidationResult(
            is_valid=False,
            score=0.3,
            errors=[],
            suggestions=[guardrail.clarification_prompt or "Could you provide more details?"],
            category=ValidationCategory.SEMANTIC.value
        )
        
        return {
            "validation_result": validation_result,
            "enhanced_prompt": prompt,
            "requirements": {},
            "domain": "unknown",
            "difficulty": "unknown",
            "category": "unknown",
            "components": [],
            "tags": [],
            "component_plan": [],
            "prompt_analysis": {},
            "needs_clarification": True,
            "clarification_prompt": guardrail.clarification_prompt,
        }
    
    def _build_fallback_response(self, prompt: str) -> Dict[str, Any]:
        """Build fallback response when both stages fail."""
        validation_result = ValidationResult(
            is_valid=True,
            score=0.5,
            errors=["Structured extraction failed — using fallback defaults"],
            suggestions=[prompt],
            category=ValidationCategory.SEMANTIC.value
        )
        
        return {
            "validation_result": validation_result,
            "enhanced_prompt": prompt,
            "requirements": {
                "dimensions": {"length": "10000mm", "width": "8000mm", "height": "15000mm"},
                "features": ["standard"],
                "materials": ["concrete", "steel"],
                "load_cases": [
                    {"type": "fixed", "target": "base"},
                    {"type": "pressure", "magnitude_mpa": 0.005, "target": "roof", "direction": [0, 0, -1]}
                ]
            },
            "domain": "architectural",
            "difficulty": "intermediate",
            "category": "architectural",
            "components": ["main_structure"],
            "tags": [],
            "component_plan": [
                {"name": "Main_Structure", "description": "Primary geometry", 
                 "priority": 1, "apis_hint": ["Part.makeBox"], "depends_on": []}
            ],
            "prompt_analysis": {},
        }
    
    def _format_component_blueprint(self, component_plan: list) -> str:
        """Format component plan into readable blueprint for the CAD generator."""
        if not component_plan:
            return ""

        lines = []
        for comp in sorted(component_plan, key=lambda c: c.get("priority", c.get("construction_order", 99))):
            name = comp.get("name", "Component")
            desc = comp.get("description", "")
            material = comp.get("material", "")
            approach = comp.get("freecad_approach", "")
            apis = ", ".join(comp.get("apis_hint", []))
            deps = ", ".join(comp.get("depends_on", []))
            
            order = comp.get('priority', comp.get('construction_order', '?'))
            line = f"  {order}. {name}"
            if material:
                line += f" [{material}]"
            line += f": {desc}"
            if approach:
                line += f" [FreeCAD: {approach}]"
            elif apis:
                line += f" [APIs: {apis}]"
            if deps:
                line += f" [After: {deps}]"
            lines.append(line)

        return "\n".join(lines)
