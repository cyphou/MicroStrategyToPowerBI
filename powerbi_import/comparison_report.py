"""
Comparison report generator.

Produces a side-by-side HTML comparison of MicroStrategy source objects
vs their Power BI equivalents, showing field-by-field mapping status.
"""

import json
import logging
import os
from html import escape as esc

logger = logging.getLogger(__name__)

# ── Status enum ──────────────────────────────────────────────────

EXACT = "exact"
APPROXIMATE = "approximate"
UNSUPPORTED = "unsupported"
MISSING = "missing"

_STATUS_COLOR = {
    EXACT: "#107c10",
    APPROXIMATE: "#ff8c00",
    UNSUPPORTED: "#a80000",
    MISSING: "#999",
}

# ── Public API ───────────────────────────────────────────────────


def generate_comparison_report(data, stats, output_dir, report_name="MicroStrategy Report"):
    """Generate a side-by-side comparison report.

    Args:
        data: dict with intermediate JSON keys.
        stats: dict from generate_pbip().
        output_dir: where to write HTML/JSON output.
        report_name: heading for the report.

    Returns:
        dict with comparison results.
    """
    os.makedirs(output_dir, exist_ok=True)

    table_map = _compare_tables(data)
    metric_map = _compare_metrics(data)
    visual_map = _compare_visuals(data)
    filter_map = _compare_filters(data)

    summary = _build_summary(table_map, metric_map, visual_map, filter_map)
    report = {
        "report_name": report_name,
        "summary": summary,
        "tables": table_map,
        "metrics": metric_map,
        "visuals": visual_map,
        "filters": filter_map,
    }

    json_path = os.path.join(output_dir, "comparison_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    html_path = os.path.join(output_dir, "comparison_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_render_html(report))

    logger.info("Comparison report written to %s", output_dir)
    return report


# ── Comparisons ──────────────────────────────────────────────────


def _compare_tables(data):
    items = []
    for ds in data.get("datasources", []):
        name = ds.get("name", "Unknown")
        cols = ds.get("columns", [])
        items.append({
            "source_type": "Table",
            "source_name": name,
            "pbi_name": name,
            "status": EXACT,
            "source_columns": len(cols),
            "pbi_columns": len(cols),
            "notes": "",
        })
    return items


def _compare_metrics(data):
    items = []
    for m in data.get("metrics", []):
        name = m.get("name", "Unknown")
        expr = m.get("expression", "")
        has_apply = "applysimple" in (expr or "").lower()
        status = APPROXIMATE if has_apply else EXACT
        items.append({
            "source_type": "Metric",
            "source_name": name,
            "pbi_name": name,
            "status": status,
            "source_expression": expr,
            "notes": "Contains ApplySimple" if has_apply else "",
        })
    for m in data.get("derived_metrics", []):
        name = m.get("name", "Unknown")
        items.append({
            "source_type": "Derived Metric",
            "source_name": name,
            "pbi_name": name,
            "status": APPROXIMATE,
            "source_expression": m.get("expression", ""),
            "notes": "OLAP/derived — verify DAX output",
        })
    return items


def _compare_visuals(data):
    items = []
    _unsupported = {"network", "sankey", "box_plot", "word_cloud", "bullet"}
    for dossier in data.get("dossiers", []):
        for ch in dossier.get("chapters", []):
            for pg in ch.get("pages", []):
                for viz in pg.get("visualizations", []):
                    vt = (viz.get("viz_type", "") or "").lower()
                    name = viz.get("name", vt)
                    if vt in _unsupported:
                        status = UNSUPPORTED
                    else:
                        status = EXACT
                    items.append({
                        "source_type": "Visual",
                        "source_name": name,
                        "source_viz_type": vt,
                        "pbi_viz_type": "tableEx" if vt in _unsupported else vt,
                        "status": status,
                        "notes": "Fallback to table" if vt in _unsupported else "",
                    })
    return items


def _compare_filters(data):
    items = []
    for sf in data.get("security_filters", []):
        name = sf.get("name", "Unknown")
        items.append({
            "source_type": "Security Filter",
            "source_name": name,
            "pbi_name": name,
            "status": APPROXIMATE,
            "notes": "Migrated as RLS role",
        })
    for p in data.get("prompts", []):
        name = p.get("name", "Unknown")
        pt = p.get("prompt_type", "")
        status = APPROXIMATE if pt in ("hierarchy", "expression") else EXACT
        items.append({
            "source_type": "Prompt",
            "source_name": name,
            "pbi_name": name,
            "status": status,
            "notes": f"Prompt type: {pt}",
        })
    return items


# ── Summary builder ──────────────────────────────────────────────


def _build_summary(table_map, metric_map, visual_map, filter_map):
    all_items = table_map + metric_map + visual_map + filter_map
    total = len(all_items)
    by_status = {}
    for item in all_items:
        s = item.get("status", MISSING)
        by_status[s] = by_status.get(s, 0) + 1

    exact = by_status.get(EXACT, 0)
    score = exact / total if total else 0
    if score >= 0.9:
        grade = "A"
    elif score >= 0.75:
        grade = "B"
    elif score >= 0.6:
        grade = "C"
    elif score >= 0.4:
        grade = "D"
    else:
        grade = "F"

    return {
        "total_items": total,
        "status_counts": by_status,
        "exact_ratio": round(score, 3),
        "grade": grade,
    }


# ── HTML renderer ────────────────────────────────────────────────


def _render_html(report):
    summary = report["summary"]
    grade = summary["grade"]
    grade_color = {"A": "#107c10", "B": "#0078d4", "C": "#ff8c00", "D": "#d83b01", "F": "#a80000"}.get(grade, "#333")

    sections = [("Tables", report["tables"]), ("Metrics", report["metrics"]),
                ("Visuals", report["visuals"]), ("Filters", report["filters"])]

    section_html = ""
    for title, items in sections:
        if not items:
            continue
        rows = []
        for item in items:
            st = item.get("status", MISSING)
            color = _STATUS_COLOR.get(st, "#333")
            rows.append(
                f"<tr><td>{esc(item.get('source_type', ''))}</td>"
                f"<td>{esc(item.get('source_name', ''))}</td>"
                f"<td>{esc(item.get('pbi_name', item.get('pbi_viz_type', '')))}</td>"
                f"<td style='color:{color};font-weight:bold'>{st.upper()}</td>"
                f"<td>{esc(item.get('notes', ''))}</td></tr>"
            )
        section_html += f"""
        <h2>{esc(title)} ({len(items)})</h2>
        <table>
        <thead><tr><th>Type</th><th>Source</th><th>PBI</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Comparison Report — {esc(report['report_name'])}</title>
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
</style>
</head>
<body>
<h1>Comparison: {esc(report['report_name'])}</h1>

<div>
  <div class="card"><div class="num" style="color:{grade_color}">{grade}</div><div class="label">Fidelity Grade</div></div>
  <div class="card"><div class="num">{summary['total_items']}</div><div class="label">Total Items</div></div>
  <div class="card"><div class="num">{summary['exact_ratio']:.0%}</div><div class="label">Exact Match</div></div>
</div>

{section_html}

</body>
</html>"""
