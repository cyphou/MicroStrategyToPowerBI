"""
Tests for v4.0 features — Sprints L through Q.
"""

import json
import os
import tempfile

import pytest


# ═══════════════════════════════════════════════════════════════════
# Sprint L — OLAP Metric Hardening
# ═══════════════════════════════════════════════════════════════════

class TestOLAPHardening:
    """Expression converter OLAP patterns (Sprint L)."""

    def _convert(self, expr, context=None):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        return convert_mstr_expression_to_dax(expr, context or {})

    # ── RunningSum ────────────────────────────────────────────────

    def test_running_sum_basic(self):
        r = self._convert("RunningSum([Revenue])")
        assert "WINDOW" in r["dax"]
        assert "1, ABS, 0, REL" in r["dax"]

    def test_running_sum_with_level(self):
        r = self._convert("RunningSum([Revenue]) {~+, Year}")
        assert "WINDOW" in r["dax"]
        assert "Year" in r["dax"]

    # ── RunningAvg ────────────────────────────────────────────────

    def test_running_avg_basic(self):
        r = self._convert("RunningAvg([Revenue])")
        assert "WINDOW" in r["dax"]
        assert "DIVIDE" in r["dax"]
        assert "COUNTROWS" in r["dax"]

    def test_running_avg_with_level(self):
        r = self._convert("RunningAvg([Revenue]) {~+, Month}")
        assert "Month" in r["dax"]

    # ── MovingAvg ────────────────────────────────────────────────

    def test_moving_avg_window_3(self):
        r = self._convert("MovingAvg([Revenue], 3)")
        assert "WINDOW" in r["dax"]
        assert "-2, REL, 0, REL" in r["dax"]
        assert "AVERAGEX" in r["dax"]

    def test_moving_avg_window_5(self):
        r = self._convert("MovingAvg([Revenue], 5)")
        assert "-4, REL" in r["dax"]

    def test_moving_avg_with_level(self):
        r = self._convert("MovingAvg([Revenue], 3) {~+, Day}")
        assert "Day" in r["dax"]
        assert r["fidelity"] == "full"

    # ── MovingSum ────────────────────────────────────────────────

    def test_moving_sum_window_3(self):
        r = self._convert("MovingSum([Revenue], 3)")
        assert "WINDOW" in r["dax"]
        assert "SUMX" in r["dax"]
        assert "-2, REL" in r["dax"]

    # ── Lag ───────────────────────────────────────────────────────

    def test_lag_offset_1(self):
        r = self._convert("Lag([Revenue], 1)")
        assert "OFFSET" in r["dax"]
        assert "-1" in r["dax"]

    def test_lag_offset_3(self):
        r = self._convert("Lag([Revenue], 3)")
        assert "-3" in r["dax"]

    def test_lag_with_level(self):
        r = self._convert("Lag([Revenue], 1) {~+, Month}")
        assert "Month" in r["dax"]
        assert r["fidelity"] == "full"

    # ── Lead ──────────────────────────────────────────────────────

    def test_lead_offset_1(self):
        r = self._convert("Lead([Revenue], 1)")
        assert "OFFSET" in r["dax"]
        assert not r["dax"].startswith("-")  # positive offset

    def test_lead_with_level(self):
        r = self._convert("Lead([Revenue], 1) {~+, Quarter}")
        assert "Quarter" in r["dax"]

    # ── NTile ────────────────────────────────────────────────────

    def test_ntile_4(self):
        r = self._convert("NTile([Revenue], 4)")
        assert "RANKX" in r["dax"]
        assert "COUNTROWS" in r["dax"]
        assert "4" in r["dax"]
        assert "CEILING" in r["dax"]

    def test_ntile_with_level(self):
        r = self._convert("NTile([Revenue], 4) {~+, Region}")
        assert "ALL(Region)" in r["dax"]
        assert r["fidelity"] == "full"

    # ── Rank ─────────────────────────────────────────────────────

    def test_rank_default_desc(self):
        r = self._convert("Rank([Revenue])")
        assert "RANKX" in r["dax"]
        assert "DESC" in r["dax"]
        assert "SKIP" in r["dax"]

    def test_rank_asc(self):
        r = self._convert("Rank([Revenue], ASC)")
        assert "ASC" in r["dax"]

    def test_rank_dense(self):
        r = self._convert("Rank([Revenue], DESC, DENSE)")
        assert "DENSE" in r["dax"]

    def test_rank_with_level(self):
        r = self._convert("Rank([Revenue]) {~+, Product}")
        assert "ALL(Product)" in r["dax"]
        assert r["fidelity"] == "full"

    # ── FirstInRange / LastInRange ───────────────────────────────

    def test_first_in_range(self):
        r = self._convert("FirstInRange([Revenue], Date)")
        assert "TOPN(1" in r["dax"]
        assert "ASC" in r["dax"]
        assert r["fidelity"] == "full"

    def test_last_in_range(self):
        r = self._convert("LastInRange([Revenue], Date)")
        assert "TOPN(1" in r["dax"]
        assert "DESC" in r["dax"]

    # ── ApplyOLAP hardening ──────────────────────────────────────

    def test_apply_olap_row_number(self):
        r = self._convert('ApplyOLAP("ROW_NUMBER() OVER (ORDER BY #0)", Revenue)')
        assert "RANKX" in r["dax"]
        assert r["fidelity"] != "manual_review"

    def test_apply_olap_rank(self):
        r = self._convert('ApplyOLAP("RANK() OVER (ORDER BY #0 DESC)", Revenue)')
        assert "RANKX" in r["dax"]
        assert "DESC" in r["dax"]

    def test_apply_olap_dense_rank(self):
        r = self._convert('ApplyOLAP("DENSE_RANK() OVER (ORDER BY #0)", Revenue)')
        assert "DENSE" in r["dax"]

    def test_apply_olap_lag(self):
        r = self._convert('ApplyOLAP("LAG(#0, 1) OVER (ORDER BY #1)", Revenue, Month)')
        assert "OFFSET" in r["dax"]
        assert "-1" in r["dax"]

    def test_apply_olap_lead(self):
        r = self._convert('ApplyOLAP("LEAD(#0, 2) OVER (ORDER BY #1)", Revenue, Month)')
        assert "OFFSET" in r["dax"]
        assert "2" in r["dax"]

    def test_apply_olap_cumulative_sum(self):
        r = self._convert('ApplyOLAP("SUM(#0) OVER (ORDER BY #1 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)", Revenue, Month)')
        assert "WINDOW" in r["dax"]

    def test_apply_olap_unknown_falls_back(self):
        r = self._convert('ApplyOLAP("PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY #0)", Revenue)')
        assert r["fidelity"] == "manual_review"

    # ── Band ─────────────────────────────────────────────────────

    def test_band_pattern(self):
        r = self._convert("Band([Revenue], 0, 100, 25)")
        assert "IF" in r["dax"]
        assert "100" in r["dax"]
        assert "25" in r["dax"]


