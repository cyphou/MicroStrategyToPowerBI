"""Tests for TMDL semantic model generator."""

import json
import os
import pathlib
import pytest

from powerbi_import.tmdl_generator import (
    generate_all_tmdl,
    generate_table_tmdl,
    generate_relationships_tmdl,
    generate_roles_tmdl,
    generate_calendar_table_tmdl,
    _map_data_type,
    _needs_quoting,
    _group_attributes_by_table,
    _group_facts_by_table,
    _group_hierarchies_by_table,
    _assign_metrics_to_tables,
    _extract_display_folder,
    _convert_security_expression,
)

EXPECTED_DIR = pathlib.Path(__file__).parent / "fixtures" / "expected_output"


# ── Data type mapping ────────────────────────────────────────────

@pytest.mark.parametrize("mstr_type, expected", [
    ("integer", "int64"),
    ("int", "int64"),
    ("bigInteger", "int64"),
    ("real", "double"),
    ("float", "double"),
    ("double", "double"),
    ("decimal", "decimal"),
    ("bigDecimal", "decimal"),
    ("nVarChar", "string"),
    ("varchar", "string"),
    ("char", "string"),
    ("date", "dateTime"),
    ("dateTime", "dateTime"),
    ("timestamp", "dateTime"),
    ("boolean", "boolean"),
    ("binary", "binary"),
    ("unknown_type", "string"),  # fallback
])
def test_map_data_type(mstr_type, expected):
    assert _map_data_type(mstr_type) == expected


# ── Name quoting ─────────────────────────────────────────────────

@pytest.mark.parametrize("name, should_quote", [
    ("CUSTOMER_ID", False),
    ("Customer Name", True),
    ("simple", False),
    ("with-dash", True),
    ("with/slash", True),
    ("with(paren)", True),
    ("ABC123", False),
])
def test_needs_quoting(name, should_quote):
    assert _needs_quoting(name) == should_quote


# ── Display folder extraction ────────────────────────────────────

@pytest.mark.parametrize("path, expected", [
    ("\\Public Objects\\Metrics\\Sales Metrics", "Sales Metrics"),
    ("\\Public Objects\\Metrics\\Customer Metrics", "Customer Metrics"),
    ("\\Public Objects\\Metrics\\Derived Metrics", "Derived Metrics"),
    ("", ""),
    ("\\Public Objects\\Metrics", "Metrics"),
])
def test_extract_display_folder(path, expected):
    assert _extract_display_folder(path) == expected


# ── Attribute grouping ───────────────────────────────────────────

def test_group_attributes_by_table(intermediate_attributes):
    by_table = _group_attributes_by_table(intermediate_attributes)
    assert "LU_CUSTOMER" in by_table
    assert "LU_PRODUCT" in by_table
    assert "LU_DATE" in by_table
    # Customer, Customer City, Customer Region all on LU_CUSTOMER
    assert len(by_table["LU_CUSTOMER"]) == 3


def test_group_facts_by_table(intermediate_facts):
    by_table = _group_facts_by_table(intermediate_facts)
    assert "FACT_SALES" in by_table
    assert "FACT_INVENTORY" in by_table
    # Revenue, Cost, Quantity, Discount on FACT_SALES
    assert len(by_table["FACT_SALES"]) == 4


# ── Hierarchy grouping ──────────────────────────────────────────

def test_group_hierarchies_by_table(intermediate_hierarchies, intermediate_attributes):
    attr_by_id = {a["id"]: a for a in intermediate_attributes}
    by_table = _group_hierarchies_by_table(intermediate_hierarchies, attr_by_id)
    # Geography hierarchy → LU_CUSTOMER (3 of 3 levels)
    assert "LU_CUSTOMER" in by_table
    geo_hiers = [h for h in by_table["LU_CUSTOMER"] if h[0] == "Geography"]
    assert len(geo_hiers) == 1
    # Product hierarchy → LU_PRODUCT
    assert "LU_PRODUCT" in by_table


# ── Metric assignment ────────────────────────────────────────────

def test_assign_metrics_to_tables(intermediate_metrics, intermediate_facts,
                                   intermediate_datasources):
    by_table = _assign_metrics_to_tables(
        intermediate_metrics, intermediate_facts, intermediate_datasources)
    # Most metrics reference Revenue/Cost/Quantity facts on FACT_SALES
    assert "FACT_SALES" in by_table
    assert len(by_table["FACT_SALES"]) >= 5


# ── Security expression conversion ──────────────────────────────

