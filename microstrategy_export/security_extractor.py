"""
Security filter extractor for MicroStrategy.

Extracts security filters (row-level security) and maps them
to Power BI RLS roles.
"""

import logging

logger = logging.getLogger(__name__)


def extract_security_filters(client):
    """Extract all security filters from the project.

    Returns list of security filter dicts.
    """
    # Security filters are searched via the search API with type 47
    try:
        results = client.search_objects(object_type=47)
    except Exception:
        # Some environments may not have security filter search
        logger.info("Security filter search not available")
        return []

    filters = []
    for sf in results:
        filters.append({
            "id": sf.get("id", ""),
            "name": sf.get("name", ""),
            "description": sf.get("description", ""),
            "expression": _extract_filter_expression(sf),
            "target_attributes": _extract_target_attributes(sf),
            "users": _extract_assigned_users(sf),
            "groups": _extract_assigned_groups(sf),
        })

    logger.info("Extracted %d security filters", len(filters))
    return filters


def _extract_filter_expression(sf):
    """Extract the filter expression."""
    expr = sf.get("expression", {})
    if isinstance(expr, str):
        return expr
    if isinstance(expr, dict):
        return expr.get("text", "") or expr.get("expressionText", "")
    return ""


def _extract_target_attributes(sf):
    """Extract target attributes the filter applies to."""
    targets = []
    for attr in sf.get("attributes", []) or sf.get("qualifications", []) or []:
        targets.append({
            "id": attr.get("id", ""),
            "name": attr.get("name", ""),
        })
    return targets


def _extract_assigned_users(sf):
    """Extract users assigned to this security filter."""
    users = []
    for u in sf.get("users", []) or []:
        users.append({
            "id": u.get("id", ""),
            "name": u.get("name", ""),
        })
    return users


def _extract_assigned_groups(sf):
    """Extract groups assigned to this security filter."""
    groups = []
    for g in sf.get("groups", []) or []:
        groups.append({
            "id": g.get("id", ""),
            "name": g.get("name", ""),
        })
    return groups
