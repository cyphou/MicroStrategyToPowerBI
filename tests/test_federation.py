"""Tests for v12.0 — Cross-Platform Federation.

Covers: universal_bi/schema.py, universal_bi/adapters/mstr_adapter.py,
universal_bi/adapters/tableau_adapter.py, universal_bi/cross_lineage.py.
"""

import copy
import json
import os
import tempfile
import unittest

from universal_bi.schema import (
    SCHEMA_VERSION,
    empty_schema,
    validate,
    merge_schemas,
    to_mstr_format,
)
from universal_bi.adapters.mstr_adapter import convert as mstr_convert
from universal_bi.adapters.tableau_adapter import convert as tableau_convert
from universal_bi.cross_lineage import (
    detect_shared_sources,
    detect_equivalent_dimensions,
    detect_equivalent_measures,
    deduplicate,
    build_lineage,
    lineage_summary,
)


# ===================================================================
# Fixtures
# ===================================================================

def _mstr_fixture():
    """Minimal MSTR intermediate data dict."""
    return {
        "datasources": [
            {"id": "DS01", "name": "FACT_SALES",
             "physical_table": "FACT_SALES",
             "db_connection": {"db_type": "oracle", "server": "srv",
                               "database": "DB", "schema": "S"},
             "columns": [{"name": "REVENUE", "data_type": "real"},
                         {"name": "CUST_ID", "data_type": "integer"}],
             "is_freeform_sql": False, "sql_statement": "", "type": "table"},
        ],
        "attributes": [
            {"id": "AT01", "name": "Customer", "description": "",
             "forms": [{"name": "ID", "category": "ID", "data_type": "integer",
                         "column_name": "CUST_ID", "table": "FACT_SALES"}],
             "data_type": "integer", "geographic_role": None,
             "sort_order": "ascending", "display_format": "",
             "parent_attributes": [], "child_attributes": [],
             "lookup_table": "FACT_SALES"},
        ],
        "facts": [
            {"id": "FA01", "name": "Revenue", "description": "",
             "expressions": [{"table": "FACT_SALES", "column": "REVENUE"}],
             "data_type": "real", "default_aggregation": "sum",
             "format_string": "$#,##0.00"},
        ],
        "metrics": [
            {"id": "ME01", "name": "Total Revenue", "description": "",
             "metric_type": "simple", "expression": "Sum(Revenue)",
             "aggregation": "sum", "format_string": "$#,##0.00",
             "subtotal_type": "sum", "folder_path": "\\Metrics",
             "is_smart_metric": False, "dependencies": [],
             "column_ref": {"fact_id": "FA01", "fact_name": "Revenue"}},
        ],
        "derived_metrics": [
            {"id": "DM01", "name": "Revenue Rank", "description": "",
             "metric_type": "derived",
             "expression": "Rank(Sum(Revenue), DESC)",
             "aggregation": "", "column_ref": None,
             "format_string": "#,##0", "subtotal_type": "none",
             "folder_path": "", "is_smart_metric": True,
             "dependencies": ["ME01"]},
        ],
        "relationships": [
            {"from_table": "DIM_CUSTOMER", "from_column": "CUST_ID",
             "to_table": "FACT_SALES", "to_column": "CUST_ID",
             "type": "many_to_one", "active": True,
             "cross_filter": "single", "source": "attribute_fact_join"},
        ],
        "hierarchies": [
            {"id": "HI01", "name": "Geography", "type": "user",
             "levels": [{"attribute_id": "AT01", "name": "Country", "order": 1}]},
        ],
        "security_filters": [
            {"id": "SF01", "name": "Region Filter",
             "expression": "Region In (North America)",
             "target_attributes": [{"id": "AT02", "name": "Region"}],
             "users": [], "groups": [{"id": "g1", "name": "Americas"}],
             "description": ""},
        ],
        "reports": [
            {"id": "RPT01", "name": "Sales Summary",
             "description": "", "report_type": "grid",
             "grid": {"rows": [{"id": "AT01", "name": "Customer",
                                 "type": "attribute", "forms": ["ID"]}],
                      "columns": [], "metrics_position": "columns"},
             "graph": None,
             "metrics": [{"id": "ME01", "name": "Total Revenue"}],
             "filters": [], "sorts": [], "subtotals": [],
             "page_by": [], "thresholds": [], "prompts": []},
        ],
        "dossiers": [
            {"id": "DOSS01", "name": "Dashboard",
             "description": "", "chapters": [
                 {"key": "ch01", "name": "Main", "pages": [
                     {"key": "pg01", "name": "KPI", "visualizations": [
                         {"key": "viz01", "name": "Revenue KPI",
                          "viz_type": "kpi",
                          "data": {"attributes": [],
                                   "metrics": [{"id": "ME01", "name": "Total Revenue"}]},
                          "formatting": {},
                          "thresholds": [],
                          "position": {"x": 0, "y": 0, "width": 600, "height": 350},
                          "actions": [], "info_window": None}
                     ]}
                 ]}
             ]},
        ],
        "prompts": [
            {"id": "PR01", "name": "Year", "type": "element",
             "required": True, "allow_multi_select": False,
             "default_value": "2026", "options": [],
             "pbi_type": "slicer", "attribute_name": "Year",
             "min_value": None, "max_value": None},
        ],
        "filters": [],
        "custom_groups": [
            {"id": "CG01", "name": "Tiers", "type": "custom_group",
             "elements": [{"name": "Enterprise",
                           "filter": {"expression": "Revenue > 1000000"}}]},
        ],
        "consolidations": [],
        "cubes": [],
        "freeform_sql": [
            {"id": "FF01", "name": "VW_CUSTOM",
             "sql_statement": "SELECT 1",
             "db_connection": {"db_type": "oracle"},
             "columns": [{"name": "val", "data_type": "integer"}]},
        ],
        "thresholds": [],
        "subtotals": [],
    }