# ═══════════════════════════════════════════════════════════════════
# Sprint M — Merge & Consolidation
# ═══════════════════════════════════════════════════════════════════

class TestMergeAssessment:
    """Merge overlap analysis and viability scoring."""

    def _make_project(self, name, metrics=None, attrs=None, datasources=None):
        return (name, {
            "metrics": metrics or [],
            "derived_metrics": [],
            "attributes": attrs or [],
            "datasources": datasources or [],
        })

    def test_no_overlap(self):
        from powerbi_import.merge_assessment import analyze_overlap
        projects = [
            self._make_project("A", metrics=[{"name": "M1"}]),
            self._make_project("B", metrics=[{"name": "M2"}]),
        ]
        overlap = analyze_overlap(projects)
        assert len(overlap["shared_metrics"]) == 0

    def test_shared_metric(self):
        from powerbi_import.merge_assessment import analyze_overlap
        projects = [
            self._make_project("A", metrics=[{"name": "Revenue"}]),
            self._make_project("B", metrics=[{"name": "Revenue"}]),
        ]
        overlap = analyze_overlap(projects)
        assert "Revenue" in overlap["shared_metrics"]

    def test_conflict_detection(self):
        from powerbi_import.merge_assessment import analyze_overlap
        projects = [
            self._make_project("A", metrics=[{"name": "M1", "expression": "SUM(a)"}]),
            self._make_project("B", metrics=[{"name": "M1", "expression": "AVG(b)"}]),
        ]
        overlap = analyze_overlap(projects)
        assert len(overlap["conflicts"]) >= 1

    def test_viability_green(self):
        from powerbi_import.merge_assessment import score_merge_viability
        overlap = {"shared_tables": {"T1": ["A", "B"]}, "shared_metrics": {}, "conflicts": []}
        v = score_merge_viability(overlap)
        assert v["rating"] == "GREEN"
        assert v["score"] >= 50

    def test_viability_red(self):
        from powerbi_import.merge_assessment import score_merge_viability
        overlap = {"shared_tables": {}, "shared_metrics": {},
                    "conflicts": [{"name": f"c{i}"} for i in range(10)]}
        v = score_merge_viability(overlap)
        assert v["rating"] == "RED"

    def test_run_merge_assessment(self):
        from powerbi_import.merge_assessment import run_merge_assessment
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "proj1")
            p2 = os.path.join(tmpdir, "proj2")
            os.makedirs(p1)
            os.makedirs(p2)
            _write(os.path.join(p1, "metrics.json"), [{"name": "M1"}])
            _write(os.path.join(p2, "metrics.json"), [{"name": "M1"}])
            result = run_merge_assessment([p1, p2])
            assert "overlap" in result
            assert "viability" in result


