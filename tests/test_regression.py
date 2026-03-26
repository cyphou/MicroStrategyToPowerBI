"""
Regression tests for PBI Desktop bugs fixed in v2.0.x.

Prevents re-introduction of all 10 bugs fixed during the PBI Desktop
conformance phase.  Each test targets a specific commit / fix.
"""

import os
import json
import pytest
import pathlib

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
INTERMEDIATE_DIR = FIXTURES_DIR / "intermediate_json"


def _load(name):
    with open(INTERMEDIATE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _load_all():
    data = {}
    for fname in INTERMEDIATE_DIR.glob("*.json"):
        key = fname.stem
        data[key] = json.loads(fname.read_text("utf-8"))
    return data


# ── F.8.1: logicalId must be a GUID (commit a76df52) ────────────

class TestLogicalIdIsGuid:
    def test_platform_logical_id_is_uuid(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = _load_all()
        generate_pbip(data, str(tmp_path), report_name="TestReg")

        for plat in tmp_path.rglob(".platform"):
            obj = json.loads(plat.read_text("utf-8"))
            lid = obj.get("config", {}).get("logicalId", "")
            # Must contain hyphens (UUID format)
            assert "-" in lid, f"logicalId must be UUID, got {lid}"
            parts = lid.split("-")
            assert len(parts) == 5, f"logicalId must be UUID with 5 parts: {lid}"


# ── F.8.2: crossFilteringBehavior must be 'oneDirection' (commit 11da4c8) ─

class TestCrossFilterDirection:
    def test_relationships_use_one_direction(self):
        from powerbi_import.tmdl_generator import generate_relationships_tmdl
        rels = [{"from_table": "A", "from_column": "id",
                 "to_table": "B", "to_column": "aid",
                 "cross_filter": "single"}]
        tmdl = generate_relationships_tmdl(rels)
        assert "oneDirection" in tmdl
        assert "singleDirection" not in tmdl


# ── F.8.3: Multi-line DAX wrapped in triple backticks (commit d2496e8) ─

class TestMultiLineDax:
    def test_multiline_dax_uses_backtick_block(self):
        from powerbi_import.tmdl_generator import _generate_measure
        metric = {
            "name": "TestMeasure",
            "id": "m1",
            "expression": "Sum(Col)",
            "metric_type": "simple",
        }
        # Patch convert_metric_to_dax to return multi-line
        import powerbi_import.tmdl_generator as tg
        orig = tg.convert_metric_to_dax

        def _fake(m, context=None):
            return {"dax": "IF(\n  [A] > 0,\n  [B],\n  BLANK()\n)"}
        tg.convert_metric_to_dax = _fake
        try:
            lines = _generate_measure(metric, "T")
            text = "\n".join(lines)
            assert "```" in text, "Multi-line DAX must be wrapped in triple backticks"
        finally:
            tg.convert_metric_to_dax = orig


# ── F.8.4: Only one isKey per table (commit 7a4104b) ────────────

class TestSingleIsKey:
    def test_at_most_one_iskey(self, tmp_path):
        from powerbi_import.tmdl_generator import generate_table_tmdl
        ds = {
            "name": "LU_TEST",
            "id": "t1",
            "columns": [
                {"name": "COL_A_ID", "data_type": "integer"},
                {"name": "COL_B_ID", "data_type": "integer"},
                {"name": "DESC_COL", "data_type": "varchar"},
            ],
        }
        attrs = [
            {"id": "a1", "name": "A", "lookup_table": "LU_TEST",
             "forms": [{"table": "LU_TEST", "column_name": "COL_A_ID", "category": "ID"}]},
            {"id": "a2", "name": "B", "lookup_table": "LU_TEST",
             "forms": [{"table": "LU_TEST", "column_name": "COL_B_ID", "category": "ID"}]},
        ]
        attr_by_id = {a["id"]: a for a in attrs}
        tmdl = generate_table_tmdl(ds, attrs, [], [], [], [], attr_by_id)
        assert tmdl.count("isKey") == 1


# ── F.8.5: Hierarchy name must not collide with column name (commit ec2fa19)

class TestHierarchyNameCollision:
    def test_hierarchy_renamed_on_collision(self):
        from powerbi_import.tmdl_generator import _generate_hierarchy
        levels = [{"name": "Year", "attribute_id": "a1", "order": 1}]
        attr_by_id = {"a1": {"name": "Year", "forms": [
            {"table": "T", "column_name": "YEAR_ID", "category": "ID"}
        ]}}
        cols = [{"name": "YEAR_ID"}, {"name": "Product"}]
        # "Product" is in col_display_names → hierarchy named "Product" should be renamed
        lines = _generate_hierarchy("Product", levels, attr_by_id, "T", cols,
                                    col_display_names={"Product"})
        text = "\n".join(lines)
        assert "Product Hierarchy" in text


# ── F.8.6: Calendar uses M partition, not DAX (commit 5de3e39) ──

class TestCalendarMPartition:
    def test_calendar_uses_m_partition(self):
        from powerbi_import.tmdl_generator import generate_calendar_table_tmdl
        tmdl = generate_calendar_table_tmdl([("T", "DateCol")])
        assert "partition Calendar = m" in tmdl
        assert "CALENDAR(" not in tmdl
        assert "#date(" in tmdl


# ── F.8.7: Calendar suppressed when date dim exists (commit c0afc84) ─

class TestCalendarSuppression:
    def test_calendar_suppressed_with_lu_date(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = _load_all()
        stats = generate_pbip(data, str(tmp_path), report_name="Reg")
        # LU_DATE exists in fixtures → no Calendar.tmdl
        cal_path = tmp_path / "Reg.SemanticModel" / "definition" / "tables" / "Calendar.tmdl"
        assert not cal_path.exists()


# ── F.8.8: --no-calendar flag (commit cfc521a) ──────────────────

class TestNoCalendarFlag:
    def test_no_calendar_flag_suppresses(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        # Minimal data with date column but no LU_DATE
        data = {
            "datasources": [{"name": "FACT_T", "id": "t1",
                             "columns": [{"name": "OrderDate", "data_type": "date"}],
                             "db_connection": {"db_type": "sql_server"}}],
            "attributes": [], "facts": [], "metrics": [], "derived_metrics": [],
            "hierarchies": [], "relationships": [], "security_filters": [],
            "freeform_sql": [], "dossiers": [], "reports": [], "prompts": [],
        }
        generate_pbip(data, str(tmp_path), report_name="Reg", no_calendar=True)
        cal = tmp_path / "Reg.SemanticModel" / "definition" / "tables" / "Calendar.tmdl"
        assert not cal.exists()


# ── F.8.9: report.json uses v2.0.0 schema (commit a76df52) ──────

class TestReportV2Schema:
    def test_report_json_v2_schema(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = _load_all()
        generate_pbip(data, str(tmp_path), report_name="Reg")
        report_json = tmp_path / "Reg.Report" / "definition" / "report.json"
        obj = json.loads(report_json.read_text("utf-8"))
        assert "2.0.0" in obj.get("$schema", "")


# ── F.8.10: Name sanitization ───────────────────────────────────

class TestNameSanitization:
    def test_needs_quoting_special_chars(self):
        from powerbi_import.tmdl_generator import _needs_quoting
        assert _needs_quoting("Sales Amount")
        assert _needs_quoting("Revenue (USD)")
        assert not _needs_quoting("Revenue")
        assert not _needs_quoting("FACT_SALES")
