"""
Visual generator for Power BI PBIR v4.0 format.

Converts intermediate dossier/report JSON into PBIR visual definitions
(page JSON + visual JSON) suitable for .pbip projects.
"""

import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────

_PBI_PAGE_WIDTH = 1280
_PBI_PAGE_HEIGHT = 720

# MSTR viz_type → PBIR visualType (canonical list from MAPPING_REFERENCE.md)
_VIZ_TYPE_MAP = {
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
    "box_plot": "tableEx",
    "word_cloud": "tableEx",
    "network": "tableEx",
    "sankey": "tableEx",
    "bullet": "tableEx",
    "text": "textbox",
    "image": "image",
    "html": "textbox",
    "filter_panel": "slicer",
    "selector": "slicer",
}

# Which visual types support which data role wells
_DATA_ROLE_MAP = {
    "tableEx": {"category": "Values", "value": "Values"},
    "matrix": {"rows": "Rows", "columns": "Columns", "value": "Values"},
    "clusteredColumnChart": {"category": "Category", "value": "Y"},
    "stackedColumnChart": {"category": "Category", "value": "Y"},
    "clusteredBarChart": {"category": "Category", "value": "Y"},
    "stackedBarChart": {"category": "Category", "value": "Y"},
    "lineChart": {"category": "Category", "value": "Y", "series": "Series"},
    "areaChart": {"category": "Category", "value": "Y", "series": "Series"},
    "stackedAreaChart": {"category": "Category", "value": "Y", "series": "Series"},
    "pieChart": {"category": "Category", "value": "Y"},
    "donutChart": {"category": "Category", "value": "Y"},
    "scatterChart": {"x": "X", "y": "Y", "details": "Details", "size": "Size"},
    "lineClusteredColumnComboChart": {"category": "Category", "columnY": "ColumnY", "lineY": "LineY"},
    "treemap": {"category": "Group", "value": "Values"},
    "waterfall": {"category": "Category", "value": "Y"},
    "funnel": {"category": "Category", "value": "Y"},
    "gauge": {"value": "Y", "target": "TargetValue", "min": "MinValue", "max": "MaxValue"},
    "kpi": {"value": "Indicator", "target": "TrendAxis", "goal": "Goal"},
    "map": {"location": "Category", "size": "Size", "color": "Color"},
    "filledMap": {"location": "Category", "color": "Color"},
    "slicer": {"field": "Field"},
}


# ── Public API ───────────────────────────────────────────────────