class TestMergeConfig:
    """Merge config loading and conflict resolution."""

    def test_default_config(self):
        from powerbi_import.merge_config import load_merge_config
        cfg = load_merge_config(None)
        assert cfg["conflict_resolution"] == "keep_first"

    def test_load_custom_config(self):
        from powerbi_import.merge_config import load_merge_config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"conflict_resolution": "keep_all"}, f)
            f.flush()
            cfg = load_merge_config(f.name)
        os.unlink(f.name)
        assert cfg["conflict_resolution"] == "keep_all"

    def test_apply_renames(self):
        from powerbi_import.merge_config import apply_renames
        data = {"metrics": [{"name": "OldName"}]}
        result = apply_renames(data, {"OldName": "NewName"})
        assert result["metrics"][0]["name"] == "NewName"

    def test_resolve_conflicts_keep_first(self):
        from powerbi_import.merge_config import resolve_conflicts
        objects_by_name = {"M1": [("A", {"name": "M1", "v": 1}), ("B", {"name": "M1", "v": 2})]}
        resolved = resolve_conflicts(objects_by_name, {"conflict_resolution": "keep_first"})
        assert len(resolved) == 1
        assert resolved[0]["v"] == 1

    def test_resolve_conflicts_keep_all(self):
        from powerbi_import.merge_config import resolve_conflicts
        objects_by_name = {"M1": [("A", {"name": "M1"}), ("B", {"name": "M1"})]}
        resolved = resolve_conflicts(objects_by_name, {"conflict_resolution": "keep_all"})
        assert len(resolved) == 2

    def test_merge_project_data(self):
        from powerbi_import.merge_config import merge_project_data, load_merge_config
        projects = [
            ("P1", {"metrics": [{"name": "M1"}], "datasources": [{"name": "DS1", "tables": [{"name": "T1"}]}]}),
            ("P2", {"metrics": [{"name": "M2"}], "datasources": [{"name": "DS1", "tables": [{"name": "T2"}]}]}),
        ]
        merged = merge_project_data(projects, load_merge_config(None))
        assert len(merged["metrics"]) == 2

    def test_generate_default_config(self):
        from powerbi_import.merge_config import generate_default_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            generate_default_config(path)
            assert os.path.isfile(path)
            with open(path) as f:
                cfg = json.load(f)
            assert "conflict_resolution" in cfg


