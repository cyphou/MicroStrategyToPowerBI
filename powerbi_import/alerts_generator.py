"""
Alerts generator — extract MSTR thresholds and convert to PBI alert rules.

Sources:
  1. ``thresholds.json`` — metric thresholds from reports/dossiers
  2. ``metrics.json``    — metric definitions with built-in thresholds
  3. ``prompts.json``    — numeric prompts that act as alert boundaries

Output: ``alert_rules.json`` with PBI-compatible data-driven alert definitions.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Operator normalisation
# ---------------------------------------------------------------------------

_OPERATOR_MAP = {
    "less_than": "<",
    "less_than_or_equal": "<=",
    "greater_than": ">",
    "greater_than_or_equal": ">=",
    "equal": "=",
    "not_equal": "!=",
    "between": "between",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "=": "=",
    "!=": "!=",
}


def _normalise_operator(op):
    """Normalise MSTR operator strings to symbols."""
    return _OPERATOR_MAP.get(op, op)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_alerts(data):
    """Extract alert candidates from all available sources.

    Args:
        data: dict with keys ``thresholds``, ``metrics``, ``prompts``.

    Returns:
        list of alert dicts: ``{name, measure, operator, threshold, source}``.
    """
    alerts = []

    # Source 1: explicit thresholds
    for th in data.get("thresholds", []):
        metric_name = th.get("metric_name", "Unknown")
        for cond in th.get("conditions", []):
            alerts.append({
                "name": f"{metric_name} alert",
                "measure": metric_name,
                "operator": _normalise_operator(cond.get("operator", ">")),
                "threshold": cond.get("value", 0),
                "source": "threshold",
                "report_id": th.get("report_id", ""),
            })

    # Source 2: metrics with embedded thresholds
    for m in data.get("metrics", []):
        for th in m.get("thresholds", []):
            for cond in th.get("conditions", []):
                alerts.append({
                    "name": f"{m.get('name', 'Metric')} alert",
                    "measure": m.get("name", "Metric"),
                    "operator": _normalise_operator(cond.get("operator", ">")),
                    "threshold": cond.get("value", 0),
                    "source": "metric_threshold",
                })

    # Source 3: numeric prompts with default values (boundary prompts)
    for p in data.get("prompts", []):
        if p.get("type") in ("numeric", "value") and p.get("default_value") is not None:
            try:
                val = float(p["default_value"])
            except (ValueError, TypeError):
                continue
            alerts.append({
                "name": f"{p.get('name', 'Prompt')} boundary",
                "measure": p.get("linked_metric", p.get("name", "Prompt")),
                "operator": ">=",
                "threshold": val,
                "source": "prompt",
            })

    return alerts


# ---------------------------------------------------------------------------
# Rule generation
# ---------------------------------------------------------------------------

def generate_alert_rules(alerts):
    """Convert raw alerts into PBI-compatible data-driven alert rule defs.

    Returns:
        list of rule dicts ready for serialisation.
    """
    rules = []
    for i, alert in enumerate(alerts, 1):
        rule = {
            "id": f"alert_{i:03d}",
            "name": alert.get("name", f"Alert {i}"),
            "measure": alert.get("measure", ""),
            "condition": {
                "operator": alert.get("operator", ">"),
                "threshold": alert.get("threshold", 0),
            },
            "frequency": "daily",
            "enabled": True,
            "source": alert.get("source", "unknown"),
        }
        if alert.get("report_id"):
            rule["report_id"] = alert["report_id"]
        rules.append(rule)
    return rules


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_alert_rules(rules, output_dir):
    """Write alert rules to ``alert_rules.json``.

    Returns:
        Path to the written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "alert_rules.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d alert rules to %s", len(rules), path)
    return path
