"""
Pre-migration assessment module.

Produces a multi-category readiness report with GREEN/YELLOW/RED scoring,
effort estimation, and recommendations.  Used by the ``--assess`` CLI flag.

Assessment categories (14):
  1. Datasource Compatibility
  2. Expression Readiness
  3. Visual & Dossier Coverage
  4. Filter & Prompt Complexity
  5. Data Model Complexity
  6. Security & RLS
  7. Migration Scope & Effort
  8. Performance Risks
  9. Freeform SQL
  10. Custom Groups & Consolidations
  11. OLAP/Derived Metric Depth
  12. Connection Diversity
  13. Cube Complexity
  14. Unsupported Features
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

# Effort estimation (hours)
_EFFORT_BASE = 1.0
_EFFORT_PER_METRIC = 0.2
_EFFORT_PER_DERIVED = 0.5
_EFFORT_PER_APPLY_SIMPLE = 0.3
_EFFORT_PER_APPLY_OLAP = 0.8
_EFFORT_PER_PAGE = 0.15
_EFFORT_PER_PROMPT = 0.25
_EFFORT_PER_SECURITY = 0.3
_EFFORT_PER_DOSSIER = 0.5
_EFFORT_PER_REPORT = 0.3
_EFFORT_PER_FREEFORM_SQL = 0.4

# ── Feature support flags ────────────────────────────────────────

_CONNECTOR_TIERS = {
    "fully_supported": {"sql_server", "postgresql", "mysql", "snowflake", "azure_sql",
                        "azure_synapse", "csv", "excel", "odata", "json", "xml"},
    "partially_supported": {"oracle", "sap_hana", "teradata", "redshift", "databricks",
                           "bigquery", "db2", "vertica", "netezza"},
    "unsupported": {"splunk", "marketo", "servicenow", "custom_odbc"},
}

_UNSUPPORTED_VIZ_TYPES = {"network", "sankey", "box_plot", "word_cloud", "bullet"}


# ── Check/Category data model ───────────────────────────────────

class CheckItem:
    """Individual assessment check result."""

    __slots__ = ("category", "name", "severity", "detail", "recommendation")

    def __init__(self, category, name, severity, detail="", recommendation=""):
        self.category = category
        self.name = name
        self.severity = severity  # pass, info, warning, fail
        self.detail = detail
        self.recommendation = recommendation

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__}


class CategoryResult:
    """Aggregated result for one assessment category."""

    def __init__(self, name, checks):
        self.name = name
        self.checks = checks

    @property
    def worst_severity(self):
        order = {"fail": 3, "warning": 2, "info": 1, "pass": 0}
        return max((c.severity for c in self.checks), key=lambda s: order.get(s, 0), default="pass")

    def to_dict(self):
        return {"name": self.name, "worst_severity": self.worst_severity,
                "checks": [c.to_dict() for c in self.checks]}


class AssessmentReport:
    """Full assessment report."""

    def __init__(self, project_name, categories, summary):
        self.project_name = project_name
        self.categories = categories
        self.summary = summary

    @property
    def overall_score(self):
        fails = sum(1 for cat in self.categories
                    for c in cat.checks if c.severity == "fail")
        warns = sum(1 for cat in self.categories
                    for c in cat.checks if c.severity == "warning")
        if fails >= 1:
            return "RED"
        if warns > 2:
            return "YELLOW"
        return "GREEN"

    def to_dict(self):
        return {
            "project_name": self.project_name,
            "overall_score": self.overall_score,
            "categories": [c.to_dict() for c in self.categories],
            "summary": self.summary,
            "checks": [ck.to_dict() for cat in self.categories for ck in cat.checks],
        }


# ── Public API ───────────────────────────────────────────────────


def assess_project(data, output_dir=None):
    """Run a comprehensive pre-migration assessment.

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
    effort = _estimate_effort(data, counts)
    connectors = _detect_connectors(data)

    # Build 14-category checks
    categories = []
    categories.append(_check_datasource_compatibility(data, connectors))
    categories.append(_check_expression_readiness(data))
    categories.append(_check_visual_coverage(data))
    categories.append(_check_filter_prompt_complexity(data))
    categories.append(_check_data_model_complexity(data, counts))
    categories.append(_check_security_rls(data))
    categories.append(_check_migration_scope(counts, effort))
    categories.append(_check_performance_risks(data))
    categories.append(_check_freeform_sql(data))
    categories.append(_check_custom_groups(data))
    categories.append(_check_olap_depth(data))
    categories.append(_check_connection_diversity(connectors))
    categories.append(_check_cube_complexity(data))
    categories.append(_check_unsupported_features(features))

    summary = {
        "object_counts": counts,
        "total_objects": sum(counts.values()),
        "complexity_score": complexity,
        "complexity_level": _complexity_level(complexity),
        "feature_support": features,
        "estimated_fidelity": round(fidelity_estimate, 3),
        "effort_hours": round(effort, 1),
        "connectors": connectors,
        "recommendations": _build_recommendations(counts, features),
    }

    report = AssessmentReport(data.get("_project_name", "MicroStrategy Project"),
                              categories, summary)
    result = report.to_dict()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "assessment_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        html_path = os.path.join(output_dir, "assessment_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_render_html(result))

        logger.info("Assessment report written to %s", output_dir)

    return result