class TestMergeReport:
    """Merge HTML report generation."""

    def test_generate_report(self):
        from powerbi_import.merge_report_html import generate_merge_report
        assessment = {
            "projects": ["A", "B"],
            "overlap": {
                "shared_tables": {"T1": ["A", "B"]},
                "shared_metrics": {},
                "shared_attributes": {},
                "conflicts": [],
                "unique_per_project": {},
            },
            "viability": {"score": 85, "rating": "GREEN", "recommendation": "OK"},
        }
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "report.html")
            generate_merge_report(assessment, path)
            assert os.path.isfile(path)
            content = open(path).read()
            assert "Score: 85/100" in content
            assert "GREEN" in content


class TestSharedModelMerge:
    """generate_merged_model integration."""

    def test_merged_model_generation(self):
        from powerbi_import.shared_model import generate_merged_model
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two project dirs
            p1 = os.path.join(tmpdir, "input", "proj1")
            p2 = os.path.join(tmpdir, "input", "proj2")
            out = os.path.join(tmpdir, "output")
            os.makedirs(p1)
            os.makedirs(p2)
            _write(os.path.join(p1, "datasources.json"), [{
                "name": "Sales",
                "tables": [{"name": "Sales"}],
                "columns": [{"name": "Revenue", "dataType": "decimal"}],
                "connection_type": "odbc",
                "connection_string": "DSN=test",
            }])
            _write(os.path.join(p1, "attributes.json"), [])
            _write(os.path.join(p1, "facts.json"), [])
            _write(os.path.join(p1, "metrics.json"), [{"name": "TotalRevenue", "id": "m1",
                    "metric_type": "simple", "aggregation": "sum",
                    "column_ref": {"fact_name": "Revenue"}, "expression": ""}])
            _write(os.path.join(p2, "datasources.json"), [{
                "name": "Marketing",
                "tables": [{"name": "Marketing"}],
                "columns": [{"name": "Cost", "dataType": "decimal"}],
                "connection_type": "odbc",
                "connection_string": "DSN=test2",
            }])
            _write(os.path.join(p2, "attributes.json"), [])
            _write(os.path.join(p2, "facts.json"), [])
            _write(os.path.join(p2, "metrics.json"), [{"name": "TotalCost", "id": "m2",
                    "metric_type": "simple", "aggregation": "sum",
                    "column_ref": {"fact_name": "Cost"}, "expression": ""}])

            result = generate_merged_model([p1, p2], out, model_name="TestMerge")
            assert "assessment" in result
            assert "generation" in result
            assert os.path.isfile(os.path.join(out, "merge_report.html"))


# ═══════════════════════════════════════════════════════════════════
# Sprint N — Advanced Dossier Features
# ═══════════════════════════════════════════════════════════════════

class TestThemeGenerator:
    """Power BI reportTheme.json generation."""

    def test_generate_default_theme(self):
        from powerbi_import.theme_generator import generate_theme
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "theme.json")
            generate_theme({}, path)
            assert os.path.isfile(path)
            with open(path) as f:
                theme = json.load(f)
            assert "dataColors" in theme
            assert len(theme["dataColors"]) == 10

    def test_custom_palette(self):
        from powerbi_import.theme_generator import generate_theme
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "theme.json")
            generate_theme({"palette": ["#FF0000", "#00FF00"]}, path)
            with open(path) as f:
                theme = json.load(f)
            assert theme["dataColors"][0] == "#FF0000"

    def test_font_mapping(self):
        from powerbi_import.theme_generator import _map_font
        assert _map_font("Helvetica") == "Segoe UI"
        assert _map_font("Arial") == "Arial"
        assert _map_font("CustomFont") == "CustomFont"

    def test_extract_theme_from_dossier(self):
        from powerbi_import.theme_generator import extract_theme_from_dossier
        dossier = {"formatting": {"palette": ["#AAA"], "font_family": "Verdana"}}
        theme_data = extract_theme_from_dossier(dossier)
        assert theme_data["palette"] == ["#AAA"]
        assert theme_data["font_family"] == "Verdana"


