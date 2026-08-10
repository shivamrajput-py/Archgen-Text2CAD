# CAD Generation Agent - Generates FreeCAD Python scripts
import json
import logging
from typing import Dict, List, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from models import (
    DOMAIN_RULES, FREECAD_PERFORMANCE_TIPS, FREECAD_CHEAT_SHEET,
    most_common_Freecad_errors, word_count
)
from rag import HybridRAG

logger = logging.getLogger(__name__)


class CADGenerationAgent:
    def __init__(self, llm: ChatOpenAI, rag_system: HybridRAG):
        self.name = "CADGenerator"
        self.llm = llm
        self.rag_system = rag_system

        self.generation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert FreeCAD Python script generator. 
Your goal is to create HIGHLY DETAILED, COMPLEX, and ROBUST FreeCAD models.
Generate clean, executable FreeCAD Python scripts. Do not include any explanations, markdown, or other text.

CRITICAL RULES:
1. Start directly with Python imports (import FreeCAD as App, import Part)
2. Create a new document (doc = App.newDocument("ModelName"))
3. Use proper FreeCAD API calls
4. Add brief comments explaining key steps
5. End with doc.recompute()
6. DO NOT include any text before or after the script
7. DO NOT use markdown code blocks
8. ONLY permitted print: `print('EXPORT_SUCCESS')` at the very end of successful export — DO NOT add any other print statements.
9. BUILD ONLY WHAT IS EXPLICITLY REQUESTED. Do NOT add features, components, helper geometry, reference lines, section planes, bolt markers, center axis lines, or any element not described in the user prompt. Every unrequested object in the output is a CRITICAL FAILURE.
10. DO NOT create duplicate geometry: if you fuse/cut parts, do NOT also add the individual intermediate shapes as separate objects in the document. Only the FINAL result should be added to the document tree.
11. SCALE: Ensure proper real-world scale using the domain rules below.

DIFFICULTY LEVEL: {difficulty}
MINIMUM LINE REQUIREMENTS:
- simple: Generate AT LEAST 50 lines of code. Basic geometry.
- intermediate: Generate AT LEAST 200 lines of code. Include windows, doors, structural elements.
- advanced: Generate AT LEAST 500 lines of code. Intricate details, sub-components, realistic features.

COMPONENTS TO INCLUDE: {components}
CATEGORY: {category}

DOMAIN-SPECIFIC ENGINEERING RULES (FOLLOW STRICTLY):
{domain_rules}

{performance_tips}

{cheat_sheet}

COMMON ERRORS TO AVOID:
{common_errors}

{error_prevention}

{engineering_constraints}

Use these similar examples as reference:
{examples}

This is iteration {iteration_count} of CAD generation.

CRITICAL INSTRUCTION:
This is a REFINEMENT step. You MUST address the feedback below.
If "PREVIOUS ITERATION GUIDANCE" lists errors, your PRIMARY GOAL is to fix them.

PREVIOUS ITERATION GUIDANCE:
{previous_guidance}

QUALITY FEEDBACK FROM PREVIOUS ITERATIONS:
{quality_history}