def generate_all_visuals(data, output_dir):
    """Generate PBIR v4.0 visual JSON for all dossiers and reports.

    Args:
        data: dict with 'dossiers', 'reports', and optionally 'prompts' keys
        output_dir: path to the Report/definition/ folder

    Returns:
        dict with generation stats
    """
    pages_dir = os.path.join(output_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    stats = {"pages": 0, "visuals": 0, "slicers": 0, "unsupported": 0}
    page_ids = []

    # Dossiers → pages with visuals
    for dossier in data.get("dossiers", []):
        _generate_dossier_pages(dossier, pages_dir, stats, page_ids)

    # Standalone reports → one page per report
    for report in data.get("reports", []):
        _generate_report_page(report, pages_dir, stats, page_ids)

    # Write pages.json (page ordering metadata)
    if page_ids:
        _write_pages_json(pages_dir, page_ids)

    # Write report.json manifest
    _write_report_manifest(data, output_dir, stats)

    logger.info(
        "Generated %d pages, %d visuals, %d slicers (%d unsupported)",
        stats["pages"], stats["visuals"], stats["slicers"], stats["unsupported"],
    )
    return stats


# ── Dossier → Pages ──────────────────────────────────────────────

def _generate_dossier_pages(dossier, pages_dir, stats, page_ids):
    """Generate pages from a dossier (chapters → page groups, pages → pages)."""
    for chapter in dossier.get("chapters", []):
        for page in chapter.get("pages", []):
            page_id = page.get("key", _make_id())
            page_name = page.get("name", "Page")

            visuals = []
            layout = page.get("layout", {})
            src_w = layout.get("width", 1024) or 1024
            src_h = layout.get("height", 768) or 768

            for viz in page.get("visualizations", []):
                visual = _convert_visualization(viz, src_w, src_h)
                if visual:
                    visuals.append(visual)
                    if visual.get("visual", {}).get("visualType") == "slicer":
                        stats["slicers"] += 1
                    else:
                        stats["visuals"] += 1

            # Selectors → slicer visuals
            for sel in page.get("selectors", []):
                slicer = _convert_selector(sel, src_w, src_h)
                if slicer:
                    visuals.append(slicer)
                    stats["slicers"] += 1

            page_json = _build_page_json(page_id, page_name, visuals,
                                         chapter.get("name", ""))
            _write_page(pages_dir, page_id, page_json, visuals)
            page_ids.append(page_id)
            stats["pages"] += 1


# ── Report → Page ────────────────────────────────────────────────

def _generate_report_page(report, pages_dir, stats, page_ids):
    """Generate a single page from a standalone report."""
    report_id = report.get("id", _make_id())
    report_name = report.get("name", "Report")
    report_type = report.get("report_type", "grid")

    visuals = []

    if report_type in ("grid", "grid_graph"):
        visual = _convert_report_grid(report)
        if visual:
            visuals.append(visual)
            stats["visuals"] += 1

    if report_type in ("graph", "grid_graph"):
        visual = _convert_report_graph(report)
        if visual:
            visuals.append(visual)
            stats["visuals"] += 1

    # Page-by → slicer
    for pb in report.get("page_by", []):
        slicer = _build_slicer_visual(pb.get("name", ""), _make_id())
        if slicer:
            visuals.append(slicer)
            stats["slicers"] += 1

    if visuals:
        page_json = _build_page_json(report_id, report_name, visuals)
        _write_page(pages_dir, report_id, page_json, visuals)
        page_ids.append(report_id)
        stats["pages"] += 1


# ── Visualization converters ─────────────────────────────────────

def _convert_visualization(viz, src_w, src_h):
    """Convert a single intermediate visualization to PBIR visual JSON."""
    viz_type = viz.get("viz_type", "") or viz.get("pbi_visual_type", "grid")
    pbi_type = _VIZ_TYPE_MAP.get(viz_type, viz.get("pbi_visual_type", "tableEx"))

    if pbi_type in ("textbox", "image"):
        return _build_static_visual(viz, pbi_type, src_w, src_h)

    data = viz.get("data", {})
    attrs = data.get("attributes", [])
    metrics = data.get("metrics", [])

    data_bindings = _build_data_bindings(pbi_type, attrs, metrics, viz)
    position = _scale_position(viz.get("position", {}), src_w, src_h)
    formatting = _build_formatting(pbi_type, viz.get("formatting", {}))
    thresholds = _build_conditional_formatting(viz.get("thresholds", []), pbi_type)

    visual_id = viz.get("key", _make_id())

    visual_json = {
        "visual": {
            "visualType": pbi_type,
            "objects": formatting,
        },
        "dataTransforms": {
            "bindings": data_bindings,
        },
        "position": position,
        "name": visual_id,
        "title": viz.get("name", ""),
    }

    if thresholds:
        visual_json["visual"]["objects"]["conditionalFormatting"] = thresholds

    return visual_json


def _convert_selector(sel, src_w, src_h):
    """Convert a dossier selector to a slicer visual."""
    attr_name = sel.get("attribute", {}).get("name", sel.get("name", ""))
    slicer_id = sel.get("key", _make_id())
    return _build_slicer_visual(attr_name, slicer_id)


def _convert_report_grid(report):
    """Convert a report grid to a table or matrix visual."""
    grid = report.get("grid", {})
    rows = grid.get("rows", [])
    columns = grid.get("columns", [])
    metrics = report.get("metrics", [])

    has_col_attrs = any(c.get("type") == "attribute" for c in columns)
    pbi_type = "matrix" if has_col_attrs else "tableEx"

    attrs = rows + [c for c in columns if c.get("type") == "attribute"]
    data_bindings = _build_data_bindings(pbi_type, attrs, metrics, report)

    visual = {
        "visual": {
            "visualType": pbi_type,
            "objects": {},
        },
        "dataTransforms": {
            "bindings": data_bindings,
        },
        "position": {"x": 0, "y": 0, "width": _PBI_PAGE_WIDTH, "height": 500},
        "name": _make_id(),
        "title": report.get("name", ""),
    }

    # Subtotals
    if report.get("subtotals") and pbi_type == "matrix":
        visual["visual"]["objects"]["subTotals"] = [
            {"properties": {"rowSubtotals": {"expr": {"Literal": {"Value": "true"}}}}}
        ]

    return visual


def _convert_report_graph(report):
    """Convert a report graph to a chart visual."""
    graph = report.get("graph", {})
    if not graph:
        return None

    mstr_type = graph.get("mstr_type", graph.get("type", "line"))
    pbi_type = _VIZ_TYPE_MAP.get(mstr_type, "lineChart")

    axis_attrs = graph.get("attributes_on_axis", [])
    axis_metrics = graph.get("metrics_on_axis", report.get("metrics", []))
    color_by = graph.get("color_by", "")

    data_bindings = _build_data_bindings(pbi_type, axis_attrs, axis_metrics, report)

    if color_by and pbi_type in ("lineChart", "areaChart", "stackedAreaChart"):
        data_bindings.append({
            "role": "Series",
            "source": {"field": color_by},
        })

    y_offset = 520 if report.get("report_type") == "grid_graph" else 0

    return {
        "visual": {
            "visualType": pbi_type,
            "objects": {},
        },
        "dataTransforms": {
            "bindings": data_bindings,
        },
        "position": {"x": 0, "y": y_offset, "width": _PBI_PAGE_WIDTH, "height": 500},
        "name": _make_id(),
        "title": report.get("name", ""),
    }


# ── Data binding builders ────────────────────────────────────────

def _build_data_bindings(pbi_type, attrs, metrics, source):
    """Build PBIR data role bindings for a visual type."""
    bindings = []
    role_map = _DATA_ROLE_MAP.get(pbi_type, {})

    if pbi_type == "tableEx":
        # Table: all fields go into "Values"
        for attr in attrs:
            bindings.append(_make_binding("Values", attr.get("name", ""), "column"))
        for metric in metrics:
            bindings.append(_make_binding("Values", metric.get("name", ""), "measure"))

    elif pbi_type == "matrix":
        rows = source.get("grid", {}).get("rows", attrs) if "grid" in source else attrs
        columns = source.get("grid", {}).get("columns", []) if "grid" in source else []
        for r in rows:
            bindings.append(_make_binding("Rows", r.get("name", ""), "column"))
        for c in columns:
            if c.get("type") == "attribute":
                bindings.append(_make_binding("Columns", c.get("name", ""), "column"))
        for m in metrics:
            bindings.append(_make_binding("Values", m.get("name", ""), "measure"))

    elif pbi_type == "scatterChart":
        if len(metrics) >= 1:
            bindings.append(_make_binding("X", metrics[0].get("name", ""), "measure"))
        if len(metrics) >= 2:
            bindings.append(_make_binding("Y", metrics[1].get("name", ""), "measure"))
        for attr in attrs:
            bindings.append(_make_binding("Details", attr.get("name", ""), "column"))
        if len(metrics) >= 3:
            bindings.append(_make_binding("Size", metrics[2].get("name", ""), "measure"))

    elif pbi_type == "gauge":
        if metrics:
            bindings.append(_make_binding("Y", metrics[0].get("name", ""), "measure"))
        fmt = source.get("formatting", {})
        if fmt.get("targetValue") is not None:
            bindings.append({"role": "TargetValue", "source": {"literal": fmt["targetValue"]}})

    elif pbi_type == "kpi":
        if metrics:
            bindings.append(_make_binding("Indicator", metrics[0].get("name", ""), "measure"))
        if attrs:
            bindings.append(_make_binding("TrendAxis", attrs[0].get("name", ""), "column"))

    elif pbi_type == "slicer":
        if attrs:
            bindings.append(_make_binding("Field", attrs[0].get("name", ""), "column"))

    elif pbi_type in ("map", "filledMap"):
        if attrs:
            bindings.append(_make_binding("Category", attrs[0].get("name", ""), "column"))
        if metrics:
            role = "Size" if pbi_type == "map" else "Color"
            bindings.append(_make_binding(role, metrics[0].get("name", ""), "measure"))

    elif pbi_type == "lineClusteredColumnComboChart":
        # Combo chart: attrs → Category, first metric → ColumnY, rest → LineY
        for attr in attrs:
            bindings.append(_make_binding("Category", attr.get("name", ""), "column"))
        if metrics:
            bindings.append(_make_binding("ColumnY", metrics[0].get("name", ""), "measure"))
        for m in metrics[1:]:
            bindings.append(_make_binding("LineY", m.get("name", ""), "measure"))

    else:
        # Standard chart pattern: attrs → Category, metrics → Y
        cat_role = role_map.get("category", "Category")
        val_role = role_map.get("value", "Y")
        for attr in attrs:
            bindings.append(_make_binding(cat_role, attr.get("name", ""), "column"))
        for m in metrics:
            bindings.append(_make_binding(val_role, m.get("name", ""), "measure"))

    return bindings


def _make_binding(role, field_name, field_type="column"):
    """Create a single data role binding."""
    return {
        "role": role,
        "source": {
            "field": field_name,
            "type": field_type,
        },
    }


# ── Positioning ──────────────────────────────────────────────────

def _scale_position(pos, src_w, src_h):
    """Scale from source dossier layout to PBI 1280×720 canvas."""
    if not pos:
        return {"x": 0, "y": 0, "width": _PBI_PAGE_WIDTH, "height": _PBI_PAGE_HEIGHT}

    sx = _PBI_PAGE_WIDTH / max(src_w, 1)
    sy = _PBI_PAGE_HEIGHT / max(src_h, 1)

    return {
        "x": round(pos.get("x", 0) * sx),
        "y": round(pos.get("y", 0) * sy),
        "width": round(pos.get("width", src_w) * sx),
        "height": round(pos.get("height", src_h) * sy),
    }


# ── Formatting ───────────────────────────────────────────────────

def _build_formatting(pbi_type, formatting):
    """Build PBIR visual formatting objects."""
    objects = {}

    if formatting.get("showDataLabels"):
        objects["labels"] = [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]

    if formatting.get("showLegend") is False:
        objects["legend"] = [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}},
        }}]
    elif formatting.get("showLegend"):
        objects["legend"] = [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]

    return objects