@pytest.mark.parametrize("expr, col, expected", [
    ("Customer Region In (Northeast, Southeast)", "REGION_ID",
     '[REGION_ID] IN {"Northeast", "Southeast"}'),
    ("Category In (Electronics, Software)", "CATEGORY_NAME",
     '[CATEGORY_NAME] IN {"Electronics", "Software"}'),
])
def test_convert_security_expression(expr, col, expected):
    assert _convert_security_expression(expr, col) == expected


# ── Table TMDL generation ────────────────────────────────────────

class TestTableTmdlGeneration:
    """Tests for individual table TMDL generation."""

    def _build_context(self, intermediate_datasources, intermediate_attributes,
                       intermediate_facts, intermediate_metrics,
                       intermediate_derived_metrics, intermediate_hierarchies):
        attr_by_id = {a["id"]: a for a in intermediate_attributes}
        attr_by_table = _group_attributes_by_table(intermediate_attributes)
        fact_by_table = _group_facts_by_table(intermediate_facts)
        hier_by_table = _group_hierarchies_by_table(
            intermediate_hierarchies, attr_by_id)
        metrics_by_table = _assign_metrics_to_tables(
            intermediate_metrics, intermediate_facts, intermediate_datasources)
        derived_by_table = _assign_metrics_to_tables(
            intermediate_derived_metrics, intermediate_facts, intermediate_datasources)
        return attr_by_id, attr_by_table, fact_by_table, hier_by_table, metrics_by_table, derived_by_table

    def test_lu_customer_table_structure(self, intermediate_datasources,
                                          intermediate_attributes,
                                          intermediate_facts,
                                          intermediate_metrics,
                                          intermediate_derived_metrics,
                                          intermediate_hierarchies):
        ctx = self._build_context(
            intermediate_datasources, intermediate_attributes,
            intermediate_facts, intermediate_metrics,
            intermediate_derived_metrics, intermediate_hierarchies)
        attr_by_id, attr_by_table, fact_by_table, hier_by_table, metrics_by_table, derived_by_table = ctx

        ds = next(d for d in intermediate_datasources if d["name"] == "LU_CUSTOMER")
        tmdl = generate_table_tmdl(
            ds, attr_by_table.get("LU_CUSTOMER", []),
            fact_by_table.get("LU_CUSTOMER", []),
            metrics_by_table.get("LU_CUSTOMER", []),
            derived_by_table.get("LU_CUSTOMER", []),
            hier_by_table.get("LU_CUSTOMER", []),
            attr_by_id)

        assert tmdl.startswith("table LU_CUSTOMER")
        assert "lineageTag:" in tmdl
        # Should have columns
        assert "column CUSTOMER_ID" in tmdl
        assert "dataType: int64" in tmdl
        assert "isHidden" in tmdl  # ID column hidden
        assert "isKey" in tmdl     # ID column is key
        # Display column from DESC form uses attribute name "Customer"
        assert "column Customer" in tmdl
        assert "dataType: string" in tmdl
        # Geographic role
        assert "dataCategory: City" in tmdl
        # Hierarchy
        assert "hierarchy Geography" in tmdl
        # Partition
        assert "partition LU_CUSTOMER = m" in tmdl
        assert "Sql.Database" in tmdl

    def test_fact_sales_has_measures(self, intermediate_datasources,
                                      intermediate_attributes,
                                      intermediate_facts,
                                      intermediate_metrics,
                                      intermediate_derived_metrics,
                                      intermediate_hierarchies):
        ctx = self._build_context(
            intermediate_datasources, intermediate_attributes,
            intermediate_facts, intermediate_metrics,
            intermediate_derived_metrics, intermediate_hierarchies)
        attr_by_id, attr_by_table, fact_by_table, hier_by_table, metrics_by_table, derived_by_table = ctx

        ds = next(d for d in intermediate_datasources if d["name"] == "FACT_SALES")
        tmdl = generate_table_tmdl(
            ds, attr_by_table.get("FACT_SALES", []),
            fact_by_table.get("FACT_SALES", []),
            metrics_by_table.get("FACT_SALES", []),
            derived_by_table.get("FACT_SALES", []),
            hier_by_table.get("FACT_SALES", []),
            attr_by_id)

        assert tmdl.startswith("table FACT_SALES")
        # All fact columns should be hidden
        assert "isHidden" in tmdl
        # Measures
        assert "measure" in tmdl
        assert "'Total Revenue'" in tmdl or "Total Revenue" in tmdl
        # Format strings
        assert "formatString:" in tmdl
        # Display folders
        assert "displayFolder:" in tmdl
        # Partition
        assert "partition FACT_SALES = m" in tmdl

    def test_fact_sales_column_count(self, intermediate_datasources,
                                      intermediate_attributes,
                                      intermediate_facts,
                                      intermediate_metrics,
                                      intermediate_derived_metrics,
                                      intermediate_hierarchies):
        ctx = self._build_context(
            intermediate_datasources, intermediate_attributes,
            intermediate_facts, intermediate_metrics,
            intermediate_derived_metrics, intermediate_hierarchies)
        attr_by_id, attr_by_table, fact_by_table, hier_by_table, metrics_by_table, derived_by_table = ctx

        ds = next(d for d in intermediate_datasources if d["name"] == "FACT_SALES")
        tmdl = generate_table_tmdl(
            ds, attr_by_table.get("FACT_SALES", []),
            fact_by_table.get("FACT_SALES", []),
            metrics_by_table.get("FACT_SALES", []),
            derived_by_table.get("FACT_SALES", []),
            hier_by_table.get("FACT_SALES", []),
            attr_by_id)

        # FACT_SALES has 9 columns in the fixture
        col_count = tmdl.count("\tcolumn ")
        assert col_count == 9