# ── Category checks ──────────────────────────────────────────────

def _check_datasource_compatibility(data, connectors):
    checks = []
    for c in connectors:
        cl = c.lower().replace(" ", "_")
        if cl in _CONNECTOR_TIERS["fully_supported"]:
            checks.append(CheckItem("Datasource Compatibility", f"Connector: {c}",
                                    "pass", f"{c} is fully supported"))
        elif cl in _CONNECTOR_TIERS["partially_supported"]:
            checks.append(CheckItem("Datasource Compatibility", f"Connector: {c}",
                                    "warning", f"{c} is partially supported",
                                    "Test connection string in Power BI Desktop"))
        else:
            checks.append(CheckItem("Datasource Compatibility", f"Connector: {c}",
                                    "fail", f"{c} may need manual configuration",
                                    "Use ODBC or custom M connector"))
    if not checks:
        checks.append(CheckItem("Datasource Compatibility", "No datasources", "info"))
    return CategoryResult("Datasource Compatibility", checks)


def _check_expression_readiness(data):
    checks = []
    apply_simple = 0
    apply_agg = 0
    apply_olap = 0
    for m in data.get("metrics", []):
        expr = (m.get("expression", "") or "").lower()
        if "applysimple" in expr:
            apply_simple += 1
        if "applyagg" in expr:
            apply_agg += 1
        if "applyolap" in expr:
            apply_olap += 1
    if apply_simple:
        checks.append(CheckItem("Expression Readiness", f"{apply_simple} ApplySimple metrics",
                                "warning" if apply_simple <= 5 else "fail",
                                "SQL expressions need DAX conversion",
                                "Review generated DAX for correctness"))
    if apply_agg:
        checks.append(CheckItem("Expression Readiness", f"{apply_agg} ApplyAgg metrics",
                                "fail", "Custom aggregations require manual conversion"))
    if apply_olap:
        checks.append(CheckItem("Expression Readiness", f"{apply_olap} ApplyOLAP metrics",
                                "warning", "OLAP functions use approximated DAX patterns"))
    if not checks:
        checks.append(CheckItem("Expression Readiness", "All expressions convertible", "pass"))
    return CategoryResult("Expression Readiness", checks)


def _check_visual_coverage(data):
    checks = []
    unsupported = 0
    total = 0
    for dossier in data.get("dossiers", []):
        for ch in dossier.get("chapters", []):
            for pg in ch.get("pages", []):
                for viz in pg.get("visualizations", []):
                    total += 1
                    vt = (viz.get("viz_type", "") or "").lower()
                    if vt in _UNSUPPORTED_VIZ_TYPES:
                        unsupported += 1
    if unsupported:
        checks.append(CheckItem("Visual Coverage", f"{unsupported}/{total} unsupported viz types",
                                "warning", "Will fall back to tableEx",
                                "Consider AppSource custom visuals"))
    else:
        checks.append(CheckItem("Visual Coverage", f"All {total} visuals mapped", "pass"))
    return CategoryResult("Visual Coverage", checks)