def _build_conditional_formatting(thresholds, pbi_type):
    """Convert MSTR thresholds to PBI conditional formatting rules."""
    if not thresholds:
        return None

    rules = []
    for t in thresholds:
        for cond in t.get("conditions", []):
            rule = {
                "metricName": t.get("metric_name", t.get("metricName", "")),
                "operator": cond.get("operator", ""),
                "value": cond.get("value", ""),
            }
            fmt = cond.get("format", {})
            if fmt.get("background_color") or fmt.get("backgroundColor"):
                rule["backgroundColor"] = (
                    fmt.get("background_color") or fmt.get("backgroundColor")
                )
            if fmt.get("font_color") or fmt.get("fontColor"):
                rule["fontColor"] = fmt.get("font_color") or fmt.get("fontColor")
            rules.append(rule)

    return rules if rules else None


# ── Static visuals ───────────────────────────────────────────────

def _build_static_visual(viz, pbi_type, src_w, src_h):
    """Build a textbox or image visual."""
    position = _scale_position(viz.get("position", {}), src_w, src_h)
    return {
        "visual": {
            "visualType": pbi_type,
            "objects": {},
        },
        "dataTransforms": {"bindings": []},
        "position": position,
        "name": viz.get("key", _make_id()),
        "title": viz.get("name", ""),
    }


