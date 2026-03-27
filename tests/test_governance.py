"""Tests for v6.0 governance features (Sprint U)."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from powerbi_import.purview_integration import (
    build_purview_entities,
    build_lineage_edges,
    export_purview_payload,
    _build_classification_map,
)
from powerbi_import.governance_report import (
    generate_governance_report,
    compute_governance_score,
)
from powerbi_import.lineage import build_lineage_graph


# ── Fixtures ─────────────────────────────────────────────────────

def _sample_data():
    return {
        "datasources": [
            {
                "id": "t1", "name": "Sales",
                "physical_table": "dbo.Sales",
                "db_connection": {"name": "MSTR_DW"},
                "columns": [
                    {"name": "Customer_ID", "data_type": "integer"},
                    {"name": "Amount", "data_type": "decimal"},
                    {"name": "SSN", "data_type": "string"},
                ],
            },
        ],
        "attributes": [
            {
                "id": "a1", "name": "Customer",
                "description": "Customer attribute",
                "forms": [{"name": "ID", "category": "ID", "column_name": "Customer_ID", "table_name": "Sales"}],
                "data_type": "integer",
                "lookup_table": "Sales",
            },
        ],
        "facts": [
            {
                "id": "f1", "name": "Sales Amount",
                "description": "Total sales",
                "expressions": [{"table": "Sales", "column": "Amount"}],
                "data_type": "decimal",
                "default_aggregation": "sum",
            },
        ],
        "metrics": [
            {
                "id": "m1", "name": "Total Sales",
                "metric_type": "simple",
                "expression": "Sum(SalesAmount)",
                "aggregation": "sum",
                "column_ref": "Sales Amount",
                "description": "Sum of all sales",
                "dependencies": [],
            },
        ],
        "derived_metrics": [],
        "reports": [
            {
                "id": "r1", "name": "Sales Report",
                "report_type": "grid",
                "grid": {"rows": [{"name": "Customer", "type": "attribute"}], "columns": []},
                "metrics": [{"name": "Total Sales"}],
                "filters": [],
            },
        ],
        "dossiers": [],
        "security_filters": [
            {
                "name": "Region Filter",
                "expression": "[Region] = USERNAME()",
                "target_attributes": [{"id": "a1"}],
            },
        ],
        "hierarchies": [],
        "relationships": [],
    }


def _data_no_security():
    d = _sample_data()
    d["security_filters"] = []
    return d


def _data_no_descriptions():
    d = _sample_data()
    for m in d["metrics"]:
        m["description"] = ""
    for a in d["attributes"]:
        a["description"] = ""
    return d


def _data_with_errors():
    d = _sample_data()
    d["reports"] = [{"id": "r_err", "name": "Bad Report", "error": "timeout"}]
    return d


# ── Purview entity tests ─────────────────────────────────────────

class TestBuildPurviewEntities:
    def test_creates_entities(self):
        payload = build_purview_entities(_sample_data())
        entities = payload["entities"]
        assert len(entities) >= 1

    def test_has_semantic_model(self):
        payload = build_purview_entities(_sample_data())
        sm = [e for e in payload["entities"] if e["typeName"] == "powerbi_semantic_model"]
        assert len(sm) == 1

    def test_has_tables(self):
        payload = build_purview_entities(_sample_data())
        tables = [e for e in payload["entities"] if e["typeName"] == "powerbi_table"]
        assert len(tables) == 1

    def test_has_columns(self):
        payload = build_purview_entities(_sample_data())
        cols = [e for e in payload["entities"] if e["typeName"] == "powerbi_column"]
        assert len(cols) == 3  # Customer_ID, Amount, SSN

    def test_has_measures(self):
        payload = build_purview_entities(_sample_data())
        measures = [e for e in payload["entities"] if e["typeName"] == "powerbi_measure"]
        assert len(measures) == 1

    def test_ssn_classified(self):
        """SSN column should get Highly Confidential label."""
        payload = build_purview_entities(_sample_data())
        ssn_col = [e for e in payload["entities"]
                   if e["typeName"] == "powerbi_column" and e["attributes"]["name"] == "SSN"]
        assert len(ssn_col) == 1
        labels = ssn_col[0]["classifications"]
        assert any(c["attributes"]["label"] == "Highly Confidential" for c in labels)

    def test_qualified_name_prefix(self):
        payload = build_purview_entities(_sample_data(), qualified_name_prefix="custom://")
        sm = [e for e in payload["entities"] if e["typeName"] == "powerbi_semantic_model"]
        assert sm[0]["attributes"]["qualifiedName"].startswith("custom://")

    def test_security_filter_classification(self):
        """Columns protected by security filters get Confidential."""
        clmap = _build_classification_map(
            _sample_data()["security_filters"],
            _sample_data()["attributes"],
        )
        assert clmap.get("customer_id") == "Confidential"


class TestBuildLineageEdges:
    def test_creates_processes(self):
        g = build_lineage_graph(_sample_data())
        payload = build_lineage_edges(g)
        # Should have process entities for each "migrated_to" edge
        assert len(payload["entities"]) >= 1

    def test_process_has_inputs_outputs(self):
        g = build_lineage_graph(_sample_data())
        payload = build_lineage_edges(g)
        for p in payload["entities"]:
            assert "inputs" in p["relationshipAttributes"]
            assert "outputs" in p["relationshipAttributes"]


class TestExportPurviewPayload:
    def test_exports_to_file(self):
        payload = build_purview_entities(_sample_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "purview.json")
            export_purview_payload(payload, path)
            assert os.path.exists(path)
            with open(path, 'r') as f:
                loaded = json.load(f)
            assert len(loaded["entities"]) == len(payload["entities"])


# ── Governance report tests ──────────────────────────────────────

class TestGovernanceReport:
    def test_generates_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_sample_data(), path)
            assert os.path.exists(path)
            content = open(path, 'r', encoding='utf-8').read()
            assert "Governance Report" in content

    def test_returns_all_categories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_sample_data(), path)
            assert "Data Ownership" in results
            assert "Sensitivity Classification" in results
            assert "Row-Level Security" in results
            assert "Lineage Coverage" in results
            assert "Documentation" in results
            assert "Migration Readiness" in results

    def test_with_lineage_graph(self):
        g = build_lineage_graph(_sample_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_sample_data(), path, lineage_graph=g)
            lineage_checks = results["Lineage Coverage"]
            assert any(c["status"] == "PASS" for c in lineage_checks)

    def test_without_lineage_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_sample_data(), path, lineage_graph=None)
            lineage_checks = results["Lineage Coverage"]
            assert any(c["status"] == "WARN" for c in lineage_checks)

    def test_no_security_warns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_data_no_security(), path)
            cls_checks = results["Sensitivity Classification"]
            assert any(c["status"] == "WARN" for c in cls_checks)

    def test_no_descriptions_warns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_data_no_descriptions(), path)
            doc_checks = results["Documentation"]
            assert any(c["status"] in ("WARN", "FAIL") for c in doc_checks)

    def test_error_reports_warn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gov.html")
            results = generate_governance_report(_data_with_errors(), path)
            ready_checks = results["Migration Readiness"]
            assert any(c["name"] == "Extraction without errors" for c in ready_checks)


class TestGovernanceScore:
    def test_all_pass(self):
        results = {"Cat": [
            {"status": "PASS", "name": "A", "detail": "ok"},
            {"status": "PASS", "name": "B", "detail": "ok"},
        ]}
        assert compute_governance_score(results) == 100.0

    def test_all_fail(self):
        results = {"Cat": [
            {"status": "FAIL", "name": "A", "detail": "bad"},
        ]}
        assert compute_governance_score(results) == 0.0

    def test_mixed(self):
        results = {"Cat": [
            {"status": "PASS", "name": "A", "detail": ""},
            {"status": "WARN", "name": "B", "detail": ""},
            {"status": "FAIL", "name": "C", "detail": ""},
        ]}
        # 1 + 0.5 + 0 = 1.5 / 3 = 50%
        assert compute_governance_score(results) == 50.0

    def test_empty(self):
        assert compute_governance_score({}) == 100.0


# ── CLI argument tests ───────────────────────────────────────────

class TestCLIv6Args:
    @pytest.fixture
    def parser(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from migrate import build_parser
        return build_parser()

    def test_lineage_flag(self, parser):
        args = parser.parse_args(['--from-export', '.', '--lineage'])
        assert args.lineage is True

    def test_purview_flag(self, parser):
        args = parser.parse_args(['--from-export', '.', '--purview', 'myaccount'])
        assert args.purview == 'myaccount'

    def test_governance_flag(self, parser):
        args = parser.parse_args(['--from-export', '.', '--governance'])
        assert args.governance is True

    def test_version_8(self, parser):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        buf_err = io.StringIO()
        buf_out = io.StringIO()
        with pytest.raises(SystemExit):
            with redirect_stderr(buf_err), redirect_stdout(buf_out):
                parser.parse_args(['--version'])
        output = buf_err.getvalue() + buf_out.getvalue()
        assert '19.0.0' in output