def _check_filter_prompt_complexity(data):
    checks = []
    complex_prompts = 0
    for p in data.get("prompts", []):
        pt = p.get("prompt_type", "")
        if pt in ("hierarchy", "expression"):
            complex_prompts += 1
    if complex_prompts:
        checks.append(CheckItem("Filter & Prompt Complexity",
                                f"{complex_prompts} complex prompts",
                                "warning", "Hierarchy/expression prompts need manual tuning"))
    else:
        checks.append(CheckItem("Filter & Prompt Complexity", "Simple prompts only", "pass"))
    return CategoryResult("Filter & Prompt Complexity", checks)


def _check_data_model_complexity(data, counts):
    checks = []
    tables = counts.get("datasources", 0)
    rels = counts.get("relationships", 0)
    if tables > 20:
        checks.append(CheckItem("Data Model Complexity", f"{tables} tables",
                                "warning", "Large model — verify performance"))
    if rels > 30:
        checks.append(CheckItem("Data Model Complexity", f"{rels} relationships",
                                "warning", "Many relationships — check for ambiguity"))
    if not checks:
        checks.append(CheckItem("Data Model Complexity", "Model within normal range", "pass"))
    return CategoryResult("Data Model Complexity", checks)


def _check_security_rls(data):
    checks = []
    sfs = data.get("security_filters", [])
    if sfs:
        complex_sf = sum(1 for sf in sfs if len(sf.get("target_attributes", [])) > 1)
        if complex_sf:
            checks.append(CheckItem("Security & RLS", f"{complex_sf} multi-attribute filters",
                                    "warning", "Complex RLS — verify DAX filter expressions"))
        else:
            checks.append(CheckItem("Security & RLS", f"{len(sfs)} simple RLS filters",
                                    "pass"))
    else:
        checks.append(CheckItem("Security & RLS", "No security filters", "info"))
    return CategoryResult("Security & RLS", checks)


def _check_migration_scope(counts, effort):
    checks = []
    total = sum(counts.values())
    sev = "pass" if effort < 8 else "warning" if effort < 24 else "fail"
    checks.append(CheckItem("Migration Scope", f"{total} objects, ~{effort:.1f}h estimated",
                            sev, f"Effort estimate: {effort:.1f} hours"))
    return CategoryResult("Migration Scope & Effort", checks)


def _check_performance_risks(data):
    checks = []
    # High cardinality: tables with many columns
    for ds in data.get("datasources", []):
        cols = len(ds.get("columns", []))
        if cols > 50:
            checks.append(CheckItem("Performance Risks", f"{ds['name']}: {cols} columns",
                                    "warning", "Wide table may impact performance"))
    if not checks:
        checks.append(CheckItem("Performance Risks", "No performance concerns", "pass"))
    return CategoryResult("Performance Risks", checks)


def _check_freeform_sql(data):
    checks = []
    ffs = data.get("freeform_sql", [])
    if ffs:
        checks.append(CheckItem("Freeform SQL", f"{len(ffs)} freeform SQL objects",
                                "warning", "Migrated as Value.NativeQuery()",
                                "Verify SQL dialect compatibility"))
    else:
        checks.append(CheckItem("Freeform SQL", "No freeform SQL", "pass"))
    return CategoryResult("Freeform SQL", checks)


def _check_custom_groups(data):
    checks = []
    cg = data.get("custom_groups", [])
    cons = data.get("consolidations", [])
    if cg:
        checks.append(CheckItem("Custom Groups", f"{len(cg)} custom groups",
                                "warning", "Require manual DAX grouping logic"))
    if cons:
        checks.append(CheckItem("Custom Groups", f"{len(cons)} consolidations",
                                "fail", "No Power BI native equivalent"))
    if not checks:
        checks.append(CheckItem("Custom Groups", "None detected", "pass"))
    return CategoryResult("Custom Groups & Consolidations", checks)


def _check_olap_depth(data):
    checks = []
    dm = data.get("derived_metrics", [])
    if dm:
        olap_types = set()
        for m in dm:
            expr = (m.get("expression", "") or "").lower()
            for pattern in ("runningsum", "runningavg", "movingavg", "lag(", "lead(",
                            "ntile", "rank"):
                if pattern in expr:
                    olap_types.add(pattern.rstrip("("))
        if olap_types:
            checks.append(CheckItem("OLAP Depth", f"{len(dm)} derived metrics ({', '.join(olap_types)})",
                                    "warning", "Converted with approximated DAX window patterns"))
        else:
            checks.append(CheckItem("OLAP Depth", f"{len(dm)} derived metrics", "pass"))
    else:
        checks.append(CheckItem("OLAP Depth", "No derived metrics", "pass"))
    return CategoryResult("OLAP/Derived Metric Depth", checks)