def _tableau_fixture():
    """Minimal Tableau intermediate data dict."""
    return {
        "datasources": [
            {"name": "federated.1", "caption": "Sales Data",
             "connection": {"type": "PostgreSQL",
                            "details": {"server": "pg", "database": "sales"}},
             "tables": [
                 {"name": "FACT_SALES", "type": "table",
                  "columns": [
                      {"name": "REVENUE", "datatype": "real",
                       "role": "measure", "ordinal": 0},
                      {"name": "CUST_ID", "datatype": "integer",
                       "role": "dimension", "ordinal": 1},
                      {"name": "ORDER_DATE", "datatype": "date",
                       "role": "dimension", "ordinal": 2},
                  ],
                  "connection": "postgres"},
                 {"name": "DIM_PRODUCT", "type": "table",
                  "columns": [
                      {"name": "PROD_ID", "datatype": "integer",
                       "role": "dimension", "ordinal": 0},
                      {"name": "PROD_NAME", "datatype": "string",
                       "role": "dimension", "ordinal": 1},
                  ],
                  "connection": "postgres"},
             ],
             "relationships": [
                 {"type": "inner",
                  "left": {"table": "DIM_PRODUCT", "column": "PROD_ID"},
                  "right": {"table": "FACT_SALES", "column": "PROD_ID"}},
             ]},
        ],
        "calculations": [
            {"name": "[Revenue]", "caption": "Revenue",
             "formula": "SUM([REVENUE])", "class": "tableau",
             "datatype": "real", "role": "measure",
             "type": "quantitative", "description": "",
             "datasource_name": "federated.1"},
            {"name": "[Region]", "caption": "Region",
             "formula": "", "class": "tableau",
             "datatype": "string", "role": "dimension",
             "type": "nominal", "description": "",
             "datasource_name": "federated.1"},
        ],
        "worksheets": [
            {"name": "Revenue Chart", "title": "", "title_format": {},
             "chart_type": "barChart",
             "original_mark_class": "Bar",
             "fields": [
                 {"name": "ORDER_DATE", "shelf": "columns",
                  "datasource": "federated.1"},
                 {"name": "REVENUE", "shelf": "rows",
                  "datasource": "federated.1"},
                 {"name": "Region", "shelf": "color",
                  "datasource": "federated.1"},
             ],
             "filters": [], "formatting": {},
             "tooltips": [], "actions": [], "sort_orders": [],
             "mark_encoding": {}, "axes": {},
             "reference_lines": [], "annotations": [],
             "trend_lines": [], "pages_shelf": {},
             "table_calcs": [], "forecasting": [],
             "map_options": {}, "clustering": [],
             "dual_axis": {},
             "totals": {"grand_totals": [], "subtotals": []},
             "description": "", "show_hide_headers": {},
             "dynamic_title": None, "analytics_stats": None},
        ],
        "dashboards": [
            {"name": "Sales Overview", "title": "",
             "size": {"width": 1600, "height": 900},
             "objects": [
                 {"type": "worksheetReference",
                  "name": "Revenue Chart",
                  "worksheetName": "Revenue Chart",
                  "position": {"x": 0, "y": 0, "w": 800, "h": 450},
                  "layout": "tiled"},
             ],
             "filters": [], "parameters": []},
        ],
        "parameters": [
            {"name": "[Parameters].[Fiscal Year]",
             "caption": "Fiscal Year",
             "datatype": "integer", "value": "2024",
             "domain_type": "range",
             "allowable_values": [{"type": "range", "min": "2020", "max": "2030"}]},
        ],
        "filters": [],
        "hierarchies": [
            {"name": "Date Hierarchy",
             "levels": [{"name": "Year", "field": "ORDER_DATE"},
                        {"name": "Quarter", "field": "ORDER_QUARTER"}]},
        ],
        "user_filters": [
            {"name": "Row Security", "field": "Region",
             "expression": "[Region] = USERNAME()",
             "users": ["admin"]},
        ],
        "groups": [
            {"name": "Top Customers", "members": ["Acme", "Globex"]},
        ],
        "sets": [
            {"name": "High Revenue", "members": []},
        ],
        "custom_sql": [
            {"name": "Revenue View", "sql": "SELECT * FROM vw_revenue",
             "columns": [{"name": "rev", "datatype": "real"}]},
        ],
    }


