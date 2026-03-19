"""
Prompt extractor for MicroStrategy.

Extracts prompt definitions and maps them to Power BI equivalents
(slicers, what-if parameters, field parameters).
"""

import logging

logger = logging.getLogger(__name__)


def extract_prompts(prompts_data):
    """Parse prompt definitions into intermediate format.

    Args:
        prompts_data: List of prompt definitions from REST API

    Returns:
        list of prompt dicts with Power BI mapping info
    """
    results = []
    for p in prompts_data or []:
        prompt = _parse_prompt(p)
        results.append(prompt)
    return results


def _parse_prompt(prompt):
    """Parse a single prompt definition."""
    prompt_type = _classify_prompt_type(prompt)

    return {
        "id": prompt.get("id", ""),
        "name": prompt.get("name", prompt.get("title", "")),
        "type": prompt_type,
        "required": prompt.get("required", False),
        "allow_multi_select": prompt.get("multiSelect", True),
        "default_value": _extract_default(prompt),
        "options": _extract_options(prompt),
        "pbi_type": _map_prompt_to_pbi(prompt_type, prompt),
        "attribute_name": prompt.get("attribute", {}).get("name", ""),
        "min_value": prompt.get("min", None),
        "max_value": prompt.get("max", None),
    }


def _classify_prompt_type(prompt):
    """Classify the prompt type."""
    ptype = (prompt.get("type", "") or prompt.get("promptType", "")).lower()

    if "value" in ptype:
        return "value"
    if "object" in ptype:
        return "object"
    if "hierarchy" in ptype:
        return "hierarchy"
    if "expression" in ptype:
        return "expression"
    if "date" in ptype or "datetime" in ptype:
        return "date"
    if "element" in ptype:
        return "element"

    # Infer from content
    if prompt.get("attribute"):
        return "element"
    if prompt.get("min") is not None or prompt.get("max") is not None:
        return "value"

    return "value"


def _map_prompt_to_pbi(prompt_type, prompt):
    """Map prompt type to Power BI equivalent."""
    mapping = {
        "value": "what_if_parameter" if not prompt.get("multiSelect") else "slicer",
        "element": "slicer",
        "object": "field_parameter",
        "hierarchy": "hierarchy_slicer",
        "expression": "manual_review",
        "date": "date_slicer",
    }
    return mapping.get(prompt_type, "slicer")


def _extract_default(prompt):
    """Extract default value(s)."""
    default = prompt.get("defaultAnswer", prompt.get("defaultValue", None))
    if isinstance(default, list):
        return [d.get("name", str(d)) if isinstance(d, dict) else str(d) for d in default]
    if default is not None:
        return str(default)
    return None


def _extract_options(prompt):
    """Extract available options for element/object prompts."""
    options = []
    for opt in prompt.get("options", []) or prompt.get("searchResults", []) or []:
        options.append({
            "id": opt.get("id", ""),
            "name": opt.get("name", str(opt)),
        })
    return options