# ── Relationship TMDL generation ─────────────────────────────────

class TestRelationshipTmdl:

    def test_relationship_count(self, intermediate_relationships):
        tmdl = generate_relationships_tmdl(intermediate_relationships)
        assert tmdl.count("relationship rel_") == 5

    def test_relationship_structure(self, intermediate_relationships):
        tmdl = generate_relationships_tmdl(intermediate_relationships)
        assert "fromColumn: LU_CUSTOMER.CUSTOMER_ID" in tmdl
        assert "toColumn: FACT_SALES.CUSTOMER_ID" in tmdl
        assert "crossFilteringBehavior: singleDirection" in tmdl

    def test_relationship_names(self, intermediate_relationships):
        tmdl = generate_relationships_tmdl(intermediate_relationships)
        assert "rel_LU_CUSTOMER_FACT_SALES" in tmdl
        assert "rel_LU_PRODUCT_FACT_SALES" in tmdl
        assert "rel_LU_DATE_FACT_SALES" in tmdl
        assert "rel_LU_PRODUCT_FACT_INVENTORY" in tmdl
        assert "rel_LU_DATE_FACT_INVENTORY" in tmdl

    def test_relationships_match_expected(self, intermediate_relationships):
        tmdl = generate_relationships_tmdl(intermediate_relationships)
        expected = (EXPECTED_DIR / "relationships.tmdl").read_text(encoding='utf-8')
        assert tmdl.strip() == expected.strip()


# ── RLS Roles TMDL generation ────────────────────────────────────

class TestRolesTmdl:

    def test_role_count(self, intermediate_security_filters, intermediate_attributes):
        attr_by_id = {a["id"]: a for a in intermediate_attributes}
        tmdl = generate_roles_tmdl(intermediate_security_filters, attr_by_id)
        assert tmdl.count("role '") == 2

    def test_role_names(self, intermediate_security_filters, intermediate_attributes):
        attr_by_id = {a["id"]: a for a in intermediate_attributes}
        tmdl = generate_roles_tmdl(intermediate_security_filters, attr_by_id)
        assert "Region Sales Filter" in tmdl
        assert "Product Category Filter" in tmdl

    def test_role_table_permissions(self, intermediate_security_filters,
                                     intermediate_attributes):
        attr_by_id = {a["id"]: a for a in intermediate_attributes}
        tmdl = generate_roles_tmdl(intermediate_security_filters, attr_by_id)
        assert "tablePermission LU_CUSTOMER" in tmdl
        assert "tablePermission LU_PRODUCT" in tmdl

    def test_roles_match_expected(self, intermediate_security_filters,
                                   intermediate_attributes):
        attr_by_id = {a["id"]: a for a in intermediate_attributes}
        tmdl = generate_roles_tmdl(intermediate_security_filters, attr_by_id)
        expected = (EXPECTED_DIR / "roles.tmdl").read_text(encoding='utf-8')
        assert tmdl.strip() == expected.strip()


# ── Calendar table generation ────────────────────────────────────

class TestCalendarTable:

    def test_calendar_structure(self):
        tmdl = generate_calendar_table_tmdl([("FACT_SALES", "DATE_ID")])
        assert "table Calendar" in tmdl
        assert "column Date" in tmdl
        assert "column Year" in tmdl
        assert "column Quarter" in tmdl
        assert "column Month" in tmdl
        assert "column MonthName" in tmdl
        assert "column Day" in tmdl

    def test_calendar_hierarchy(self):
        tmdl = generate_calendar_table_tmdl([("FACT_SALES", "DATE_ID")])
        assert "hierarchy 'Date Hierarchy'" in tmdl
        assert "level Year" in tmdl
        assert "level Quarter" in tmdl
        assert "level Month" in tmdl
        assert "level Day" in tmdl

    def test_calendar_partition(self):
        tmdl = generate_calendar_table_tmdl(
            [("FACT_SALES", "DATE_ID")], start_year=2015, end_year=2025)
        assert "partition Calendar = calculated" in tmdl
        assert "CALENDAR(DATE(2015, 1, 1), DATE(2025, 12, 31))" in tmdl

    def test_calendar_default_years(self):
        tmdl = generate_calendar_table_tmdl([("FACT_SALES", "DATE_ID")])
        assert "DATE(2020, 1, 1)" in tmdl
        assert "DATE(2030, 12, 31)" in tmdl


