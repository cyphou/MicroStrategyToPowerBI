"""
Goals generator — convert MicroStrategy scorecards to Power BI Goals
API payloads (Fabric Scorecard / Metrics feature).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "on_track": "OnTrack",
    "on track": "OnTrack",
    "at_risk": "AtRisk",
    "at risk": "AtRisk",
    "behind": "Behind",
    "critical": "Behind",
    "exceeded": "Exceeded",
    "not_started": "NotStarted",
    "not started": "NotStarted",
}


def generate_goals(scorecards, output_dir):
    """Generate Power BI Goals API payloads from scorecards.

    Creates:
      - goals_payload.json: array of scorecard goal definitions
      - goals_summary.json: summary of generated goals

    Args:
        scorecards: list of scorecard dicts from scorecard_extractor.
        output_dir: Directory to write output files.

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    goals = []
    stats = {"scorecards": 0, "goals": 0, "kpis": 0, "warnings": []}

    for sc in scorecards:
        scorecard_goals = _convert_scorecard(sc, stats)
        goals.extend(scorecard_goals)
        stats["scorecards"] += 1

    # Write goals payload
    payload_path = os.path.join(output_dir, "goals_payload.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(goals, f, indent=2, ensure_ascii=False)

    # Write summary
    summary = {
        "total_scorecards": stats["scorecards"],
        "total_goals": stats["goals"],
        "total_kpis": stats["kpis"],
        "warnings": stats["warnings"],
    }
    summary_path = os.path.join(output_dir, "goals_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(
        "Generated %d goals from %d scorecards (%d KPIs)",
        stats["goals"], stats["scorecards"], stats["kpis"],
    )
    return stats


def _convert_scorecard(scorecard, stats):
    """Convert a single scorecard to PBI Goals objects."""
    goals = []
    sc_name = scorecard.get("name", "Scorecard")

    # Root scorecard as a goal group
    for objective in scorecard.get("objectives", []):
        goal = _convert_objective(objective, sc_name, stats)
        goals.append(goal)

    # KPIs as standalone goals
    for kpi in scorecard.get("kpis", []):
        goal = _convert_kpi(kpi, sc_name, stats)
        goals.append(goal)
        stats["kpis"] += 1

    return goals


def _convert_objective(objective, scorecard_name, stats):
    """Convert a scorecard objective to a PBI Goal."""
    status = _map_status(objective.get("status", ""))
    target = objective.get("target_value")
    current = objective.get("current_value")

    goal = {
        "name": objective.get("name", ""),
        "description": objective.get("description", ""),
        "scorecardName": scorecard_name,
        "status": status,
        "owner": "",
        "startDate": None,
        "dueDate": None,
        "values": {
            "current": current,
            "target": target,
            "unit": "",
        },
        "statusRules": _convert_thresholds(objective.get("thresholds", [])),
        "subGoals": [],
        "notes": [],
    }

    # Connection to metric (if available)
    metric_name = objective.get("metric_name", "")
    if metric_name:
        goal["connectedMeasure"] = {
            "measureName": metric_name,
        }

    # Sub-objectives
    for child in objective.get("children", []):
        sub_goal = _convert_objective(child, scorecard_name, stats)
        goal["subGoals"].append(sub_goal)

    stats["goals"] += 1
    return goal


def _convert_kpi(kpi, scorecard_name, stats):
    """Convert a KPI to a PBI Goal."""
    return {
        "name": kpi.get("name", ""),
        "description": "",
        "scorecardName": scorecard_name,
        "status": "NotStarted",
        "owner": "",
        "startDate": None,
        "dueDate": None,
        "values": {
            "current": None,
            "target": kpi.get("target"),
            "unit": kpi.get("unit", ""),
        },
        "statusRules": _convert_thresholds(kpi.get("thresholds", [])),
        "subGoals": [],
        "connectedMeasure": {
            "measureName": kpi.get("name", ""),
        },
        "notes": [],
    }


def _convert_thresholds(thresholds):
    """Convert MSTR threshold bands to PBI Goals status rules."""
    rules = []
    for t in thresholds:
        rule = {
            "status": _map_status(t.get("status", t.get("name", ""))),
        }
        if t.get("min_value") is not None:
            rule["minValue"] = t["min_value"]
        if t.get("max_value") is not None:
            rule["maxValue"] = t["max_value"]
        rules.append(rule)
    return rules


def _map_status(status_str):
    """Map MSTR status string to PBI Goals status."""
    if not status_str:
        return "NotStarted"
    return _STATUS_MAP.get(status_str.lower().strip(), "NotStarted")
