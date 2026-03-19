"""Tests for Sprint E: deployment, batch, shared model, expression hardening, gateway."""

import json
import os
import pathlib
from unittest.mock import patch, MagicMock

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
INTERMEDIATE_DIR = FIXTURES_DIR / "intermediate_json"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def data():
    """Load all 18 intermediate JSON files."""
    file_map = {
        "datasources": "datasources.json",
        "attributes": "attributes.json",
        "facts": "facts.json",
        "metrics": "metrics.json",
        "derived_metrics": "derived_metrics.json",
        "reports": "reports.json",
        "dossiers": "dossiers.json",
        "cubes": "cubes.json",
        "filters": "filters.json",
        "prompts": "prompts.json",
        "custom_groups": "custom_groups.json",
        "consolidations": "consolidations.json",
        "hierarchies": "hierarchies.json",
        "relationships": "relationships.json",
        "security_filters": "security_filters.json",
        "freeform_sql": "freeform_sql.json",
        "thresholds": "thresholds.json",
        "subtotals": "subtotals.json",
    }
    d = {}
    for key, filename in file_map.items():
        path = INTERMEDIATE_DIR / filename
        raw = _load_json(path)
        d[key] = raw if isinstance(raw, list) else [raw]
    return d


# ═══════════════════════════════════════════════════════════════════
#  PBI Service Deployer (mock)
# ═══════════════════════════════════════════════════════════════════