# ── Full generation pipeline ─────────────────────────────────────

class TestGenerateAllTmdl:

    def test_generates_table_files(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        stats = generate_all_tmdl(data, str(output_dir))

        tables_dir = output_dir / "tables"
        assert tables_dir.exists()
        # 5 regular tables + 1 freeform SQL
        tmdl_files = list(tables_dir.glob("*.tmdl"))
        assert len(tmdl_files) >= 5

    def test_generates_relationships_file(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        generate_all_tmdl(data, str(output_dir))
        assert (output_dir / "relationships.tmdl").exists()

    def test_generates_roles_file(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        generate_all_tmdl(data, str(output_dir))
        assert (output_dir / "roles.tmdl").exists()

    def test_stats_accuracy(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        stats = generate_all_tmdl(data, str(output_dir))
        assert stats["tables"] >= 5
        assert stats["relationships"] == 5
        assert stats["roles"] == 2
        assert stats["measures"] > 0
        assert stats["columns"] > 0

    def test_table_file_names(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        generate_all_tmdl(data, str(output_dir))
        tables_dir = output_dir / "tables"
        names = {f.stem for f in tables_dir.glob("*.tmdl")}
        assert "LU_CUSTOMER" in names
        assert "LU_PRODUCT" in names
        assert "LU_DATE" in names
        assert "FACT_SALES" in names
        assert "FACT_INVENTORY" in names

    def test_freeform_sql_table_generated(self, all_intermediate_json, output_dir):
        data = self._load_data(all_intermediate_json)
        generate_all_tmdl(data, str(output_dir))
        tables_dir = output_dir / "tables"
        assert (tables_dir / "VW_MONTHLY_SUMMARY.tmdl").exists()
        content = (tables_dir / "VW_MONTHLY_SUMMARY.tmdl").read_text(encoding='utf-8')
        assert "Value.NativeQuery" in content

    def _load_data(self, json_dir):
        data = {}
        file_map = {
            'datasources': 'datasources.json',
            'attributes': 'attributes.json',
            'facts': 'facts.json',
            'metrics': 'metrics.json',
            'derived_metrics': 'derived_metrics.json',
            'hierarchies': 'hierarchies.json',
            'relationships': 'relationships.json',
            'security_filters': 'security_filters.json',
            'freeform_sql': 'freeform_sql.json',
        }
        for key, filename in file_map.items():
            path = json_dir / filename
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data[key] = json.load(f)
            else:
                data[key] = []
        return data


# ── Import orchestrator integration ──────────────────────────────

class TestImportOrchestrator:

    def test_import_all_produces_tmdl(self, all_intermediate_json, output_dir):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter(source_dir=str(all_intermediate_json))
        result = importer.import_all(
            report_name="TestReport",
            output_dir=str(output_dir))
        assert result
        assert result["tables"] >= 5
        # Check TMDL directory exists
        sm_dir = output_dir / "TestReport.SemanticModel" / "definition" / "tables"
        assert sm_dir.exists()
        assert len(list(sm_dir.glob("*.tmdl"))) >= 5

    def test_import_all_produces_summary(self, all_intermediate_json, output_dir):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter(source_dir=str(all_intermediate_json))
        importer.import_all(report_name="TestReport", output_dir=str(output_dir))
        summary_path = output_dir / "migration_summary.json"
        assert summary_path.exists()
        with open(summary_path) as f:
            summary = json.load(f)
        assert summary["status"] == "complete"
        assert summary["tables"] >= 5

    def test_import_all_no_data(self, tmp_path, output_dir):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        importer = PowerBIImporter(source_dir=str(empty_dir))
        result = importer.import_all(output_dir=str(output_dir))
        assert result is False

    def test_semantic_model_manifest(self, all_intermediate_json, output_dir):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter(source_dir=str(all_intermediate_json))
        importer.import_all(report_name="TestReport", output_dir=str(output_dir))
        manifest = output_dir / "TestReport.SemanticModel" / "definition.pbism"
        assert manifest.exists()
        platform = output_dir / "TestReport.SemanticModel" / ".platform"
        assert platform.exists()
