"""
Pre-migration assessment module.

Produces a complexity/readiness report without actually generating
any output.  Used by the ``--assess`` CLI flag.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── Complexity weights ───────────────────────────────────────────

_OBJECT_WEIGHTS = {
    "report": 1,
    "dossier": 3,
    "cube": 2,
    "metric_simple": 1,
    "metric_compound": 2,
    "metric_derived": 3,
    "security_filter": 2,
    "prompt": 1,
    "custom_group": 4,
    "freeform_sql": 3,
}


# ── Feature support flags ────────────────────────────────────────

_UNSUPPORTED_FEATURES = {
    "network_visualization",
    "sankey_visualization",
    "makepoint_spatial",
    "apply_simple_complex_sql",
}

_APPROXIMATED_FEATURES = {
    "olap_running_sum",
    "olap_moving_avg",
    "olap_lag_lead",
    "prompt_hierarchy",
    "threshold_icon",
}


# ── Public API ───────────────────────────────────────────────────


def assess_project(data, output_dir=None):
    """Run a pre-migration assessment.

    Args:
        data: dict with all intermediate JSON keys
        output_dir: if provided, write assessment report JSON/HTML here

    Returns:
        dict with assessment results
    """
    counts = _count_objects(data)
    complexity = _compute_complexity(data, counts)
    features = _detect_features(data)
    fidelity_estimate = _estimate_fidelity(counts, features)

    report = {
        "object_counts": counts,
        "total_objects": sum(counts.values()),
        "complexity_score": complexity,
        "complexity_level": _complexity_level(complexity),
        "feature_support": features,
        "estimated_fidelity": round(fidelity_estimate, 3),
        "recommendations": _build_recommendations(counts, features),
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "assessment_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        html_path = os.path.join(output_dir, "assessment_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_render_html(report))

        logger.info("Assessment report written to %s", output_dir)

    return report


# ── Object counting ──────────────────────────────────────────────


def _count_objects(data):
    counts = {
        "datasources": len(data.get("datasources", [])),
        "attributes": len(data.get("attributes", [])),
        "facts": len(data.get("facts", [])),
        "metrics": len(data.get("metrics", [])),
        "derived_metrics": len(data.get("derived_metrics", [])),
        "reports": len(data.get("reports", [])),
        "dossiers": len(data.get("dossiers", [])),
        "cubes": len(data.get("cubes", [])),
        "prompts": len(data.get("prompts", [])),
        "security_filters": len(data.get("security_filters", [])),
        "custom_groups": len(data.get("custom_groups", [])),
        "freeform_sql": len(data.get("freeform_sql", [])),
        "hierarchies": len(data.get("hierarchies", [])),
        "relationships": len(data.get("relationships", [])),
    }
    return counts


# ── Complexity scoring ───────────────────────────────────────────


def _compute_complexity(data, counts):
    """Compute a 0–100 complexity score."""
    score = 0
    score += counts["reports"] * _OBJECT_WEIGHTS["report"]
    score += counts["dossiers"] * _OBJECT_WEIGHTS["dossier"]
    score += counts["cubes"] * _OBJECT_WEIGHTS["cube"]
    score += counts["security_filters"] * _OBJECT_WEIGHTS["security_filter"]
    score += counts["prompts"] * _OBJECT_WEIGHTS["prompt"]
    score += counts["custom_groups"] * _OBJECT_WEIGHTS["custom_group"]
    score += counts["freeform_sql"] * _OBJECT_WEIGHTS["freeform_sql"]

    # Metric complexity
    for m in data.get("metrics", []):
        mt = m.get("metric_type", "simple")
        score += _OBJECT_WEIGHTS.get(f"metric_{mt}", 1)
    for m in data.get("derived_metrics", []):
        score += _OBJECT_WEIGHTS["metric_derived"]

    # Cap at 100
    return min(score, 100)


def _complexity_level(score):
    if score <= 20:
        return "low"
    elif score <= 50:
        return "medium"
    elif score <= 80:
        return "high"
    return "very_high"


# ── Feature detection ────────────────────────────────────────────


def _detect_features(data):
    """Detect which features are present and their support level."""
    features = {}

    # Check for OLAP/derived metric features
    for m in data.get("derived_metrics", []):
        expr = m.get("expression", "").lower()
        if "runningsum" in expr:
            features["olap_running_sum"] = "approximated"
        if "movingavg" in expr:
            features["olap_moving_avg"] = "approximated"
        if "lag(" in expr or "lead(" in expr:
            features["olap_lag_lead"] = "approximated"

    # Check for ApplySimple in metrics
    for m in data.get("metrics", []):
        expr = m.get("expression", "").lower()
        if "applysimple" in expr:
            features["apply_simple_complex_sql"] = "unsupported"

    # Check for custom groups
    if data.get("custom_groups"):
        features["custom_groups"] = "manual_review"

    # Check for freeform SQL
    if data.get("freeform_sql"):
        features["freeform_sql"] = "supported"

    # Check for security filters
    if data.get("security_filters"):
        features["row_level_security"] = "approximated"

    # Check visualizations for unsupported types
    for dossier in data.get("dossiers", []):
        for chapter in dossier.get("chapters", []):
            for page in chapter.get("pages", []):
                for viz in page.get("visualizations", []):
                    vtype = viz.get("viz_type", "").lower()
                    if vtype in ("network", "sankey"):
                        features[f"{vtype}_visualization"] = "unsupported"

    return features


# ── Fidelity estimation ──────────────────────────────────────────


def _estimate_fidelity(counts, features):
    """Estimate the migration fidelity as 0.0–1.0."""
    total = sum(counts.values())
    if total == 0:
        return 0.0

    unsupported_count = sum(1 for v in features.values() if v == "unsupported")
    approximated_count = sum(1 for v in features.values() if v == "approximated")
    manual_count = sum(1 for v in features.values() if v == "manual_review")

    # Penalty: each unsupported feature reduces fidelity
    penalty = (unsupported_count * 0.10) + (approximated_count * 0.03) + (manual_count * 0.05)
    return max(0.0, min(1.0, 1.0 - penalty))


# ── Recommendations ──────────────────────────────────────────────


def _build_recommendations(counts, features):
    recs = []
    if features.get("apply_simple_complex_sql") == "unsupported":
        recs.append("ApplySimple SQL metrics detected — these will need manual DAX conversion")
    if features.get("custom_groups") == "manual_review":
        recs.append("Custom groups detected — create calculated columns or DAX grouping logic manually")
    if features.get("row_level_security") == "approximated":
        recs.append("Security filters will be migrated as RLS roles — verify filter expressions in Power BI")
    if features.get("network_visualization") == "unsupported":
        recs.append("Network visualizations have no built-in Power BI equivalent — use AppSource custom visuals")
    if any(k.startswith("olap_") for k in features):
        recs.append("OLAP/derived metrics use approximated DAX window patterns — verify results after migration")
    if counts.get("freeform_sql", 0) > 0:
        recs.append("Freeform SQL tables detected — review generated Value.NativeQuery() expressions")
    if not recs:
        recs.append("No major migration risks detected — proceed with confidence")
    return recs


# ── HTML renderer ────────────────────────────────────────────────


def _render_html(report):
    from html import escape as esc

    counts = report["object_counts"]
    features = report["feature_support"]
    recs = report["recommendations"]

    count_rows = "\n".join(
        f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in counts.items() if v > 0
    )

    feature_rows = "\n".join(
        f"<tr><td>{esc(k)}</td><td><span class='badge {esc(v)}'>{esc(v)}</span></td></tr>"
        for k, v in features.items()
    ) if features else "<tr><td colspan='2'>No special features detected</td></tr>"

    rec_items = "\n".join(f"<li>{esc(r)}</li>" for r in recs)

    level = report["complexity_level"]
    level_color = {"low": "#107c10", "medium": "#ff8c00", "high": "#d83b01", "very_high": "#a80000"}.get(level, "#333")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pre-Migration Assessment</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 2rem; color: #333; }}
h1 {{ color: #0078d4; }}
.card {{ display: inline-block; background: #f3f3f3; border-radius: 8px;
         padding: 1rem 1.5rem; margin: 0.5rem; text-align: center; }}
.card .num {{ font-size: 2rem; font-weight: bold; }}
.card .label {{ font-size: 0.85rem; color: #666; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #0078d4; color: #fff; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; color: #fff; }}
.supported {{ background: #107c10; }}
.approximated {{ background: #ff8c00; }}
.manual_review {{ background: #d83b01; }}
.unsupported {{ background: #a80000; }}
</style>
</head>
<body>
<h1>Pre-Migration Assessment</h1>

<div>
  <div class="card"><div class="num">{report['total_objects']}</div><div class="label">Total Objects</div></div>
  <div class="card"><div class="num" style="color:{level_color}">{report['complexity_score']}</div><div class="label">Complexity ({level})</div></div>
  <div class="card"><div class="num">{report['estimated_fidelity']:.0%}</div><div class="label">Est. Fidelity</div></div>
</div>

<h2>Object Counts</h2>
<table>
<thead><tr><th>Object Type</th><th>Count</th></tr></thead>
<tbody>{count_rows}</tbody>
</table>

<h2>Feature Support</h2>
<table>
<thead><tr><th>Feature</th><th>Status</th></tr></thead>
<tbody>{feature_rows}</tbody>
</table>

<h2>Recommendations</h2>
<ul>{rec_items}</ul>
</body>
</html>"""