Technical requirements:
{requirements}"""),
            ("human", "Generate FreeCAD script for: {prompt}")
        ])

    def _process_previous_feedback(self, input_data: Dict) -> str:
        """Convert previous validation results into actionable guidance"""
        guidance = []

        # Execution errors
        if "validation_results" in input_data and "execution" in input_data["validation_results"]:
            exec_result = input_data["validation_results"]["execution"]
            if not exec_result.is_valid:
                guidance.append(f"CRITICAL EXECUTION ERROR: {'; '.join(exec_result.errors)} -> YOU MUST FIX THIS.")

        # Quality feedback
        if "previous_quality_feedback" in input_data:
            try:
                feedback = json.loads(input_data["previous_quality_feedback"])
                if "weaknesses" in feedback:
                    guidance.append(f"ADDRESS WEAKNESSES: {'; '.join(feedback['weaknesses'][:3])}")
                if "suggestions" in feedback:
                    guidance.append(f"APPLY SUGGESTIONS: {'; '.join(feedback['suggestions'][:3])}")
            except:
                pass

        # Previous errors
        previous_errors = input_data.get("previous_errors", [])
        if previous_errors:
            recent_errors = previous_errors[-3:]
            guidance.append(f"PREVIOUS RUNTIME ERRORS: {'; '.join(recent_errors)} -> AVOID REPEATING THESE.")

        return "\n".join(guidance) if guidance else "Focus on creating robust, well-structured FreeCAD script"

    def _build_quality_history_context(self, input_data: Dict) -> str:
        """Build comprehensive quality history context"""
        history = []

        if "iteration_history" in input_data:
            for i, iteration in enumerate(input_data["iteration_history"][-2:], 1):
                scores = iteration.get("validation_scores", {})
                issues = iteration.get("primary_issues", [])

                history.append(
                    f"Iteration {iteration.get('iteration', i)}: Quality={scores.get('quality', 0):.2f}, Issues: {', '.join(issues[:2])}")

        return "\n".join(history) if history else "No previous quality history available"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = input_data.get("enhanced_prompt", input_data.get("prompt", ""))
        requirements = input_data.get("requirements", {})
        domain = input_data.get("domain", "architectural")
        iteration_count = input_data.get("iteration_count", 0)
        
        difficulty = input_data.get("difficulty", "intermediate")
        category = input_data.get("category", "architectural")
        components = input_data.get("components", [])

        try:
            example_text = ""
            similar_examples = []
            # ── RAG retrieval ONLY on iteration 1 ──
            # Iteration 2+ already has the examples in context from iteration 1.
            # Re-retrieving wastes tokens and adds nothing. Instead, iterations 2+
            # focus on the previous script + refinement feedback.
            if iteration_count <= 1:
                # Build search query from full PromptAnalysis JSON (not just the prompt string)
                prompt_analysis = input_data.get("prompt_analysis", {})
                if prompt_analysis:
                    import json as _json
                    search_query = _json.dumps(prompt_analysis, ensure_ascii=False)
                else:
                    search_query = f"prompt: {prompt}, requirements: {requirements}, domain: {domain}"
                
                similar_examples = self.rag_system.retrieve_similar_examples(
                    query=search_query,
                    k=3,
                    category=category,
                    difficulty=difficulty,
                    components=components,
                    script_only=False,
                    use_mmr=True
                )
                logger.info(f"Iteration 1: Retrieved {len(similar_examples)} RAG examples (MMR, full)")

                for rank, example in enumerate(similar_examples, 1):
                    example_text += f"\n--- Example {rank} (score: {example.get('boosted_score', 0):.2f}) ---\n"
                    example_text += f"PROMPT: {example.get('prompt', '')}\n"
                    example_text += f"DIFFICULTY: {example.get('difficulty', 'unknown')}\n"

                    # Full metadata for all examples on iteration 1
                    if example.get('tags'):
                        example_text += f"TAGS: {', '.join(example['tags'])}\n"
                    if example.get('components'):
                        example_text += f"COMPONENTS: {', '.join(example['components'])}\n"
                    if example.get('engineering_concepts'):
                        example_text += f"CONCEPTS: {', '.join(example['engineering_concepts'])}\n"
                    if example.get('freecad_apis'):
                        example_text += f"APIs USED: {', '.join(example['freecad_apis'])}\n"
                    if example.get('validation_criteria'):
                        example_text += f"VALIDATION CRITERIA: {example['validation_criteria']}\n"
                    if 'chain_of_thoughts' in example:
                        example_text += f"REASONING: {example['chain_of_thoughts'][:200]}\n"

                    # ── Progressive script truncation by rank ──
                    # Rank 1: full script (best example gets full context)
                    # Rank 2: 70% of script
                    # Rank 3: 50% of script
                    script = example.get('script', '')
                    script_lines = script.splitlines()
                    total_lines = len(script_lines)
                    
                    if rank == 1:
                        # Full script for best match
                        example_text += f"SCRIPT:\n{script}\n"
                    elif rank == 2:
                        # 70% of script
                        cut_at = int(total_lines * 0.7)
                        truncated = '\n'.join(script_lines[:cut_at])
                        omitted_pct = 30
                        example_text += f"SCRIPT:\n{truncated}\n# [truncated — {omitted_pct}% omitted for token budget]\n"
                    else:
                        # 50% of script
                        cut_at = int(total_lines * 0.5)
                        truncated = '\n'.join(script_lines[:cut_at])
                        omitted_pct = 50
                        example_text += f"SCRIPT:\n{truncated}\n# [truncated — {omitted_pct}% omitted for token budget]\n"
                
                # Store examples in context for reference (not for re-retrieval)
                input_data["_rag_examples_text"] = example_text
                
            else:
                # Iteration 2+: No RAG retrieval — use previous script + feedback
                logger.info(f"Iteration {iteration_count}: Skipping RAG (using previous script + refinement feedback)")
                example_text = "No new examples retrieved. Focus on fixing the issues in the previous iteration's script."

            previous_guidance = self._process_previous_feedback(input_data)
            quality_history = self._build_quality_history_context(input_data)
            
            domain_rules_dict = DOMAIN_RULES.get(category, DOMAIN_RULES.get("architectural", {}))
            domain_rules_str = "\n".join([f"- {k}: {v}" for k, v in domain_rules_dict.items()])

            # Error prevention from error memory system
            error_prevention = input_data.get("error_prevention", "")

            response = await self.llm.ainvoke(
                self.generation_prompt.format_messages(
                    prompt=prompt,
                    examples=example_text,
                    requirements=json.dumps(requirements),
                    iteration_count=iteration_count,
                    previous_guidance=previous_guidance,
                    quality_history=quality_history,
                    difficulty=difficulty,
                    category=category,
                    components=", ".join(components) if components else "Not specified",
                    domain_rules=domain_rules_str,
                    performance_tips=FREECAD_PERFORMANCE_TIPS,
                    cheat_sheet=FREECAD_CHEAT_SHEET,
                    common_errors=most_common_Freecad_errors if most_common_Freecad_errors.strip() else "None specified yet",
                    error_prevention=error_prevention if error_prevention else "No additional error prevention context.",
                    engineering_constraints=input_data.get("engineering_constraints", "")
                )
            )

            generated_script = response.content.strip()
            logger.info(f"Generated script length: {word_count(generated_script)} words")

            return {
                "generated_script": generated_script,
                "examples_used": len(similar_examples),
                "success": True
            }

        except Exception as e:
            logger.error(f"CAD generation failed: {e}")
            return {
                "generated_script": "",
                "examples_used": 0,
                "success": False,
                "error": str(e)
            }
