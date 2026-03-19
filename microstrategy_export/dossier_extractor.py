"""
Dossier extractor for MicroStrategy.

Extracts dossier (interactive dashboard) definitions including
chapters, pages, visualizations, panel stacks, filter panels, and selectors.
"""

import logging

logger = logging.getLogger(__name__)


def extract_dossier_definition(defn, summary):
    """Parse a dossier definition into intermediate format.

    Args:
        defn: Full dossier definition from REST API
        summary: Dossier summary metadata

    Returns:
        dict with dossier structure
    """
    chapters = []
    for ch in defn.get("chapters", []) or []:
        chapters.append(_extract_chapter(ch))

    dossier = {
        "id": summary.get("id", ""),
        "name": summary.get("name", ""),
        "description": summary.get("description", defn.get("description", "")),
        "chapters": chapters,
        "filter_panels": _extract_filter_panels(defn),
        "themes": _extract_theme(defn),
        "prompts": _extract_dossier_prompts(defn),
    }
    return dossier


def _extract_chapter(chapter):
    """Extract a dossier chapter (maps to a PBI page group)."""
    pages = []
    for page in chapter.get("pages", []) or []:
        pages.append(_extract_page(page))

    return {
        "key": chapter.get("key", ""),
        "name": chapter.get("name", ""),
        "pages": pages,
    }


def _extract_page(page):
    """Extract a dossier page (maps to a PBI report page)."""
    visualizations = []
    for viz in page.get("visualizations", []) or []:
        visualizations.append(_extract_visualization(viz))

    panel_stacks = []
    for ps in page.get("panelStacks", []) or []:
        panel_stacks.append(_extract_panel_stack(ps))

    return {
        "key": page.get("key", ""),
        "name": page.get("name", ""),
        "visualizations": visualizations,
        "panel_stacks": panel_stacks,
        "selectors": _extract_selectors(page),
        "layout": _extract_page_layout(page),
    }


def _extract_visualization(viz):
    """Extract a single visualization from a dossier page."""
    viz_type = _classify_viz_type(viz)

    return {
        "key": viz.get("key", ""),
        "name": viz.get("name", ""),
        "viz_type": viz_type,
        "mstr_viz_type": viz.get("vizType", "") or viz.get("visualizationType", ""),
        "pbi_visual_type": _map_viz_to_pbi(viz_type),
        "data": _extract_viz_data(viz),
        "formatting": _extract_viz_formatting(viz),
        "thresholds": _extract_viz_thresholds(viz),
        "position": _extract_viz_position(viz),
        "actions": _extract_viz_actions(viz),
        "info_window": _extract_info_window(viz),
    }


def _classify_viz_type(viz):
    """Classify the visualization type."""
    vtype = (viz.get("vizType", "") or viz.get("visualizationType", "")).lower()

    type_map = {
        "grid": "grid",
        "crosstab": "crosstab",
        "verticalbar": "vertical_bar",
        "vertical_bar": "vertical_bar",
        "horizontalbar": "horizontal_bar",
        "horizontal_bar": "horizontal_bar",
        "stackedverticalbar": "stacked_vertical_bar",
        "stackedhorizontalbar": "stacked_horizontal_bar",
        "line": "line",
        "area": "area",
        "stackedarea": "stacked_area",
        "pie": "pie",
        "ring": "ring",
        "donut": "ring",
        "scatter": "scatter",
        "bubble": "bubble",
        "combo": "combo",
        "dualaxis": "dual_axis",
        "map": "map",
        "geospatial": "map",
        "areamap": "filled_map",
        "filledmap": "filled_map",
        "treemap": "treemap",
        "waterfall": "waterfall",
        "funnel": "funnel",
        "gauge": "gauge",
        "kpi": "kpi",
        "heatmap": "heat_map",
        "heat_map": "heat_map",
        "histogram": "histogram",
        "boxplot": "box_plot",
        "box_plot": "box_plot",
        "wordcloud": "word_cloud",
        "network": "network",
        "sankey": "sankey",
        "bullet": "bullet",
        "text": "text",
        "image": "image",
        "html": "html",
        "filter": "filter_panel",
        "selector": "selector",
    }

    return type_map.get(vtype.replace(" ", "").replace("-", ""), "grid")


def _map_viz_to_pbi(viz_type):
    """Map intermediate viz type to Power BI visual type."""
    mapping = {
        "grid": "tableEx",
        "crosstab": "matrix",
        "vertical_bar": "clusteredColumnChart",
        "stacked_vertical_bar": "stackedColumnChart",
        "horizontal_bar": "clusteredBarChart",
        "stacked_horizontal_bar": "stackedBarChart",
        "line": "lineChart",
        "area": "areaChart",
        "stacked_area": "stackedAreaChart",
        "pie": "pieChart",
        "ring": "donutChart",
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
        "word_cloud": "custom_wordCloud",
        "network": "custom_networkNavigator",
        "sankey": "custom_sankeyDiagram",
        "bullet": "custom_bulletChart",
        "text": "textbox",
        "image": "image",
        "html": "textbox",
        "filter_panel": "slicer",
        "selector": "slicer",
    }
    return mapping.get(viz_type, "tableEx")