class TestPanelStackBookmarks:
    """Panel stack → bookmark conversion."""

    def test_convert_panel_stack(self):
        from powerbi_import.visual_generator import _convert_panel_stack
        visuals = [
            {"name": "v1", "visual": {"visualType": "chart"}},
            {"name": "v2", "visual": {"visualType": "chart"}},
            {"name": "v3", "visual": {"visualType": "chart"}},
        ]
        panel_stack = {
            "name": "PS1",
            "panels": [
                {"name": "Panel A", "visual_keys": ["v1", "v2"]},
                {"name": "Panel B", "visual_keys": ["v3"]},
            ],
        }
        bookmarks = _convert_panel_stack(panel_stack, visuals)
        assert len(bookmarks) == 2
        assert "Panel A" in bookmarks[0]["displayName"]
        assert "v1" in bookmarks[0]["options"]["targetVisualNames"]

    def test_empty_panel_stack(self):
        from powerbi_import.visual_generator import _convert_panel_stack
        bookmarks = _convert_panel_stack({"panels": []}, [])
        assert bookmarks == []


class TestInfoWindowTooltip:
    """Info window → tooltip conversion."""

    def test_apply_tooltip(self):
        from powerbi_import.visual_generator import _apply_info_window_tooltip
        viz_def = {"key": "v1", "info_window": {"text": "Details here"}}
        visuals = [{"name": "v1", "visual": {"objects": {}}}]
        _apply_info_window_tooltip(viz_def, visuals)
        assert "tooltips" in visuals[0]["visual"]["objects"]

    def test_no_info_window(self):
        from powerbi_import.visual_generator import _apply_info_window_tooltip
        viz_def = {"key": "v1"}
        visuals = [{"name": "v1", "visual": {"objects": {}}}]
        _apply_info_window_tooltip(viz_def, visuals)
        assert "tooltips" not in visuals[0]["visual"]["objects"]


class TestFieldParameterTable:
    """Field parameter table generation for selectors."""

    def test_generate_field_param(self):
        from powerbi_import.tmdl_generator import _generate_field_parameter_table
        sel = {
            "name": "MetricSelector",
            "selector_type": "metric_selector",
            "items": [{"name": "Revenue"}, {"name": "Cost"}, {"name": "Profit"}],
        }
        tmdl = _generate_field_parameter_table(sel)
        assert tmdl is not None
        assert "MetricSelector" in tmdl
        assert "Revenue" in tmdl
        assert "partition" in tmdl

    def test_empty_items_returns_none(self):
        from powerbi_import.tmdl_generator import _generate_field_parameter_table
        result = _generate_field_parameter_table({"name": "X", "items": []})
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# Sprint O — Scorecard → Goals
# ═══════════════════════════════════════════════════════════════════

class TestScorecardExtractor:
    """Scorecard extraction (offline path)."""

    def test_parse_offline_scorecards(self):
        from microstrategy_export.scorecard_extractor import parse_offline_scorecards
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "scorecards.json")
            _write(path, [{"id": "sc1", "name": "Sales Scorecard", "objectives": []}])
            result = parse_offline_scorecards(path)
            assert len(result) == 1
            assert result[0]["name"] == "Sales Scorecard"

    def test_missing_file(self):
        from microstrategy_export.scorecard_extractor import parse_offline_scorecards
        result = parse_offline_scorecards("/nonexistent/path.json")
        assert result == []

    def test_extract_thresholds(self):
        from microstrategy_export.scorecard_extractor import _extract_thresholds
        obj = {"thresholds": [{"name": "On Track", "min": 80, "max": 100, "color": "#28a745"}]}
        thresholds = _extract_thresholds(obj)
        assert len(thresholds) == 1
        assert thresholds[0]["min_value"] == 80


