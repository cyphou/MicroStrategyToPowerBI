"""
Tests for v3.0 modules:
- Assessment v3 (14-category model, effort estimation)
- Server assessment
- Global assessment
- Strategy advisor
- Comparison report
- Visual diff
- Telemetry / Telemetry dashboard
- Thin report generator
- Progress tracker
- Plugin system
"""

import json
import os
import pytest

from powerbi_import.assessment import (
    assess_project, CheckItem, CategoryResult, AssessmentReport,
)
from powerbi_import.server_assessment import (
    run_server_assessment, WorkbookReadiness, MigrationWave,
)
from powerbi_import.global_assessment import (
    run_global_assessment, ProjectProfile, _pairwise_score, _cluster_projects,
)
from powerbi_import.strategy_advisor import (
    recommend_strategy, IMPORT, DIRECT_QUERY, COMPOSITE, DIRECT_LAKE,
)
from powerbi_import.comparison_report import generate_comparison_report
from powerbi_import.visual_diff import compute_visual_diff
from powerbi_import.telemetry import MigrationRun, save_run, load_runs
from powerbi_import.telemetry_dashboard import generate_telemetry_dashboard
from powerbi_import.thin_report_generator import generate_thin_report
from powerbi_import.progress import ProgressTracker
from powerbi_import.plugins import register_hook, fire_hook, clear_hooks, discover_plugins


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def rich_data():
    """Sample data with enough objects to exercise all assessment categories."""
    return {
        "datasources": [
            {"name": "Sales", "columns": [{"name": f"col{i}"} for i in range(5)],
             "db_connection": {"db_type": "sql_server"}},
            {"name": "Products", "columns": [{"name": "name"}],
             "db_connection": {"db_type": "oracle"}},
        ],
        "attributes": [{"id": "a1"}, {"id": "a2"}],
        "facts": [{"id": "f1"}],
        "metrics": [
            {"id": "m1", "name": "Revenue", "metric_type": "simple", "expression": "Sum(Revenue)"},
            {"id": "m2", "name": "Custom", "metric_type": "compound", "expression": "ApplySimple(...)"},
        ],
        "derived_metrics": [
            {"id": "dm1", "name": "Running", "expression": "RunningSum(Sales)"},
        ],
        "reports": [{"id": "r1", "name": "Sales Report", "grid": {"rows": [{"name": "Region"}], "columns": [{"name": "Revenue"}]}}],
        "dossiers": [{
            "id": "d1", "name": "Dashboard",
            "chapters": [{"pages": [{"visualizations": [
                {"name": "Chart1", "viz_type": "bar", "rows": [{"name": "x"}]},
                {"name": "Chart2", "viz_type": "network"},
            ]}]}],
        }],
        "cubes": [{"id": "c1"}],
        "prompts": [{"id": "p1", "name": "DatePrompt", "prompt_type": "value"}],
        "security_filters": [{"id": "sf1", "name": "Region Filter", "target_attributes": [{"name": "Region"}]}],
        "custom_groups": [{"id": "cg1"}],
        "freeform_sql": [{"id": "fs1"}],
        "hierarchies": [{"id": "h1"}],
        "relationships": [{"id": "rel1"}],
        "filters": [],
        "consolidations": [],
        "thresholds": [],
        "subtotals": [],
    }


# ── Assessment v3 ────────────────────────────────────────────────


class TestAssessmentV3:
    def test_14_categories(self, rich_data):
        result = assess_project(rich_data)
        assert len(result["categories"]) == 14

    def test_overall_score_present(self, rich_data):
        result = assess_project(rich_data)
        assert result["overall_score"] in ("GREEN", "YELLOW", "RED")

    def test_effort_hours_positive(self, rich_data):
        result = assess_project(rich_data)
        assert result["summary"]["effort_hours"] > 0

    def test_connectors_detected(self, rich_data):
        result = assess_project(rich_data)
        assert "sql_server" in result["summary"]["connectors"]

    def test_check_item_model(self):
        ci = CheckItem("Test", "check1", "warning", "detail", "rec")
        d = ci.to_dict()
        assert d["severity"] == "warning"
        assert d["category"] == "Test"

    def test_category_result_worst_severity(self):
        checks = [CheckItem("A", "c1", "pass"), CheckItem("A", "c2", "fail")]
        cr = CategoryResult("A", checks)
        assert cr.worst_severity == "fail"

    def test_assessment_report_score_green(self):
        checks = [CheckItem("A", "c1", "pass")]
        cats = [CategoryResult("A", checks)]
        rpt = AssessmentReport("Test", cats, {})
        assert rpt.overall_score == "GREEN"

    def test_assessment_report_score_red(self):
        checks = [CheckItem("A", "c1", "fail")]
        cats = [CategoryResult("A", checks)]
        rpt = AssessmentReport("Test", cats, {})
        assert rpt.overall_score == "RED"

    def test_html_report_generated(self, rich_data, tmp_path):
        assess_project(rich_data, output_dir=str(tmp_path))
        html = (tmp_path / "assessment_report.html").read_text(encoding="utf-8")
        assert "Assessment Categories (14)" in html
        assert "Detailed Checks" in html