def _extract_viz_data(viz):
    """Extract data bindings for a visualization."""
    data = {
        "attributes": [],
        "metrics": [],
        "rows": [],
        "columns": [],
        "color_by": None,
        "size_by": None,
    }

    # Extract from various API response structures
    for attr in viz.get("attributes", []) or viz.get("data", {}).get("attributes", []) or []:
        data["attributes"].append({
            "id": attr.get("id", ""),
            "name": attr.get("name", ""),
            "forms": [f.get("name", "") for f in attr.get("forms", []) or []],
        })

    for met in viz.get("metrics", []) or viz.get("data", {}).get("metrics", []) or []:
        data["metrics"].append({
            "id": met.get("id", ""),
            "name": met.get("name", ""),
        })

    # Grid-specific: rows and columns placement
    for r in viz.get("rows", []) or []:
        data["rows"].append({"name": r.get("name", ""), "type": r.get("type", "")})
    for c in viz.get("columns", []) or []:
        data["columns"].append({"name": c.get("name", ""), "type": c.get("type", "")})

    # Chart-specific encodings
    data["color_by"] = viz.get("colorBy", {})
    data["size_by"] = viz.get("sizeBy", {})

    return data


def _extract_viz_formatting(viz):
    """Extract formatting properties."""
    fmt = viz.get("formatting", {}) or viz.get("format", {}) or {}
    return {
        "title": viz.get("title", viz.get("name", "")),
        "show_title": fmt.get("showTitle", True),
        "font_size": fmt.get("fontSize", 10),
        "font_family": fmt.get("fontFamily", ""),
        "colors": fmt.get("colors", []),
        "background_color": fmt.get("backgroundColor", ""),
        "border": fmt.get("border", {}),
    }


def _extract_viz_thresholds(viz):
    """Extract threshold (conditional formatting) from visualization."""
    thresholds = []
    for t in viz.get("thresholds", []) or []:
        thresholds.append({
            "metric_name": t.get("metricName", ""),
            "conditions": t.get("conditions", []),
            "format": {
                "background_color": t.get("format", {}).get("backgroundColor", ""),
                "font_color": t.get("format", {}).get("fontColor", ""),
                "icon": t.get("format", {}).get("icon", ""),
            },
        })
    return thresholds


def _extract_viz_position(viz):
    """Extract visualization position on the page."""
    pos = viz.get("position", {}) or {}
    return {
        "x": pos.get("x", 0),
        "y": pos.get("y", 0),
        "width": pos.get("width", 400),
        "height": pos.get("height", 300),
    }


def _extract_viz_actions(viz):
    """Extract actions (links, navigation, filters) on the visualization."""
    actions = []
    for a in viz.get("actions", []) or []:
        actions.append({
            "type": a.get("type", ""),
            "target": a.get("target", ""),
            "url": a.get("url", ""),
        })
    return actions


def _extract_info_window(viz):
    """Extract info window (tooltip) configuration."""
    iw = viz.get("infoWindow", {}) or {}
    if not iw:
        return None
    return {
        "type": iw.get("type", ""),
        "content": iw.get("content", ""),
        "visualizations": iw.get("visualizations", []),
    }


def _extract_panel_stack(panel_stack):
    """Extract panel stack (tabbed container)."""
    panels = []
    for panel in panel_stack.get("panels", []) or []:
        panels.append({
            "key": panel.get("key", ""),
            "name": panel.get("name", ""),
            "visualizations": [
                _extract_visualization(v) for v in panel.get("visualizations", []) or []
            ],
        })

    return {
        "key": panel_stack.get("key", ""),
        "name": panel_stack.get("name", ""),
        "panels": panels,
        "default_panel": panel_stack.get("currentPanel", 0),
    }


def _extract_selectors(page):
    """Extract selector controls from a page."""
    selectors = []
    for sel in page.get("selectors", []) or []:
        selectors.append({
            "key": sel.get("key", ""),
            "name": sel.get("name", ""),
            "type": sel.get("type", ""),  # attribute_selector, metric_selector
            "targets": sel.get("targets", []),
            "multi_select": sel.get("multiSelect", True),
            "position": _extract_viz_position(sel),
        })
    return selectors


def _extract_filter_panels(defn):
    """Extract top-level filter panels from dossier."""
    panels = []
    for fp in defn.get("filterPanels", []) or defn.get("filters", []) or []:
        panels.append({
            "name": fp.get("name", ""),
            "type": fp.get("type", "attribute"),
            "attribute": fp.get("attribute", {}).get("name", ""),
            "multi_select": fp.get("multiSelect", True),
            "default_values": [v.get("name", "") for v in fp.get("defaultValues", []) or []],
        })
    return panels


def _extract_theme(defn):
    """Extract dossier theme/palette."""
    theme = defn.get("theme", {}) or {}
    return {
        "name": theme.get("name", ""),
        "colors": theme.get("colors", []),
        "font_family": theme.get("fontFamily", ""),
        "background_color": theme.get("backgroundColor", ""),
    }


def _extract_dossier_prompts(defn):
    """Extract dossier-level prompts."""
    return defn.get("prompts", []) or []


def _extract_page_layout(page):
    """Extract page layout dimensions."""
    layout = page.get("layout", {}) or {}
    return {
        "width": layout.get("width", 1280),
        "height": layout.get("height", 720),
    }
