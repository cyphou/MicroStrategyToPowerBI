"""
Pre-migration governance report.

Generates an HTML checklist covering data ownership, sensitivity
classification coverage, RLS completeness, lineage gaps, and migration
readiness across all extracted MicroStrategy objects.
"""

import html
import json
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Check categories ─────────────────────────────────────────────

_CATEGORY_OWNERSHIP = "Data Ownership"
_CATEGORY_CLASSIFICATION = "Sensitivity Classification"
_CATEGORY_RLS = "Row-Level Security"
_CATEGORY_LINEAGE = "Lineage Coverage"
_CATEGORY_DOCUMENTATION = "Documentation"
_CATEGORY_READINESS = "Migration Readiness"

_ALL_CATEGORIES = [
    _CATEGORY_OWNERSHIP,
    _CATEGORY_CLASSIFICATION,
    _CATEGORY_RLS,
    _CATEGORY_LINEAGE,
    _CATEGORY_DOCUMENTATION,
    _CATEGORY_READINESS,
]


# ── Public API ───────────────────────────────────────────────────

def generate_governance_report(data, output_path, *, lineage_graph=None):
    """Run governance checks and produce an HTML report.

    Args:
        data: dict with intermediate JSON keys
        output_path: Path for the output .html file
        lineage_graph: Optional LineageGraph for lineage-gap analysis

    Returns:
        dict with {category: [CheckResult, ...]}
    """
    results = {}
    results[_CATEGORY_OWNERSHIP] = _check_ownership(data)
    results[_CATEGORY_CLASSIFICATION] = _check_classification(data)
    results[_CATEGORY_RLS] = _check_rls(data)
    results[_CATEGORY_LINEAGE] = _check_lineage(data, lineage_graph)
    results[_CATEGORY_DOCUMENTATION] = _check_documentation(data)
    results[_CATEGORY_READINESS] = _check_readiness(data)

    _write_html(results, output_path)
    logger.info("Governance report written to %s", output_path)
    return results


def compute_governance_score(results):
    """Compute an overall governance score (0–100) from check results.

    Each PASS=1, WARN=0.5, FAIL=0.  Score = (points / total) * 100.
    """
    total = 0
    points = 0.0
    for checks in results.values():
        for c in checks:
            total += 1
            if c["status"] == "PASS":
                points += 1
            elif c["status"] == "WARN":
                points += 0.5
    return round(points / total * 100, 1) if total else 100.0


# ── Check implementations ────────────────────────────────────────

def _check_ownership(data):
    """Verify that source tables have identifiable owners / connections."""
    checks = []
    datasources = data.get("datasources", [])
    tables_with_conn = sum(1 for ds in datasources
                           if ds.get("db_connection", {}).get("name"))
    total = len(datasources)
    pct = (tables_with_conn / total * 100) if total else 100

    checks.append({
        "name": "Tables with identified data source connection",
        "status": "PASS" if pct >= 90 else ("WARN" if pct >= 50 else "FAIL"),
        "detail": f"{tables_with_conn}/{total} tables ({pct:.0f}%) have a named connection",
    })

    # Check for orphan tables (no attributes or facts reference them)
    attr_tables = set()
    for a in data.get("attributes", []):
        for form in a.get("forms", []):
            t = form.get("table_name") or form.get("table", "")
            if t:
                attr_tables.add(t)
    for f in data.get("facts", []):
        for expr in f.get("expressions", []):
            t = expr.get("table", "")
            if t:
                attr_tables.add(t)
    orphans = [ds["name"] for ds in datasources if ds["name"] not in attr_tables]
    checks.append({
        "name": "No orphan tables",
        "status": "PASS" if not orphans else "WARN",
        "detail": f"{len(orphans)} orphan table(s)" + (f": {', '.join(orphans[:5])}" if orphans else ""),
    })
    return checks


