"""
Report extractor for MicroStrategy.

Extracts report templates (grid/graph), filters, subtotals,
sort orders, and legacy document structures.
"""

import logging

logger = logging.getLogger(__name__)


def extract_report_definition(defn, summary):
    """Parse a report definition into intermediate format.

    Args:
        defn: Full report definition from REST API
        summary: Report summary metadata

    Returns:
        dict with report structure
    """
    report = {
        "id": summary.get("id", ""),
        "name": summary.get("name", ""),
        "description": summary.get("description", defn.get("description", "")),
        "type": _classify_report_type(defn),
        "grid": _extract_grid(defn),
        "graph": _extract_graph(defn),
        "filters": _extract_report_filters(defn),
        "sorts": _extract_sorts(defn),
        "subtotals": _extract_subtotals(defn),
        "page_by": _extract_page_by(defn),
        "thresholds": _extract_report_thresholds(defn),
        "prompts": [],  # Populated separately
    }
    return report


def _classify_report_type(defn):
    """Classify report as grid, graph, grid+graph, or document."""
    has_grid = bool(defn.get("grid") or defn.get("definition", {}).get("grid"))
    has_graph = bool(defn.get("graph") or defn.get("definition", {}).get("graph"))

    if has_grid and has_graph:
        return "grid_graph"
    elif has_grid:
        return "grid"
    elif has_graph:
        return "graph"
    return "grid"  # Default


def _extract_grid(defn):
    """Extract grid definition (rows, columns, metrics)."""
    grid = defn.get("grid", {}) or defn.get("definition", {}).get("grid", {}) or {}

    rows = []
    for r in grid.get("rows", []) or []:
        rows.append(_parse_grid_element(r))

    columns = []
    for c in grid.get("columns", []) or []:
        columns.append(_parse_grid_element(c))

    return {
        "rows": rows,
        "columns": columns,
        "metrics_position": grid.get("metricsPosition", "columns"),
    }


def _extract_graph(defn):
    """Extract graph (chart) definition."""
    graph = defn.get("graph", {}) or defn.get("definition", {}).get("graph", {}) or {}
    if not graph:
        return None

    return {
        "type": _map_mstr_graph_type(graph.get("graphType", "")),
        "mstr_type": graph.get("graphType", ""),
        "attributes_on_axis": _extract_axis_elements(graph, "category"),
        "metrics_on_axis": _extract_axis_elements(graph, "value"),
        "color_by": graph.get("colorBy", ""),
        "size_by": graph.get("sizeBy", ""),
    }


def _extract_report_filters(defn):
    """Extract report filters."""
    filters = []
    filter_def = defn.get("filter", {}) or defn.get("definition", {}).get("filter", {}) or {}

    for f in filter_def.get("qualifications", []) or []:
        filters.append({
            "type": f.get("type", ""),
            "attribute": f.get("attribute", {}).get("name", ""),
            "operator": f.get("operator", ""),
            "values": [v.get("name", str(v)) for v in f.get("values", []) or []],
            "is_view_filter": f.get("isViewFilter", False),
        })

    return filters


def _extract_sorts(defn):
    """Extract sort order definitions."""
    sorts = []
    for s in defn.get("sorts", []) or defn.get("definition", {}).get("sorts", []) or []:
        sorts.append({
            "name": s.get("name", ""),
            "type": s.get("type", "attribute"),
            "order": s.get("order", "ascending"),
        })
    return sorts


def _extract_subtotals(defn):
    """Extract subtotal definitions."""
    subtotals = []
    grid = defn.get("grid", {}) or defn.get("definition", {}).get("grid", {}) or {}
    for st in grid.get("subtotals", []) or []:
        subtotals.append({
            "name": st.get("name", ""),
            "function": st.get("function", "sum"),
            "position": st.get("position", "bottom"),
        })
    return subtotals


def _extract_page_by(defn):
    """Extract page-by (sectioning) elements."""
    page_by = []
    for p in defn.get("pageBy", []) or defn.get("definition", {}).get("pageBy", []) or []:
        page_by.append(_parse_grid_element(p))
    return page_by


def _extract_report_thresholds(defn):
    """Extract thresholds from report definition."""
    thresholds = []
    for metric in defn.get("metrics", []) or []:
        for t in metric.get("thresholds", []) or []:
            thresholds.append({
                "metric_name": metric.get("name", ""),
                "conditions": t.get("conditions", []),
                "format": t.get("format", {}),
            })
    return thresholds


def _parse_grid_element(element):
    """Parse a grid row/column element."""
    return {
        "id": element.get("id", ""),
        "name": element.get("name", ""),
        "type": element.get("type", ""),  # attribute, metric, etc.
        "forms": [f.get("name", "") if isinstance(f, dict) else f for f in element.get("forms", []) or []],
    }


def _extract_axis_elements(graph, axis_type):
    """Extract elements on a graph axis."""
    elements = []
    axis = graph.get(axis_type, []) or graph.get(f"{axis_type}Axis", []) or []
    if isinstance(axis, list):
        for elem in axis:
            elements.append({
                "name": elem.get("name", ""),
                "type": elem.get("type", ""),
            })
    return elements


def _map_mstr_graph_type(mstr_type):
    """Map MicroStrategy graph type to intermediate chart type."""
    mapping = {
        "vertical_bar": "clusteredColumnChart",
        "stacked_vertical_bar": "stackedColumnChart",
        "horizontal_bar": "clusteredBarChart",
        "stacked_horizontal_bar": "stackedBarChart",
        "100_stacked_vertical_bar": "hundredPercentStackedColumnChart",
        "100_stacked_horizontal_bar": "hundredPercentStackedBarChart",
        "line": "lineChart",
        "area": "areaChart",
        "stacked_area": "stackedAreaChart",
        "pie": "pieChart",
        "ring": "donutChart",
        "donut": "donutChart",
        "scatter": "scatterChart",
        "bubble": "scatterChart",
        "combo": "lineClusteredColumnComboChart",
        "dual_axis": "lineClusteredColumnComboChart",
        "map": "map",
        "filled_map": "filledMap",
        "treemap": "treemap",
        "waterfall": "waterfall",
        "funnel": "funnel",
        "gauge": "gauge",
        "kpi": "kpi",
        "heat_map": "matrix",
        "histogram": "clusteredColumnChart",
        "box_plot": "custom_boxPlot",
        "radar": "custom_radar",
        "network": "custom_network",
    }
    return mapping.get(mstr_type.lower().replace(" ", "_"), "clusteredColumnChart")
