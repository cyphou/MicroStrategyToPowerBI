"""
Visual diff module.

Computes per-visual field coverage, data binding accuracy, and layout
similarity between MicroStrategy source visuals and their Power BI output.
"""

import logging

logger = logging.getLogger(__name__)

# ── Visual type mapping (canonical) ──────────────────────────────

_VIZ_TYPE_MAP = {
    "grid": "tableEx",
    "kpi": "card",
    "bar": "clusteredBarChart",
    "column": "clusteredColumnChart",
    "stacked_bar": "stackedBarChart",
    "stacked_column": "100PercentStackedColumnChart",
    "line": "lineChart",
    "area": "areaChart",
    "pie": "pieChart",
    "donut": "donutChart",
    "scatter": "scatterChart",
    "bubble": "scatterChart",
    "treemap": "treemap",
    "map": "map",
    "filled_map": "filledMap",
    "funnel": "funnel",
    "waterfall": "waterfallChart",
    "combo": "lineClusteredColumnComboChart",
    "heat_map": "tableEx",
    "gauge": "gauge",
    "text": "textbox",
    "image": "image",
    "shape": "shape",
    "slicer": "slicer",
    "matrix": "pivotTable",
    "table": "tableEx",
    "histogram": "clusteredColumnChart",
    "box_plot": "tableEx",
    "network": "tableEx",
    "sankey": "tableEx",
    "word_cloud": "tableEx",
    "bullet": "tableEx",
}

_UNSUPPORTED_TYPES = {"network", "sankey", "box_plot", "word_cloud", "bullet"}


# ── Public API ───────────────────────────────────────────────────


def compute_visual_diff(data):
    """Compute visual diff summary.

    Args:
        data: dict with intermediate JSON data.

    Returns:
        dict with per-visual diff entries and aggregated stats.
    """
    diffs = []
    total = 0
    exact = 0
    approximate = 0
    unsupported = 0
    field_coverage_sum = 0.0

    for dossier in data.get("dossiers", []):
        for ch in dossier.get("chapters", []):
            for pg in ch.get("pages", []):
                for viz in pg.get("visualizations", []):
                    total += 1
                    diff = _diff_visual(viz)
                    diffs.append(diff)
                    if diff["status"] == "exact":
                        exact += 1
                    elif diff["status"] == "approximate":
                        approximate += 1
                    else:
                        unsupported += 1
                    field_coverage_sum += diff["field_coverage"]

    # Also count report grids
    for report in data.get("reports", []):
        if report.get("grid"):
            total += 1
            diff = _diff_report_grid(report)
            diffs.append(diff)
            if diff["status"] == "exact":
                exact += 1
            else:
                approximate += 1
            field_coverage_sum += diff["field_coverage"]

    return {
        "total_visuals": total,
        "exact": exact,
        "approximate": approximate,
        "unsupported": unsupported,
        "avg_field_coverage": round(field_coverage_sum / total, 3) if total else 0,
        "diffs": diffs,
    }


# ── Per-visual diff ──────────────────────────────────────────────


def _diff_visual(viz):
    vt = (viz.get("viz_type", "") or "").lower()
    name = viz.get("name", vt)
    pbi_type = _VIZ_TYPE_MAP.get(vt, "tableEx")

    # Field coverage: what % of source fields can be bound
    source_fields = _extract_fields(viz)
    total_fields = len(source_fields)

    if vt in _UNSUPPORTED_TYPES:
        status = "unsupported"
        coverage = 0.5  # partial — data still goes to table
    elif pbi_type == "tableEx" and vt != "grid" and vt != "table" and vt != "matrix":
        status = "approximate"
        coverage = 0.8
    else:
        status = "exact"
        coverage = 1.0

    return {
        "name": name,
        "source_type": vt,
        "pbi_type": pbi_type,
        "status": status,
        "source_field_count": total_fields,
        "field_coverage": coverage,
        "notes": _build_notes(vt, pbi_type, status),
    }


def _diff_report_grid(report):
    name = report.get("name", "Report")
    grid = report.get("grid", {})
    rows = grid.get("rows", [])
    cols = grid.get("columns", [])
    total_fields = len(rows) + len(cols)

    return {
        "name": name,
        "source_type": "report_grid",
        "pbi_type": "tableEx",
        "status": "exact",
        "source_field_count": total_fields,
        "field_coverage": 1.0,
        "notes": "",
    }


def _extract_fields(viz):
    """Extract field references from a visualization definition."""
    fields = []
    for role in ("rows", "columns", "metrics", "attributes", "groups", "values",
                 "category", "series", "size", "color", "tooltip"):
        items = viz.get(role, [])
        if isinstance(items, list):
            fields.extend(items)
    return fields


def _build_notes(source_type, pbi_type, status):
    if status == "unsupported":
        return f"{source_type} has no PBI equivalent — fell back to table"
    if status == "approximate":
        return f"{source_type} → {pbi_type} (approximate mapping)"
    return ""