def _check_classification(data):
    """Assess sensitivity classification coverage."""
    checks = []
    security_filters = data.get("security_filters", [])
    attributes = data.get("attributes", [])

    # How many attributes are protected by security filters?
    protected_ids = set()
    for sf in security_filters:
        for t in sf.get("target_attributes", []):
            protected_ids.add(t.get("id", ""))
    total_attrs = len(attributes)
    protected_pct = (len(protected_ids) / total_attrs * 100) if total_attrs else 0

    checks.append({
        "name": "Attributes covered by security filters",
        "status": "PASS" if protected_pct >= 10 else ("WARN" if security_filters else "FAIL"),
        "detail": f"{len(protected_ids)}/{total_attrs} attributes ({protected_pct:.0f}%) have security filters",
    })

    # Are there security filters at all?
    checks.append({
        "name": "Security filters defined",
        "status": "PASS" if security_filters else "WARN",
        "detail": f"{len(security_filters)} security filter(s) found",
    })
    return checks


def _check_rls(data):
    """Verify RLS readiness."""
    checks = []
    security_filters = data.get("security_filters", [])

    # RLS filters should have target attributes and expressions
    valid = sum(1 for sf in security_filters
                if sf.get("target_attributes") and sf.get("expression"))
    total = len(security_filters)

    if total == 0:
        checks.append({
            "name": "RLS filter completeness",
            "status": "WARN",
            "detail": "No security filters to migrate — consider adding RLS in Power BI",
        })
    else:
        pct = valid / total * 100
        checks.append({
            "name": "RLS filter completeness",
            "status": "PASS" if pct >= 80 else ("WARN" if pct >= 50 else "FAIL"),
            "detail": f"{valid}/{total} filters ({pct:.0f}%) have valid expressions",
        })
    return checks


def _check_lineage(data, lineage_graph):
    """Assess lineage coverage."""
    checks = []
    if lineage_graph is None:
        checks.append({
            "name": "Lineage graph available",
            "status": "WARN",
            "detail": "No lineage graph provided — run with --lineage to generate",
        })
        return checks

    checks.append({
        "name": "Lineage graph available",
        "status": "PASS",
        "detail": f"{lineage_graph.node_count} nodes, {lineage_graph.edge_count} edges",
    })

    # Check for orphan nodes (no incoming or outgoing edges)
    orphans = [n for n in lineage_graph.nodes.values()
               if not lineage_graph.get_parents(n.id)
               and not lineage_graph.get_children(n.id)]
    checks.append({
        "name": "No orphan lineage nodes",
        "status": "PASS" if not orphans else "WARN",
        "detail": f"{len(orphans)} orphan node(s)" + (
            f": {', '.join(n.name for n in orphans[:5])}" if orphans else ""),
    })

    # Cycles
    cycles = lineage_graph.detect_cycles()
    checks.append({
        "name": "No cycles in lineage graph",
        "status": "PASS" if not cycles else "FAIL",
        "detail": f"{len(cycles)} cycle(s) detected" if cycles else "DAG is acyclic",
    })
    return checks


def _check_documentation(data):
    """Check documentation coverage (descriptions on objects)."""
    checks = []

    # Metrics with descriptions
    all_metrics = data.get("metrics", []) + data.get("derived_metrics", [])
    described = sum(1 for m in all_metrics if m.get("description"))
    total = len(all_metrics)
    pct = (described / total * 100) if total else 100

    checks.append({
        "name": "Metrics with descriptions",
        "status": "PASS" if pct >= 70 else ("WARN" if pct >= 30 else "FAIL"),
        "detail": f"{described}/{total} metrics ({pct:.0f}%) have descriptions",
    })

    # Attributes with descriptions
    attrs = data.get("attributes", [])
    described_a = sum(1 for a in attrs if a.get("description"))
    total_a = len(attrs)
    pct_a = (described_a / total_a * 100) if total_a else 100

    checks.append({
        "name": "Attributes with descriptions",
        "status": "PASS" if pct_a >= 70 else ("WARN" if pct_a >= 30 else "FAIL"),
        "detail": f"{described_a}/{total_a} attributes ({pct_a:.0f}%) have descriptions",
    })
    return checks