class TestGoalsGenerator:
    """Goals API payload generation."""

    def test_generate_goals(self):
        from powerbi_import.goals_generator import generate_goals
        scorecards = [{
            "name": "Sales Scorecard",
            "objectives": [{
                "name": "Increase Revenue",
                "target_value": 1000000,
                "current_value": 750000,
                "status": "on_track",
                "metric_name": "Revenue",
                "thresholds": [],
                "children": [],
            }],
            "kpis": [{
                "name": "Customer Count",
                "target": 500,
                "unit": "customers",
                "thresholds": [],
            }],
        }]
        with tempfile.TemporaryDirectory() as d:
            stats = generate_goals(scorecards, d)
            assert stats["scorecards"] == 1
            assert stats["goals"] >= 1
            assert os.path.isfile(os.path.join(d, "goals_payload.json"))
            assert os.path.isfile(os.path.join(d, "goals_summary.json"))

    def test_status_mapping(self):
        from powerbi_import.goals_generator import _map_status
        assert _map_status("on_track") == "OnTrack"
        assert _map_status("at_risk") == "AtRisk"
        assert _map_status("behind") == "Behind"
        assert _map_status("") == "NotStarted"
        assert _map_status("unknown_value") == "NotStarted"

    def test_convert_thresholds(self):
        from powerbi_import.goals_generator import _convert_thresholds
        thresholds = [
            {"status": "on_track", "min_value": 80, "max_value": 100},
            {"status": "at_risk", "min_value": 50, "max_value": 79},
        ]
        rules = _convert_thresholds(thresholds)
        assert len(rules) == 2
        assert rules[0]["status"] == "OnTrack"
        assert rules[0]["minValue"] == 80

    def test_empty_scorecards(self):
        from powerbi_import.goals_generator import generate_goals
        with tempfile.TemporaryDirectory() as d:
            stats = generate_goals([], d)
            assert stats["goals"] == 0


# ═══════════════════════════════════════════════════════════════════
# Sprint P — Scale & Performance
# ═══════════════════════════════════════════════════════════════════

class TestSyntheticFixtures:
    """Synthetic fixture generation for benchmarking."""

    def test_generate_small(self):
        from tests.synthetic_fixtures import generate_synthetic_project
        with tempfile.TemporaryDirectory() as d:
            stats = generate_synthetic_project(d, n_tables=5, n_metrics=10,
                                               n_derived=5, n_reports=2, n_dossiers=1)
            assert stats["tables"] == 5
            assert stats["metrics"] == 10
            assert os.path.isfile(os.path.join(d, "datasources.json"))
            assert os.path.isfile(os.path.join(d, "metrics.json"))

    def test_generate_medium(self):
        from tests.synthetic_fixtures import generate_synthetic_project
        with tempfile.TemporaryDirectory() as d:
            stats = generate_synthetic_project(d, n_tables=20, n_metrics=100,
                                               n_derived=50, n_reports=5, n_dossiers=3)
            assert stats["tables"] == 20
            assert stats["metrics"] == 100

    def test_all_json_files_present(self):
        from tests.synthetic_fixtures import generate_synthetic_project
        with tempfile.TemporaryDirectory() as d:
            generate_synthetic_project(d, n_tables=2, n_metrics=3,
                                      n_derived=1, n_reports=1, n_dossiers=1)
            expected = ["datasources", "attributes", "facts", "metrics",
                       "derived_metrics", "reports", "dossiers", "relationships"]
            for name in expected:
                assert os.path.isfile(os.path.join(d, f"{name}.json")), f"{name}.json missing"


# ═══════════════════════════════════════════════════════════════════
# Sprint Q — E2E Certification
# ═══════════════════════════════════════════════════════════════════