def _build_slicer_visual(attr_name, slicer_id):
    """Build a slicer visual for an attribute or selector."""
    return {
        "visual": {
            "visualType": "slicer",
            "objects": {},
        },
        "dataTransforms": {
            "bindings": [_make_binding("Field", attr_name, "column")],
        },
        "position": {"x": 0, "y": 0, "width": 200, "height": 60},
        "name": slicer_id,
        "title": attr_name,
    }


# ── Page assembly ────────────────────────────────────────────────

def _build_page_json(page_id, page_name, visuals, section_name=""):
    """Build a PBIR page JSON structure (v2.0.0 — no inline visuals)."""
    page = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": page_id,
        "displayName": page_name,
        "displayOption": "FitToPage",
        "height": _PBI_PAGE_HEIGHT,
        "width": _PBI_PAGE_WIDTH,
    }
    return page


def _write_page(pages_dir, page_id, page_json, visuals):
    """Write page.json and individual visual.json files."""
    page_dir = os.path.join(pages_dir, page_id)
    os.makedirs(page_dir, exist_ok=True)

    # Write page.json (metadata only, no visuals)
    path = os.path.join(page_dir, "page.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(page_json, f, indent=2, ensure_ascii=False)
    logger.debug("Wrote page %s → %s", page_id, path)

    # Write each visual as visuals/<visual_name>/visual.json
    visuals_dir = os.path.join(page_dir, "visuals")
    for vis in visuals:
        visual_name = vis.get("name", _make_id())
        visual_dir = os.path.join(visuals_dir, visual_name)
        os.makedirs(visual_dir, exist_ok=True)

        visual_json = _build_visual_json(vis)
        vpath = os.path.join(visual_dir, "visual.json")
        with open(vpath, "w", encoding="utf-8") as f:
            json.dump(visual_json, f, indent=2, ensure_ascii=False)


def _build_visual_json(vis):
    """Build a PBIR v2.5.0 visual.json from an internal visual dict."""
    position = vis.get("position", {})
    # Ensure z and tabOrder exist
    if "z" not in position:
        position["z"] = 0
    if "tabOrder" not in position:
        position["tabOrder"] = position.get("z", 0)

    visual_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
        "name": vis.get("name", _make_id()),
        "position": position,
        "visual": vis.get("visual", {}),
    }

    # Add title via objects if present
    title = vis.get("title", "")
    if title:
        objects = visual_json["visual"].setdefault("objects", {})
        objects["title"] = [{
            "properties": {
                "text": {
                    "expr": {
                        "Literal": {"Value": f"'{title}'"}
                    }
                }
            }
        }]

    return visual_json


def _write_pages_json(pages_dir, page_ids):
    """Write pages/pages.json with page ordering metadata."""
    pages_meta = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": page_ids,
        "activePageName": page_ids[0] if page_ids else "",
    }
    path = os.path.join(pages_dir, "pages.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pages_meta, f, indent=2, ensure_ascii=False)


def _write_report_manifest(data, output_dir, stats):
    """Write the top-level report.json manifest (PBIR v2.0.0 schema)."""
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/2.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {
                "name": "CY24SU06",
                "reportVersionAtImport": "5.55",
                "type": "SharedResources",
            }
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [
                    {
                        "name": "CY24SU06",
                        "path": "BaseThemes/CY24SU06.json",
                        "type": "BaseTheme",
                    }
                ],
            }
        ],
        "settings": {
            "hideVisualContainerHeader": True,
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "None",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
        },
    }
    path = os.path.join(output_dir, "report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.debug("Wrote report manifest → %s", path)


# ── Helpers ──────────────────────────────────────────────────────

def _make_id():
    """Generate a deterministic-ish visual ID."""
    return uuid.uuid4().hex[:16]
