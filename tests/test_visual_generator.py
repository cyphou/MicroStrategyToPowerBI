"""Tests for visual generator module (PBIR v4.0 visual JSON generation)."""

import json
import os
import pytest

from powerbi_import.visual_generator import (
    generate_all_visuals,
    _VIZ_TYPE_MAP,
    _DATA_ROLE_MAP,
    _build_data_bindings,
    _scale_position,
    _build_formatting,
    _build_conditional_formatting,
    _make_binding,
    _convert_visualization,
    _convert_report_grid,
    _convert_report_graph,
    _convert_selector,
    _build_slicer_visual,
    _build_page_json,
)


# ── Viz Type Mapping ──────────────────────────────────────────────

class TestVizTypeMap:
    """Test MSTR→PBI visual type mapping."""

    @pytest.mark.parametrize("mstr_type,expected_pbi", [
        ("grid", "tableEx"),
        ("crosstab", "matrix"),
        ("vertical_bar", "clusteredColumnChart"),
        ("stacked_vertical_bar", "stackedColumnChart"),
        ("horizontal_bar", "clusteredBarChart"),
        ("stacked_horizontal_bar", "stackedBarChart"),
        ("line", "lineChart"),
        ("area", "areaChart"),
        ("stacked_area", "stackedAreaChart"),
        ("pie", "pieChart"),
        ("ring", "donutChart"),
        ("scatter", "scatterChart"),
        ("bubble", "scatterChart"),
        ("combo", "lineClusteredColumnComboChart"),
        ("dual_axis", "lineClusteredColumnComboChart"),
        ("map", "map"),
        ("filled_map", "filledMap"),
        ("treemap", "treemap"),
        ("waterfall", "waterfall"),
        ("funnel", "funnel"),
        ("gauge", "gauge"),
        ("kpi", "kpi"),
        ("heat_map", "matrix"),
        ("histogram", "clusteredColumnChart"),
        ("text", "textbox"),
        ("image", "image"),
        ("html", "textbox"),
        ("filter_panel", "slicer"),
        ("selector", "slicer"),
    ])
    def test_viz_type_mapping(self, mstr_type, expected_pbi):
        assert _VIZ_TYPE_MAP[mstr_type] == expected_pbi

    def test_all_types_have_mappings(self):
        assert len(_VIZ_TYPE_MAP) >= 29

    def test_unsupported_falls_back(self):
        """Unknown types should use pbi_visual_type from intermediate data or tableEx."""
        viz = {
            "viz_type": "unknown_custom_type",
            "pbi_visual_type": "tableEx",
            "data": {"attributes": [], "metrics": []},
            "position": {},
            "formatting": {},
            "thresholds": [],
            "key": "test_viz",
            "name": "Test",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "tableEx"


# ── Data Role Map ────────────────────────────────────────────────

class TestDataRoleMap:

    def test_table_has_values(self):
        assert "Values" in _DATA_ROLE_MAP["tableEx"].values()

    def test_matrix_has_rows_columns_values(self):
        roles = _DATA_ROLE_MAP["matrix"]
        assert "Rows" in roles.values()
        assert "Columns" in roles.values()
        assert "Values" in roles.values()

    def test_chart_has_category_and_y(self):
        for chart in ("clusteredColumnChart", "lineChart", "pieChart"):
            roles = _DATA_ROLE_MAP[chart]
            assert "Category" in roles.values()

    def test_scatter_has_xy_details(self):
        roles = _DATA_ROLE_MAP["scatterChart"]
        assert "X" in roles.values()
        assert "Y" in roles.values()
        assert "Details" in roles.values()


# ── Data Bindings ────────────────────────────────────────────────

class TestBuildDataBindings:

    def _attrs(self, *names):
        return [{"id": f"id_{n}", "name": n} for n in names]

    def _metrics(self, *names):
        return [{"id": f"id_{n}", "name": n} for n in names]

    def test_table_bindings(self):
        bindings = _build_data_bindings(
            "tableEx",
            self._attrs("Customer"), self._metrics("Revenue"), {}
        )
        assert len(bindings) == 2
        roles = [b["role"] for b in bindings]
        assert all(r == "Values" for r in roles)

    def test_matrix_bindings(self):
        source = {
            "grid": {
                "rows": [{"name": "Customer", "type": "attribute"}],
                "columns": [{"name": "Year", "type": "attribute"}],
            }
        }
        bindings = _build_data_bindings(
            "matrix",
            self._attrs("Customer"), self._metrics("Revenue"), source
        )
        roles = {b["role"] for b in bindings}
        assert "Rows" in roles
        assert "Columns" in roles
        assert "Values" in roles

    def test_bar_chart_bindings(self):
        bindings = _build_data_bindings(
            "clusteredColumnChart",
            self._attrs("Region"), self._metrics("Revenue", "Cost"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "Category" in roles
        assert roles.count("Y") == 2

    def test_line_chart_bindings(self):
        bindings = _build_data_bindings(
            "lineChart",
            self._attrs("Month"), self._metrics("Revenue"), {}
        )
        assert any(b["role"] == "Category" for b in bindings)
        assert any(b["role"] == "Y" for b in bindings)

    def test_pie_chart_bindings(self):
        bindings = _build_data_bindings(
            "pieChart",
            self._attrs("Category"), self._metrics("Revenue"), {}
        )
        assert any(b["role"] == "Category" for b in bindings)
        assert any(b["role"] == "Y" for b in bindings)

    def test_scatter_chart_bindings(self):
        bindings = _build_data_bindings(
            "scatterChart",
            self._attrs("Product"), self._metrics("Revenue", "Quantity", "Count"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "X" in roles
        assert "Y" in roles
        assert "Details" in roles
        assert "Size" in roles

    def test_scatter_two_metrics(self):
        bindings = _build_data_bindings(
            "scatterChart",
            self._attrs("Product"), self._metrics("Revenue", "Quantity"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "X" in roles
        assert "Y" in roles
        assert "Size" not in roles

    def test_combo_chart_bindings(self):
        bindings = _build_data_bindings(
            "lineClusteredColumnComboChart",
            self._attrs("Month"), self._metrics("Revenue", "Cost"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "Category" in roles
        assert "ColumnY" in roles
        assert "LineY" in roles

    def test_kpi_bindings(self):
        bindings = _build_data_bindings(
            "kpi",
            self._attrs("Month"), self._metrics("Revenue"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "Indicator" in roles
        assert "TrendAxis" in roles

    def test_gauge_bindings(self):
        bindings = _build_data_bindings(
            "gauge",
            [], self._metrics("Profit Margin"),
            {"formatting": {"targetValue": 0.2}}
        )
        roles = [b["role"] for b in bindings]
        assert "Y" in roles
        assert "TargetValue" in roles

    def test_slicer_bindings(self):
        bindings = _build_data_bindings(
            "slicer",
            self._attrs("Year"), [], {}
        )
        assert len(bindings) == 1
        assert bindings[0]["role"] == "Field"

    def test_map_bindings(self):
        bindings = _build_data_bindings(
            "map",
            self._attrs("City"), self._metrics("Revenue"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "Category" in roles
        assert "Size" in roles

    def test_filled_map_bindings(self):
        bindings = _build_data_bindings(
            "filledMap",
            self._attrs("Country"), self._metrics("Revenue"), {}
        )
        roles = [b["role"] for b in bindings]
        assert "Category" in roles
        assert "Color" in roles

    def test_empty_data(self):
        bindings = _build_data_bindings("clusteredColumnChart", [], [], {})
        assert bindings == []


# ── Make Binding ─────────────────────────────────────────────────

class TestMakeBinding:

    def test_basic_binding(self):
        b = _make_binding("Values", "Revenue", "measure")
        assert b["role"] == "Values"
        assert b["source"]["field"] == "Revenue"
        assert b["source"]["type"] == "measure"

    def test_default_type_is_column(self):
        b = _make_binding("Category", "Month")
        assert b["source"]["type"] == "column"


# ── Position Scaling ─────────────────────────────────────────────

class TestScalePosition:

    def test_identity_scale(self):
        """1280×720 source → no change."""
        pos = _scale_position({"x": 100, "y": 50, "width": 400, "height": 300}, 1280, 720)
        assert pos == {"x": 100, "y": 50, "width": 400, "height": 300}

    def test_scale_from_1024x768(self):
        pos = _scale_position({"x": 0, "y": 0, "width": 1024, "height": 768}, 1024, 768)
        assert pos["width"] == 1280
        assert pos["height"] == 720

    def test_proportional_scaling(self):
        pos = _scale_position({"x": 512, "y": 384, "width": 256, "height": 192}, 1024, 768)
        assert pos["x"] == 640
        assert pos["y"] == 360
        assert pos["width"] == 320
        assert pos["height"] == 180

    def test_empty_position(self):
        pos = _scale_position({}, 1024, 768)
        assert pos["width"] == 1280
        assert pos["height"] == 720

    def test_none_position(self):
        pos = _scale_position(None, 1024, 768)
        assert pos["width"] == 1280
        assert pos["height"] == 720


# ── Formatting ───────────────────────────────────────────────────

class TestBuildFormatting:

    def test_data_labels_on(self):
        fmt = _build_formatting("lineChart", {"showDataLabels": True})
        assert "labels" in fmt

    def test_legend_hidden(self):
        fmt = _build_formatting("lineChart", {"showLegend": False})
        assert "legend" in fmt
        prop = fmt["legend"][0]["properties"]["show"]["expr"]["Literal"]["Value"]
        assert prop == "false"

    def test_legend_shown(self):
        fmt = _build_formatting("lineChart", {"showLegend": True})
        assert "legend" in fmt
        prop = fmt["legend"][0]["properties"]["show"]["expr"]["Literal"]["Value"]
        assert prop == "true"

    def test_empty_formatting(self):
        fmt = _build_formatting("lineChart", {})
        assert fmt == {}


# ── Conditional Formatting ───────────────────────────────────────

class TestConditionalFormatting:

    def test_threshold_conversion(self):
        thresholds = [{
            "metric_name": "Profit Margin",
            "conditions": [
                {"operator": "less_than", "value": 0.10, "format": {"background_color": "#FF0000"}},
                {"operator": "greater_than", "value": 0.25, "format": {"background_color": "#00FF00"}},
            ]
        }]
        rules = _build_conditional_formatting(thresholds, "tableEx")
        assert len(rules) == 2
        assert rules[0]["backgroundColor"] == "#FF0000"
        assert rules[1]["backgroundColor"] == "#00FF00"
        assert rules[0]["metricName"] == "Profit Margin"

    def test_font_color_conversion(self):
        thresholds = [{
            "metric_name": "Score",
            "conditions": [
                {"operator": "less_than", "value": 50, "format": {"font_color": "#FFFFFF"}},
            ]
        }]
        rules = _build_conditional_formatting(thresholds, "tableEx")
        assert rules[0]["fontColor"] == "#FFFFFF"

    def test_empty_thresholds(self):
        assert _build_conditional_formatting([], "tableEx") is None

    def test_none_thresholds(self):
        assert _build_conditional_formatting(None, "tableEx") is None


# ── Convert Visualization ────────────────────────────────────────

class TestConvertVisualization:

    def _make_viz(self, viz_type, attrs=None, metrics=None, **kwargs):
        return {
            "key": f"test_{viz_type}",
            "name": f"Test {viz_type}",
            "viz_type": viz_type,
            "pbi_visual_type": _VIZ_TYPE_MAP.get(viz_type, "tableEx"),
            "data": {
                "attributes": attrs or [],
                "metrics": metrics or [],
            },
            "formatting": kwargs.get("formatting", {}),
            "thresholds": kwargs.get("thresholds", []),
            "position": kwargs.get("position", {"x": 0, "y": 0, "width": 500, "height": 300}),
        }

    def test_line_chart_visual(self):
        viz = self._make_viz("line",
            attrs=[{"id": "a1", "name": "Month"}],
            metrics=[{"id": "m1", "name": "Revenue"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "lineChart"
        assert result["title"] == "Test line"
        assert len(result["dataTransforms"]["bindings"]) == 2

    def test_grid_visual(self):
        viz = self._make_viz("grid",
            attrs=[{"id": "a1", "name": "Customer"}],
            metrics=[{"id": "m1", "name": "Revenue"}, {"id": "m2", "name": "Cost"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "tableEx"
        assert len(result["dataTransforms"]["bindings"]) == 3

    def test_pie_chart_visual(self):
        viz = self._make_viz("pie",
            attrs=[{"id": "a1", "name": "Category"}],
            metrics=[{"id": "m1", "name": "Revenue"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "pieChart"

    def test_kpi_visual(self):
        viz = self._make_viz("kpi",
            metrics=[{"id": "m1", "name": "Revenue"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "kpi"
        assert any(b["role"] == "Indicator" for b in result["dataTransforms"]["bindings"])

    def test_gauge_visual(self):
        viz = self._make_viz("gauge",
            metrics=[{"id": "m1", "name": "Profit Margin"}],
            formatting={"targetValue": 0.2})
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "gauge"

    def test_scatter_visual(self):
        viz = self._make_viz("scatter",
            attrs=[{"id": "a1", "name": "Product"}],
            metrics=[{"id": "m1", "name": "Revenue"}, {"id": "m2", "name": "Quantity"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "scatterChart"
        roles = {b["role"] for b in result["dataTransforms"]["bindings"]}
        assert "X" in roles
        assert "Y" in roles

    def test_treemap_visual(self):
        viz = self._make_viz("treemap",
            attrs=[{"id": "a1", "name": "Category"}, {"id": "a2", "name": "Product"}],
            metrics=[{"id": "m1", "name": "Revenue"}])
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "treemap"

    def test_textbox_visual(self):
        viz = self._make_viz("text")
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "textbox"
        assert result["dataTransforms"]["bindings"] == []

    def test_image_visual(self):
        viz = self._make_viz("image")
        result = _convert_visualization(viz, 1024, 768)
        assert result["visual"]["visualType"] == "image"

    def test_position_is_scaled(self):
        viz = self._make_viz("line",
            attrs=[{"id": "a1", "name": "Month"}],
            metrics=[{"id": "m1", "name": "Revenue"}],
            position={"x": 0, "y": 0, "width": 1024, "height": 768})
        result = _convert_visualization(viz, 1024, 768)
        assert result["position"]["width"] == 1280
        assert result["position"]["height"] == 720

    def test_thresholds_attached(self):
        viz = self._make_viz("grid",
            attrs=[{"id": "a1", "name": "Customer"}],
            metrics=[{"id": "m1", "name": "Revenue"}],
            thresholds=[{
                "metric_name": "Revenue",
                "conditions": [{"operator": "less_than", "value": 100, "format": {"background_color": "#FF0000"}}]
            }])
        result = _convert_visualization(viz, 1024, 768)
        assert "conditionalFormatting" in result["visual"]["objects"]


# ── Convert Report Grid ──────────────────────────────────────────

class TestConvertReportGrid:

    def test_simple_grid_becomes_table(self):
        report = {
            "grid": {
                "rows": [{"name": "Customer", "type": "attribute"}],
                "columns": [],
            },
            "metrics": [{"name": "Revenue"}],
        }
        result = _convert_report_grid(report)
        assert result["visual"]["visualType"] == "tableEx"

    def test_crosstab_becomes_matrix(self):
        report = {
            "grid": {
                "rows": [{"name": "Region", "type": "attribute"}],
                "columns": [{"name": "Year", "type": "attribute"}],
            },
            "metrics": [{"name": "Revenue"}],
        }
        result = _convert_report_grid(report)
        assert result["visual"]["visualType"] == "matrix"
        roles = {b["role"] for b in result["dataTransforms"]["bindings"]}
        assert "Rows" in roles
        assert "Columns" in roles
        assert "Values" in roles

    def test_subtotals_on_matrix(self):
        report = {
            "grid": {
                "rows": [{"name": "Region", "type": "attribute"}],
                "columns": [{"name": "Year", "type": "attribute"}],
            },
            "metrics": [{"name": "Revenue"}],
            "subtotals": [{"type": "grand_total"}],
        }
        result = _convert_report_grid(report)
        assert "subTotals" in result["visual"]["objects"]


# ── Convert Report Graph ─────────────────────────────────────────

class TestConvertReportGraph:

    def test_line_graph(self):
        report = {
            "graph": {
                "mstr_type": "line",
                "attributes_on_axis": [{"name": "Month"}],
                "metrics_on_axis": [{"name": "Revenue"}],
                "color_by": "",
            },
            "metrics": [{"name": "Revenue"}],
            "report_type": "graph",
        }
        result = _convert_report_graph(report)
        assert result["visual"]["visualType"] == "lineChart"

    def test_graph_with_color_by(self):
        report = {
            "graph": {
                "mstr_type": "line",
                "attributes_on_axis": [{"name": "Month"}],
                "metrics_on_axis": [{"name": "Revenue"}],
                "color_by": "Product",
            },
            "metrics": [{"name": "Revenue"}],
            "report_type": "graph",
        }
        result = _convert_report_graph(report)
        roles = [b["role"] for b in result["dataTransforms"]["bindings"]]
        assert "Series" in roles

    def test_no_graph_returns_none(self):
        report = {"graph": None, "metrics": [], "report_type": "grid"}
        assert _convert_report_graph(report) is None

    def test_grid_graph_offset(self):
        report = {
            "graph": {
                "mstr_type": "line",
                "attributes_on_axis": [{"name": "Month"}],
                "metrics_on_axis": [{"name": "Revenue"}],
                "color_by": "",
            },
            "metrics": [{"name": "Revenue"}],
            "report_type": "grid_graph",
        }
        result = _convert_report_graph(report)
        assert result["position"]["y"] == 520


# ── Convert Selector ─────────────────────────────────────────────

class TestConvertSelector:

    def test_selector_to_slicer(self):
        sel = {
            "key": "sel_01",
            "name": "Year Selector",
            "attribute": {"id": "a1", "name": "Year"},
        }
        result = _convert_selector(sel, 1024, 768)
        assert result["visual"]["visualType"] == "slicer"
        assert result["dataTransforms"]["bindings"][0]["source"]["field"] == "Year"


# ── Build Slicer Visual ─────────────────────────────────────────

class TestBuildSlicerVisual:

    def test_slicer_structure(self):
        result = _build_slicer_visual("Year", "slicer_01")
        assert result["visual"]["visualType"] == "slicer"
        assert result["name"] == "slicer_01"
        assert result["title"] == "Year"
        assert result["dataTransforms"]["bindings"][0]["role"] == "Field"


# ── Page JSON ────────────────────────────────────────────────────

class TestBuildPageJson:

    def test_page_structure(self):
        page = _build_page_json("pg_01", "My Page", [{"visual": "v1"}])
        assert page["name"] == "pg_01"
        assert page["displayName"] == "My Page"
        assert page["width"] == 1280
        assert page["height"] == 720
        assert "$schema" in page
        # Visuals are no longer inline in page.json (PBIR v2.0.0)
        assert "visuals" not in page

    def test_section_name(self):
        # sectionName is no longer written in PBIR v2.0.0 page.json
        page = _build_page_json("pg_01", "My Page", [], section_name="Overview")
        assert "sectionName" not in page

    def test_no_section_name(self):
        page = _build_page_json("pg_01", "My Page", [])
        assert "sectionName" not in page


# ── Full Pipeline (generate_all_visuals) ─────────────────────────

class TestGenerateAllVisuals:

    def test_generates_pages_from_dossier(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        stats = generate_all_visuals(data, str(output_dir))
        assert stats["pages"] >= 1
        assert stats["visuals"] >= 1
        assert os.path.exists(output_dir / "pages")
        assert os.path.exists(output_dir / "report.json")

    def test_generates_pages_from_reports(self, intermediate_reports, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": [], "reports": intermediate_reports}
        stats = generate_all_visuals(data, str(output_dir))
        assert stats["pages"] >= 1

    def test_dossier_page_count(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        stats = generate_all_visuals(data, str(output_dir))
        # Fixture dossier has 3 pages (KPI Summary, Regional Analysis, Product Performance)
        assert stats["pages"] == 3

    def test_visual_count(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        stats = generate_all_visuals(data, str(output_dir))
        # Fixture has: KPI (2), gauge, line, pie, grid, bar, scatter, treemap = 9 viz but 2 KPIs are kpi type
        assert stats["visuals"] >= 7

    def test_selector_becomes_slicer(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        stats = generate_all_visuals(data, str(output_dir))
        # Fixture has 1 selector on Regional Analysis page
        assert stats["slicers"] >= 1

    def test_report_manifest_written(self, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": [], "reports": []}
        generate_all_visuals(data, str(output_dir))
        manifest_path = output_dir / "report.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "report/2.0.0/schema.json" in manifest["$schema"]
        assert "settings" in manifest
        assert "resourcePackages" in manifest
        assert "datasetBinding" not in manifest

    def test_page_json_files_written(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        generate_all_visuals(data, str(output_dir))
        pages_dir = output_dir / "pages"
        page_dirs = [d for d in pages_dir.iterdir() if d.is_dir()]
        assert len(page_dirs) >= 1
        # Each page dir should have a page.json
        for pd in page_dirs:
            assert (pd / "page.json").exists()

    def test_page_json_has_visuals(self, intermediate_dossiers, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": []}
        generate_all_visuals(data, str(output_dir))
        pages_dir = output_dir / "pages"
        for pd in pages_dir.iterdir():
            if pd.is_dir() and (pd / "page.json").exists():
                page = json.loads((pd / "page.json").read_text(encoding="utf-8"))
                assert "displayName" in page
                # Visuals are now in separate visuals/<id>/visual.json files
                assert "visuals" not in page
                visuals_dir = pd / "visuals"
                assert visuals_dir.exists()
                visual_files = list(visuals_dir.glob("*/visual.json"))
                assert len(visual_files) >= 1

    def test_combined_dossiers_and_reports(self, intermediate_dossiers,
                                            intermediate_reports, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": intermediate_dossiers, "reports": intermediate_reports}
        stats = generate_all_visuals(data, str(output_dir))
        # Should have dossier pages + report pages
        assert stats["pages"] >= 4

    def test_empty_data(self, tmp_path):
        output_dir = tmp_path / "Report" / "definition"
        data = {"dossiers": [], "reports": []}
        stats = generate_all_visuals(data, str(output_dir))
        assert stats["pages"] == 0
        assert stats["visuals"] == 0
        # report.json should still be written
        assert os.path.exists(output_dir / "report.json")