def _check_connection_diversity(connectors):
    checks = []
    if len(connectors) > 3:
        checks.append(CheckItem("Connection Diversity", f"{len(connectors)} different connector types",
                                "warning", "Multi-source model — consider Composite mode"))
    else:
        checks.append(CheckItem("Connection Diversity", f"{len(connectors)} connector(s)", "pass"))
    return CategoryResult("Connection Diversity", checks)


def _check_cube_complexity(data):
    checks = []
    cubes = data.get("cubes", [])
    if cubes:
        checks.append(CheckItem("Cube Complexity", f"{len(cubes)} cubes",
                                "info", "Cubes mapped to Import-mode tables"))
    else:
        checks.append(CheckItem("Cube Complexity", "No cubes", "pass"))
    return CategoryResult("Cube Complexity", checks)


def _check_unsupported_features(features):
    checks = []
    for feat, status in features.items():
        if status == "unsupported":
            checks.append(CheckItem("Unsupported Features", feat, "fail",
                                    "No automatic conversion available"))
    if not checks:
        checks.append(CheckItem("Unsupported Features", "None detected", "pass"))
    return CategoryResult("Unsupported Features", checks)


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
    score = 0
    score += counts["reports"] * _OBJECT_WEIGHTS["report"]
    score += counts["dossiers"] * _OBJECT_WEIGHTS["dossier"]
    score += counts["cubes"] * _OBJECT_WEIGHTS["cube"]
    score += counts["security_filters"] * _OBJECT_WEIGHTS["security_filter"]
    score += counts["prompts"] * _OBJECT_WEIGHTS["prompt"]
    score += counts["custom_groups"] * _OBJECT_WEIGHTS["custom_group"]
    score += counts["freeform_sql"] * _OBJECT_WEIGHTS["freeform_sql"]

    for m in data.get("metrics", []):
        mt = m.get("metric_type", "simple")
        score += _OBJECT_WEIGHTS.get(f"metric_{mt}", 1)
    for m in data.get("derived_metrics", []):
        score += _OBJECT_WEIGHTS["metric_derived"]

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
    features = {}
    for m in data.get("derived_metrics", []):
        expr = (m.get("expression", "") or "").lower()
        if "runningsum" in expr:
            features["olap_running_sum"] = "approximated"
        if "movingavg" in expr:
            features["olap_moving_avg"] = "approximated"
        if "lag(" in expr or "lead(" in expr:
            features["olap_lag_lead"] = "approximated"

    for m in data.get("metrics", []):
        expr = (m.get("expression", "") or "").lower()
        if "applysimple" in expr:
            features["apply_simple_complex_sql"] = "unsupported"

    if data.get("custom_groups"):
        features["custom_groups"] = "manual_review"
    if data.get("freeform_sql"):
        features["freeform_sql"] = "supported"
    if data.get("security_filters"):
        features["row_level_security"] = "approximated"

    for dossier in data.get("dossiers", []):
        for chapter in dossier.get("chapters", []):
            for page in chapter.get("pages", []):
                for viz in page.get("visualizations", []):
                    vtype = (viz.get("viz_type", "") or "").lower()
                    if vtype in _UNSUPPORTED_VIZ_TYPES:
                        features[f"{vtype}_visualization"] = "unsupported"
    return features


def _detect_connectors(data):
    connectors = set()
    for ds in data.get("datasources", []):
        db = ds.get("db_connection", {})
        ct = db.get("db_type", "")
        if ct:
            connectors.add(ct)
    return sorted(connectors)


# ── Effort estimation ────────────────────────────────────────────