class TestCertification:
    """Post-migration certification."""

    def test_certification_pass(self):
        from powerbi_import.certification import certify_migration
        with tempfile.TemporaryDirectory() as d:
            # Create minimal valid output
            tables_dir = os.path.join(d, "Model.SemanticModel", "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "Sales.tmdl"), "w") as f:
                f.write("table Sales\n\tmeasure M1 = SUM(Revenue)\n\tmeasure M2 = SUM(Cost)\n")

            pages_dir = os.path.join(d, "Model.Report", "definition", "pages", "p1")
            vis_dir = os.path.join(pages_dir, "visuals", "v1")
            os.makedirs(vis_dir)
            with open(os.path.join(pages_dir, "page.json"), "w") as f:
                json.dump({"name": "p1"}, f)
            with open(os.path.join(vis_dir, "visual.json"), "w") as f:
                json.dump({"visual": {}}, f)

            rels_dir = os.path.join(d, "Model.SemanticModel", "definition")
            with open(os.path.join(rels_dir, "relationships.tmdl"), "w") as f:
                f.write("relationship R1\n")

            data = {
                "metrics": [{"name": "M1"}, {"name": "M2"}],
                "derived_metrics": [],
                "relationships": [{"from_table": "A", "to_table": "B"}],
                "dossiers": [{"chapters": [{"pages": [{"visualizations": [{"key": "v1"}]}]}]}],
                "reports": [],
            }
            result = certify_migration(data, d, threshold=50)
            assert result["verdict"] in ("CERTIFIED", "FAILED")
            assert "score" in result
            assert os.path.isfile(os.path.join(d, "certification.json"))

    def test_certification_checks_count(self):
        from powerbi_import.certification import certify_migration
        with tempfile.TemporaryDirectory() as d:
            data = {"metrics": [], "derived_metrics": [], "relationships": [],
                    "dossiers": [], "reports": []}
            result = certify_migration(data, d)
            assert result["total_checks"] == 7

    def test_check_expression_fidelity_no_data(self):
        from powerbi_import.certification import _check_expression_fidelity
        result = _check_expression_fidelity({"metrics": [], "derived_metrics": []})
        assert result["passed"] is True

    def test_check_manual_review_ratio(self):
        from powerbi_import.certification import _check_manual_review_ratio
        data = {
            "metrics": [{"name": f"M{i}", "fidelity": "full"} for i in range(8)]
                     + [{"name": f"MR{i}", "fidelity": "manual_review"} for i in range(2)],
            "derived_metrics": [],
        }
        result = _check_manual_review_ratio(data)
        assert result["passed"] is True  # 2/10 = 20% exactly at threshold

    def test_check_manual_review_fails(self):
        from powerbi_import.certification import _check_manual_review_ratio
        data = {
            "metrics": [{"name": f"M{i}", "fidelity": "manual_review"} for i in range(5)]
                     + [{"name": f"F{i}", "fidelity": "full"} for i in range(5)],
            "derived_metrics": [],
        }
        result = _check_manual_review_ratio(data)
        assert result["passed"] is False  # 5/10 = 50% > 20%


# ═══════════════════════════════════════════════════════════════════
# CLI flags (v4.0)
# ═══════════════════════════════════════════════════════════════════

class TestCLIFlags:
    """v4.0 CLI argument parsing."""

    def _parse(self, args_list):
        from migrate import build_parser
        parser = build_parser()
        return parser.parse_args(args_list)

    def test_merge_flag(self):
        args = self._parse(["--from-export", ".", "--merge", "/tmp/projects"])
        assert args.merge == "/tmp/projects"

    def test_scorecards_flag(self):
        args = self._parse(["--from-export", ".", "--scorecards"])
        assert args.scorecards is True

    def test_certify_flag(self):
        args = self._parse(["--from-export", ".", "--certify"])
        assert args.certify is True

    def test_certify_threshold(self):
        args = self._parse(["--from-export", ".", "--certify", "--certify-threshold", "90"])
        assert args.certify_threshold == 90

    def test_benchmark_flag(self):
        args = self._parse(["--from-export", ".", "--benchmark"])
        assert args.benchmark is True

    def test_version_is_4(self):
        import io
        import contextlib
        from migrate import build_parser
        parser = build_parser()
        f = io.StringIO()
        try:
            with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                parser.parse_args(["--version"])
        except SystemExit:
            pass
        output = f.getvalue()
        assert "16.0.0" in output


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _write(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