def _check_readiness(data):
    """Overall migration readiness checks."""
    checks = []

    # Are there datasources?
    ds = data.get("datasources", [])
    checks.append({
        "name": "Data sources present",
        "status": "PASS" if ds else "FAIL",
        "detail": f"{len(ds)} data source table(s)",
    })

    # Are there reports or dossiers?
    reports = data.get("reports", [])
    dossiers = data.get("dossiers", [])
    total_content = len(reports) + len(dossiers)
    checks.append({
        "name": "Reports / dossiers present",
        "status": "PASS" if total_content else "FAIL",
        "detail": f"{len(reports)} reports + {len(dossiers)} dossiers",
    })

    # Error-free extraction
    error_reports = sum(1 for r in reports if r.get("error"))
    error_dossiers = sum(1 for d in dossiers if d.get("error"))
    total_errors = error_reports + error_dossiers
    checks.append({
        "name": "Extraction without errors",
        "status": "PASS" if total_errors == 0 else ("WARN" if total_errors <= 3 else "FAIL"),
        "detail": f"{total_errors} extraction error(s)",
    })

    # Metrics convertible (non manual_review)
    all_metrics = data.get("metrics", []) + data.get("derived_metrics", [])
    if all_metrics:
        # We don't have DAX results here, so just check expression presence
        with_expr = sum(1 for m in all_metrics if m.get("expression"))
        pct = with_expr / len(all_metrics) * 100
        checks.append({
            "name": "Metrics with expressions",
            "status": "PASS" if pct >= 80 else ("WARN" if pct >= 50 else "FAIL"),
            "detail": f"{with_expr}/{len(all_metrics)} ({pct:.0f}%) have expressions",
        })

    return checks


# ── HTML output ──────────────────────────────────────────────────

_STATUS_ICONS = {"PASS": "&#x2705;", "WARN": "&#x26A0;&#xFE0F;", "FAIL": "&#x274C;"}
_STATUS_COLORS = {"PASS": "#198754", "WARN": "#ffc107", "FAIL": "#dc3545"}


def _write_html(results, output_path):
    """Render governance checks as HTML."""
    score = compute_governance_score(results)

    rows = []
    for category in _ALL_CATEGORIES:
        checks = results.get(category, [])
        for i, c in enumerate(checks):
            icon = _STATUS_ICONS.get(c["status"], "")
            color = _STATUS_COLORS.get(c["status"], "#888")
            cat_cell = f'<td rowspan="{len(checks)}" class="cat">{html.escape(category)}</td>' if i == 0 else ""
            rows.append(
                f"<tr>{cat_cell}"
                f'<td style="color:{color}">{icon} {c["status"]}</td>'
                f"<td>{html.escape(c['name'])}</td>"
                f"<td>{html.escape(c['detail'])}</td></tr>"
            )

    score_color = "#198754" if score >= 80 else ("#ffc107" if score >= 50 else "#dc3545")

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Governance Report</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#1e1e1e;color:#d4d4d4;padding:24px}}
h1{{color:#fff;margin-bottom:4px}}
.score{{font-size:28px;font-weight:700;color:{score_color};margin:12px 0 20px}}
table{{border-collapse:collapse;width:100%;margin-top:12px}}
th,td{{border:1px solid #444;padding:8px 12px;text-align:left;font-size:13px}}
th{{background:#333;color:#fff}}
.cat{{background:#2d2d2d;font-weight:600;vertical-align:top}}
tr:nth-child(even){{background:#262626}}
</style></head><body>
<h1>Governance Report</h1>
<div class="score">Score: {score}%</div>
<table>
<tr><th>Category</th><th>Status</th><th>Check</th><th>Detail</th></tr>
{''.join(rows)}
</table>
</body></html>"""

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)
