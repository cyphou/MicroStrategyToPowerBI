"""
Metric extractor for MicroStrategy.

Extracts metric definitions (simple, compound, derived/OLAP) and
threshold (conditional formatting) definitions.
"""

import logging

logger = logging.getLogger(__name__)


def extract_metrics(client):
    """Extract all metrics from the project.

    Returns:
        (metrics, derived_metrics) — two lists of metric dicts.
    """
    raw_metrics = client.get_metrics()
    metrics = []
    derived = []

    for m in raw_metrics:
        try:
            detail = client.get_metric(m['id'])
        except Exception as e:
            logger.warning("Failed to get metric details for '%s': %s", m.get('name', ''), e)
            detail = m

        metric = _parse_metric(detail, m)
        if metric.get("metric_type") == "derived":
            derived.append(metric)
        else:
            metrics.append(metric)

    logger.info("Extracted %d simple/compound metrics, %d derived metrics", len(metrics), len(derived))
    return metrics, derived


def extract_thresholds(visualization_def):
    """Extract thresholds (conditional formatting) from a visualization definition.

    Returns list of threshold dicts.
    """
    thresholds = []
    for threshold in visualization_def.get("thresholds", []) or []:
        t = {
            "name": threshold.get("name", ""),
            "metric_name": threshold.get("metricName", ""),
            "conditions": _extract_threshold_conditions(threshold),
            "format": _extract_threshold_format(threshold),
        }
        thresholds.append(t)
    return thresholds


# ── Internal helpers ─────────────────────────────────────────────

def _parse_metric(detail, summary):
    """Parse a metric definition into our intermediate format."""
    metric_type = _classify_metric_type(detail)

    metric = {
        "id": detail.get("id", summary.get("id", "")),
        "name": detail.get("name", summary.get("name", "")),
        "description": detail.get("description", ""),
        "metric_type": metric_type,
        "expression": _extract_expression_text(detail),
        "aggregation": _extract_aggregation(detail),
        "column_ref": _extract_column_ref(detail),
        "format_string": _extract_format_string(detail),
        "subtotal_type": detail.get("subtotalType", ""),
        "folder_path": _extract_folder_path(summary),
        "is_smart_metric": _is_smart_metric(detail),
        "dependencies": _extract_metric_dependencies(detail),
    }
    return metric


def _classify_metric_type(detail):
    """Classify metric as simple, compound, or derived."""
    # Check explicit metricType from the API response first
    explicit_type = detail.get("metricType", "")
    if explicit_type in ("simple", "compound", "derived"):
        return explicit_type

    subtype = detail.get("subtype", 0) or detail.get("subType", 0)

    # MicroStrategy metric subtypes
    if subtype == 786432:  # Derived metric
        return "derived"
    if subtype == 786433:  # Smart metric (OLAP)
        return "derived"

    expression = _extract_expression_text(detail)
    if not expression:
        return "simple"

    # Check for OLAP function keywords
    olap_keywords = ["Rank(", "RunningSum(", "RunningAvg(", "RunningCount(",
                     "MovingAvg(", "MovingSum(", "Lag(", "Lead(", "NTile(",
                     "OLAPRank(", "FirstInRange(", "LastInRange("]
    for kw in olap_keywords:
        if kw.lower() in expression.lower():
            return "derived"

    # Check for compound metric (references other metrics)
    if _has_metric_references(expression):
        return "compound"

    return "simple"


def _extract_expression_text(detail):
    """Extract the expression text from a metric definition."""
    expr = detail.get("expression", {})
    if isinstance(expr, str):
        return expr
    if isinstance(expr, dict):
        return expr.get("text", "") or expr.get("expressionText", "")
    # Try tokens-based expression
    tokens = detail.get("tokens", []) or detail.get("expression", {}).get("tokens", [])
    if tokens:
        return " ".join(t.get("value", "") for t in tokens)
    return ""


def _extract_aggregation(detail):
    """Extract the aggregation function."""
    # From metric function type
    func = detail.get("metricFunction", "") or detail.get("function", "")
    if func:
        return func.lower()

    # Infer from expression
    expression = _extract_expression_text(detail)
    if expression:
        for agg in ["sum", "avg", "count", "min", "max", "stdev", "median"]:
            if expression.lower().startswith(f"{agg}("):
                return agg

    return "sum"


def _extract_column_ref(detail):
    """Extract the column reference (Table[Column] format) for simple metrics."""
    # From fact reference
    facts = detail.get("facts", []) or detail.get("target", {}).get("facts", []) or []
    if facts:
        fact = facts[0]
        table = fact.get("tableName", "Table")
        column = fact.get("columnName", fact.get("name", ""))
        if column:
            return f"{table}[{column}]"
    return ""


def _extract_format_string(detail):
    """Extract number format string."""
    fmt = detail.get("formatString", "") or detail.get("format", {}).get("formatString", "")
    return fmt


def _extract_folder_path(summary):
    """Extract the folder location for display folder mapping."""
    ancestors = summary.get("ancestors", []) or []
    if ancestors:
        return "/".join(a.get("name", "") for a in ancestors if a.get("name"))
    return ""


def _is_smart_metric(detail):
    """Check if this is a smart metric (OLAP function)."""
    subtype = detail.get("subtype", 0) or detail.get("subType", 0)
    return subtype == 786433


def _has_metric_references(expression):
    """Check if expression references other metrics (compound metric)."""
    import re
    # Heuristic: look for arithmetic operators between function calls or values
    # e.g. "Sum(Revenue) - Sum(Cost)" or "MetricA / MetricB"
    return bool(re.search(r'[\w)]\s*[-+*/]\s*[\w(]', expression))


def _extract_metric_dependencies(detail):
    """Extract metric dependencies (other metrics this one references)."""
    deps = []
    for dep in detail.get("dependentObjects", []) or detail.get("dependencies", []) or []:
        if isinstance(dep, str):
            deps.append({"id": dep, "name": ""})
        elif isinstance(dep, dict) and dep.get("type") == 4:  # Metric type
            deps.append({
                "id": dep.get("id", ""),
                "name": dep.get("name", ""),
            })
    return deps


def _extract_threshold_conditions(threshold):
    """Extract conditions from a threshold definition."""
    conditions = []
    for cond in threshold.get("conditions", []) or []:
        conditions.append({
            "operator": cond.get("operator", ""),
            "value": cond.get("value", ""),
            "type": cond.get("type", "value"),
        })
    return conditions


def _extract_threshold_format(threshold):
    """Extract formatting from a threshold definition."""
    fmt = threshold.get("format", {}) or {}
    return {
        "background_color": fmt.get("backgroundColor", ""),
        "font_color": fmt.get("fontColor", ""),
        "font_weight": fmt.get("fontWeight", ""),
        "icon": fmt.get("icon", ""),
    }