# ── Server Assessment ────────────────────────────────────────────


class TestServerAssessment:
    def test_workbook_readiness(self, rich_data):
        assessments = [assess_project(rich_data)]
        result = run_server_assessment(assessments)
        assert "workbooks" in result
        assert len(result["workbooks"]) == 1

    def test_migration_waves(self, rich_data):
        assessments = [assess_project(rich_data)]
        result = run_server_assessment(assessments)
        assert "waves" in result
        total = sum(len(w["members"]) for w in result["waves"])
        assert total == 1

    def test_empty_assessment(self):
        result = run_server_assessment([])
        assert result["total_workbooks"] == 0


# ── Global Assessment ────────────────────────────────────────────


class TestGlobalAssessment:
    def test_pairwise_score_identical(self):
        a = assess_project({"datasources": [{"db_connection": {"db_type": "sql_server"}}]})
        pa = ProjectProfile("A", "/a", a)
        score = _pairwise_score(pa, pa)
        assert score >= 0.5

    def test_cluster_single(self):
        a = assess_project({})
        pa = ProjectProfile("A", "/a", a)
        clusters = _cluster_projects([pa])
        assert len(clusters) == 1

    def test_run_on_empty_dir(self, tmp_path):
        result = run_global_assessment(str(tmp_path))
        assert result["total_projects"] == 0

    def test_run_on_real_projects(self, tmp_path, rich_data):
        # Create a sub-project with datasources.json
        sub = tmp_path / "proj1"
        sub.mkdir()
        (sub / "datasources.json").write_text(json.dumps(rich_data.get("datasources", [])))
        (sub / "metrics.json").write_text(json.dumps(rich_data.get("metrics", [])))

        result = run_global_assessment(str(tmp_path), output_dir=str(tmp_path))
        assert result["total_projects"] == 1
        assert (tmp_path / "global_assessment.json").exists()
        assert (tmp_path / "global_assessment.html").exists()


# ── Strategy Advisor ─────────────────────────────────────────────


class TestStrategyAdvisor:
    def test_default_import(self):
        data = {"datasources": [{"db_connection": {"db_type": "sql_server"}}]}
        result = recommend_strategy(data)
        assert result["recommended"] == IMPORT

    def test_multi_connector_composite(self):
        data = {"datasources": [
            {"db_connection": {"db_type": "sql_server"}},
            {"db_connection": {"db_type": "oracle"}},
        ]}
        result = recommend_strategy(data)
        assert result["recommended"] == COMPOSITE

    def test_fabric_cubes_directlake(self):
        data = {"cubes": [{"id": "c1"}], "datasources": []}
        result = recommend_strategy(data, fabric_available=True)
        assert result["recommended"] == DIRECT_LAKE

    def test_large_table_dq(self):
        data = {"datasources": [
            {"db_connection": {"db_type": "sql_server"}, "row_count": 50_000_000, "columns": []},
        ]}
        result = recommend_strategy(data)
        assert result["recommended"] == DIRECT_QUERY

    def test_empty_data(self):
        result = recommend_strategy({})
        assert result["recommended"] == IMPORT


# ── Comparison Report ────────────────────────────────────────────


class TestComparisonReport:
    def test_generates_files(self, rich_data, tmp_path):
        result = generate_comparison_report(rich_data, {}, str(tmp_path))
        assert (tmp_path / "comparison_report.json").exists()
        assert (tmp_path / "comparison_report.html").exists()

    def test_summary_has_grade(self, rich_data, tmp_path):
        result = generate_comparison_report(rich_data, {}, str(tmp_path))
        assert result["summary"]["grade"] in ("A", "B", "C", "D", "F")

    def test_tables_mapped(self, rich_data, tmp_path):
        result = generate_comparison_report(rich_data, {}, str(tmp_path))
        assert len(result["tables"]) == 2  # Sales + Products

    def test_unsupported_visual_detected(self, rich_data, tmp_path):
        result = generate_comparison_report(rich_data, {}, str(tmp_path))
        unsupported = [v for v in result["visuals"] if v["status"] == "unsupported"]
        assert len(unsupported) >= 1  # network viz


# ── Visual Diff ──────────────────────────────────────────────────