# ===================================================================
# Schema tests
# ===================================================================

class TestEmptySchema(unittest.TestCase):
    def test_structure(self):
        s = empty_schema()
        self.assertEqual(s["schema_version"], SCHEMA_VERSION)
        self.assertIsInstance(s["datasources"], list)
        self.assertIsInstance(s["measures"], list)
        self.assertEqual(len(s["source_platforms"]), 0)

    def test_with_platforms(self):
        s = empty_schema(["microstrategy", "tableau"])
        self.assertEqual(s["source_platforms"], ["microstrategy", "tableau"])


class TestValidate(unittest.TestCase):
    def test_valid_empty(self):
        self.assertEqual(validate(empty_schema()), [])

    def test_bad_version(self):
        s = empty_schema()
        s["schema_version"] = "0.0.0"
        errors = validate(s)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_missing_section(self):
        s = empty_schema()
        del s["measures"]
        errors = validate(s)
        self.assertTrue(any("measures" in e for e in errors))

    def test_duplicate_datasource(self):
        s = empty_schema()
        s["datasources"] = [{"name": "A"}, {"name": "A"}]
        errors = validate(s)
        self.assertTrue(any("Duplicate" in e for e in errors))

    def test_invalid_measure_type(self):
        s = empty_schema()
        s["measures"] = [{"name": "X", "measure_type": "invalid"}]
        errors = validate(s)
        self.assertTrue(any("measure_type" in e for e in errors))


class TestMergeSchemas(unittest.TestCase):
    def test_merge_two(self):
        s1 = empty_schema(["microstrategy"])
        s1["datasources"] = [{"name": "T1", "columns": [{"name": "A"}]}]
        s1["measures"] = [{"name": "M1"}]

        s2 = empty_schema(["tableau"])
        s2["datasources"] = [{"name": "T1", "columns": [{"name": "B"}]},
                             {"name": "T2", "columns": []}]
        s2["measures"] = [{"name": "M2"}]

        merged = merge_schemas(s1, s2)
        self.assertEqual(sorted(merged["source_platforms"]),
                         ["microstrategy", "tableau"])
        # T1 merged (columns A + B), T2 added
        self.assertEqual(len(merged["datasources"]), 2)
        t1 = [d for d in merged["datasources"] if d["name"] == "T1"][0]
        self.assertEqual(len(t1["columns"]), 2)
        self.assertEqual(len(merged["measures"]), 2)

    def test_relationship_dedup(self):
        s1 = empty_schema()
        s1["relationships"] = [
            {"from_table": "A", "from_column": "id",
             "to_table": "B", "to_column": "id"}
        ]
        s2 = empty_schema()
        s2["relationships"] = [
            {"from_table": "A", "from_column": "id",
             "to_table": "B", "to_column": "id"}
        ]
        merged = merge_schemas(s1, s2)
        self.assertEqual(len(merged["relationships"]), 1)


