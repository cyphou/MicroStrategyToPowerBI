"""
Cube (Intelligent Cube) extractor for MicroStrategy.

Extracts cube definitions including attributes, metrics, and filters.
"""

import logging

logger = logging.getLogger(__name__)


def extract_cube_definition(defn, summary):
    """Parse an Intelligent Cube definition.

    Args:
        defn: Full cube definition from REST API
        summary: Cube summary metadata

    Returns:
        dict with cube structure
    """
    cube = {
        "id": summary.get("id", ""),
        "name": summary.get("name", ""),
        "description": summary.get("description", defn.get("description", "")),
        "attributes": _extract_cube_attributes(defn),
        "metrics": _extract_cube_metrics(defn),
        "filter": _extract_cube_filter(defn),
        "refresh_policy": _extract_refresh_policy(defn),
    }
    return cube


def _extract_cube_attributes(defn):
    """Extract attributes from cube definition."""
    attributes = []
    for attr in defn.get("attributes", []) or defn.get("definition", {}).get("attributes", []) or []:
        attributes.append({
            "id": attr.get("id", ""),
            "name": attr.get("name", ""),
            "forms": [f.get("name", "") for f in attr.get("forms", []) or []],
        })
    return attributes


def _extract_cube_metrics(defn):
    """Extract metrics from cube definition."""
    metrics = []
    for met in defn.get("metrics", []) or defn.get("definition", {}).get("metrics", []) or []:
        metrics.append({
            "id": met.get("id", ""),
            "name": met.get("name", ""),
        })
    return metrics


def _extract_cube_filter(defn):
    """Extract filter applied to the cube."""
    f = defn.get("filter", {}) or {}
    return {
        "expression": f.get("expression", ""),
        "qualifications": f.get("qualifications", []),
    }


def _extract_refresh_policy(defn):
    """Extract cube refresh policy."""
    return defn.get("refreshPolicy", "manual")