class TestVisualDiff:
    def test_compute_diff(self, rich_data):
        result = compute_visual_diff(rich_data)
        assert result["total_visuals"] >= 2  # 2 dossier + 1 report grid
        assert result["unsupported"] >= 1

    def test_field_coverage(self, rich_data):
        result = compute_visual_diff(rich_data)
        assert 0 <= result["avg_field_coverage"] <= 1.0

    def test_empty_data(self):
        result = compute_visual_diff({})
        assert result["total_visuals"] == 0


# ── Telemetry ────────────────────────────────────────────────────


class TestTelemetry:
    def test_migration_run_lifecycle(self):
        run = MigrationRun("TestProject")
        run.object_counts = {"tables": 5}
        run.finish("success")
        d = run.to_dict()
        assert d["status"] == "success"
        assert d["duration_seconds"] >= 0

    def test_save_and_load(self, tmp_path):
        run = MigrationRun("Test")
        run.finish("success")
        save_run(run, str(tmp_path))

        runs = load_runs(str(tmp_path))
        assert len(runs) == 1
        assert runs[0]["project_name"] == "Test"

    def test_append_runs(self, tmp_path):
        for i in range(3):
            run = MigrationRun(f"P{i}")
            run.finish("success")
            save_run(run, str(tmp_path))
        runs = load_runs(str(tmp_path))
        assert len(runs) == 3


# ── Telemetry Dashboard ─────────────────────────────────────────


class TestTelemetryDashboard:
    def test_no_data_returns_none(self, tmp_path):
        result = generate_telemetry_dashboard(str(tmp_path))
        assert result is None

    def test_generates_html(self, tmp_path):
        run = MigrationRun("Test")
        run.finish("success")
        save_run(run, str(tmp_path))

        path = generate_telemetry_dashboard(str(tmp_path))
        assert path is not None
        html = open(path, encoding="utf-8").read()
        assert "Telemetry Dashboard" in html


# ── Thin Report Generator ───────────────────────────────────────


class TestThinReportGenerator:
    def test_generates_pbip(self, rich_data, tmp_path):
        stats = generate_thin_report(
            rich_data, str(tmp_path),
            report_name="Sales Thin",
            shared_model_name="SharedModel",
        )
        assert (tmp_path / "Sales Thin" / "Sales Thin.pbip").exists()
        assert (tmp_path / "Sales Thin" / "Sales Thin.Report" / ".platform").exists()

    def test_pbir_references_shared_model(self, rich_data, tmp_path):
        generate_thin_report(
            rich_data, str(tmp_path),
            report_name="ThinRpt",
            shared_model_name="MyModel",
        )
        pbir_path = tmp_path / "ThinRpt" / "ThinRpt.Report" / "definition" / "definition.pbir"
        pbir = json.loads(pbir_path.read_text(encoding="utf-8"))
        assert pbir["datasetReference"]["byPath"]["path"].endswith("SemanticModel")

    def test_with_remote_model_id(self, rich_data, tmp_path):
        generate_thin_report(
            rich_data, str(tmp_path),
            report_name="RemoteRpt",
            shared_model_name="SM",
            shared_model_id="abc-123",
        )
        pbir_path = tmp_path / "RemoteRpt" / "RemoteRpt.Report" / "definition" / "definition.pbir"
        pbir = json.loads(pbir_path.read_text(encoding="utf-8"))
        assert pbir["datasetReference"]["byConnection"]["pbiModelDatabaseName"] == "abc-123"


# ── Progress Tracker ─────────────────────────────────────────────


class TestProgressTracker:
    def test_basic_usage(self):
        with ProgressTracker(10, desc="Test", quiet=True) as pt:
            for _ in range(10):
                pt.update()
            assert pt.current == 10

    def test_zero_total(self):
        with ProgressTracker(0, quiet=True) as pt:
            assert pt.total == 0


# ── Plugin System ────────────────────────────────────────────────


class TestPluginSystem:
    def setup_method(self):
        clear_hooks()

    def test_register_and_fire(self):
        results = []
        register_hook("pre_generate", lambda data, config: results.append(data))
        fire_hook("pre_generate", "test_data", "config")
        assert results == ["test_data"]

    def test_fire_returns_last_non_none(self):
        register_hook("custom_expression", lambda name, args: None)
        register_hook("custom_expression", lambda name, args: f"DAX({name})")
        result = fire_hook("custom_expression", "MyFunc", [])
        assert result == "DAX(MyFunc)"

    def test_unknown_hook(self):
        # Should not raise
        register_hook("nonexistent", lambda: None)

    def test_discover_empty_dir(self, tmp_path):
        count = discover_plugins(str(tmp_path))
        assert count == 0

    def test_discover_plugins(self, tmp_path):
        (tmp_path / "my_plugin.py").write_text(
            "from powerbi_import.plugins import register_hook\n"
            "register_hook('post_generate', lambda stats, out: None)\n"
        )
        count = discover_plugins(str(tmp_path))
        assert count == 1
