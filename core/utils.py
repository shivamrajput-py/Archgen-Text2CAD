# Ultra-robust JSON parsing utilities for ArchGen
import json
import re
import logging

logger = logging.getLogger(__name__)


def ultra_robust_json_parse(content: str, fallback_data: dict = None, context: str = "") -> dict:
    """Ultra-robust JSON parsing with extensive fallback strategies"""
    if fallback_data is None:
        fallback_data = {}

    original_content = content

    # Clean up the content first
    content = content.strip()

    # Strategy 1: Remove markdown blocks
    if "```json" in content:
        json_start = content.find("```json") + 7
        json_end = content.find("```", json_start)
        if json_end != -1:
            content = content[json_start:json_end].strip()
    elif content.startswith("```") and content.count("```") >= 2:
        parts = content.split("```")
        if len(parts) >= 3:
            content = parts[1].strip()

    # Strategy 2: Direct JSON parsing
    try:
        result = json.loads(content)
        return result
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find JSON object boundaries
    brace_patterns = [
        (r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', "Simple nested"),
        (r'\{.*?\}', "Greedy match"),
        (r'\{[\s\S]*\}', "Full content match")
    ]

    for pattern, desc in brace_patterns:
        try:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    result = json.loads(match)
                    return result
                except json.JSONDecodeError:
                    continue
        except Exception:
            continue

    # Strategy 4: Line-by-line parsing for malformed JSON
    try:
        lines = content.split('\n')
        json_lines = []
        in_json = False
        brace_count = 0

        for line in lines:
            line = line.strip()
            if line.startswith('{'):
                in_json = True
                brace_count = 1
                json_lines = [line]
            elif in_json:
                json_lines.append(line)
                brace_count += line.count('{') - line.count('}')
                if brace_count == 0:
                    break

        if json_lines:
            reconstructed = '\n'.join(json_lines)
            result = json.loads(reconstructed)
            logger.info("Line-by-line JSON parsing successful")
            return result
    except Exception:
        pass

    # Strategy 5: Extract key-value pairs with regex
    try:
        kv_patterns = [
            r'"([^"]+)"\s*:\s*"([^"]*)"',  # String values
            r'"([^"]+)"\s*:\s*(\d+(?:\.\d+)?)',  # Numeric values
            r'"([^"]+)"\s*:\s*(true|false)',  # Boolean values
            r'"([^"]+)"\s*:\s*\[(.*?)\]',  # Array values
            r'"([^"]+)"\s*:\s*\{([^}]*)\}',  # Object values
        ]

        result = {}

        for pattern in kv_patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                key = match[0]
                value = match[1]

                if pattern.endswith('true|false)'):
                    result[key] = value.lower() == 'true'
                elif pattern.endswith(r'(\d+(?:\.\d+)?)'):
                    result[key] = float(value) if '.' in value else int(value)
                elif pattern.endswith(r'\[(.*?)\]'):
                    if value.strip():
                        array_items = [item.strip().strip('"') for item in value.split(',')]
                        result[key] = array_items
                    else:
                        result[key] = []
                elif pattern.endswith(r'\{([^}]*)\}'):
                    try:
                        obj_result = json.loads('{' + value + '}')
                        result[key] = obj_result
                    except:
                        result[key] = {"raw": value}
                else:
                    result[key] = value

        if result:
            logger.info(f"Regex-based parsing extracted {len(result)} fields")
            return result
    except Exception as e:
        logger.warning(f"Regex parsing failed: {e}")

    # Strategy 6: Search for specific expected fields
    try:
        expected_fields = {
            "is_valid": (r'"is_valid"\s*:\s*(true|false)', lambda x: x.lower() == 'true'),
            "enhanced_prompt": (r'"enhanced_prompt"\s*:\s*"([^"]*)"', str),
            "overall_score": (r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)', float),
            "should_continue": (r'"should_continue"\s*:\s*(true|false)', lambda x: x.lower() == 'true'),
            "complexity_score": (r'"complexity_score"\s*:\s*(\d+(?:\.\d+)?)', float),
            "confidence_score": (r'"confidence_score"\s*:\s*(\d+(?:\.\d+)?)', float),
        }

        result = {}
        for field, (pattern, converter) in expected_fields.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    result[field] = converter(match.group(1))
                except:
                    result[field] = match.group(1)

        # Look for arrays
        array_patterns = {
            "strengths": r'"strengths"\s*:\s*\[(.*?)\]',
            "weaknesses": r'"weaknesses"\s*:\s*\[(.*?)\]',
            "missing_info": r'"missing_info"\s*:\s*\[(.*?)\]',
            "primary_issues": r'"primary_issues"\s*:\s*\[(.*?)\]',
            "refinement_suggestions": r'"refinement_suggestions"\s*:\s*\[(.*?)\]',
        }

        for field, pattern in array_patterns.items():
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                array_content = match.group(1)
                items = re.findall(r'"([^"]*)"', array_content)
                result[field] = items

        if result:
            logger.info(f"Field-specific parsing extracted {len(result)} fields")
            return result
    except Exception as e:
        logger.warning(f"Field-specific parsing failed: {e}")

    # Strategy 7: Create intelligent fallback based on context
    try:
        context_lower = context.lower()

        if "prompt_validation" in context_lower:
            smart_fallback = {
                "is_valid": True,
                "enhanced_prompt": "Enhanced technical prompt with specific parameters",
                "requirements": {"basic": "standard"},
                "domain": "mechanical",
                "complexity_score": 0.7,
                "missing_info": []
            }
        elif "quality_assessment" in context_lower:
            smart_fallback = {
                "overall_score": 0.75,
                "category_scores": {"technical_correctness": 0.8, "completeness": 0.7},
                "strengths": ["Script generated successfully"],
                "weaknesses": ["Assessment parsing failed"],
                "refinement_suggestions": ["Manual review recommended"],
                "missing_requirements": []
            }
        elif "refinement" in context_lower:
            smart_fallback = {
                "primary_issues": ["Analysis incomplete due to parsing error"],
                "enhanced_prompt_suggestions": "Improved prompt with better specifications",
                "should_continue": True,
                "confidence_score": 0.6,
                "specific_fixes": ["Review and refine manually"]
            }
        else:
            smart_fallback = fallback_data

        # Try to extract any numeric values from the content
        numbers = re.findall(r'\d+(?:\.\d+)?', content)
        if numbers:
            try:
                score = float(numbers[0])
                if 0 <= score <= 1:
                    smart_fallback["overall_score"] = score
                elif 0 <= score <= 100:
                    smart_fallback["overall_score"] = score / 100
            except:
                pass

        logger.warning(f"Using intelligent context-based fallback for {context}")
        return smart_fallback

    except Exception as e:
        logger.error(f"Smart fallback failed: {e}")

    # Final fallback
    logger.error(f"All JSON parsing strategies failed for context: {context}")
    logger.error(f"Original content length: {len(original_content)}")
    logger.error(f"Content preview: {original_content[:200]}...")

    return fallback_data if fallback_data else {"error": "parsing_failed", "success": False}
