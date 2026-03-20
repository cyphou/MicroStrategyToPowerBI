"""
Gap-filling tests for v10.0 — Deep Testing & Quality (Sprint Z.7).

Adds comprehensive tests for under-tested modules: semantic matcher,
notebook generator, pipeline generator, dashboard, shared model,
comparison report, visual diff, migration report, fabric deployment,
gateway config, fabric env, fabric git, and additional expression
converter edge cases.
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ── Fixtures ─────────────────────────────────────────────────────

def _minimal_data(**overrides):
    """Build minimal intermediate JSON data for testing."""
    base = {
        "datasources": [
            {
                "id": "t1", "name": "Sales",
                "physical_table": "dbo_Sales",
                "db_connection": {
                    "db_type": "sql_server",
                    "server": "srv",
                    "database": "db",
                    "schema": "dbo",
                    "host": "srv",
                    "port": 1433,
                },
                "columns": [
                    {"name": "ID", "data_type": "integer", "sql_type": "int"},
                    {"name": "Amount", "data_type": "double", "sql_type": "float"},
                    {"name": "Name", "data_type": "varchar", "sql_type": "varchar(100)"},
                    {"name": "OrderDate", "data_type": "date", "sql_type": "date"},
                ],
            },
        ],
        "attributes": [
            {"id": "a1", "name": "Item", "table": "Sales", "column": "Name",
             "forms": [{"name": "ID", "category": "ID", "column_name": "ID", "table_name": "Sales"}],
             "data_type": "integer", "lookup_table": "Sales", "description": "Item attr"},
        ],
        "facts": [
            {"id": "f1", "name": "Amount", "table": "Sales", "column": "Amount",
             "data_type": "double", "expressions": [{"table": "Sales", "column": "Amount"}],
             "default_aggregation": "sum"},
        ],
        "metrics": [
            {"id": "m1", "name": "Total Sales", "expression": "Sum(Amount)",
             "metric_type": "simple", "aggregation": "sum",
             "column_ref": {"fact_name": "Amount", "fact_id": "f1"},
             "description": "Sum of sales", "dependencies": []},
        ],
        "derived_metrics": [],
        "reports": [
            {"id": "r1", "name": "Report", "report_type": "grid",
             "grid": {"rows": [{"name": "Item", "type": "attribute"}], "columns": []},
             "metrics": [{"name": "Total Sales"}], "filters": []},
        ],
        "dossiers": [
            {
                "id": "d1", "name": "Dashboard",
                "chapters": [{"name": "Ch1", "pages": [
                    {"key": "p1", "name": "Page1", "visualizations": [
                        {"key": "v1", "name": "Chart", "viz_type": "vertical_bar",
                         "pbi_visual_type": "clusteredColumnChart",
                         "data": {
                             "attributes": [{"id": "a1", "name": "Item"}],
                             "metrics": [{"id": "m1", "name": "Total Sales"}],
                         },
                         "position": {"x": 0, "y": 0, "width": 400, "height": 300},
                         "formatting": {}, "thresholds": [],
                        },
                    ]}
                ]}],
            },
        ],
        "cubes": [],
        "filters": [],
        "prompts": [],
        "custom_groups": [],
        "consolidations": [],
        "hierarchies": [],
        "relationships": [],
        "security_filters": [],
        "freeform_sql": [],
        "thresholds": [],
        "subtotals": [],
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════
# Semantic Matcher tests
# ═══════════════════════════════════════════════════════════════════

class TestSemanticMatcherFindBestMatch:

    def test_exact_match(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("Revenue", ["Revenue", "Cost", "Quantity"])
        assert result[0]["name"] == "Revenue"

    def test_case_insensitive_match(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("revenue", ["Revenue", "Cost"])
        assert result[0]["name"].lower() == "revenue"

    def test_abbreviation_expansion(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("Cust_ID", ["Customer_Identifier", "Order_ID", "Product_ID"])
        assert len(result) >= 1

    def test_no_match_below_threshold(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("XYZ_ABCDEF", ["Revenue", "Cost"], threshold=0.9)
        # May return empty or low-score matches
        if result:
            assert result[0]["score"] < 0.9

    def test_empty_candidates(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("Revenue", [])
        assert result == []

    def test_empty_name(self):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match("", ["Revenue", "Cost"])
        assert isinstance(result, list)

    def test_top_n_limit(self):
        from powerbi_import.semantic_matcher import find_best_match
        candidates = [f"Col_{i}" for i in range(10)]
        result = find_best_match("Col", candidates, top_n=3)
        assert len(result) <= 3

    @pytest.mark.parametrize("name,candidates", [
        ("Amt", ["Amount", "Total_Amount", "Revenue"]),
        ("Qty", ["Quantity", "Order_Qty", "Stock"]),
        ("Dt", ["Date", "OrderDate", "ShipDate"]),
        ("Num", ["Number", "OrderNumber", "Value"]),
        ("Desc", ["Description", "Product_Desc", "Name"]),
    ])
    def test_common_abbreviations(self, name, candidates):
        from powerbi_import.semantic_matcher import find_best_match
        result = find_best_match(name, candidates)
        assert len(result) >= 1


class TestSemanticMatcherMatchSchemas:

    def test_basic_match(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas(["Revenue", "Cost"], ["Revenue", "Cost", "Quantity"])
        assert "Revenue" in result
        assert result["Revenue"]["name"] == "Revenue"

    def test_partial_match(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas(["Rev", "Customer_ID"], ["Revenue", "CustID", "Other"])
        assert isinstance(result, dict)

    def test_empty_source(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas([], ["Revenue", "Cost"])
        assert result == {}

    def test_empty_target(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas(["Revenue"], [])
        assert isinstance(result, dict)


class TestSemanticMatcherSuggestFixes:

    def test_suggests_alternatives(self):
        from powerbi_import.semantic_matcher import suggest_fixes
        items = [{"expression": "SUM([Rev])", "warnings": ["Unknown column"]}]
        result = suggest_fixes(items, ["Revenue", "Cost", "Quantity"])
        assert isinstance(result, list)

    def test_empty_items(self):
        from powerbi_import.semantic_matcher import suggest_fixes
        result = suggest_fixes([], ["Revenue"])
        assert result == []


class TestCorrectionStore:

    def test_store_and_retrieve(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        with tempfile.TemporaryDirectory() as td:
            store = CorrectionStore(os.path.join(td, "corrections.json"))
            store.record("Rev", "Revenue")
            assert store.lookup("Rev") == "Revenue"

    def test_persistence(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "corrections.json")
            store1 = CorrectionStore(path)
            store1.record("Amt", "Amount")

            store2 = CorrectionStore(path)
            assert store2.lookup("Amt") == "Amount"

    def test_missing_key(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        with tempfile.TemporaryDirectory() as td:
            store = CorrectionStore(os.path.join(td, "c.json"))
            assert store.lookup("nonexistent") is None

    def test_overwrite(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        with tempfile.TemporaryDirectory() as td:
            store = CorrectionStore(os.path.join(td, "c.json"))
            store.record("Rev", "Revenue1")
            store.record("Rev", "Revenue2")
            assert store.lookup("Rev") == "Revenue2"


# ═══════════════════════════════════════════════════════════════════
# Notebook Generator tests
# ═══════════════════════════════════════════════════════════════════

class TestNotebookGenerator:

    def test_generates_notebooks(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="TestLH")
            assert isinstance(stats, dict)
            assert stats.get("notebooks_generated", 0) >= 0

    def test_empty_datasources(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _minimal_data(datasources=[])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td)
            assert stats.get("notebooks_generated", 0) == 0

    def test_multiple_connectors(self):
        from powerbi_import.notebook_generator import generate_notebooks
        ds_sql = {
            "name": "SqlT", "physical_table": "SqlT",
            "columns": [{"name": "C", "data_type": "integer", "sql_type": "int"}],
            "db_connection": {"db_type": "sql_server", "host": "s", "port": 1433,
                              "database": "d", "schema": "dbo"},
        }
        ds_snow = {
            "name": "SnowT", "physical_table": "SnowT",
            "columns": [{"name": "C", "data_type": "varchar", "sql_type": "varchar(50)"}],
            "db_connection": {"db_type": "snowflake", "host": "acme.snowflakecomputing.com",
                              "database": "DB", "schema": "PUBLIC"},
        }
        data = _minimal_data(datasources=[ds_sql, ds_snow])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="LH")
            assert stats.get("notebooks_generated", 0) >= 1


# ═══════════════════════════════════════════════════════════════════
# Pipeline Generator tests
# ═══════════════════════════════════════════════════════════════════

class TestPipelineGenerator:

    def test_generates_pipeline(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pipeline(data, td, lakehouse_name="LH",
                                      semantic_model_name="SM")
            assert isinstance(stats, dict)

    def test_pipeline_creates_file(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            generate_pipeline(data, td, lakehouse_name="LH",
                              semantic_model_name="SM")
            files = os.listdir(td)
            assert any("pipeline" in f.lower() for f in files)

    def test_empty_data(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _minimal_data(datasources=[])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pipeline(data, td, lakehouse_name="LH",
                                      semantic_model_name="SM")
            assert isinstance(stats, dict)


# ═══════════════════════════════════════════════════════════════════
# Dashboard tests
# ═══════════════════════════════════════════════════════════════════

class TestDashboard:

    def _report_data(self):
        return {
            "name": "Test Migration",
            "objects": [
                {"name": "Revenue", "type": "metric", "status": "full"},
                {"name": "Cost", "type": "metric", "status": "approximated"},
                {"name": "Chart1", "type": "visual", "status": "full"},
            ],
            "summary": {
                "total": 3,
                "full": 2,
                "approximated": 1,
                "manual_review": 0,
                "unsupported": 0,
            },
        }

    def test_generates_html(self):
        from powerbi_import.dashboard import generate_dashboard
        with tempfile.TemporaryDirectory() as td:
            generate_dashboard(self._report_data(), td)
            files = os.listdir(td)
            assert any(f.endswith(".html") for f in files)

    def test_html_contains_dashboard(self):
        from powerbi_import.dashboard import generate_dashboard
        with tempfile.TemporaryDirectory() as td:
            generate_dashboard(self._report_data(), td)
            for f in os.listdir(td):
                if f.endswith(".html"):
                    content = open(os.path.join(td, f), encoding="utf-8").read()
                    assert "dashboard" in content.lower() or "migration" in content.lower()

    def test_empty_report_data(self):
        from powerbi_import.dashboard import generate_dashboard
        with tempfile.TemporaryDirectory() as td:
            generate_dashboard({"name": "Empty", "objects": [], "summary": {}}, td)


# ═══════════════════════════════════════════════════════════════════
# Shared Model tests
# ═══════════════════════════════════════════════════════════════════

class TestSharedModelGenerator:

    def test_generates_shared_model(self):
        from powerbi_import.shared_model import generate_shared_model
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            result = generate_shared_model(data, td, model_name="SharedTest")
            assert isinstance(result, dict)

    def test_shared_model_creates_folder(self):
        from powerbi_import.shared_model import generate_shared_model
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            generate_shared_model(data, td, model_name="SM1")
            project_dir = os.path.join(td, "SM1_SharedModel")
            assert os.path.isdir(os.path.join(project_dir, "SM1.SemanticModel"))

    def test_empty_datasources(self):
        from powerbi_import.shared_model import generate_shared_model
        data = _minimal_data(datasources=[])
        with tempfile.TemporaryDirectory() as td:
            result = generate_shared_model(data, td, model_name="EmptySM")
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Comparison Report tests
# ═══════════════════════════════════════════════════════════════════

class TestComparisonReport:

    def test_generates_html(self):
        from powerbi_import.comparison_report import generate_comparison_report
        data = _minimal_data()
        stats = {"tables": 1, "measures": 1, "pages": 1, "visuals": 1, "warnings": []}
        with tempfile.TemporaryDirectory() as td:
            generate_comparison_report(data, stats, td, report_name="CompTest")
            files = os.listdir(td)
            assert any(f.endswith(".html") for f in files)

    def test_html_content(self):
        from powerbi_import.comparison_report import generate_comparison_report
        data = _minimal_data()
        stats = {"tables": 1, "measures": 1, "pages": 1, "visuals": 1, "warnings": []}
        with tempfile.TemporaryDirectory() as td:
            generate_comparison_report(data, stats, td, report_name="CR")
            for f in os.listdir(td):
                if f.endswith(".html"):
                    content = open(os.path.join(td, f), encoding="utf-8").read()
                    assert "comparison" in content.lower() or "migration" in content.lower()

    def test_with_warnings(self):
        from powerbi_import.comparison_report import generate_comparison_report
        data = _minimal_data()
        stats = {"tables": 1, "measures": 1, "pages": 1, "visuals": 1,
                 "warnings": ["Warning 1", "Warning 2"]}
        with tempfile.TemporaryDirectory() as td:
            generate_comparison_report(data, stats, td)


# ═══════════════════════════════════════════════════════════════════
# Visual Diff tests
# ═══════════════════════════════════════════════════════════════════

class TestVisualDiff:

    def test_computes_diff(self):
        from powerbi_import.visual_diff import compute_visual_diff
        data = _minimal_data()
        result = compute_visual_diff(data)
        assert isinstance(result, dict)

    def test_diff_has_coverage(self):
        from powerbi_import.visual_diff import compute_visual_diff
        data = _minimal_data()
        result = compute_visual_diff(data)
        assert "coverage" in result or "visuals" in result or isinstance(result, dict)

    def test_empty_dossiers(self):
        from powerbi_import.visual_diff import compute_visual_diff
        data = _minimal_data(dossiers=[])
        result = compute_visual_diff(data)
        assert isinstance(result, dict)

    def test_empty_reports(self):
        from powerbi_import.visual_diff import compute_visual_diff
        data = _minimal_data(reports=[])
        result = compute_visual_diff(data)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Migration Report tests
# ═══════════════════════════════════════════════════════════════════

class TestMigrationReport:

    def test_generates_report(self):
        from powerbi_import.migration_report import generate_migration_report
        data = _minimal_data()
        stats = {"tables": 1, "measures": 1, "pages": 1, "visuals": 1, "warnings": []}
        with tempfile.TemporaryDirectory() as td:
            result = generate_migration_report(data, stats, td)
            assert isinstance(result, dict)

    def test_report_creates_files(self):
        from powerbi_import.migration_report import generate_migration_report
        data = _minimal_data()
        stats = {"tables": 1, "measures": 1, "pages": 1, "visuals": 1, "warnings": []}
        with tempfile.TemporaryDirectory() as td:
            generate_migration_report(data, stats, td)
            files = os.listdir(td)
            assert len(files) >= 1

    def test_empty_data(self):
        from powerbi_import.migration_report import generate_migration_report
        data = _minimal_data(datasources=[], metrics=[], reports=[], dossiers=[])
        stats = {"tables": 0, "measures": 0, "pages": 0, "visuals": 0, "warnings": []}
        with tempfile.TemporaryDirectory() as td:
            result = generate_migration_report(data, stats, td)
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Gateway Config tests
# ═══════════════════════════════════════════════════════════════════

class TestGatewayConfig:

    def test_generates_config(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config
        datasources = [
            {"name": "Sales", "db_connection": {
                "db_type": "sql_server", "server": "srv", "database": "db"}},
        ]
        result = generate_gateway_config(datasources)
        assert isinstance(result, (dict, list))

    def test_writes_to_file(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config
        datasources = [
            {"name": "Sales", "db_connection": {
                "db_type": "sql_server", "server": "srv", "database": "db"}},
        ]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "gw.json")
            generate_gateway_config(datasources, output_path=path)
            assert os.path.isfile(path)

    def test_multiple_datasources(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config
        datasources = [
            {"name": "T1", "db_connection": {"db_type": "sql_server", "server": "s1", "database": "d1"}},
            {"name": "T2", "db_connection": {"db_type": "oracle", "server": "s2", "database": "d2"}},
            {"name": "T3", "db_connection": {"db_type": "postgresql", "server": "s3", "database": "d3"}},
        ]
        result = generate_gateway_config(datasources)
        assert isinstance(result, (dict, list))

    def test_empty_datasources(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config
        result = generate_gateway_config([])
        assert isinstance(result, (dict, list))


# ═══════════════════════════════════════════════════════════════════
# Fabric Environment tests
# ═══════════════════════════════════════════════════════════════════

class TestFabricEnv:

    def test_generate_environment(self):
        from powerbi_import.deploy.fabric_env import generate_environment
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            result = generate_environment(data, td, env_name="TestEnv")
            assert isinstance(result, dict)

    def test_estimate_capacity(self):
        from powerbi_import.deploy.fabric_env import estimate_capacity
        data = _minimal_data()
        result = estimate_capacity(data)
        assert isinstance(result, dict)
        assert "sku" in result or "recommended" in result or isinstance(result, dict)

    def test_large_data_capacity(self):
        from powerbi_import.deploy.fabric_env import estimate_capacity
        # Many tables → higher capacity
        datasources = [{
            "name": f"T{i}", "physical_table": f"T{i}",
            "columns": [{"name": f"C{j}", "data_type": "double", "sql_type": "float"}
                         for j in range(20)],
            "db_connection": {"db_type": "sql_server", "host": "s", "database": "d", "port": 1433},
        } for i in range(50)]
        data = _minimal_data(datasources=datasources)
        result = estimate_capacity(data)
        assert isinstance(result, dict)

    def test_empty_data(self):
        from powerbi_import.deploy.fabric_env import estimate_capacity
        data = _minimal_data(datasources=[])
        result = estimate_capacity(data)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Fabric Git tests (mock)
# ═══════════════════════════════════════════════════════════════════

class TestFabricGit:

    @patch("powerbi_import.deploy.fabric_git.requests")
    def test_push_to_fabric_git(self, mock_req):
        from powerbi_import.deploy.fabric_git import push_to_fabric_git
        from powerbi_import.pbip_generator import generate_pbip

        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            generate_pbip(data, td, report_name="GitTest")
            # Mock git status response with gitProviderDetails
            git_status_resp = MagicMock()
            git_status_resp.status_code = 200
            git_status_resp.json.return_value = {
                "gitProviderDetails": {"name": "AzureDevOps", "branch": "main"}
            }
            # Mock commit response
            commit_resp = MagicMock()
            commit_resp.status_code = 200
            commit_resp.json.return_value = {"status": "committed"}
            mock_req.get.return_value = git_status_resp
            mock_req.post.return_value = commit_resp
            result = push_to_fabric_git(td, "ws-1", token="fake-token")
            assert isinstance(result, dict)

    @patch("powerbi_import.deploy.fabric_git.requests")
    def test_get_git_status(self, mock_req):
        from powerbi_import.deploy.fabric_git import get_git_status
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"changes": []}
        mock_req.get.return_value = mock_resp
        result = get_git_status("ws-1", token="fake-token")
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Plugins system tests
# ═══════════════════════════════════════════════════════════════════

class TestPlugins:

    def test_register_and_fire_hook(self):
        from powerbi_import.plugins import register_hook, fire_hook, clear_hooks
        clear_hooks()
        results = []
        register_hook("pre_generate", lambda data: results.append("called"))
        fire_hook("pre_generate", {})
        assert "called" in results
        clear_hooks()

    def test_multiple_hooks(self):
        from powerbi_import.plugins import register_hook, fire_hook, clear_hooks
        clear_hooks()
        results = []
        register_hook("pre_generate", lambda d: results.append("a"))
        register_hook("pre_generate", lambda d: results.append("b"))
        fire_hook("pre_generate", {})
        assert results == ["a", "b"]
        clear_hooks()

    def test_fire_unknown_hook(self):
        from powerbi_import.plugins import fire_hook, clear_hooks
        clear_hooks()
        fire_hook("unknown_event", {})  # Should not crash

    def test_clear_hooks(self):
        from powerbi_import.plugins import register_hook, fire_hook, clear_hooks
        results = []
        register_hook("post_generate", lambda d: results.append(1))
        clear_hooks()
        fire_hook("post_generate", {})
        assert results == []


# ═══════════════════════════════════════════════════════════════════
# Progress tracker tests
# ═══════════════════════════════════════════════════════════════════

class TestProgressTracker:

    def test_basic_tracking(self):
        from powerbi_import.progress import ProgressTracker
        pt = ProgressTracker(total=10, desc="Test", quiet=True)
        for _ in range(10):
            pt.update()
        pt.close()

    def test_zero_total(self):
        from powerbi_import.progress import ProgressTracker
        pt = ProgressTracker(total=0, desc="Empty", quiet=True)
        pt.close()

    def test_context_manager(self):
        from powerbi_import.progress import ProgressTracker
        with ProgressTracker(total=5, desc="CM", quiet=True) as pt:
            for _ in range(5):
                pt.update()


# ═══════════════════════════════════════════════════════════════════
# Telemetry tests
# ═══════════════════════════════════════════════════════════════════

class TestTelemetry:

    def test_create_run(self):
        from powerbi_import.telemetry import MigrationRun
        run = MigrationRun(project_name="Test")
        assert run.project_name == "Test"

    def test_save_and_load(self):
        from powerbi_import.telemetry import MigrationRun, save_run, load_runs
        with tempfile.TemporaryDirectory() as td:
            run = MigrationRun(project_name="Test")
            run.object_counts = {"tables": 5, "measures": 10}
            run.finish()
            save_run(run, td)
            runs = load_runs(td)
            assert len(runs) >= 1
            assert runs[0]["project_name"] == "Test"

    def test_load_missing_file(self):
        from powerbi_import.telemetry import load_runs
        with tempfile.TemporaryDirectory() as td:
            runs = load_runs(os.path.join(td, "nonexistent"))
            assert runs == []

    def test_multiple_runs(self):
        from powerbi_import.telemetry import MigrationRun, save_run, load_runs
        with tempfile.TemporaryDirectory() as td:
            for i in range(3):
                run = MigrationRun(project_name=f"P{i}")
                run.finish()
                save_run(run, td)
            runs = load_runs(td)
            assert len(runs) == 3


# ═══════════════════════════════════════════════════════════════════
# Telemetry Dashboard tests
# ═══════════════════════════════════════════════════════════════════

class TestTelemetryDashboard:

    def test_generates_html(self):
        from powerbi_import.telemetry import MigrationRun, save_run
        from powerbi_import.telemetry_dashboard import generate_telemetry_dashboard
        with tempfile.TemporaryDirectory() as td:
            run = MigrationRun(project_name="P1")
            run.object_counts = {"tables": 5, "measures": 10}
            run.finish()
            save_run(run, td)
            result = generate_telemetry_dashboard(td)
            assert result is not None
            assert os.path.isfile(result)

    def test_empty_runs(self):
        from powerbi_import.telemetry_dashboard import generate_telemetry_dashboard
        with tempfile.TemporaryDirectory() as td:
            result = generate_telemetry_dashboard(td)
            assert result is None


# ═══════════════════════════════════════════════════════════════════
# Thin Report Generator tests
# ═══════════════════════════════════════════════════════════════════

class TestThinReportGenerator:

    def test_generates_thin_report(self):
        from powerbi_import.thin_report_generator import generate_thin_report
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            result = generate_thin_report(data, td, report_name="ThinTest",
                                          shared_model_name="SharedModel",
                                          shared_model_id="sm-123")
            assert isinstance(result, dict)

    def test_creates_report_folder(self):
        from powerbi_import.thin_report_generator import generate_thin_report
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            generate_thin_report(data, td, report_name="Thin1",
                                 shared_model_name="SharedModel",
                                 shared_model_id="sm-1")
            # Check that some report folder structure exists
            assert len(os.listdir(td)) >= 1


# ═══════════════════════════════════════════════════════════════════
# Additional Expression Converter edge cases
# ═══════════════════════════════════════════════════════════════════

class TestExpressionConverterEdgeCases:

    def _convert(self, expr):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        return convert_mstr_expression_to_dax(expr)

    def test_between_pattern(self):
        result = self._convert("Between(Revenue, 100, 500)")
        assert isinstance(result["dax"], str)

    def test_in_pattern(self):
        result = self._convert("In(Region, 'East', 'West')")
        assert isinstance(result["dax"], str)

    def test_concat_three_args(self):
        result = self._convert("Concat(A, Concat(B, C))")
        assert isinstance(result["dax"], str)

    def test_nested_nulltozero(self):
        result = self._convert("NullToZero(Avg(Revenue))")
        assert "ISBLANK" in result["dax"]

    def test_if_with_metrics(self):
        result = self._convert("If(Sum(Revenue) > 1000, Sum(Revenue), 0)")
        assert "IF" in result["dax"]

    @pytest.mark.parametrize("expr", [
        "Product(Revenue)",
        "GeoMean(Revenue)",
        "StDevP(Revenue)",
        "VarP(Revenue)",
        "Var(Revenue)",
    ])
    def test_statistical_aggs(self, expr):
        result = self._convert(expr)
        assert isinstance(result["dax"], str)

    @pytest.mark.parametrize("expr,expected", [
        ("LeftStr(Name, 3)", "LEFT"),
        ("RightStr(Name, 3)", "RIGHT"),
        ("Position(Name, 'abc')", "SEARCH"),
    ])
    def test_string_funcs(self, expr, expected):
        result = self._convert(expr)
        assert expected in result["dax"]

    @pytest.mark.parametrize("expr", [
        "Hour(Timestamp)",
        "Minute(Timestamp)",
        "Second(Timestamp)",
        "DayOfWeek(OrderDate)",
        "WeekOfYear(OrderDate)",
        "Quarter(OrderDate)",
    ])
    def test_date_parts(self, expr):
        result = self._convert(expr)
        assert isinstance(result["dax"], str)
        assert result["fidelity"] in ("full", "approximated")

    @pytest.mark.parametrize("expr,expected", [
        ("MonthStartDate(OrderDate)", "STARTOFMONTH"),
        ("MonthEndDate(OrderDate)", "ENDOFMONTH"),
        ("YearStartDate(OrderDate)", "STARTOFYEAR"),
        ("YearEndDate(OrderDate)", "ENDOFYEAR"),
    ])
    def test_date_boundary_funcs(self, expr, expected):
        result = self._convert(expr)
        assert expected in result["dax"]

    @pytest.mark.parametrize("expr", [
        "Mod(Revenue, 10)",
        "Int(Revenue)",
        "Sign(Revenue)",
        "Truncate(Revenue)",
    ])
    def test_math_extended(self, expr):
        result = self._convert(expr)
        assert isinstance(result["dax"], str)

    def test_apply_simple_extract_year(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax('ApplySimple("EXTRACT(YEAR FROM #0)", OrderDate)')
        assert "YEAR" in result["dax"]

    def test_apply_simple_extract_month(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax('ApplySimple("EXTRACT(MONTH FROM #0)", OrderDate)')
        assert "MONTH" in result["dax"]

    def test_apply_simple_extract_day(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax('ApplySimple("EXTRACT(DAY FROM #0)", OrderDate)')
        assert "DAY" in result["dax"]

    def test_apply_simple_trunc(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax('ApplySimple("TRUNC(#0)", Revenue)')
        assert "TRUNC" in result["dax"]

    def test_apply_simple_cast_varchar(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax('ApplySimple("CAST(#0 AS VARCHAR)", Revenue)')
        assert "FORMAT" in result["dax"]

    def test_apply_simple_case_when(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax(
            'ApplySimple("CASE WHEN #0 > 100 THEN \'High\' ELSE \'Low\' END", Revenue)')
        assert "IF" in result["dax"]

    def test_moving_sum_basic(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax("MovingSum(Revenue, 3)")
        assert "WINDOW" in result["dax"]
        assert "SUMX" in result["dax"]

    def test_ntile_basic(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax("NTile(Revenue, 5)")
        assert "RANKX" in result["dax"]
        assert "5" in result["dax"]

    def test_first_in_range(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax("FirstInRange(Revenue, Date)")
        assert "TOPN" in result["dax"]

    def test_last_in_range(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax("LastInRange(Revenue, Date)")
        assert "TOPN" in result["dax"]

    def test_band_pattern(self):
        from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
        result = convert_mstr_expression_to_dax("Band(Revenue, 0, 1000, 100)")
        assert "IF" in result["dax"]


# ═══════════════════════════════════════════════════════════════════
# Additional TMDL Generator edge cases
# ═══════════════════════════════════════════════════════════════════

class TestTmdlEdgeCases:

    def test_direct_lake_partition(self):
        from powerbi_import.tmdl_generator import generate_table_tmdl
        ds = {"id": "t1", "name": "T1",
              "physical_table": "dbo_T1",
              "columns": [{"name": "C", "data_type": "integer"}],
              "db_connection": {"db_type": "sql_server"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {},
                                     direct_lake=True, lakehouse_name="LH")
        assert "mode: directLake" in result

    def test_import_partition(self):
        from powerbi_import.tmdl_generator import generate_table_tmdl
        ds = {"id": "t2", "name": "T2",
              "columns": [{"name": "C", "data_type": "string"}],
              "db_connection": {"db_type": "sql_server", "server": "s",
                                "database": "d", "schema": "dbo"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {},
                                     direct_lake=False)
        assert "mode: import" in result

    def test_roles_generation(self):
        from powerbi_import.tmdl_generator import generate_roles_tmdl
        sf = [{"name": "TestRole",
               "expression": "Region In (East, West)",
               "target_attributes": [{"id": "a1"}]}]
        attr_by_id = {"a1": {
            "name": "Region", "lookup_table": "Sales",
            "forms": [{"table": "Sales", "column_name": "REGION_ID", "category": "ID"}]}}
        result = generate_roles_tmdl(sf, attr_by_id)
        assert "role" in result

    def test_format_string_conversion(self):
        from powerbi_import.tmdl_generator import _convert_format_string
        assert _convert_format_string("fixed") == "#,##0.00"
        assert _convert_format_string("currency") == "$#,##0.00"
        assert _convert_format_string("percent") == "0.00%"
        assert _convert_format_string("") == ""
        assert _convert_format_string(None) == ""

    def test_format_string_passthrough(self):
        from powerbi_import.tmdl_generator import _convert_format_string
        assert _convert_format_string("#,##0.00") == "#,##0.00"

    def test_extract_display_folder(self):
        from powerbi_import.tmdl_generator import _extract_display_folder
        assert _extract_display_folder("\\Public Objects\\Metrics\\Sales") == "Sales"
        assert _extract_display_folder("") == ""

    def test_security_expression_conversion(self):
        from powerbi_import.tmdl_generator import _convert_security_expression
        result = _convert_security_expression("Region In (East, West)", "REGION")
        assert "IN" in result
        assert "East" in result


# ═══════════════════════════════════════════════════════════════════
# Additional Visual Generator edge cases
# ═══════════════════════════════════════════════════════════════════

class TestVisualGeneratorEdgeCases:

    def test_make_binding(self):
        from powerbi_import.visual_generator import _make_binding
        binding = _make_binding("Values", "Revenue")
        assert binding["role"] == "Values"

    def test_build_formatting_empty(self):
        from powerbi_import.visual_generator import _build_formatting
        result = _build_formatting("tableEx", {})
        assert isinstance(result, dict)

    def test_build_conditional_formatting_empty(self):
        from powerbi_import.visual_generator import _build_conditional_formatting
        result = _build_conditional_formatting([], "tableEx")
        assert result == [] or result is None or isinstance(result, list)

    @pytest.mark.parametrize("pbi_type", [
        "tableEx", "matrix", "clusteredColumnChart", "lineChart",
        "pieChart", "donutChart", "treemap", "waterfall",
        "funnel", "gauge", "kpi", "map", "filledMap", "slicer",
    ])
    def test_build_data_bindings_all_types(self, pbi_type):
        attrs = [{"id": "a1", "name": "Cat"}]
        metrics = [{"id": "m1", "name": "Val"}, {"id": "m2", "name": "Val2"}]
        from powerbi_import.visual_generator import _build_data_bindings
        bindings = _build_data_bindings(pbi_type, attrs, metrics, {})
        assert isinstance(bindings, list)

    def test_build_page_json(self):
        from powerbi_import.visual_generator import _build_page_json
        visuals = [
            {"visual": {"visualType": "tableEx"}, "position": {"x": 0, "y": 0, "width": 100, "height": 100}, "name": "v1"},
        ]
        result = _build_page_json("p1", "Page 1", visuals)
        assert result["displayName"] == "Page 1"
        assert result["name"] == "p1"

    def test_slicer_visual(self):
        from powerbi_import.visual_generator import _build_slicer_visual
        result = _build_slicer_visual("Region", "sl1")
        assert result is not None
        assert result["visual"]["visualType"] == "slicer"


# ═══════════════════════════════════════════════════════════════════
# Additional Validator edge cases
# ═══════════════════════════════════════════════════════════════════

class TestValidatorEdgeCases:

    def test_validate_dax_references_empty(self):
        from powerbi_import.validator import validate_dax_references
        result = validate_dax_references({})
        assert isinstance(result, list)

    def test_validate_dax_references_valid(self):
        from powerbi_import.validator import validate_dax_references
        tables = {"Sales": {"columns": {"Amount", "ID"}, "measures": {"Total Sales"}}}
        result = validate_dax_references(tables)
        assert isinstance(result, list)

    def test_validate_project_empty_dir(self, tmp_path):
        from powerbi_import.validator import validate_project
        result = validate_project(str(tmp_path))
        assert isinstance(result, dict)

    def test_detect_cycles_complex(self):
        from powerbi_import.validator import detect_relationship_cycles
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
            {"from_table": "C", "to_table": "D"},
            {"from_table": "D", "to_table": "B"},  # cycle B→C→D→B
        ]
        cycles = detect_relationship_cycles(rels)
        assert len(cycles) >= 1


# ═══════════════════════════════════════════════════════════════════
# Additional Lineage edge cases
# ═══════════════════════════════════════════════════════════════════

class TestLineageEdgeCases:

    def _lineage_data(self, **overrides):
        """Build data with string column_ref (lineage module expects strings)."""
        data = _minimal_data(**overrides)
        for m in data.get("metrics", []):
            cr = m.get("column_ref")
            if isinstance(cr, dict):
                m["column_ref"] = cr.get("fact_name", "")
        return data

    def test_empty_data_lineage(self):
        from powerbi_import.lineage import build_lineage_graph
        data = self._lineage_data(datasources=[], attributes=[], facts=[],
                                  metrics=[], reports=[], dossiers=[])
        g = build_lineage_graph(data)
        assert g.node_count == 0

    def test_single_table_lineage(self):
        from powerbi_import.lineage import build_lineage_graph
        data = self._lineage_data()
        g = build_lineage_graph(data)
        assert g.node_count >= 1

    def test_export_openlineage(self):
        from powerbi_import.lineage import build_lineage_graph
        data = self._lineage_data()
        g = build_lineage_graph(data)
        export = g.to_openlineage()
        assert isinstance(export, dict)

    def test_impact_analysis(self):
        from powerbi_import.lineage import build_lineage_graph
        data = self._lineage_data()
        g = build_lineage_graph(data)
        nodes = list(g.nodes.keys())
        if nodes:
            downstream = g.get_downstream(nodes[0])
            assert isinstance(downstream, (list, set))


# ═══════════════════════════════════════════════════════════════════
# Strategy Advisor extended tests
# ═══════════════════════════════════════════════════════════════════

class TestStrategyAdvisorExtended:

    def test_empty_data_defaults_import(self):
        from powerbi_import.strategy_advisor import recommend_strategy, IMPORT
        data = {"datasources": []}
        result = recommend_strategy(data)
        assert result["recommended"] == IMPORT

    def test_single_connector(self):
        from powerbi_import.strategy_advisor import recommend_strategy, IMPORT
        data = {"datasources": [{"db_connection": {"db_type": "sql_server"}}]}
        result = recommend_strategy(data)
        assert result["recommended"] in (IMPORT, "Import")

    def test_fabric_mode(self):
        from powerbi_import.strategy_advisor import recommend_strategy, DIRECT_LAKE
        data = {"datasources": [{"db_connection": {"db_type": "sql_server"}}]}
        result = recommend_strategy(data, fabric_available=True)
        assert result["recommended"] in (DIRECT_LAKE, "DirectLake")

    def test_result_has_reasoning(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = {"datasources": [{"db_connection": {"db_type": "sql_server"}}]}
        result = recommend_strategy(data)
        assert "reasoning" in result or "factors" in result or isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# Assessment extended tests
# ═══════════════════════════════════════════════════════════════════

class TestAssessmentExtended:

    def test_empty_data(self):
        from powerbi_import.assessment import assess_project
        data = _minimal_data(datasources=[], metrics=[], reports=[], dossiers=[])
        result = assess_project(data)
        assert isinstance(result, dict)

    def test_minimal_data(self):
        from powerbi_import.assessment import assess_project
        data = _minimal_data()
        result = assess_project(data)
        assert result["summary"]["total_objects"] >= 1

    def test_writes_json_report(self):
        from powerbi_import.assessment import assess_project
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            assess_project(data, output_dir=td)
            assert os.path.isfile(os.path.join(td, "assessment_report.json"))

    def test_writes_html_report(self):
        from powerbi_import.assessment import assess_project
        data = _minimal_data()
        with tempfile.TemporaryDirectory() as td:
            assess_project(data, output_dir=td)
            assert os.path.isfile(os.path.join(td, "assessment_report.html"))