class TestToMstrFormat(unittest.TestCase):
    def test_roundtrip(self):
        mstr = _mstr_fixture()
        schema = mstr_convert(mstr)
        result = to_mstr_format(schema)
        self.assertEqual(len(result["datasources"]), 1)
        self.assertEqual(len(result["attributes"]), 1)
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(len(result["derived_metrics"]), 1)
        self.assertEqual(len(result["relationships"]), 1)
        self.assertEqual(len(result["hierarchies"]), 1)
        self.assertEqual(len(result["security_filters"]), 1)
        self.assertEqual(len(result["prompts"]), 1)
        self.assertEqual(len(result["freeform_sql"]), 1)

    def test_pages_to_dossiers(self):
        schema = empty_schema()
        schema["pages"] = [
            {"id": "P1", "name": "Page1", "parent_name": "Report",
             "parent_type": "report", "visuals": [
                 {"id": "V1", "name": "Chart", "viz_type": "bar",
                  "fields": [{"name": "X", "role": "axis"},
                             {"name": "Y", "role": "value"}],
                  "position": {"x": 0, "y": 0, "width": 600, "height": 350},
                  "filters": [], "formatting": {}}
             ]},
        ]
        result = to_mstr_format(schema)
        self.assertEqual(len(result["dossiers"]), 1)
        self.assertEqual(len(result["dossiers"][0]["chapters"]), 1)

    def test_measure_types(self):
        schema = empty_schema()
        schema["measures"] = [
            {"name": "Fact1", "measure_type": "fact",
             "data_type": "real", "aggregation": "sum"},
            {"name": "Simple1", "measure_type": "simple",
             "expression": "Sum(X)", "aggregation": "sum"},
            {"name": "Derived1", "measure_type": "derived",
             "expression": "Rank(X)"},
        ]
        result = to_mstr_format(schema)
        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(len(result["derived_metrics"]), 1)


# ===================================================================
# MSTR Adapter tests
# ===================================================================

class TestMstrAdapter(unittest.TestCase):
    def test_convert(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(schema["schema_version"], SCHEMA_VERSION)
        self.assertIn("microstrategy", schema["source_platforms"])
        self.assertEqual(len(schema["datasources"]), 1)
        self.assertEqual(schema["datasources"][0]["source_platform"], "microstrategy")

    def test_dimensions(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["dimensions"]), 1)
        self.assertEqual(schema["dimensions"][0]["name"], "Customer")

    def test_measures(self):
        schema = mstr_convert(_mstr_fixture())
        # 1 fact + 1 simple metric + 1 derived = 3
        self.assertEqual(len(schema["measures"]), 3)
        types = {m["measure_type"] for m in schema["measures"]}
        self.assertEqual(types, {"fact", "simple", "derived"})

    def test_relationships(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["relationships"]), 1)
        self.assertEqual(schema["relationships"][0]["type"], "many_to_one")

    def test_pages_from_reports_and_dossiers(self):
        schema = mstr_convert(_mstr_fixture())
        # 1 report + 1 dossier page = 2 pages
        self.assertEqual(len(schema["pages"]), 2)

    def test_parameters(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["parameters"]), 1)
        self.assertEqual(schema["parameters"][0]["name"], "Year")

    def test_security(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["security_rules"]), 1)

    def test_hierarchies(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["hierarchies"]), 1)

    def test_custom_sql(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["custom_sql"]), 1)

    def test_custom_groups(self):
        schema = mstr_convert(_mstr_fixture())
        self.assertEqual(len(schema["custom_groups"]), 1)

    def test_empty_input(self):
        schema = mstr_convert({})
        self.assertEqual(validate(schema), [])


# ===================================================================
# Tableau Adapter tests
# ===================================================================

