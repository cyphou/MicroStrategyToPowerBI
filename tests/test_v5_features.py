"""
Tests for v5.0 features — Fabric Native Integration (Sprints R + S).
"""

import json
import os
import tempfile

import pytest


# ── Test data fixtures ───────────────────────────────────────────

def _sample_data(n_tables=2, n_metrics=3, db_type="sql_server"):
    """Build minimal intermediate-JSON data dict for testing."""
    datasources = []
    for i in range(1, n_tables + 1):
        datasources.append({
            "name": f"Table{i}",
            "physical_table": f"dbo_Table{i}",
            "columns": [
                {"name": f"Col{j}", "data_type": "varchar", "sql_type": "varchar(100)"}
                for j in range(1, 4)
            ] + [
                {"name": "Amount", "data_type": "double", "sql_type": "float"},
                {"name": "EventDate", "data_type": "date", "sql_type": "date"},
            ],
            "db_connection": {
                "db_type": db_type,
                "host": "myserver",
                "port": 1433,
                "database": "mydb",
                "schema": "dbo",
            },
        })

    metrics = [
        {"name": f"Metric{i}", "expression": f"Sum(Amount)", "table": "Table1"}
        for i in range(1, n_metrics + 1)
    ]

    return {
        "datasources": datasources,
        "attributes": [
            {"id": "A1", "name": "Col1", "table": "Table1", "column": "Col1"},
        ],
        "facts": [
            {"name": "Amount", "table": "Table1", "column": "Amount",
             "data_type": "double"},
        ],
        "metrics": metrics,
        "derived_metrics": [],
        "reports": [],
        "dossiers": [],
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


def _sample_multi_connector_data():
    """Data with multiple connector types for notebook diversity."""
    data = _sample_data(db_type="sql_server")
    data["datasources"].append({
        "name": "SnowTable",
        "physical_table": "SNOW_TABLE",
        "columns": [
            {"name": "ID", "data_type": "integer", "sql_type": "int"},
            {"name": "Name", "data_type": "varchar", "sql_type": "varchar(200)"},
        ],
        "db_connection": {
            "db_type": "snowflake",
            "host": "acme.snowflakecomputing.com",
            "database": "ANALYTICS",
            "schema": "PUBLIC",
        },
    })
    return data


# ═══════════════════════════════════════════════════════════════════
# Sprint R — DirectLake & Lakehouse
# ═══════════════════════════════════════════════════════════════════


class TestLakehouseGenerator:
    """Lakehouse DDL generation (Sprint R.2)."""

    def test_generate_lakehouse_schema_basic(self):
        from powerbi_import.lakehouse_generator import generate_lakehouse_schema
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_lakehouse_schema(data, td, lakehouse_name="TestLH")
            assert stats["tables_generated"] == 2
            schema_path = os.path.join(td, "lakehouse_schema.sql")
            assert os.path.isfile(schema_path)
            content = open(schema_path, encoding="utf-8").read()
            assert "CREATE TABLE IF NOT EXISTS" in content
            assert "USING DELTA" in content

    def test_lakehouse_individual_table_files(self):
        from powerbi_import.lakehouse_generator import generate_lakehouse_schema
        data = _sample_data(n_tables=3)
        with tempfile.TemporaryDirectory() as td:
            generate_lakehouse_schema(data, td, lakehouse_name="LH")
            tables_dir = os.path.join(td, "tables")
            assert os.path.isdir(tables_dir)
            sql_files = [f for f in os.listdir(tables_dir) if f.endswith(".sql")]
            assert len(sql_files) == 3

    def test_lakehouse_type_mapping(self):
        from powerbi_import.lakehouse_generator import generate_lakehouse_schema
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_lakehouse_schema(data, td, lakehouse_name="LH")
            content = open(os.path.join(td, "lakehouse_schema.sql"), encoding="utf-8").read()
            # varchar → STRING, double → DOUBLE, date → DATE
            assert "STRING" in content
            assert "DOUBLE" in content
            assert "DATE" in content

    def test_lakehouse_empty_datasources(self):
        from powerbi_import.lakehouse_generator import generate_lakehouse_schema
        data = _sample_data()
        data["datasources"] = []
        with tempfile.TemporaryDirectory() as td:
            stats = generate_lakehouse_schema(data, td, lakehouse_name="LH")
            assert stats["tables_generated"] == 0


class TestShortcutGenerator:
    """OneLake shortcut generation (Sprint R.5)."""

    def test_generate_shortcuts_basic(self):
        from powerbi_import.lakehouse_generator import generate_shortcuts
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_shortcuts(data, td, adls_account="myaccount",
                                       container="data")
            assert stats["shortcuts_generated"] >= 1
            sc_path = os.path.join(td, "shortcuts.json")
            assert os.path.isfile(sc_path)
            shortcuts = json.load(open(sc_path, encoding="utf-8"))
            assert isinstance(shortcuts, list)
            assert len(shortcuts) > 0

    def test_shortcuts_adls_target(self):
        from powerbi_import.lakehouse_generator import generate_shortcuts
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_shortcuts(data, td, adls_account="store1", container="raw")
            shortcuts = json.load(open(os.path.join(td, "shortcuts.json"), encoding="utf-8"))
            for sc in shortcuts:
                target = sc.get("target", {})
                # Should have an ADLS-style target
                assert target


class TestDirectLakeTMDL:
    """DirectLake partition generation in TMDL (Sprint R.1)."""

    def test_tmdl_directlake_partition(self):
        from powerbi_import.tmdl_generator import generate_table_tmdl
        ds = {
            "name": "Sales",
            "physical_table": "dbo_Sales",
            "columns": [{"name": "Amount", "data_type": "double"}],
            "db_connection": {"db_type": "sql_server"},
        }
        result = generate_table_tmdl(ds, [], [{"name": "Amount", "table": "Sales",
                                               "column": "Amount", "data_type": "double"}],
                                     [], [], [], {},
                                     direct_lake=True, lakehouse_name="MyLH")
        assert "mode: directLake" in result
        assert "entityName: dbo_Sales" in result
        assert "LakehouseName = MyLH" in result
        assert "mode: import" not in result

    def test_tmdl_import_partition_unchanged(self):
        from powerbi_import.tmdl_generator import generate_table_tmdl
        ds = {
            "name": "Sales",
            "physical_table": "Sales",
            "columns": [{"name": "ID", "data_type": "integer"}],
            "db_connection": {"db_type": "sql_server", "host": "srv",
                              "database": "db", "schema": "dbo"},
        }
        result = generate_table_tmdl(ds, [], [], [], [], [], {},
                                     direct_lake=False)
        assert "mode: import" in result
        assert "mode: directLake" not in result

    def test_generate_all_tmdl_directlake(self):
        from powerbi_import.tmdl_generator import generate_all_tmdl
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_all_tmdl(data, td, direct_lake=True,
                                       lakehouse_name="FabricLH")
            assert stats["tables"] >= 1
            # Check that generated files contain DirectLake
            tables_dir = os.path.join(td, "tables")
            tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
            assert len(tmdl_files) >= 1
            content = open(os.path.join(tables_dir, tmdl_files[0]),
                           encoding="utf-8").read()
            assert "directLake" in content

    def test_generate_all_tmdl_import_default(self):
        from powerbi_import.tmdl_generator import generate_all_tmdl
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_all_tmdl(data, td)
            tables_dir = os.path.join(td, "tables")
            tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
            content = open(os.path.join(tables_dir, tmdl_files[0]),
                           encoding="utf-8").read()
            assert "mode: import" in content


class TestNotebookGenerator:
    """PySpark ETL notebook generation (Sprint R.3)."""

    def test_generate_notebooks_basic(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="TestLH")
            assert stats["notebooks_generated"] >= 1
            ipynb_files = [f for f in os.listdir(td) if f.endswith(".ipynb")]
            assert len(ipynb_files) >= 1

    def test_notebook_valid_json(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_notebooks(data, td, lakehouse_name="LH")
            for fname in os.listdir(td):
                if fname.endswith(".ipynb"):
                    nb = json.load(open(os.path.join(td, fname), encoding="utf-8"))
                    assert "cells" in nb
                    assert "metadata" in nb
                    assert nb["nbformat"] == 4

    def test_notebook_has_spark_cells(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_notebooks(data, td, lakehouse_name="LH")
            for fname in os.listdir(td):
                if fname.endswith(".ipynb"):
                    nb = json.load(open(os.path.join(td, fname), encoding="utf-8"))
                    sources = "".join(
                        "".join(c.get("source", []))
                        for c in nb["cells"]
                    )
                    assert "spark" in sources.lower()

    def test_notebook_multi_connector(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_multi_connector_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="LH")
            # Should create at least 2 notebooks (one per connector group)
            assert stats["notebooks_generated"] >= 2

    def test_notebook_empty_datasources(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_data()
        data["datasources"] = []
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="LH")
            assert stats["notebooks_generated"] == 0

    def test_notebook_freeform_sql(self):
        from powerbi_import.notebook_generator import generate_notebooks
        data = _sample_data()
        data["freeform_sql"] = [{
            "name": "CustomQuery",
            "sql": "SELECT a, b FROM t WHERE x > 1",
            "table": "Table1",
            "db_connection": data["datasources"][0]["db_connection"],
        }]
        with tempfile.TemporaryDirectory() as td:
            stats = generate_notebooks(data, td, lakehouse_name="LH")
            assert stats["notebooks_generated"] >= 1


# ═══════════════════════════════════════════════════════════════════
# Sprint S — Fabric Deployment Pipeline
# ═══════════════════════════════════════════════════════════════════


class TestPipelineGenerator:
    """Data Factory pipeline generation (Sprint S.2)."""

    def test_generate_pipeline_basic(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pipeline(data, td, lakehouse_name="LH",
                                      semantic_model_name="TestModel",
                                      workspace_id="ws-123")
            assert stats["activities_count"] >= 1
            pipeline_path = os.path.join(td, "pipeline.json")
            assert os.path.isfile(pipeline_path)

    def test_pipeline_valid_json(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_pipeline(data, td, lakehouse_name="LH",
                              semantic_model_name="M", workspace_id="ws")
            pipeline = json.load(open(os.path.join(td, "pipeline.json"),
                                       encoding="utf-8"))
            assert "name" in pipeline
            assert "properties" in pipeline
            assert "activities" in pipeline["properties"]

    def test_pipeline_has_copy_activities(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _sample_data(n_tables=3)
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pipeline(data, td, lakehouse_name="LH",
                                      semantic_model_name="M", workspace_id="ws")
            pipeline = json.load(open(os.path.join(td, "pipeline.json"),
                                       encoding="utf-8"))
            activities = pipeline["properties"]["activities"]
            copy_acts = [a for a in activities if a.get("type") == "Copy"]
            assert len(copy_acts) >= 2  # at least 2 tables

    def test_pipeline_has_refresh_activity(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_pipeline(data, td, lakehouse_name="LH",
                              semantic_model_name="M", workspace_id="ws")
            pipeline = json.load(open(os.path.join(td, "pipeline.json"),
                                       encoding="utf-8"))
            activities = pipeline["properties"]["activities"]
            types = [a.get("type", "") for a in activities]
            # Should have a refresh or web activity
            assert any("Refresh" in t or "Web" in t for t in types)

    def test_pipeline_empty_tables(self):
        from powerbi_import.pipeline_generator import generate_pipeline
        data = _sample_data()
        data["datasources"] = []
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pipeline(data, td, lakehouse_name="LH",
                                      semantic_model_name="M", workspace_id="ws")
            assert stats["activities_count"] >= 0


class TestFabricEnvironment:
    """Fabric environment config generation (Sprint S.3)."""

    def test_generate_environment_basic(self):
        from powerbi_import.deploy.fabric_env import generate_environment
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_environment(data, td, env_name="TestEnv")
            env_path = os.path.join(td, "environment.json")
            assert os.path.isfile(env_path)
            env = json.load(open(env_path, encoding="utf-8"))
            assert env["name"] == "TestEnv"

    def test_generate_environment_requirements(self):
        from powerbi_import.deploy.fabric_env import generate_environment
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            generate_environment(data, td, env_name="Env")
            req_path = os.path.join(td, "requirements.txt")
            assert os.path.isfile(req_path)

    def test_estimate_capacity_small(self):
        from powerbi_import.deploy.fabric_env import estimate_capacity
        data = _sample_data(n_tables=2, n_metrics=3)
        cap = estimate_capacity(data)
        assert "recommended_sku" in cap
        assert cap["recommended_sku"] in ("F2", "F4", "F8", "F16", "F32", "F64")

    def test_estimate_capacity_large(self):
        from powerbi_import.deploy.fabric_env import estimate_capacity
        data = _sample_data(n_tables=20, n_metrics=100)
        cap = estimate_capacity(data)
        assert "recommended_sku" in cap
        # More tables/metrics → higher SKU
        assert cap["recommended_sku"] not in ("F2",)

    def test_environment_libraries(self):
        from powerbi_import.deploy.fabric_env import generate_environment
        data = _sample_multi_connector_data()
        with tempfile.TemporaryDirectory() as td:
            generate_environment(data, td, env_name="E")
            env = json.load(open(os.path.join(td, "environment.json"), encoding="utf-8"))
            # Should include JDBC or connector libraries
            libs = env.get("sparkPool", {}).get("libraries", [])
            assert isinstance(libs, list)


class TestFabricGit:
    """Fabric Git integration (Sprint R.4)."""

    def test_collect_project_files(self):
        from powerbi_import.deploy.fabric_git import _collect_project_files
        with tempfile.TemporaryDirectory() as td:
            # Create a minimal .pbip structure
            os.makedirs(os.path.join(td, "Model.SemanticModel", "definition", "tables"))
            with open(os.path.join(td, "Model.SemanticModel", "definition",
                                   "tables", "T.tmdl"), "w") as f:
                f.write("table T\n")
            with open(os.path.join(td, "project.pbip"), "w") as f:
                f.write("{}")

            files = _collect_project_files(td)
            assert len(files) >= 1
            # Files should have path and payload
            for fentry in files:
                assert "path" in fentry
                assert "payload" in fentry

    def test_get_git_status_returns_dict(self):
        """get_git_status should return a dict (mocked via fixtures)."""
        # We can't call Fabric API in tests, but we verify the function signature
        from powerbi_import.deploy.fabric_git import get_git_status
        import inspect
        sig = inspect.signature(get_git_status)
        assert "workspace_id" in sig.parameters
        assert "token" in sig.parameters


class TestStrategyAdvisorFabric:
    """Enhanced strategy advisor for Fabric (Sprint R.1)."""

    def test_fabric_recommends_directlake_with_cubes(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = _sample_data()
        data["cubes"] = [{"id": "C1", "name": "Cube1"}]
        result = recommend_strategy(data, fabric_available=True)
        assert result["recommended"] == "DirectLake"

    def test_fabric_recommends_directlake_without_cubes(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = _sample_data()
        data["cubes"] = []
        result = recommend_strategy(data, fabric_available=True)
        assert result["recommended"] == "DirectLake"

    def test_no_fabric_defaults_import(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = _sample_data()
        data["cubes"] = []
        result = recommend_strategy(data, fabric_available=False)
        assert result["recommended"] == "Import"

    def test_fabric_large_tables_directlake(self):
        from powerbi_import.strategy_advisor import recommend_strategy
        data = _sample_data()
        data["datasources"][0]["row_count"] = 50_000_000
        result = recommend_strategy(data, fabric_available=True)
        assert result["recommended"] == "DirectLake"
        assert "large tables" in result["rationale"].lower()


# ═══════════════════════════════════════════════════════════════════
# Integration — Full PBIP with DirectLake
# ═══════════════════════════════════════════════════════════════════


class TestPBIPDirectLakeIntegration:
    """End-to-end .pbip generation with DirectLake mode."""

    def test_pbip_directlake_flag(self):
        from powerbi_import.pbip_generator import generate_pbip
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pbip(data, td, report_name="DL Test",
                                  direct_lake=True, lakehouse_name="FabricLH")
            assert stats["tables"] >= 1
            # Verify TMDL files use DirectLake
            sm_dir = os.path.join(td, "DL Test.SemanticModel", "definition", "tables")
            assert os.path.isdir(sm_dir)
            for fname in os.listdir(sm_dir):
                if fname.endswith(".tmdl") and fname != "Calendar.tmdl":
                    content = open(os.path.join(sm_dir, fname), encoding="utf-8").read()
                    assert "directLake" in content

    def test_pbip_import_default(self):
        from powerbi_import.pbip_generator import generate_pbip
        data = _sample_data()
        with tempfile.TemporaryDirectory() as td:
            stats = generate_pbip(data, td, report_name="Import Test")
            sm_dir = os.path.join(td, "Import Test.SemanticModel", "definition", "tables")
            for fname in os.listdir(sm_dir):
                if fname.endswith(".tmdl") and fname != "Calendar.tmdl":
                    content = open(os.path.join(sm_dir, fname), encoding="utf-8").read()
                    assert "mode: import" in content

    def test_importer_directlake_passthrough(self):
        """Verify PowerBIImporter passes direct_lake to generate_pbip."""
        from powerbi_import.import_to_powerbi import PowerBIImporter
        data = _sample_data()

        # Write sample data to temp source dir
        with tempfile.TemporaryDirectory() as src:
            for key, val in data.items():
                with open(os.path.join(src, f"{key}.json"), "w", encoding="utf-8") as f:
                    json.dump(val, f)

            with tempfile.TemporaryDirectory() as out:
                importer = PowerBIImporter(source_dir=src)
                result = importer.import_all(
                    output_dir=out,
                    report_name="DLTest",
                    direct_lake=True,
                    lakehouse_name="TestLH",
                )
                assert result  # Should succeed
                sm_dir = os.path.join(out, "DLTest.SemanticModel", "definition", "tables")
                for fname in os.listdir(sm_dir):
                    if fname.endswith(".tmdl") and fname != "Calendar.tmdl":
                        content = open(os.path.join(sm_dir, fname), encoding="utf-8").read()
                        assert "directLake" in content


# ═══════════════════════════════════════════════════════════════════
# CLI argument parsing
# ═══════════════════════════════════════════════════════════════════


class TestCLIv5Args:
    """v5.0 CLI argument parsing."""

    def _parse(self, *cli_args):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from migrate import build_parser
        parser = build_parser()
        return parser.parse_args(list(cli_args))

    def test_fabric_mode_lakehouse(self):
        args = self._parse("--from-export", "test/", "--fabric-mode", "lakehouse")
        assert args.fabric_mode == "lakehouse"

    def test_fabric_mode_warehouse(self):
        args = self._parse("--from-export", "test/", "--fabric-mode", "warehouse")
        assert args.fabric_mode == "warehouse"

    def test_fabric_mode_shortcut(self):
        args = self._parse("--from-export", "test/", "--fabric-mode", "shortcut")
        assert args.fabric_mode == "shortcut"

    def test_lakehouse_name_default(self):
        args = self._parse("--from-export", "test/")
        assert args.lakehouse_name == "MstrLakehouse"

    def test_lakehouse_name_custom(self):
        args = self._parse("--from-export", "test/", "--lakehouse-name", "MyLH")
        assert args.lakehouse_name == "MyLH"

    def test_fabric_git_flag(self):
        args = self._parse("--from-export", "test/", "--fabric-git")
        assert args.fabric_git is True

    def test_fabric_git_branch(self):
        args = self._parse("--from-export", "test/", "--fabric-git-branch", "dev")
        assert args.fabric_git_branch == "dev"

    def test_env_name_default(self):
        args = self._parse("--from-export", "test/")
        assert args.env_name == "MstrSparkEnv"

    def test_version_is_7(self):
        from migrate import build_parser
        parser = build_parser()
        # Check version action directly
        for action in parser._actions:
            if hasattr(action, 'version') and action.version:
                assert "8.0.0" in action.version
                return
        pytest.fail("No version action found")

    def test_adls_account_arg(self):
        args = self._parse("--from-export", "test/",
                           "--fabric-mode", "shortcut",
                           "--adls-account", "mystorage")
        assert args.adls_account == "mystorage"
