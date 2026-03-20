"""
Scorecard extractor — extract MicroStrategy scorecards via REST API
and produce scorecards.json intermediate file.
"""

import logging

logger = logging.getLogger(__name__)


def extract_scorecards(client, project_id):
    """Extract scorecards from a MicroStrategy project.

    Args:
        client: Authenticated REST API client.
        project_id: MicroStrategy project ID.

    Returns:
        list of scorecard dicts with objectives and KPIs.
    """
    scorecards = []

    try:
        response = client.get(f"/api/documents?type=55&projectId={project_id}")
        docs = response if isinstance(response, list) else response.get("documents", [])
    except Exception as e:
        logger.warning("Could not fetch scorecards: %s", e)
        return scorecards

    for doc in docs:
        obj_id = doc.get("id", "")
        name = doc.get("name", "")

        try:
            detail = client.get(f"/api/documents/{obj_id}?projectId={project_id}")
        except Exception as e:
            logger.warning("Could not fetch scorecard detail %s: %s", obj_id, e)
            detail = {}

        scorecard = {
            "id": obj_id,
            "name": name,
            "description": doc.get("description", ""),
            "objectives": _extract_objectives(detail),
            "perspectives": _extract_perspectives(detail),
            "kpis": _extract_kpis(detail),
        }
        scorecards.append(scorecard)
        logger.info("Extracted scorecard: %s (%s)", name, obj_id)

    return scorecards


def _extract_objectives(detail):
    """Extract objectives (strategic goals) from scorecard detail."""
    objectives = []
    for obj in detail.get("objectives", detail.get("chapters", [])):
        objective = {
            "id": obj.get("id", obj.get("key", "")),
            "name": obj.get("name", ""),
            "description": obj.get("description", ""),
            "target_value": obj.get("target", {}).get("value"),
            "current_value": obj.get("current", {}).get("value"),
            "status": obj.get("status", ""),
            "weight": obj.get("weight", 1.0),
            "metric_id": obj.get("metric_id", obj.get("metricId", "")),
            "metric_name": obj.get("metric_name", obj.get("metricName", "")),
            "thresholds": _extract_thresholds(obj),
            "children": [],
        }
        # Nested sub-objectives
        for child in obj.get("children", obj.get("sub_objectives", [])):
            objective["children"].append({
                "id": child.get("id", ""),
                "name": child.get("name", ""),
                "target_value": child.get("target", {}).get("value"),
                "current_value": child.get("current", {}).get("value"),
                "status": child.get("status", ""),
                "metric_id": child.get("metric_id", child.get("metricId", "")),
                "metric_name": child.get("metric_name", child.get("metricName", "")),
            })
        objectives.append(objective)
    return objectives


def _extract_perspectives(detail):
    """Extract balanced scorecard perspectives."""
    perspectives = []
    for p in detail.get("perspectives", []):
        perspectives.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "objective_ids": [o.get("id", "") for o in p.get("objectives", [])],
        })
    return perspectives


def _extract_kpis(detail):
    """Extract KPI definitions from scorecard."""
    kpis = []
    for kpi in detail.get("kpis", detail.get("metrics", [])):
        kpis.append({
            "id": kpi.get("id", ""),
            "name": kpi.get("name", ""),
            "metric_id": kpi.get("metric_id", kpi.get("metricId", kpi.get("id", ""))),
            "target": kpi.get("target", {}).get("value"),
            "unit": kpi.get("unit", ""),
            "format": kpi.get("format", ""),
            "thresholds": _extract_thresholds(kpi),
        })
    return kpis


def _extract_thresholds(obj):
    """Extract threshold/status bands from a scorecard object."""
    thresholds = []
    for t in obj.get("thresholds", obj.get("bands", [])):
        thresholds.append({
            "name": t.get("name", t.get("status", "")),
            "min_value": t.get("min", t.get("minValue")),
            "max_value": t.get("max", t.get("maxValue")),
            "color": t.get("color", ""),
            "status": t.get("status", ""),
        })
    return thresholds


def parse_offline_scorecards(scorecards_path):
    """Parse scorecards from an offline JSON file.

    Args:
        scorecards_path: Path to scorecards.json file.

    Returns:
        list of scorecard dicts.
    """
    import json
    import os

    if not os.path.isfile(scorecards_path):
        logger.warning("Scorecards file not found: %s", scorecards_path)
        return []

    with open(scorecards_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data if isinstance(data, list) else data.get("scorecards", [])