def _estimate_effort(data, counts):
    effort = _EFFORT_BASE
    effort += counts.get("metrics", 0) * _EFFORT_PER_METRIC
    effort += counts.get("derived_metrics", 0) * _EFFORT_PER_DERIVED
    effort += counts.get("dossiers", 0) * _EFFORT_PER_DOSSIER
    effort += counts.get("reports", 0) * _EFFORT_PER_REPORT
    effort += counts.get("prompts", 0) * _EFFORT_PER_PROMPT
    effort += counts.get("security_filters", 0) * _EFFORT_PER_SECURITY
    effort += counts.get("freeform_sql", 0) * _EFFORT_PER_FREEFORM_SQL

    # Count pages in dossiers
    for d in data.get("dossiers", []):
        for ch in d.get("chapters", []):
            effort += len(ch.get("pages", [])) * _EFFORT_PER_PAGE

    # ApplySimple/ApplyOLAP surcharges
    for m in data.get("metrics", []):
        expr = (m.get("expression", "") or "").lower()
        if "applysimple" in expr:
            effort += _EFFORT_PER_APPLY_SIMPLE
        if "applyolap" in expr:
            effort += _EFFORT_PER_APPLY_OLAP

    return effort


# ── Fidelity estimation ──────────────────────────────────────────

def _estimate_fidelity(counts, features):
    total = sum(counts.values())
    if total == 0:
        return 0.0

    unsupported_count = sum(1 for v in features.values() if v == "unsupported")
    approximated_count = sum(1 for v in features.values() if v == "approximated")
    manual_count = sum(1 for v in features.values() if v == "manual_review")

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

    summary = report.get("summary", report)
    counts = summary.get("object_counts", {})
    features = summary.get("feature_support", {})
    recs = summary.get("recommendations", [])
    categories = report.get("categories", [])
    score = report.get("overall_score", "GREEN")
    effort = summary.get("effort_hours", 0)

    score_color = {"GREEN": "#107c10", "YELLOW": "#ff8c00", "RED": "#a80000"}.get(score, "#333")

    count_rows = "\n".join(
        f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in counts.items() if v > 0
    )

    cat_rows = []
    sev_color = {"pass": "#107c10", "info": "#0078d4", "warning": "#ff8c00", "fail": "#a80000"}
    for cat in categories:
        ws = cat.get("worst_severity", "pass")
        cat_rows.append(
            f"<tr><td>{esc(cat['name'])}</td>"
            f"<td style='color:{sev_color.get(ws, '#333')};font-weight:bold'>{ws.upper()}</td>"
            f"<td>{len(cat.get('checks', []))}</td></tr>"
        )
    cat_table = "\n".join(cat_rows)

    check_rows = []
    for chk in report.get("checks", []):
        sv = chk.get("severity", "info")
        check_rows.append(
            f"<tr><td>{esc(chk.get('category', ''))}</td>"
            f"<td>{esc(chk.get('name', ''))}</td>"
            f"<td style='color:{sev_color.get(sv, '#333')}'>{sv.upper()}</td>"
            f"<td>{esc(chk.get('detail', ''))}</td>"
            f"<td>{esc(chk.get('recommendation', ''))}</td></tr>"
        )
    checks_table = "\n".join(check_rows)

    feature_rows = "\n".join(
        f"<tr><td>{esc(k)}</td><td><span class='badge {esc(v)}'>{esc(v)}</span></td></tr>"
        for k, v in features.items()
    ) if features else "<tr><td colspan='2'>No special features detected</td></tr>"

    rec_items = "\n".join(f"<li>{esc(r)}</li>" for r in recs)

    level = summary.get("complexity_level", "low")
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
  <div class="card"><div class="num" style="color:{score_color}">{score}</div><div class="label">Overall Score</div></div>
  <div class="card"><div class="num">{summary.get('total_objects', 0)}</div><div class="label">Total Objects</div></div>
  <div class="card"><div class="num" style="color:{level_color}">{summary.get('complexity_score', 0)}</div><div class="label">Complexity ({level})</div></div>
  <div class="card"><div class="num">{summary.get('estimated_fidelity', 0):.0%}</div><div class="label">Est. Fidelity</div></div>
  <div class="card"><div class="num">{effort:.1f}h</div><div class="label">Est. Effort</div></div>
</div>

<h2>Assessment Categories (14)</h2>
<table>
<thead><tr><th>Category</th><th>Status</th><th>Checks</th></tr></thead>
<tbody>{cat_table}</tbody>
</table>

<h2>Detailed Checks</h2>
<table>
<thead><tr><th>Category</th><th>Check</th><th>Severity</th><th>Detail</th><th>Recommendation</th></tr></thead>
<tbody>{checks_table}</tbody>
</table>

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