class TestTableauAdapter(unittest.TestCase):
    def test_convert(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertIn("tableau", schema["source_platforms"])

    def test_datasources(self):
        schema = tableau_convert(_tableau_fixture())
        # 2 tables across 1 datasource
        self.assertEqual(len(schema["datasources"]), 2)
        self.assertEqual(schema["datasources"][0]["source_platform"], "tableau")

    def test_dimensions(self):
        schema = tableau_convert(_tableau_fixture())
        # CUST_ID, ORDER_DATE from FACT_SALES + PROD_ID, PROD_NAME from DIM_PRODUCT + "Region" calc
        dim_names = {d["name"] for d in schema["dimensions"]}
        self.assertIn("CUST_ID", dim_names)
        self.assertIn("Region", dim_names)

    def test_measures(self):
        schema = tableau_convert(_tableau_fixture())
        # "Revenue" calculation (measure) + REVENUE column (fact)
        self.assertGreaterEqual(len(schema["measures"]), 2)
        calc_measures = [m for m in schema["measures"]
                         if m["measure_type"] == "calculated"]
        self.assertEqual(len(calc_measures), 1)

    def test_relationships(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertEqual(len(schema["relationships"]), 1)

    def test_worksheets_to_pages(self):
        schema = tableau_convert(_tableau_fixture())
        ws_pages = [p for p in schema["pages"]
                    if p["parent_type"] == "worksheet"]
        self.assertEqual(len(ws_pages), 1)
        self.assertEqual(ws_pages[0]["visuals"][0]["viz_type"], "bar")

    def test_dashboards_to_pages(self):
        schema = tableau_convert(_tableau_fixture())
        db_pages = [p for p in schema["pages"]
                    if p["parent_type"] == "dashboard"]
        self.assertEqual(len(db_pages), 1)

    def test_parameters(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertEqual(len(schema["parameters"]), 1)
        self.assertEqual(schema["parameters"][0]["name"], "Fiscal Year")

    def test_hierarchies(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertEqual(len(schema["hierarchies"]), 1)
        self.assertEqual(len(schema["hierarchies"][0]["levels"]), 2)

    def test_security(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertEqual(len(schema["security_rules"]), 1)

    def test_custom_groups(self):
        schema = tableau_convert(_tableau_fixture())
        # 1 group + 1 set
        self.assertEqual(len(schema["custom_groups"]), 2)

    def test_custom_sql(self):
        schema = tableau_convert(_tableau_fixture())
        self.assertEqual(len(schema["custom_sql"]), 1)

    def test_empty_input(self):
        schema = tableau_convert({})
        self.assertEqual(validate(schema), [])


# ===================================================================
# Cross-Lineage tests
# ===================================================================

class TestDetectSharedSources(unittest.TestCase):
    def test_shared_table(self):
        """Shared sources need source_platform diversity within merged datasources."""
        schema = empty_schema(["microstrategy", "tableau"])
        # Simulate a pre-dedup merge with two datasources with the same name
        # but different source_platform tags
        schema["datasources"] = [
            {"name": "FACT_SALES", "source_platform": "microstrategy",
             "columns": [{"name": "REVENUE"}]},
            {"name": "FACT_SALES", "source_platform": "tableau",
             "columns": [{"name": "REVENUE"}]},
        ]
        shared = detect_shared_sources(schema)
        names = {s["name"].lower() for s in shared}
        self.assertIn("fact_sales", names)

    def test_no_shared(self):
        s1 = empty_schema(["a"])
        s1["datasources"] = [{"name": "X", "source_platform": "a", "columns": []}]
        s2 = empty_schema(["b"])
        s2["datasources"] = [{"name": "Y", "source_platform": "b", "columns": []}]
        merged = merge_schemas(s1, s2)
        self.assertEqual(detect_shared_sources(merged), [])


class TestDetectEquivalentDimensions(unittest.TestCase):
    def test_same_name(self):
        schema = empty_schema()
        schema["dimensions"] = [
            {"name": "Customer", "table": "DIM_CUSTOMER",
             "column_name": "CUST_ID", "source_platform": "microstrategy"},
            {"name": "Customer", "table": "DIM_CUSTOMER",
             "column_name": "CUST_ID", "source_platform": "tableau"},
        ]
        equivs = detect_equivalent_dimensions(schema, threshold=0.5)
        self.assertEqual(len(equivs), 1)
        self.assertGreater(equivs[0]["score"], 0.8)

    def test_no_match(self):
        schema = empty_schema()
        schema["dimensions"] = [
            {"name": "Customer", "source_platform": "a"},
            {"name": "Product", "source_platform": "b"},
        ]
        self.assertEqual(detect_equivalent_dimensions(schema), [])


class TestDetectEquivalentMeasures(unittest.TestCase):
    def test_same_name(self):
        schema = empty_schema()
        schema["measures"] = [
            {"name": "Total Revenue", "aggregation": "sum",
             "source_platform": "microstrategy"},
            {"name": "Total Revenue", "aggregation": "sum",
             "source_platform": "tableau"},
        ]
        equivs = detect_equivalent_measures(schema, threshold=0.5)
        self.assertEqual(len(equivs), 1)

    def test_different_names(self):
        schema = empty_schema()
        schema["measures"] = [
            {"name": "Revenue", "source_platform": "a"},
            {"name": "Profit", "source_platform": "b"},
        ]
        self.assertEqual(detect_equivalent_measures(schema), [])


class TestDeduplicate(unittest.TestCase):
    def test_removes_duplicates(self):
        schema = empty_schema()
        schema["dimensions"] = [
            {"name": "Region", "table": "DIM_GEO", "column_name": "REGION",
             "source_platform": "microstrategy"},
            {"name": "Region", "table": "DIM_GEO", "column_name": "REGION",
             "source_platform": "tableau"},
        ]
        schema["measures"] = [
            {"name": "Revenue", "aggregation": "sum",
             "source_platform": "microstrategy"},
            {"name": "Revenue", "aggregation": "sum",
             "source_platform": "tableau"},
        ]
        result = deduplicate(schema, dim_threshold=0.5, measure_threshold=0.5)
        self.assertEqual(len(result["dimensions"]), 1)
        self.assertEqual(len(result["measures"]), 1)
        self.assertGreater(len(result["dedup_log"]), 0)

    def test_keeps_unique(self):
        schema = empty_schema()
        schema["dimensions"] = [
            {"name": "Customer", "source_platform": "a"},
            {"name": "Product", "source_platform": "b"},
        ]
        result = deduplicate(schema)
        self.assertEqual(len(result["dimensions"]), 2)


class TestBuildLineage(unittest.TestCase):
    def test_produces_graph(self):
        schema = mstr_convert(_mstr_fixture())
        lineage = build_lineage(schema)
        self.assertIn("nodes", lineage)
        self.assertIn("edges", lineage)
        self.assertGreater(len(lineage["nodes"]), 0)

    def test_node_types(self):
        schema = mstr_convert(_mstr_fixture())
        lineage = build_lineage(schema)
        types = {n["type"] for n in lineage["nodes"]}
        self.assertIn("source", types)
        self.assertIn("page", types)

    def test_cross_platform(self):
        merged = merge_schemas(
            mstr_convert(_mstr_fixture()),
            tableau_convert(_tableau_fixture()),
        )
        lineage = build_lineage(merged)
        platforms = {n["platform"] for n in lineage["nodes"] if n.get("platform")}
        self.assertIn("microstrategy", platforms)
        self.assertIn("tableau", platforms)


class TestLineageSummary(unittest.TestCase):
    def test_summary(self):
        schema = mstr_convert(_mstr_fixture())
        lineage = build_lineage(schema)
        summary = lineage_summary(lineage)
        self.assertIn("total_nodes", summary)
        self.assertIn("total_edges", summary)
        self.assertIn("by_type", summary)
        self.assertIn("by_platform", summary)


# ===================================================================
# Integration: full MSTR + Tableau federation pipeline
# ===================================================================

class TestFullFederation(unittest.TestCase):
    def test_end_to_end(self):
        """Full pipeline: extract → adapt → merge → dedup → generate MSTR format."""
        mstr_schema = mstr_convert(_mstr_fixture())
        tab_schema = tableau_convert(_tableau_fixture())
        merged = merge_schemas(mstr_schema, tab_schema)
        merged = deduplicate(merged, dim_threshold=0.5, measure_threshold=0.5)

        errors = validate(merged)
        self.assertEqual(errors, [])

        result = to_mstr_format(merged)
        # Should have data from both platforms
        self.assertGreater(len(result["datasources"]), 0)
        self.assertGreater(len(result["attributes"]), 0)
        self.assertGreater(len(result["metrics"]), 0)
        # Should have dossiers from pages
        self.assertGreater(len(result["dossiers"]), 0)

    def test_write_and_read_back(self):
        """Write federated data to JSON and read it back."""
        mstr_schema = mstr_convert(_mstr_fixture())
        result = to_mstr_format(mstr_schema)

        with tempfile.TemporaryDirectory() as td:
            for key, value in result.items():
                path = os.path.join(td, f"{key}.json")
                with open(path, 'w') as f:
                    json.dump(value, f)

            # Read back
            for key in result:
                path = os.path.join(td, f"{key}.json")
                self.assertTrue(os.path.exists(path))
                with open(path) as f:
                    loaded = json.load(f)
                self.assertEqual(len(loaded), len(result[key]))


if __name__ == "__main__":
    unittest.main()