class TestPbiDeployer:
    """Test pbi_deployer with mocked HTTP."""

    def test_create_project_zip(self, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.pbi_deployer import _create_project_zip

        generate_pbip(data, str(tmp_path), report_name="ZipTest")
        zip_bytes = _create_project_zip(str(tmp_path))
        assert len(zip_bytes) > 0
        # Verify it's a valid zip
        import zipfile
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any(n.endswith(".pbip") for n in names)

    def test_infer_display_name(self, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.pbi_deployer import _infer_display_name

        generate_pbip(data, str(tmp_path), report_name="InferTest")
        name = _infer_display_name(str(tmp_path))
        assert name == "InferTest"

    @patch("powerbi_import.deploy.pbi_deployer.requests")
    def test_deploy_to_service_mock(self, mock_requests, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.pbi_deployer import deploy_to_service

        generate_pbip(data, str(tmp_path), report_name="Deploy")

        # Mock token
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="fake-token")

        # Mock import POST
        mock_import_resp = MagicMock()
        mock_import_resp.status_code = 202
        mock_import_resp.json.return_value = {"id": "import-123"}

        # Mock poll GET (succeeded)
        mock_poll_resp = MagicMock()
        mock_poll_resp.status_code = 200
        mock_poll_resp.json.return_value = {
            "importState": "Succeeded",
            "datasets": [{"id": "ds-1"}],
            "reports": [{"id": "rpt-1"}],
        }

        mock_requests.post.return_value = mock_import_resp
        mock_requests.get.return_value = mock_poll_resp
        mock_requests.utils.quote = lambda x: x

        result = deploy_to_service(
            str(tmp_path), "ws-abc",
            credential=mock_cred,
        )
        assert result["status"] == "succeeded"
        assert result["dataset_id"] == "ds-1"
        assert result["report_id"] == "rpt-1"

    @patch("powerbi_import.deploy.pbi_deployer.requests")
    def test_deploy_import_failure(self, mock_requests, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.pbi_deployer import deploy_to_service

        generate_pbip(data, str(tmp_path), report_name="Fail")
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="t")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        mock_requests.post.return_value = mock_resp
        mock_requests.utils.quote = lambda x: x

        with pytest.raises(RuntimeError, match="Import failed"):
            deploy_to_service(str(tmp_path), "ws-abc", credential=mock_cred)


# ═══════════════════════════════════════════════════════════════════
#  Fabric Deployer (mock)
# ═══════════════════════════════════════════════════════════════════


class TestFabricDeployer:
    """Test fabric_deployer with mocked HTTP."""

    def test_read_semantic_model_definition(self, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.fabric_deployer import _read_semantic_model_definition

        generate_pbip(data, str(tmp_path), report_name="FabDef")
        parts = _read_semantic_model_definition(str(tmp_path), "FabDef")
        assert len(parts) > 0
        assert all("path" in p for p in parts)
        assert all("payload" in p for p in parts)

    def test_read_report_definition(self, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.fabric_deployer import _read_report_definition

        generate_pbip(data, str(tmp_path), report_name="FabRpt")
        parts = _read_report_definition(str(tmp_path), "FabRpt")
        assert len(parts) > 0

    def test_infer_display_name(self, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.fabric_deployer import _infer_display_name

        generate_pbip(data, str(tmp_path), report_name="FabName")
        assert _infer_display_name(str(tmp_path)) == "FabName"

    @patch("powerbi_import.deploy.fabric_deployer.requests")
    def test_deploy_to_fabric_mock(self, mock_requests, data, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        from powerbi_import.deploy.fabric_deployer import deploy_to_fabric

        generate_pbip(data, str(tmp_path), report_name="Fab")
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="t")

        # Mock item creation
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "sm-1"}
        mock_resp.text = '{"id": "sm-1"}'

        mock_rpt_resp = MagicMock()
        mock_rpt_resp.status_code = 201
        mock_rpt_resp.json.return_value = {"id": "rpt-1"}
        mock_rpt_resp.text = '{"id": "rpt-1"}'

        mock_requests.post.side_effect = [mock_resp, mock_rpt_resp]

        result = deploy_to_fabric(str(tmp_path), "ws-fab", credential=mock_cred)
        assert result["status"] == "succeeded"
        assert result["semantic_model_id"] == "sm-1"


# ═══════════════════════════════════════════════════════════════════
#  Gateway Config
# ═══════════════════════════════════════════════════════════════════


class TestGatewayConfig:
    """Test gateway configuration generator."""

    def test_generate_empty(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        result = generate_gateway_config([])
        assert result["connections"] == []
        assert len(result["instructions"]) >= 1

    def test_generate_oracle(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "oracle", "server": "ora-host", "database": "ORCL",
               "service_name": "orcl.world", "name": "OracleDS"}]
        result = generate_gateway_config(ds)
        assert len(result["connections"]) == 1
        conn = result["connections"][0]
        assert conn["gatewayDataSourceType"] == "Oracle"
        assert conn["server"] == "ora-host"
        assert conn["connectionProperties"]["serviceName"] == "orcl.world"

    def test_generate_sql_server(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "sql_server", "server": "sql-host", "database": "SalesDB"}]
        result = generate_gateway_config(ds)
        assert result["connections"][0]["gatewayDataSourceType"] == "Sql"

    def test_generate_snowflake(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "snowflake", "server": "acct.snowflakecomputing.com",
               "database": "PROD", "warehouse": "WH1", "role": "ANALYST"}]
        result = generate_gateway_config(ds)
        conn = result["connections"][0]
        assert conn["gatewayDataSourceType"] == "Snowflake"
        assert conn["connectionProperties"]["warehouse"] == "WH1"

    def test_unknown_type_skipped(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "unknown_db", "server": "x"}]
        result = generate_gateway_config(ds)
        assert result["connections"] == []

    def test_write_config_file(self, tmp_path):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "postgresql", "server": "pg-host", "database": "app"}]
        out = str(tmp_path / "gw.json")
        generate_gateway_config(ds, output_path=out)
        assert os.path.exists(out)
        config = json.loads(open(out, encoding="utf-8").read())
        assert config["connections"][0]["gatewayDataSourceType"] == "PostgreSql"

    def test_auth_windows(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "sql_server", "server": "h", "database": "d",
               "auth_type": "windows"}]
        result = generate_gateway_config(ds)
        assert result["connections"][0]["authentication"]["type"] == "Windows"

    def test_instructions_include_steps(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [{"db_type": "mysql", "server": "h", "database": "d"}]
        result = generate_gateway_config(ds)
        instructions = "\n".join(result["instructions"])
        assert "gateway" in instructions.lower()

    def test_multiple_datasources(self):
        from powerbi_import.deploy.gateway_config import generate_gateway_config

        ds = [
            {"db_type": "oracle", "server": "ora", "database": "A"},
            {"db_type": "postgresql", "server": "pg", "database": "B"},
        ]
        result = generate_gateway_config(ds)
        assert len(result["connections"]) == 2


# ═══════════════════════════════════════════════════════════════════
#  Shared Model
# ═══════════════════════════════════════════════════════════════════


class TestSharedModel:
    """Test shared semantic model generation."""

    def test_generates_valid_pbip(self, data, tmp_path):
        from powerbi_import.shared_model import generate_shared_model

        stats = generate_shared_model(data, str(tmp_path), model_name="Shared")
        project_dir = tmp_path / "Shared_SharedModel"
        assert (project_dir / "Shared.pbip").exists()
        assert (project_dir / "Shared.SemanticModel").is_dir()
        assert (project_dir / "Shared.Report").is_dir()

    def test_shared_model_has_tmdl(self, data, tmp_path):
        from powerbi_import.shared_model import generate_shared_model

        generate_shared_model(data, str(tmp_path), model_name="SM")
        sm = tmp_path / "SM_SharedModel" / "SM.SemanticModel" / "definition"
        assert (sm / "model.tmdl").exists()
        assert (sm / "tables").is_dir()

    def test_shared_model_returns_stats(self, data, tmp_path):
        from powerbi_import.shared_model import generate_shared_model

        stats = generate_shared_model(data, str(tmp_path), model_name="St")
        assert "tables" in stats
        assert stats["tables"] >= 1

    def test_report_shell_is_empty(self, data, tmp_path):
        from powerbi_import.shared_model import generate_shared_model

        generate_shared_model(data, str(tmp_path), model_name="E")
        page = tmp_path / "E_SharedModel" / "E.Report" / "definition" / "pages" / "overview" / "page.json"
        assert page.exists()
        pg = json.loads(page.read_text(encoding="utf-8"))
        assert pg["visuals"] == []

    def test_validates_clean(self, data, tmp_path):
        from powerbi_import.shared_model import generate_shared_model
        from powerbi_import.validator import validate_project

        generate_shared_model(data, str(tmp_path), model_name="V")
        result = validate_project(str(tmp_path / "V_SharedModel"))
        assert result["valid"] is True, f"Errors: {result['errors']}"


# ═══════════════════════════════════════════════════════════════════
#  Expression Hardening
# ═══════════════════════════════════════════════════════════════════

from microstrategy_export.expression_converter import (
    convert_mstr_expression_to_dax,
    resolve_nested_metrics,
    qualify_column_references,
)


class TestExpressionHardening:
    """Test newly hardened expression conversion patterns."""

    def test_ntile(self):
        result = convert_mstr_expression_to_dax("NTile(Revenue, 4)")
        assert "RANKX" in result["dax"]
        assert "4" in result["dax"]
        assert result["fidelity"] == "approximated"

    def test_band(self):
        result = convert_mstr_expression_to_dax("Band(Revenue, 0, 1000, 100)")
        assert "0" in result["dax"]
        assert "1000" in result["dax"]
        assert "100" in result["dax"]
        assert result["fidelity"] == "approximated"

    def test_moving_sum(self):
        result = convert_mstr_expression_to_dax("MovingSum(Revenue, 3)")
        assert "SUMX" in result["dax"]
        assert "3" in result["dax"]

    def test_apply_logic(self):
        result = convert_mstr_expression_to_dax('ApplyLogic("#0 > 0 AND #1 < 100", Revenue, Cost)')
        assert "&&" in result["dax"]
        assert "[Revenue]" in result["dax"]
        assert result["fidelity"] == "approximated"

    def test_apply_comparison(self):
        result = convert_mstr_expression_to_dax('ApplyComparison("#0 > #1", Revenue, Cost)')
        assert "[Revenue]" in result["dax"]
        assert "[Cost]" in result["dax"]
        assert result["fidelity"] == "approximated"

    def test_apply_olap_manual_review(self):
        result = convert_mstr_expression_to_dax('ApplyOLAP("ROW_NUMBER() OVER (ORDER BY #0)", Revenue)')
        assert result["fidelity"] == "manual_review"
        assert "MANUAL REVIEW" in result["dax"]

    def test_nested_metric_resolution(self):
        lookup = {"Revenue": "SUM(Sales[Revenue])", "Cost": "SUM(Sales[Cost])"}
        expr = "[Revenue] - [Cost]"
        resolved = resolve_nested_metrics(expr, lookup)
        assert "SUM(Sales[Revenue])" in resolved
        assert "SUM(Sales[Cost])" in resolved

    def test_nested_metric_unknown_left_alone(self):
        lookup = {"Revenue": "SUM(Sales[Revenue])"}
        expr = "[Revenue] + [Unknown]"
        resolved = resolve_nested_metrics(expr, lookup)
        assert "SUM(Sales[Revenue])" in resolved
        assert "[Unknown]" in resolved

    def test_qualify_bare_columns(self):
        expr = "SUM(Revenue)"
        result = qualify_column_references(expr, "Sales")
        assert "'Sales'[Revenue]" in result

    def test_qualify_already_qualified(self):
        expr = "SUM('Sales'[Revenue])"
        result = qualify_column_references(expr, "Sales")
        assert result == expr

    def test_qualify_multiple_functions(self):
        expr = "SUM(Revenue) + COUNT(OrderID)"
        result = qualify_column_references(expr, "Fact")
        assert "'Fact'[Revenue]" in result
        assert "'Fact'[OrderID]" in result


# ═══════════════════════════════════════════════════════════════════
#  Batch Mode (generate per-object)
# ═══════════════════════════════════════════════════════════════════


class TestBatchGeneration:
    """Test batch mode generates separate projects."""

    def test_batch_per_report(self, data, tmp_path):
        """Each report gets its own subfolder."""
        from powerbi_import.pbip_generator import generate_pbip

        reports = data.get("reports", [])
        if not reports:
            pytest.skip("No reports in fixtures")

        for i, report in enumerate(reports):
            obj_data = dict(data)
            obj_data["reports"] = [report]
            obj_data["dossiers"] = []
            name = report.get("name", f"R{i}")
            sub = tmp_path / name.replace(" ", "_")
            generate_pbip(obj_data, str(sub), report_name=name)
            assert any(f.name.endswith(".pbip") for f in sub.iterdir())

    def test_batch_per_dossier(self, data, tmp_path):
        """Each dossier gets its own subfolder."""
        from powerbi_import.pbip_generator import generate_pbip

        dossiers = data.get("dossiers", [])
        if not dossiers:
            pytest.skip("No dossiers in fixtures")

        for j, dossier in enumerate(dossiers):
            obj_data = dict(data)
            obj_data["reports"] = []
            obj_data["dossiers"] = [dossier]
            name = dossier.get("name", f"D{j}")
            sub = tmp_path / name.replace(" ", "_")
            generate_pbip(obj_data, str(sub), report_name=name)
            assert any(f.name.endswith(".pbip") for f in sub.iterdir())


# ═══════════════════════════════════════════════════════════════════
#  CLI Argument Parsing
# ═══════════════════════════════════════════════════════════════════


class TestCliArgs:
    """Test CLI argument parser has Sprint E flags."""

    def test_deploy_flag(self):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--deploy", "ws-123"])
        assert args.deploy == "ws-123"

    def test_fabric_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--fabric"])
        assert args.fabric is True

    def test_direct_lake_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--direct-lake", "--lakehouse-id", "lh-1"])
        assert args.direct_lake is True
        assert args.lakehouse_id == "lh-1"

    def test_batch_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--batch"])
        assert args.batch is True

    def test_shared_model_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--shared-model"])
        assert args.shared_model is True

    def test_tenant_client_flags(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--from-export", ".",
            "--tenant-id", "t1",
            "--client-id", "c1",
            "--client-secret", "s1",
        ])
        assert args.tenant_id == "t1"
        assert args.client_id == "c1"
        assert args.client_secret == "s1"
