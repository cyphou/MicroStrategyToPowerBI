#!/usr/bin/env python3
"""
Generate 4 MicroStrategy intermediate-JSON example projects:
  simple/        — 1 table, 2 attrs, 2 facts, 3 metrics, 1 report
  medium/        — 3 tables, 8 attrs, 5 facts, 10 metrics, 3 reports, 1 dossier
  complex/       — 6 tables, 15 attrs, 10 facts, 25 metrics, 5 reports, 3 dossiers, RLS, prompts
  ultra_complex/ — 12 tables, 30 attrs, 20 facts, 60 metrics, 15 reports, 8 dossiers, scorecards, freeform SQL, merge scenario

Run:  python examples/generate_examples.py
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

_EMPTY = {
    "filters": [], "consolidations": [], "custom_groups": [],
    "subtotals": [], "thresholds": [],
}


def _w(directory, name, data):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _id(prefix, n):
    return f"{prefix}_{n:04d}"


# ══════════════════════════════════════════════════════════════════
#  SIMPLE — "My First Migration"
#  1 fact table, 2 attributes, 2 facts, 3 metrics, 1 grid report
# ══════════════════════════════════════════════════════════════════

def generate_simple():
    d = os.path.join(BASE, "simple")

    datasources = [{
        "id": "DS_0001", "name": "ORDERS",
        "physical_table": "ORDERS",
        "db_connection": {"db_type": "sql_server", "server": "localhost", "database": "SimpleDB", "schema": "dbo"},
        "columns": [
            {"name": "ORDER_ID", "data_type": "integer"},
            {"name": "PRODUCT_NAME", "data_type": "nVarChar"},
            {"name": "AMOUNT", "data_type": "real"},
            {"name": "QUANTITY", "data_type": "integer"},
        ],
        "is_freeform_sql": False, "sql_statement": "", "type": "table",
    }]

    attributes = [
        {"id": "ATTR_0001", "name": "Order ID", "description": "Unique order identifier",
         "forms": [{"name": "ID", "category": "ID", "data_type": "integer", "column_name": "ORDER_ID", "table": "ORDERS"}],
         "data_type": "integer", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": "ORDERS"},
        {"id": "ATTR_0002", "name": "Product Name", "description": "Name of the product sold",
         "forms": [{"name": "DESC", "category": "DESC", "data_type": "nVarChar", "column_name": "PRODUCT_NAME", "table": "ORDERS"}],
         "data_type": "nVarChar", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": "ORDERS"},
    ]

    facts = [
        {"id": "FACT_0001", "name": "Amount", "description": "Sales amount",
         "expressions": [{"table": "ORDERS", "column": "AMOUNT"}],
         "data_type": "real", "default_aggregation": "sum", "format_string": "$#,##0.00"},
        {"id": "FACT_0002", "name": "Quantity", "description": "Units sold",
         "expressions": [{"table": "ORDERS", "column": "QUANTITY"}],
         "data_type": "integer", "default_aggregation": "sum", "format_string": "#,##0"},
    ]

    metrics = [
        {"id": "MET_0001", "name": "Total Sales", "description": "Sum of Amount",
         "metric_type": "simple", "expression": "Sum(Amount)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0001", "fact_name": "Amount"},
         "format_string": "$#,##0.00", "subtotal_type": "sum",
         "folder_path": "\\Metrics", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0002", "name": "Total Quantity", "description": "Sum of Quantity",
         "metric_type": "simple", "expression": "Sum(Quantity)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0002", "fact_name": "Quantity"},
         "format_string": "#,##0", "subtotal_type": "sum",
         "folder_path": "\\Metrics", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0003", "name": "Avg Price", "description": "Average unit price",
         "metric_type": "compound", "expression": "Sum(Amount) / Sum(Quantity)",
         "aggregation": "", "column_ref": None,
         "format_string": "$#,##0.00", "subtotal_type": "none",
         "folder_path": "\\Metrics", "is_smart_metric": False,
         "dependencies": ["MET_0001", "MET_0002"]},
    ]

    reports = [{
        "id": "RPT_0001", "name": "Product Sales Summary",
        "description": "Simple grid showing sales by product",
        "report_type": "grid",
        "grid": {
            "rows": [{"id": "ATTR_0002", "name": "Product Name", "type": "attribute", "forms": ["DESC"]}],
            "columns": [], "metrics_position": "columns",
        },
        "graph": None,
        "metrics": [{"id": "MET_0001", "name": "Total Sales"},
                    {"id": "MET_0002", "name": "Total Quantity"},
                    {"id": "MET_0003", "name": "Avg Price"}],
        "filters": [], "sorts": [{"attribute": "Total Sales", "order": "descending"}],
        "subtotals": [{"type": "grand_total", "position": "bottom", "function": "sum"}],
        "page_by": [], "thresholds": [], "prompts": [],
    }]

    for name, data in [("datasources", datasources), ("attributes", attributes),
                       ("facts", facts), ("metrics", metrics), ("derived_metrics", []),
                       ("reports", reports), ("dossiers", []), ("cubes", []),
                       ("prompts", []), ("hierarchies", []), ("relationships", []),
                       ("security_filters", []), ("freeform_sql", []),
                       *((k, v) for k, v in _EMPTY.items())]:
        _w(d, name, data)
    print(f"  ✓ simple/ — 1 table, {len(metrics)} metrics, {len(reports)} report")


# ══════════════════════════════════════════════════════════════════
#  MEDIUM — "Sales Analytics"
#  3 tables (Customer, Product, Sales), 8 attrs, 5 facts, 10 metrics,
#  3 reports (grid, graph, grid+graph), 1 dossier, 1 hierarchy,
#  3 relationships
# ══════════════════════════════════════════════════════════════════

def generate_medium():
    d = os.path.join(BASE, "medium")

    datasources = [
        {"id": "DS_0001", "name": "LU_CUSTOMER", "physical_table": "LU_CUSTOMER",
         "db_connection": {"db_type": "postgresql", "server": "pg-prod.company.com", "database": "SalesDB", "schema": "public"},
         "columns": [{"name": "CUSTOMER_ID", "data_type": "integer"}, {"name": "CUSTOMER_NAME", "data_type": "nVarChar"},
                     {"name": "CITY", "data_type": "nVarChar"}, {"name": "REGION", "data_type": "nVarChar"}],
         "is_freeform_sql": False, "sql_statement": "", "type": "table"},
        {"id": "DS_0002", "name": "LU_PRODUCT", "physical_table": "LU_PRODUCT",
         "db_connection": {"db_type": "postgresql", "server": "pg-prod.company.com", "database": "SalesDB", "schema": "public"},
         "columns": [{"name": "PRODUCT_ID", "data_type": "integer"}, {"name": "PRODUCT_NAME", "data_type": "nVarChar"},
                     {"name": "CATEGORY", "data_type": "nVarChar"}, {"name": "UNIT_PRICE", "data_type": "real"}],
         "is_freeform_sql": False, "sql_statement": "", "type": "table"},
        {"id": "DS_0003", "name": "FACT_SALES", "physical_table": "FACT_SALES",
         "db_connection": {"db_type": "postgresql", "server": "pg-prod.company.com", "database": "SalesDB", "schema": "public"},
         "columns": [{"name": "SALE_ID", "data_type": "integer"}, {"name": "CUSTOMER_ID", "data_type": "integer"},
                     {"name": "PRODUCT_ID", "data_type": "integer"}, {"name": "SALE_DATE", "data_type": "date"},
                     {"name": "REVENUE", "data_type": "real"}, {"name": "COST", "data_type": "real"},
                     {"name": "QUANTITY", "data_type": "integer"}, {"name": "DISCOUNT", "data_type": "real"}],
         "is_freeform_sql": False, "sql_statement": "", "type": "table"},
    ]

    attributes = [
        {"id": "ATTR_0001", "name": "Customer", "description": "Customer dimension",
         "forms": [{"name": "ID", "category": "ID", "data_type": "integer", "column_name": "CUSTOMER_ID", "table": "LU_CUSTOMER"},
                   {"name": "DESC", "category": "DESC", "data_type": "nVarChar", "column_name": "CUSTOMER_NAME", "table": "LU_CUSTOMER"}],
         "data_type": "integer", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [{"id": "ATTR_0002", "name": "City"}], "lookup_table": "LU_CUSTOMER"},
        {"id": "ATTR_0002", "name": "City", "description": "Customer city",
         "forms": [{"name": "ID", "category": "ID", "data_type": "nVarChar", "column_name": "CITY", "table": "LU_CUSTOMER"}],
         "data_type": "nVarChar", "geographic_role": "city", "sort_order": "ascending",
         "display_format": "", "parent_attributes": [{"id": "ATTR_0003", "name": "Region"}], "child_attributes": [], "lookup_table": "LU_CUSTOMER"},
        {"id": "ATTR_0003", "name": "Region", "description": "Geographic region",
         "forms": [{"name": "ID", "category": "ID", "data_type": "nVarChar", "column_name": "REGION", "table": "LU_CUSTOMER"}],
         "data_type": "nVarChar", "geographic_role": "state_province", "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [{"id": "ATTR_0002", "name": "City"}], "lookup_table": "LU_CUSTOMER"},
        {"id": "ATTR_0004", "name": "Product", "description": "Product dimension",
         "forms": [{"name": "ID", "category": "ID", "data_type": "integer", "column_name": "PRODUCT_ID", "table": "LU_PRODUCT"},
                   {"name": "DESC", "category": "DESC", "data_type": "nVarChar", "column_name": "PRODUCT_NAME", "table": "LU_PRODUCT"}],
         "data_type": "integer", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": "LU_PRODUCT"},
        {"id": "ATTR_0005", "name": "Category", "description": "Product category",
         "forms": [{"name": "ID", "category": "ID", "data_type": "nVarChar", "column_name": "CATEGORY", "table": "LU_PRODUCT"}],
         "data_type": "nVarChar", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [{"id": "ATTR_0004", "name": "Product"}], "lookup_table": "LU_PRODUCT"},
        {"id": "ATTR_0006", "name": "Sale Date", "description": "Transaction date",
         "forms": [{"name": "ID", "category": "ID", "data_type": "date", "column_name": "SALE_DATE", "table": "FACT_SALES"}],
         "data_type": "date", "geographic_role": None, "sort_order": "ascending",
         "display_format": "yyyy-MM-dd", "parent_attributes": [], "child_attributes": [], "lookup_table": "FACT_SALES"},
        {"id": "ATTR_0007", "name": "Year", "description": "Calculated year",
         "forms": [{"name": "ID", "category": "ID", "data_type": "integer", "column_name": "SALE_DATE", "table": "FACT_SALES"}],
         "data_type": "integer", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": "FACT_SALES"},
        {"id": "ATTR_0008", "name": "Month", "description": "Calculated month",
         "forms": [{"name": "ID", "category": "ID", "data_type": "integer", "column_name": "SALE_DATE", "table": "FACT_SALES"}],
         "data_type": "integer", "geographic_role": None, "sort_order": "ascending",
         "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": "FACT_SALES"},
    ]

    facts = [
        {"id": "FACT_0001", "name": "Revenue", "description": "Sales revenue",
         "expressions": [{"table": "FACT_SALES", "column": "REVENUE"}],
         "data_type": "real", "default_aggregation": "sum", "format_string": "$#,##0.00"},
        {"id": "FACT_0002", "name": "Cost", "description": "Cost of goods sold",
         "expressions": [{"table": "FACT_SALES", "column": "COST"}],
         "data_type": "real", "default_aggregation": "sum", "format_string": "$#,##0.00"},
        {"id": "FACT_0003", "name": "Quantity", "description": "Units sold",
         "expressions": [{"table": "FACT_SALES", "column": "QUANTITY"}],
         "data_type": "integer", "default_aggregation": "sum", "format_string": "#,##0"},
        {"id": "FACT_0004", "name": "Discount", "description": "Discount given",
         "expressions": [{"table": "FACT_SALES", "column": "DISCOUNT"}],
         "data_type": "real", "default_aggregation": "sum", "format_string": "$#,##0.00"},
        {"id": "FACT_0005", "name": "Unit Price", "description": "Product unit price",
         "expressions": [{"table": "LU_PRODUCT", "column": "UNIT_PRICE"}],
         "data_type": "real", "default_aggregation": "avg", "format_string": "$#,##0.00"},
    ]

    metrics = [
        {"id": "MET_0001", "name": "Total Revenue", "description": "Sum of revenue", "metric_type": "simple",
         "expression": "Sum(Revenue)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0001", "fact_name": "Revenue"},
         "format_string": "$#,##0.00", "subtotal_type": "sum", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0002", "name": "Total Cost", "description": "Sum of cost", "metric_type": "simple",
         "expression": "Sum(Cost)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0002", "fact_name": "Cost"},
         "format_string": "$#,##0.00", "subtotal_type": "sum", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0003", "name": "Total Quantity", "description": "Sum of quantity", "metric_type": "simple",
         "expression": "Sum(Quantity)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0003", "fact_name": "Quantity"},
         "format_string": "#,##0", "subtotal_type": "sum", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0004", "name": "Total Discount", "description": "Sum of discount", "metric_type": "simple",
         "expression": "Sum(Discount)", "aggregation": "sum",
         "column_ref": {"fact_id": "FACT_0004", "fact_name": "Discount"},
         "format_string": "$#,##0.00", "subtotal_type": "sum", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0005", "name": "Profit", "description": "Revenue minus Cost", "metric_type": "compound",
         "expression": "Sum(Revenue) - Sum(Cost)", "aggregation": "", "column_ref": None,
         "format_string": "$#,##0.00", "subtotal_type": "sum", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False,
         "dependencies": ["MET_0001", "MET_0002"]},
        {"id": "MET_0006", "name": "Profit Margin", "description": "Profit/Revenue ratio", "metric_type": "compound",
         "expression": "(Sum(Revenue) - Sum(Cost)) / Sum(Revenue)", "aggregation": "", "column_ref": None,
         "format_string": "0.0%", "subtotal_type": "none", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False,
         "dependencies": ["MET_0001", "MET_0002"]},
        {"id": "MET_0007", "name": "Avg Unit Price", "description": "Average unit price", "metric_type": "simple",
         "expression": "Avg(Unit Price)", "aggregation": "avg",
         "column_ref": {"fact_id": "FACT_0005", "fact_name": "Unit Price"},
         "format_string": "$#,##0.00", "subtotal_type": "avg", "folder_path": "\\Metrics\\Product", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0008", "name": "Customer Count", "description": "Distinct customer count", "metric_type": "simple",
         "expression": "Count<Distinct=True>(Customer)", "aggregation": "distinctcount",
         "column_ref": {"fact_id": "ATTR_0001", "fact_name": "Customer"},
         "format_string": "#,##0", "subtotal_type": "count", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False, "dependencies": []},
        {"id": "MET_0009", "name": "Revenue per Customer", "description": "Revenue / Customer Count", "metric_type": "compound",
         "expression": "Sum(Revenue) / Count<Distinct=True>(Customer)", "aggregation": "", "column_ref": None,
         "format_string": "$#,##0.00", "subtotal_type": "none", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False,
         "dependencies": ["MET_0001", "MET_0008"]},
        {"id": "MET_0010", "name": "Discount Rate", "description": "Discount/Revenue ratio", "metric_type": "compound",
         "expression": "Sum(Discount) / Sum(Revenue)", "aggregation": "", "column_ref": None,
         "format_string": "0.0%", "subtotal_type": "none", "folder_path": "\\Metrics\\Sales", "is_smart_metric": False,
         "dependencies": ["MET_0004", "MET_0001"]},
    ]

    derived = [
        {"id": "DER_0001", "name": "Revenue Rank", "description": "Rank by revenue",
         "metric_type": "derived", "expression": "Rank(Sum(Revenue))", "aggregation": "", "column_ref": None,
         "format_string": "#,##0", "subtotal_type": "none", "folder_path": "\\Metrics\\Derived", "is_smart_metric": True,
         "dependencies": ["MET_0001"]},
        {"id": "DER_0002", "name": "Running Revenue", "description": "Cumulative revenue",
         "metric_type": "derived", "expression": "RunningSum(Sum(Revenue)) {~+, Month}", "aggregation": "", "column_ref": None,
         "format_string": "$#,##0.00", "subtotal_type": "none", "folder_path": "\\Metrics\\Derived", "is_smart_metric": True,
         "dependencies": ["MET_0001"]},
    ]

    reports = [
        {"id": "RPT_0001", "name": "Revenue by Region", "description": "Grid: revenue breakdown by region and city",
         "report_type": "grid",
         "grid": {"rows": [{"id": "ATTR_0003", "name": "Region", "type": "attribute", "forms": ["ID"]},
                           {"id": "ATTR_0002", "name": "City", "type": "attribute", "forms": ["ID"]}],
                  "columns": [], "metrics_position": "columns"},
         "graph": None,
         "metrics": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0005", "name": "Profit"},
                     {"id": "MET_0006", "name": "Profit Margin"}],
         "filters": [], "sorts": [{"attribute": "Total Revenue", "order": "descending"}],
         "subtotals": [{"type": "grand_total", "position": "bottom", "function": "sum"}],
         "page_by": [], "thresholds": [], "prompts": []},
        {"id": "RPT_0002", "name": "Monthly Revenue Trend", "description": "Line chart of monthly revenue",
         "report_type": "graph",
         "grid": {"rows": [{"id": "ATTR_0008", "name": "Month", "type": "attribute", "forms": ["ID"]}],
                  "columns": [], "metrics_position": "rows"},
         "graph": {"type": "line", "mstr_type": "line", "attributes_on_axis": [{"id": "ATTR_0008", "name": "Month"}],
                   "metrics_on_axis": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0002", "name": "Total Cost"}],
                   "color_by": ""},
         "metrics": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0002", "name": "Total Cost"}],
         "filters": [], "sorts": [], "subtotals": [], "page_by": [], "thresholds": [], "prompts": []},
        {"id": "RPT_0003", "name": "Product Performance", "description": "Grid + bar chart for products",
         "report_type": "grid_graph",
         "grid": {"rows": [{"id": "ATTR_0004", "name": "Product", "type": "attribute", "forms": ["DESC"]},
                           {"id": "ATTR_0005", "name": "Category", "type": "attribute", "forms": ["ID"]}],
                  "columns": [], "metrics_position": "columns"},
         "graph": {"type": "vertical_bar", "mstr_type": "vertical_bar",
                   "attributes_on_axis": [{"id": "ATTR_0005", "name": "Category"}],
                   "metrics_on_axis": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0003", "name": "Total Quantity"}],
                   "color_by": ""},
         "metrics": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0003", "name": "Total Quantity"},
                     {"id": "MET_0007", "name": "Avg Unit Price"}],
         "filters": [], "sorts": [], "subtotals": [], "page_by": [], "thresholds": [], "prompts": []},
    ]

    dossiers = [{
        "id": "DOSS_0001", "name": "Sales Overview Dashboard",
        "description": "Executive dashboard with KPIs, trends, and breakdowns",
        "chapters": [{
            "key": "ch_01", "name": "Overview",
            "pages": [{
                "key": "pg_01", "name": "Key Metrics",
                "visualizations": [
                    {"key": "viz_01", "name": "Revenue KPI", "viz_type": "kpi",
                     "data": {"attributes": [], "metrics": [{"id": "MET_0001", "name": "Total Revenue"}]},
                     "formatting": {"showTrend": True}, "thresholds": [],
                     "position": {"x": 0, "y": 0, "width": 300, "height": 180}, "actions": [], "info_window": None},
                    {"key": "viz_02", "name": "Profit KPI", "viz_type": "kpi",
                     "data": {"attributes": [], "metrics": [{"id": "MET_0005", "name": "Profit"}]},
                     "formatting": {"showTrend": True}, "thresholds": [],
                     "position": {"x": 320, "y": 0, "width": 300, "height": 180}, "actions": [], "info_window": None},
                    {"key": "viz_03", "name": "Revenue by Region", "viz_type": "vertical_bar",
                     "data": {"attributes": [{"id": "ATTR_0003", "name": "Region"}],
                              "metrics": [{"id": "MET_0001", "name": "Total Revenue"}]},
                     "formatting": {"showDataLabels": True, "showLegend": False}, "thresholds": [],
                     "position": {"x": 0, "y": 200, "width": 620, "height": 400}, "actions": [], "info_window": None},
                    {"key": "viz_04", "name": "Revenue Trend", "viz_type": "line",
                     "data": {"attributes": [{"id": "ATTR_0008", "name": "Month"}],
                              "metrics": [{"id": "MET_0001", "name": "Total Revenue"}, {"id": "MET_0002", "name": "Total Cost"}]},
                     "formatting": {"showDataLabels": False, "showLegend": True}, "thresholds": [],
                     "position": {"x": 640, "y": 200, "width": 620, "height": 400}, "actions": [], "info_window": None},
                ],
                "selectors": [], "layout": {"width": 1280, "height": 720},
            }],
        }],
    }]

    relationships = [
        {"from_table": "LU_CUSTOMER", "from_column": "CUSTOMER_ID", "to_table": "FACT_SALES", "to_column": "CUSTOMER_ID",
         "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "LU_PRODUCT", "from_column": "PRODUCT_ID", "to_table": "FACT_SALES", "to_column": "PRODUCT_ID",
         "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
    ]

    hierarchies = [
        {"id": "HIER_0001", "name": "Geography", "type": "user",
         "levels": [{"attribute_id": "ATTR_0003", "name": "Region", "order": 1},
                    {"attribute_id": "ATTR_0002", "name": "City", "order": 2},
                    {"attribute_id": "ATTR_0001", "name": "Customer", "order": 3}]},
        {"id": "HIER_0002", "name": "Product", "type": "user",
         "levels": [{"attribute_id": "ATTR_0005", "name": "Category", "order": 1},
                    {"attribute_id": "ATTR_0004", "name": "Product", "order": 2}]},
    ]

    for name, data in [("datasources", datasources), ("attributes", attributes), ("facts", facts),
                       ("metrics", metrics), ("derived_metrics", derived), ("reports", reports),
                       ("dossiers", dossiers), ("cubes", []), ("prompts", []),
                       ("hierarchies", hierarchies), ("relationships", relationships),
                       ("security_filters", []), ("freeform_sql", []),
                       *((k, v) for k, v in _EMPTY.items())]:
        _w(d, name, data)
    print(f"  ✓ medium/ — 3 tables, {len(metrics)} metrics, {len(reports)} reports, {len(dossiers)} dossier")


# ══════════════════════════════════════════════════════════════════
#  COMPLEX — "Enterprise Sales"
#  6 tables, 15 attrs, 10 facts, 25 metrics (including OLAP),
#  5 reports, 3 dossiers, RLS, prompts, thresholds, custom groups,
#  freeform SQL, scorecards
# ══════════════════════════════════════════════════════════════════

def generate_complex():
    d = os.path.join(BASE, "complex")

    datasources = [
        _ds("DS_C01", "DIM_CUSTOMER", "oracle", [("CUST_ID","integer"),("CUST_NAME","nVarChar"),("CUST_EMAIL","nVarChar"),
                                                   ("CITY","nVarChar"),("STATE","nVarChar"),("COUNTRY","nVarChar"),
                                                   ("REGION","nVarChar"),("SEGMENT","nVarChar")]),
        _ds("DS_C02", "DIM_PRODUCT", "oracle", [("PROD_ID","integer"),("PROD_NAME","nVarChar"),("CATEGORY","nVarChar"),
                                                  ("SUBCATEGORY","nVarChar"),("BRAND","nVarChar"),("UNIT_COST","real")]),
        _ds("DS_C03", "DIM_DATE", "oracle", [("DATE_KEY","date"),("DAY_NAME","nVarChar"),("MONTH_NAME","nVarChar"),
                                              ("MONTH_NUM","integer"),("QUARTER","integer"),("YEAR","integer"),("FISCAL_YEAR","integer")]),
        _ds("DS_C04", "DIM_CHANNEL", "oracle", [("CHANNEL_ID","integer"),("CHANNEL_NAME","nVarChar"),("CHANNEL_TYPE","nVarChar")]),
        _ds("DS_C05", "FACT_SALES", "oracle", [("SALE_ID","integer"),("CUST_ID","integer"),("PROD_ID","integer"),
                                                 ("DATE_KEY","date"),("CHANNEL_ID","integer"),
                                                 ("REVENUE","real"),("COST","real"),("QUANTITY","integer"),
                                                 ("DISCOUNT","real"),("TAX","real")]),
        _ds("DS_C06", "FACT_RETURNS", "oracle", [("RETURN_ID","integer"),("SALE_ID","integer"),("PROD_ID","integer"),
                                                   ("DATE_KEY","date"),("RETURN_QTY","integer"),("RETURN_AMOUNT","real")]),
    ]

    # 15 attributes
    attributes = [
        _attr("AC01", "Customer", "DIM_CUSTOMER", [("ID","integer","CUST_ID"),("DESC","nVarChar","CUST_NAME")]),
        _attr("AC02", "City", "DIM_CUSTOMER", [("ID","nVarChar","CITY")], geo="city"),
        _attr("AC03", "State", "DIM_CUSTOMER", [("ID","nVarChar","STATE")], geo="state_province"),
        _attr("AC04", "Country", "DIM_CUSTOMER", [("ID","nVarChar","COUNTRY")], geo="country"),
        _attr("AC05", "Region", "DIM_CUSTOMER", [("ID","nVarChar","REGION")]),
        _attr("AC06", "Segment", "DIM_CUSTOMER", [("ID","nVarChar","SEGMENT")]),
        _attr("AC07", "Product", "DIM_PRODUCT", [("ID","integer","PROD_ID"),("DESC","nVarChar","PROD_NAME")]),
        _attr("AC08", "Category", "DIM_PRODUCT", [("ID","nVarChar","CATEGORY")]),
        _attr("AC09", "Subcategory", "DIM_PRODUCT", [("ID","nVarChar","SUBCATEGORY")]),
        _attr("AC10", "Brand", "DIM_PRODUCT", [("ID","nVarChar","BRAND")]),
        _attr("AC11", "Date", "DIM_DATE", [("ID","date","DATE_KEY")]),
        _attr("AC12", "Month", "DIM_DATE", [("ID","integer","MONTH_NUM"),("DESC","nVarChar","MONTH_NAME")]),
        _attr("AC13", "Quarter", "DIM_DATE", [("ID","integer","QUARTER")]),
        _attr("AC14", "Year", "DIM_DATE", [("ID","integer","YEAR")]),
        _attr("AC15", "Channel", "DIM_CHANNEL", [("ID","integer","CHANNEL_ID"),("DESC","nVarChar","CHANNEL_NAME")]),
    ]

    # 10 facts
    facts = [
        _fact("FC01", "Revenue", "FACT_SALES", "REVENUE", "real", "$#,##0.00"),
        _fact("FC02", "Cost", "FACT_SALES", "COST", "real", "$#,##0.00"),
        _fact("FC03", "Quantity", "FACT_SALES", "QUANTITY", "integer", "#,##0"),
        _fact("FC04", "Discount", "FACT_SALES", "DISCOUNT", "real", "$#,##0.00"),
        _fact("FC05", "Tax", "FACT_SALES", "TAX", "real", "$#,##0.00"),
        _fact("FC06", "Return Qty", "FACT_RETURNS", "RETURN_QTY", "integer", "#,##0"),
        _fact("FC07", "Return Amount", "FACT_RETURNS", "RETURN_AMOUNT", "real", "$#,##0.00"),
        _fact("FC08", "Unit Cost", "DIM_PRODUCT", "UNIT_COST", "real", "$#,##0.00"),
        _fact("FC09", "Fiscal Year", "DIM_DATE", "FISCAL_YEAR", "integer", "#,##0"),
        _fact("FC10", "Month Num", "DIM_DATE", "MONTH_NUM", "integer", "#,##0"),
    ]

    # 15 simple + 10 compound/derived = 25 metrics
    metrics = [
        _met("MC01", "Total Revenue", "Sum(Revenue)", "sum", "FC01", "Revenue", "$#,##0.00"),
        _met("MC02", "Total Cost", "Sum(Cost)", "sum", "FC02", "Cost", "$#,##0.00"),
        _met("MC03", "Total Quantity", "Sum(Quantity)", "sum", "FC03", "Quantity", "#,##0"),
        _met("MC04", "Total Discount", "Sum(Discount)", "sum", "FC04", "Discount", "$#,##0.00"),
        _met("MC05", "Total Tax", "Sum(Tax)", "sum", "FC05", "Tax", "$#,##0.00"),
        _met("MC06", "Return Quantity", "Sum(Return Qty)", "sum", "FC06", "Return Qty", "#,##0"),
        _met("MC07", "Return Amount", "Sum(Return Amount)", "sum", "FC07", "Return Amount", "$#,##0.00"),
        _met("MC08", "Avg Unit Cost", "Avg(Unit Cost)", "avg", "FC08", "Unit Cost", "$#,##0.00"),
        _met("MC09", "Customer Count", "Count<Distinct=True>(Customer)", "distinctcount", "AC01", "Customer", "#,##0"),
        _met("MC10", "Product Count", "Count<Distinct=True>(Product)", "distinctcount", "AC07", "Product", "#,##0"),
        _met("MC11", "Profit", "Sum(Revenue) - Sum(Cost)", "", None, None, "$#,##0.00", mt="compound", deps=["MC01","MC02"]),
        _met("MC12", "Profit Margin", "(Sum(Revenue) - Sum(Cost)) / Sum(Revenue)", "", None, None, "0.0%", mt="compound", deps=["MC01","MC02"]),
        _met("MC13", "Gross Revenue", "Sum(Revenue) - Sum(Discount)", "", None, None, "$#,##0.00", mt="compound", deps=["MC01","MC04"]),
        _met("MC14", "Net Revenue", "Sum(Revenue) - Sum(Cost) - Sum(Tax)", "", None, None, "$#,##0.00", mt="compound", deps=["MC01","MC02","MC05"]),
        _met("MC15", "Return Rate", "Sum(Return Qty) / Sum(Quantity)", "", None, None, "0.0%", mt="compound", deps=["MC06","MC03"]),
        _met("MC16", "Revenue per Customer", "Sum(Revenue) / Count<Distinct=True>(Customer)", "", None, None, "$#,##0.00", mt="compound", deps=["MC01","MC09"]),
        _met("MC17", "Avg Order Value", "Sum(Revenue) / Count(SALE_ID)", "", None, None, "$#,##0.00", mt="compound"),
        _met("MC18", "Discount Rate", "Sum(Discount) / Sum(Revenue)", "", None, None, "0.0%", mt="compound", deps=["MC04","MC01"]),
    ]

    derived = [
        _der("DC01", "Revenue Rank", "Rank(Sum(Revenue), DESC) {~+, Customer}", ["MC01"]),
        _der("DC02", "Running Revenue", "RunningSum(Sum(Revenue)) {~+, Month}", ["MC01"]),
        _der("DC03", "Revenue MoM Change", "(Sum(Revenue) - Lag(Sum(Revenue), 1)) / Lag(Sum(Revenue), 1)", ["MC01"]),
        _der("DC04", "3M Moving Avg Revenue", "MovingAvg(Sum(Revenue), 3) {~+, Month}", ["MC01"]),
        _der("DC05", "Revenue YoY", "(Sum(Revenue) - Lag(Sum(Revenue), 12, Month)) / Lag(Sum(Revenue), 12, Month)", ["MC01"]),
        _der("DC06", "Profit NTile", "NTile(Sum(Revenue) - Sum(Cost), 4)", ["MC01", "MC02"]),
        _der("DC07", "Revenue Quartile", "NTile(Sum(Revenue), 4) {~+, Region}", ["MC01"]),
    ]

    reports = [
        {"id": "RPT_C01", "name": "Executive Revenue Summary", "description": "Top-level grid by region and channel",
         "report_type": "grid",
         "grid": {"rows": [{"id": "AC05", "name": "Region", "type": "attribute", "forms": ["ID"]},
                           {"id": "AC15", "name": "Channel", "type": "attribute", "forms": ["DESC"]}],
                  "columns": [], "metrics_position": "columns"},
         "graph": None,
         "metrics": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC11", "name": "Profit"},
                     {"id": "MC12", "name": "Profit Margin"}, {"id": "MC09", "name": "Customer Count"}],
         "filters": [], "sorts": [{"attribute": "Total Revenue", "order": "descending"}],
         "subtotals": [{"type": "grand_total", "position": "bottom", "function": "sum"}],
         "page_by": [], "prompts": [],
         "thresholds": [{"name": "Margin Alert", "metric_name": "Profit Margin",
                         "conditions": [{"operator": "less_than", "value": 0.15, "format": {"background_color": "#FF6B6B", "font_color": "#FFFFFF"}},
                                        {"operator": "greater_than", "value": 0.30, "format": {"background_color": "#6BCB77", "font_color": "#000000"}}]}]},
        {"id": "RPT_C02", "name": "Product Performance Matrix", "description": "Crosstab: product × quarter",
         "report_type": "grid",
         "grid": {"rows": [{"id": "AC08", "name": "Category", "type": "attribute", "forms": ["ID"]},
                           {"id": "AC07", "name": "Product", "type": "attribute", "forms": ["DESC"]}],
                  "columns": [{"id": "AC13", "name": "Quarter", "type": "attribute", "forms": ["ID"]}],
                  "metrics_position": "columns"},
         "graph": None,
         "metrics": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC03", "name": "Total Quantity"}],
         "filters": [{"type": "attribute_element_list", "attribute": "Year", "operator": "In", "values": ["2025","2026"], "is_view_filter": False}],
         "sorts": [], "subtotals": [{"type": "grand_total", "position": "bottom", "function": "sum"}],
         "page_by": [{"id": "AC14", "name": "Year"}], "thresholds": [], "prompts": []},
        {"id": "RPT_C03", "name": "Monthly Trend Analysis", "description": "Line chart with revenue and cost trends",
         "report_type": "graph",
         "grid": {"rows": [{"id": "AC12", "name": "Month", "type": "attribute", "forms": ["ID","DESC"]}], "columns": [], "metrics_position": "rows"},
         "graph": {"type": "line", "mstr_type": "line",
                   "attributes_on_axis": [{"id": "AC12", "name": "Month"}],
                   "metrics_on_axis": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC02", "name": "Total Cost"}, {"id": "MC11", "name": "Profit"}],
                   "color_by": ""},
         "metrics": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC02", "name": "Total Cost"}, {"id": "MC11", "name": "Profit"}],
         "filters": [], "sorts": [], "subtotals": [], "page_by": [], "thresholds": [], "prompts": []},
        {"id": "RPT_C04", "name": "Customer Profitability", "description": "Grid+graph: customer × profit",
         "report_type": "grid_graph",
         "grid": {"rows": [{"id": "AC01", "name": "Customer", "type": "attribute", "forms": ["ID","DESC"]}], "columns": [], "metrics_position": "columns"},
         "graph": {"type": "scatter", "mstr_type": "scatter",
                   "attributes_on_axis": [{"id": "AC01", "name": "Customer"}],
                   "metrics_on_axis": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC11", "name": "Profit"}],
                   "color_by": ""},
         "metrics": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC11", "name": "Profit"}, {"id": "MC12", "name": "Profit Margin"}],
         "filters": [], "sorts": [{"attribute": "Total Revenue", "order": "descending"}],
         "subtotals": [], "page_by": [], "thresholds": [], "prompts": []},
        {"id": "RPT_C05", "name": "Returns Analysis", "description": "Return rates by product",
         "report_type": "grid",
         "grid": {"rows": [{"id": "AC08", "name": "Category", "type": "attribute", "forms": ["ID"]},
                           {"id": "AC07", "name": "Product", "type": "attribute", "forms": ["DESC"]}], "columns": [], "metrics_position": "columns"},
         "graph": None,
         "metrics": [{"id": "MC03", "name": "Total Quantity"}, {"id": "MC06", "name": "Return Quantity"}, {"id": "MC15", "name": "Return Rate"}],
         "filters": [], "sorts": [{"attribute": "Return Rate", "order": "descending"}],
         "subtotals": [{"type": "grand_total", "position": "bottom", "function": "sum"}],
         "page_by": [], "thresholds": [{"name": "High Returns", "metric_name": "Return Rate",
                                         "conditions": [{"operator": "greater_than", "value": 0.10, "format": {"background_color": "#FF6B6B", "font_color": "#FFF"}}]}],
         "prompts": []},
    ]

    dossiers = [
        _dossier("DOSS_C01", "Executive Dashboard", [
            _page("exec_kpi", "KPI Overview", [
                _viz("ek1", "Revenue KPI", "kpi", [], ["MC01"]),
                _viz("ek2", "Profit KPI", "kpi", [], ["MC11"]),
                _viz("ek3", "Customer Count KPI", "kpi", [], ["MC09"]),
                _viz("ek4", "Revenue by Region", "vertical_bar", ["AC05"], ["MC01"]),
                _viz("ek5", "Revenue Trend", "line", ["AC12"], ["MC01","MC02"]),
            ]),
            _page("exec_detail", "Regional Detail", [
                _viz("ed1", "Region × Category", "crosstab", ["AC05","AC08"], ["MC01","MC11"]),
                _viz("ed2", "Profit Margin Map", "filled_map", ["AC03"], ["MC12"]),
            ]),
        ]),
        _dossier("DOSS_C02", "Product Analytics", [
            _page("prod_overview", "Products", [
                _viz("po1", "Category Breakdown", "pie", ["AC08"], ["MC01"]),
                _viz("po2", "Product Table", "grid", ["AC07","AC08"], ["MC01","MC03","MC15"]),
                _viz("po3", "Brand Comparison", "horizontal_bar", ["AC10"], ["MC01"]),
            ]),
        ]),
        _dossier("DOSS_C03", "Customer Insights", [
            _page("cust_seg", "Segmentation", [
                _viz("cs1", "Segment Revenue", "stacked_vertical_bar", ["AC06"], ["MC01","MC02"]),
                _viz("cs2", "Top Customers", "grid", ["AC01"], ["MC01","MC11","MC16"]),
                _viz("cs3", "Customer Scatter", "scatter", ["AC01"], ["MC01","MC11"]),
            ]),
        ]),
    ]

    relationships = [
        {"from_table": "DIM_CUSTOMER", "from_column": "CUST_ID", "to_table": "FACT_SALES", "to_column": "CUST_ID", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "DIM_PRODUCT", "from_column": "PROD_ID", "to_table": "FACT_SALES", "to_column": "PROD_ID", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "DIM_DATE", "from_column": "DATE_KEY", "to_table": "FACT_SALES", "to_column": "DATE_KEY", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "DIM_CHANNEL", "from_column": "CHANNEL_ID", "to_table": "FACT_SALES", "to_column": "CHANNEL_ID", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "DIM_PRODUCT", "from_column": "PROD_ID", "to_table": "FACT_RETURNS", "to_column": "PROD_ID", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "DIM_DATE", "from_column": "DATE_KEY", "to_table": "FACT_RETURNS", "to_column": "DATE_KEY", "type": "many_to_one", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
        {"from_table": "FACT_SALES", "from_column": "SALE_ID", "to_table": "FACT_RETURNS", "to_column": "SALE_ID", "type": "one_to_many", "active": True, "cross_filter": "single", "source": "attribute_fact_join"},
    ]

    hierarchies = [
        {"id": "HC01", "name": "Geography", "type": "user",
         "levels": [{"attribute_id": "AC04", "name": "Country", "order": 1}, {"attribute_id": "AC05", "name": "Region", "order": 2},
                    {"attribute_id": "AC03", "name": "State", "order": 3}, {"attribute_id": "AC02", "name": "City", "order": 4},
                    {"attribute_id": "AC01", "name": "Customer", "order": 5}]},
        {"id": "HC02", "name": "Product", "type": "user",
         "levels": [{"attribute_id": "AC08", "name": "Category", "order": 1}, {"attribute_id": "AC09", "name": "Subcategory", "order": 2},
                    {"attribute_id": "AC07", "name": "Product", "order": 3}]},
        {"id": "HC03", "name": "Time", "type": "system",
         "levels": [{"attribute_id": "AC14", "name": "Year", "order": 1}, {"attribute_id": "AC13", "name": "Quarter", "order": 2},
                    {"attribute_id": "AC12", "name": "Month", "order": 3}, {"attribute_id": "AC11", "name": "Date", "order": 4}]},
    ]

    security_filters = [
        {"id": "SF_C01", "name": "Region Filter - East", "description": "East region sales only",
         "expression": "Region In (East, Northeast)", "target_attributes": [{"id": "AC05", "name": "Region"}],
         "users": [{"id": "u01", "name": "EastManager"}], "groups": [{"id": "g01", "name": "East Team"}]},
        {"id": "SF_C02", "name": "Channel Filter - Online", "description": "Online channel only",
         "expression": "Channel In (Web, Mobile)", "target_attributes": [{"id": "AC15", "name": "Channel"}],
         "users": [], "groups": [{"id": "g02", "name": "Digital Team"}]},
    ]

    prompts = [
        {"id": "PRM_C01", "name": "Select Year", "type": "element", "required": True, "allow_multi_select": False,
         "default_value": "2026", "options": [{"id": "y24", "name": "2024"}, {"id": "y25", "name": "2025"}, {"id": "y26", "name": "2026"}],
         "pbi_type": "slicer", "attribute_name": "Year", "min_value": None, "max_value": None},
        {"id": "PRM_C02", "name": "Revenue Threshold", "type": "value", "required": False, "allow_multi_select": False,
         "default_value": "50000", "options": [], "pbi_type": "what_if_parameter", "attribute_name": "",
         "min_value": 0, "max_value": 10000000},
        {"id": "PRM_C03", "name": "Select Region", "type": "element", "required": False, "allow_multi_select": True,
         "default_value": "", "options": [{"id": "r1", "name": "East"}, {"id": "r2", "name": "West"}, {"id": "r3", "name": "North"}, {"id": "r4", "name": "South"}],
         "pbi_type": "slicer", "attribute_name": "Region", "min_value": None, "max_value": None},
    ]

    custom_groups = [
        {"id": "CG_C01", "name": "Customer Tier", "type": "custom_group",
         "elements": [{"name": "Platinum", "filter": {"expression": "Sum(Revenue) > 500000"}},
                      {"name": "Gold", "filter": {"expression": "Sum(Revenue) Between 100000 And 500000"}},
                      {"name": "Silver", "filter": {"expression": "Sum(Revenue) Between 10000 And 100000"}},
                      {"name": "Bronze", "filter": {"expression": "Sum(Revenue) < 10000"}}]},
    ]

    freeform_sql = [
        {"id": "FFS_C01", "name": "VW_MONTHLY_REVENUE",
         "sql_statement": "SELECT d.YEAR, d.MONTH_NUM, d.MONTH_NAME, SUM(s.REVENUE) AS MONTHLY_REV, SUM(s.COST) AS MONTHLY_COST, COUNT(DISTINCT s.CUST_ID) AS CUST_CNT FROM FACT_SALES s JOIN DIM_DATE d ON s.DATE_KEY = d.DATE_KEY GROUP BY d.YEAR, d.MONTH_NUM, d.MONTH_NAME",
         "db_connection": {"db_type": "oracle", "server": "ora-prod.company.com", "database": "SALESDB", "schema": "SALES"},
         "columns": [{"name": "YEAR", "data_type": "integer"}, {"name": "MONTH_NUM", "data_type": "integer"},
                     {"name": "MONTH_NAME", "data_type": "nVarChar"}, {"name": "MONTHLY_REV", "data_type": "real"},
                     {"name": "MONTHLY_COST", "data_type": "real"}, {"name": "CUST_CNT", "data_type": "integer"}]},
    ]

    thresholds = [
        {"report_id": "RPT_C01", "metric_name": "Profit Margin",
         "conditions": [{"operator": "less_than", "value": 0.15, "format": {"background_color": "#FF6B6B"}},
                        {"operator": "greater_than", "value": 0.30, "format": {"background_color": "#6BCB77"}}]},
        {"report_id": "RPT_C05", "metric_name": "Return Rate",
         "conditions": [{"operator": "greater_than", "value": 0.10, "format": {"background_color": "#FF6B6B"}}]},
    ]

    subtotals = [
        {"report_id": "RPT_C01", "type": "grand_total", "position": "bottom", "function": "sum"},
        {"report_id": "RPT_C02", "type": "grand_total", "position": "bottom", "function": "sum"},
        {"report_id": "RPT_C05", "type": "grand_total", "position": "bottom", "function": "sum"},
    ]

    cubes = [
        {"id": "CUBE_C01", "name": "Sales Summary Cube", "description": "Pre-aggregated sales data",
         "attributes": [{"id": "AC05", "name": "Region", "forms": ["ID"]}, {"id": "AC08", "name": "Category", "forms": ["ID"]},
                        {"id": "AC14", "name": "Year", "forms": ["ID"]}, {"id": "AC13", "name": "Quarter", "forms": ["ID"]}],
         "metrics": [{"id": "MC01", "name": "Total Revenue"}, {"id": "MC02", "name": "Total Cost"}, {"id": "MC11", "name": "Profit"}],
         "filter": {"expression": "Year >= 2024", "qualifications": []}, "refresh_policy": "scheduled"},
    ]

    scorecards = [
        {"id": "SC_C01", "name": "Sales Performance Scorecard",
         "description": "Quarterly sales targets",
         "objectives": [
             {"id": "OBJ_C01", "name": "Grow Revenue 20%", "target_value": 12000000, "current_value": 10500000,
              "status": "at_risk", "weight": 0.4, "metric_id": "MC01", "metric_name": "Total Revenue",
              "thresholds": [{"name": "On Track", "min": 11000000, "max": None, "color": "#6BCB77", "status": "on_track"},
                             {"name": "At Risk", "min": 9000000, "max": 11000000, "color": "#FFD93D", "status": "at_risk"},
                             {"name": "Behind", "min": None, "max": 9000000, "color": "#FF6B6B", "status": "behind"}],
              "children": []},
             {"id": "OBJ_C02", "name": "Margin Above 25%", "target_value": 0.25, "current_value": 0.22,
              "status": "at_risk", "weight": 0.3, "metric_id": "MC12", "metric_name": "Profit Margin",
              "thresholds": [], "children": []},
             {"id": "OBJ_C03", "name": "Reduce Returns Below 5%", "target_value": 0.05, "current_value": 0.07,
              "status": "behind", "weight": 0.3, "metric_id": "MC15", "metric_name": "Return Rate",
              "thresholds": [], "children": []},
         ],
         "perspectives": [], "kpis": []},
    ]

    for name, data in [("datasources", datasources), ("attributes", attributes), ("facts", facts),
                       ("metrics", metrics), ("derived_metrics", derived), ("reports", reports),
                       ("dossiers", dossiers), ("cubes", cubes), ("prompts", prompts),
                       ("hierarchies", hierarchies), ("relationships", relationships),
                       ("security_filters", security_filters), ("freeform_sql", freeform_sql),
                       ("filters", []), ("consolidations", []), ("custom_groups", custom_groups),
                       ("subtotals", subtotals), ("thresholds", thresholds), ("scorecards", scorecards)]:
        _w(d, name, data)
    print(f"  ✓ complex/ — {len(datasources)} tables, {len(metrics)+len(derived)} metrics, "
          f"{len(reports)} reports, {len(dossiers)} dossiers, RLS, prompts, scorecards")


# ══════════════════════════════════════════════════════════════════
#  ULTRA COMPLEX — "Global Enterprise Analytics"
#  12 tables, 30 attrs, 20 facts, 60 metrics, 15 reports,
#  8 dossiers, 2 scorecards, freeform SQL, ApplyOLAP,
#  multi-source (Oracle + SQL Server + Snowflake),
#  panel stacks, selectors, info windows
# ══════════════════════════════════════════════════════════════════

def generate_ultra_complex():
    d = os.path.join(BASE, "ultra_complex")

    # 12 tables across 3 different databases
    datasources = [
        # Oracle — core sales
        _ds("DU01", "DIM_CUSTOMER", "oracle", [("CUST_ID","integer"),("CUST_NAME","nVarChar"),("CUST_EMAIL","nVarChar"),
            ("CITY","nVarChar"),("STATE","nVarChar"),("COUNTRY","nVarChar"),("REGION","nVarChar"),
            ("SEGMENT","nVarChar"),("TIER","nVarChar"),("ACCT_MGR","nVarChar")], server="ora-prod"),
        _ds("DU02", "DIM_PRODUCT", "oracle", [("PROD_ID","integer"),("PROD_NAME","nVarChar"),("CATEGORY","nVarChar"),
            ("SUBCATEGORY","nVarChar"),("BRAND","nVarChar"),("UNIT_COST","real"),("WEIGHT_KG","real"),
            ("IS_ACTIVE","boolean")], server="ora-prod"),
        _ds("DU03", "DIM_DATE", "oracle", [("DATE_KEY","date"),("DAY_NAME","nVarChar"),("MONTH_NAME","nVarChar"),
            ("MONTH_NUM","integer"),("QUARTER","integer"),("YEAR","integer"),("FISCAL_QTR","integer"),
            ("FISCAL_YEAR","integer"),("IS_HOLIDAY","boolean")], server="ora-prod"),
        _ds("DU04", "DIM_CHANNEL", "oracle", [("CHANNEL_ID","integer"),("CHANNEL_NAME","nVarChar"),
            ("CHANNEL_TYPE","nVarChar"),("COMMISSION_PCT","real")], server="ora-prod"),
        _ds("DU05", "DIM_EMPLOYEE", "oracle", [("EMP_ID","integer"),("EMP_NAME","nVarChar"),("TITLE","nVarChar"),
            ("DEPARTMENT","nVarChar"),("HIRE_DATE","date"),("MANAGER_ID","integer")], server="ora-prod"),
        _ds("DU06", "DIM_PROMOTION", "oracle", [("PROMO_ID","integer"),("PROMO_NAME","nVarChar"),
            ("PROMO_TYPE","nVarChar"),("START_DATE","date"),("END_DATE","date"),("DISCOUNT_PCT","real")], server="ora-prod"),
        # SQL Server — transactions
        _ds("DU07", "FACT_SALES", "sql_server", [("SALE_ID","integer"),("CUST_ID","integer"),("PROD_ID","integer"),
            ("DATE_KEY","date"),("CHANNEL_ID","integer"),("EMP_ID","integer"),("PROMO_ID","integer"),
            ("REVENUE","real"),("COST","real"),("QUANTITY","integer"),("DISCOUNT","real"),("TAX","real"),
            ("SHIPPING","real"),("COMMISSION","real")], server="sql-prod"),
        _ds("DU08", "FACT_RETURNS", "sql_server", [("RETURN_ID","integer"),("SALE_ID","integer"),("PROD_ID","integer"),
            ("DATE_KEY","date"),("RETURN_QTY","integer"),("RETURN_AMT","real"),("REASON_CODE","nVarChar")], server="sql-prod"),
        _ds("DU09", "FACT_INVENTORY", "sql_server", [("INV_ID","integer"),("PROD_ID","integer"),("DATE_KEY","date"),
            ("WAREHOUSE_ID","integer"),("ON_HAND","integer"),("ON_ORDER","integer"),("REORDER_POINT","integer")], server="sql-prod"),
        # Snowflake — web analytics
        _ds("DU10", "FACT_WEB_VISITS", "snowflake", [("VISIT_ID","integer"),("CUST_ID","integer"),("DATE_KEY","date"),
            ("PAGE_VIEWS","integer"),("SESSION_DURATION_SEC","integer"),("BOUNCE","boolean"),("DEVICE_TYPE","nVarChar")],
            server="acme.snowflakecomputing.com"),
        _ds("DU11", "FACT_MARKETING_SPEND", "snowflake", [("SPEND_ID","integer"),("CHANNEL_ID","integer"),("DATE_KEY","date"),
            ("SPEND_AMOUNT","real"),("IMPRESSIONS","integer"),("CLICKS","integer"),("CONVERSIONS","integer")],
            server="acme.snowflakecomputing.com"),
        _ds("DU12", "DIM_WAREHOUSE", "sql_server", [("WAREHOUSE_ID","integer"),("WAREHOUSE_NAME","nVarChar"),
            ("CITY","nVarChar"),("COUNTRY","nVarChar"),("CAPACITY","integer")], server="sql-prod"),
    ]

    # 30 attributes
    attributes = [
        _attr("AU01","Customer","DIM_CUSTOMER",[("ID","integer","CUST_ID"),("DESC","nVarChar","CUST_NAME"),("Email","nVarChar","CUST_EMAIL")]),
        _attr("AU02","City","DIM_CUSTOMER",[("ID","nVarChar","CITY")],geo="city"),
        _attr("AU03","State","DIM_CUSTOMER",[("ID","nVarChar","STATE")],geo="state_province"),
        _attr("AU04","Country","DIM_CUSTOMER",[("ID","nVarChar","COUNTRY")],geo="country"),
        _attr("AU05","Region","DIM_CUSTOMER",[("ID","nVarChar","REGION")]),
        _attr("AU06","Segment","DIM_CUSTOMER",[("ID","nVarChar","SEGMENT")]),
        _attr("AU07","Customer Tier","DIM_CUSTOMER",[("ID","nVarChar","TIER")]),
        _attr("AU08","Account Manager","DIM_CUSTOMER",[("ID","nVarChar","ACCT_MGR")]),
        _attr("AU09","Product","DIM_PRODUCT",[("ID","integer","PROD_ID"),("DESC","nVarChar","PROD_NAME")]),
        _attr("AU10","Category","DIM_PRODUCT",[("ID","nVarChar","CATEGORY")]),
        _attr("AU11","Subcategory","DIM_PRODUCT",[("ID","nVarChar","SUBCATEGORY")]),
        _attr("AU12","Brand","DIM_PRODUCT",[("ID","nVarChar","BRAND")]),
        _attr("AU13","Date","DIM_DATE",[("ID","date","DATE_KEY")]),
        _attr("AU14","Month","DIM_DATE",[("ID","integer","MONTH_NUM"),("DESC","nVarChar","MONTH_NAME")]),
        _attr("AU15","Quarter","DIM_DATE",[("ID","integer","QUARTER")]),
        _attr("AU16","Year","DIM_DATE",[("ID","integer","YEAR")]),
        _attr("AU17","Fiscal Year","DIM_DATE",[("ID","integer","FISCAL_YEAR")]),
        _attr("AU18","Channel","DIM_CHANNEL",[("ID","integer","CHANNEL_ID"),("DESC","nVarChar","CHANNEL_NAME")]),
        _attr("AU19","Channel Type","DIM_CHANNEL",[("ID","nVarChar","CHANNEL_TYPE")]),
        _attr("AU20","Employee","DIM_EMPLOYEE",[("ID","integer","EMP_ID"),("DESC","nVarChar","EMP_NAME")]),
        _attr("AU21","Department","DIM_EMPLOYEE",[("ID","nVarChar","DEPARTMENT")]),
        _attr("AU22","Promotion","DIM_PROMOTION",[("ID","integer","PROMO_ID"),("DESC","nVarChar","PROMO_NAME")]),
        _attr("AU23","Promo Type","DIM_PROMOTION",[("ID","nVarChar","PROMO_TYPE")]),
        _attr("AU24","Warehouse","DIM_WAREHOUSE",[("ID","integer","WAREHOUSE_ID"),("DESC","nVarChar","WAREHOUSE_NAME")]),
        _attr("AU25","Device Type","FACT_WEB_VISITS",[("ID","nVarChar","DEVICE_TYPE")]),
        _attr("AU26","Return Reason","FACT_RETURNS",[("ID","nVarChar","REASON_CODE")]),
        _attr("AU27","Is Holiday","DIM_DATE",[("ID","boolean","IS_HOLIDAY")]),
        _attr("AU28","Is Active Product","DIM_PRODUCT",[("ID","boolean","IS_ACTIVE")]),
        _attr("AU29","Fiscal Quarter","DIM_DATE",[("ID","integer","FISCAL_QTR")]),
        _attr("AU30","Manager","DIM_EMPLOYEE",[("ID","integer","MANAGER_ID")]),
    ]

    # 20 facts
    facts = [
        _fact("FU01","Revenue","FACT_SALES","REVENUE","real","$#,##0.00"),
        _fact("FU02","Cost","FACT_SALES","COST","real","$#,##0.00"),
        _fact("FU03","Quantity","FACT_SALES","QUANTITY","integer","#,##0"),
        _fact("FU04","Discount","FACT_SALES","DISCOUNT","real","$#,##0.00"),
        _fact("FU05","Tax","FACT_SALES","TAX","real","$#,##0.00"),
        _fact("FU06","Shipping","FACT_SALES","SHIPPING","real","$#,##0.00"),
        _fact("FU07","Commission","FACT_SALES","COMMISSION","real","$#,##0.00"),
        _fact("FU08","Return Qty","FACT_RETURNS","RETURN_QTY","integer","#,##0"),
        _fact("FU09","Return Amount","FACT_RETURNS","RETURN_AMT","real","$#,##0.00"),
        _fact("FU10","On Hand","FACT_INVENTORY","ON_HAND","integer","#,##0"),
        _fact("FU11","On Order","FACT_INVENTORY","ON_ORDER","integer","#,##0"),
        _fact("FU12","Reorder Point","FACT_INVENTORY","REORDER_POINT","integer","#,##0"),
        _fact("FU13","Page Views","FACT_WEB_VISITS","PAGE_VIEWS","integer","#,##0"),
        _fact("FU14","Session Duration","FACT_WEB_VISITS","SESSION_DURATION_SEC","integer","#,##0"),
        _fact("FU15","Marketing Spend","FACT_MARKETING_SPEND","SPEND_AMOUNT","real","$#,##0.00"),
        _fact("FU16","Impressions","FACT_MARKETING_SPEND","IMPRESSIONS","integer","#,##0"),
        _fact("FU17","Clicks","FACT_MARKETING_SPEND","CLICKS","integer","#,##0"),
        _fact("FU18","Conversions","FACT_MARKETING_SPEND","CONVERSIONS","integer","#,##0"),
        _fact("FU19","Unit Cost","DIM_PRODUCT","UNIT_COST","real","$#,##0.00"),
        _fact("FU20","Capacity","DIM_WAREHOUSE","CAPACITY","integer","#,##0"),
    ]

    # 40 simple/compound + 20 derived = 60 metrics
    metrics = [
        _met("MU01","Total Revenue","Sum(Revenue)","sum","FU01","Revenue","$#,##0.00"),
        _met("MU02","Total Cost","Sum(Cost)","sum","FU02","Cost","$#,##0.00"),
        _met("MU03","Total Quantity","Sum(Quantity)","sum","FU03","Quantity","#,##0"),
        _met("MU04","Total Discount","Sum(Discount)","sum","FU04","Discount","$#,##0.00"),
        _met("MU05","Total Tax","Sum(Tax)","sum","FU05","Tax","$#,##0.00"),
        _met("MU06","Total Shipping","Sum(Shipping)","sum","FU06","Shipping","$#,##0.00"),
        _met("MU07","Total Commission","Sum(Commission)","sum","FU07","Commission","$#,##0.00"),
        _met("MU08","Return Quantity","Sum(Return Qty)","sum","FU08","Return Qty","#,##0"),
        _met("MU09","Return Amount","Sum(Return Amount)","sum","FU09","Return Amount","$#,##0.00"),
        _met("MU10","Inventory On Hand","Sum(On Hand)","sum","FU10","On Hand","#,##0"),
        _met("MU11","Inventory On Order","Sum(On Order)","sum","FU11","On Order","#,##0"),
        _met("MU12","Total Page Views","Sum(Page Views)","sum","FU13","Page Views","#,##0"),
        _met("MU13","Total Sessions","Count(Session Duration)","count","FU14","Session Duration","#,##0"),
        _met("MU14","Marketing Spend","Sum(Marketing Spend)","sum","FU15","Marketing Spend","$#,##0.00"),
        _met("MU15","Total Impressions","Sum(Impressions)","sum","FU16","Impressions","#,##0"),
        _met("MU16","Total Clicks","Sum(Clicks)","sum","FU17","Clicks","#,##0"),
        _met("MU17","Total Conversions","Sum(Conversions)","sum","FU18","Conversions","#,##0"),
        _met("MU18","Customer Count","Count<Distinct=True>(Customer)","distinctcount","AU01","Customer","#,##0"),
        _met("MU19","Product Count","Count<Distinct=True>(Product)","distinctcount","AU09","Product","#,##0"),
        _met("MU20","Avg Unit Cost","Avg(Unit Cost)","avg","FU19","Unit Cost","$#,##0.00"),
        # Compound
        _met("MU21","Profit","Sum(Revenue) - Sum(Cost)","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU02"]),
        _met("MU22","Profit Margin","(Sum(Revenue) - Sum(Cost)) / Sum(Revenue)","",None,None,"0.0%",mt="compound",deps=["MU01","MU02"]),
        _met("MU23","Gross Revenue","Sum(Revenue) - Sum(Discount)","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU04"]),
        _met("MU24","Net Revenue","Sum(Revenue) - Sum(Cost) - Sum(Tax) - Sum(Shipping)","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU02","MU05","MU06"]),
        _met("MU25","Return Rate","Sum(Return Qty) / Sum(Quantity)","",None,None,"0.0%",mt="compound",deps=["MU08","MU03"]),
        _met("MU26","Revenue per Customer","Sum(Revenue) / Count<Distinct=True>(Customer)","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU18"]),
        _met("MU27","Avg Order Value","Sum(Revenue) / Count(SALE_ID)","",None,None,"$#,##0.00",mt="compound"),
        _met("MU28","Discount Rate","Sum(Discount) / Sum(Revenue)","",None,None,"0.0%",mt="compound",deps=["MU04","MU01"]),
        _met("MU29","Click-Through Rate","Sum(Clicks) / Sum(Impressions)","",None,None,"0.00%",mt="compound",deps=["MU16","MU15"]),
        _met("MU30","Cost per Click","Sum(Marketing Spend) / Sum(Clicks)","",None,None,"$#,##0.00",mt="compound",deps=["MU14","MU16"]),
        _met("MU31","Cost per Conversion","Sum(Marketing Spend) / Sum(Conversions)","",None,None,"$#,##0.00",mt="compound",deps=["MU14","MU17"]),
        _met("MU32","ROAS","Sum(Revenue) / Sum(Marketing Spend)","",None,None,"#,##0.00",mt="compound",deps=["MU01","MU14"]),
        _met("MU33","Avg Session Duration","Avg(Session Duration)","avg","FU14","Session Duration","#,##0"),
        _met("MU34","Bounce Rate","Count(Bounce=True) / Count(Session Duration)","",None,None,"0.0%",mt="compound"),
        _met("MU35","Inventory Weeks of Supply","Sum(On Hand) / (Sum(Quantity) / 52)","",None,None,"#,##0.0",mt="compound",deps=["MU10","MU03"]),
        _met("MU36","Fill Rate","1 - (Sum(Return Qty) / Sum(Quantity))","",None,None,"0.0%",mt="compound",deps=["MU08","MU03"]),
        _met("MU37","Commission Rate","Sum(Commission) / Sum(Revenue)","",None,None,"0.0%",mt="compound",deps=["MU07","MU01"]),
        _met("MU38","Effective Tax Rate","Sum(Tax) / Sum(Revenue)","",None,None,"0.0%",mt="compound",deps=["MU05","MU01"]),
        _met("MU39","Revenue per Page View","Sum(Revenue) / Sum(Page Views)","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU12"]),
        _met("MU40","Customer Lifetime Value","Sum(Revenue) / Count<Distinct=True>(Customer) * 3","",None,None,"$#,##0.00",mt="compound",deps=["MU01","MU18"]),
    ]

    derived = [
        _der("DU01","Revenue Rank","Rank(Sum(Revenue), DESC) {~+, Customer}",["MU01"]),
        _der("DU02","Running Revenue","RunningSum(Sum(Revenue)) {~+, Month}",["MU01"]),
        _der("DU03","Revenue MoM %","(Sum(Revenue) - Lag(Sum(Revenue), 1)) / Lag(Sum(Revenue), 1)",["MU01"]),
        _der("DU04","3M Moving Avg","MovingAvg(Sum(Revenue), 3) {~+, Month}",["MU01"]),
        _der("DU05","Revenue YoY %","(Sum(Revenue) - Lag(Sum(Revenue), 12, Month)) / Lag(Sum(Revenue), 12, Month)",["MU01"]),
        _der("DU06","Profit Quartile","NTile(Sum(Revenue) - Sum(Cost), 4) {~+, Region}",["MU01","MU02"]),
        _der("DU07","6M Moving Sum","MovingSum(Sum(Revenue), 6) {~+, Month}",["MU01"]),
        _der("DU08","Lead Revenue","Lead(Sum(Revenue), 1) {~+, Month}",["MU01"]),
        _der("DU09","First Month Revenue","FirstInRange(Sum(Revenue), Month)",["MU01"]),
        _der("DU10","Last Month Revenue","LastInRange(Sum(Revenue), Month)",["MU01"]),
        _der("DU11","Cost Running Avg","RunningAvg(Sum(Cost)) {~+, Month}",["MU02"]),
        _der("DU12","Profit Running Sum","RunningSum(Sum(Revenue) - Sum(Cost)) {~+, Month}",["MU01","MU02"]),
        _der("DU13","Rank by Profit","Rank(Sum(Revenue) - Sum(Cost), DESC, DENSE) {~+, Customer}",["MU01","MU02"]),
        _der("DU14","Revenue Band","Band(Sum(Revenue), 0, 1000000, 100000)",["MU01"]),
        _der("DU15","ApplyOLAP RowNum",'ApplyOLAP("ROW_NUMBER() OVER (ORDER BY #0 DESC)", Revenue)',["MU01"]),
        _der("DU16","ApplyOLAP Rank",'ApplyOLAP("DENSE_RANK() OVER (ORDER BY #0 DESC)", Revenue)',["MU01"]),
        _der("DU17","ApplyOLAP Lag",'ApplyOLAP("LAG(#0, 1) OVER (ORDER BY #1)", Revenue, Month)',["MU01"]),
        _der("DU18","ApplyOLAP CumSum",'ApplyOLAP("SUM(#0) OVER (ORDER BY #1 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)", Revenue, Month)',["MU01"]),
        _der("DU19","Conversion Rank","Rank(Sum(Conversions), DESC) {~+, Channel}",["MU17"]),
        _der("DU20","Spend Running Sum","RunningSum(Sum(Marketing Spend)) {~+, Month}",["MU14"]),
    ]

    # 15 reports including diverse types
    reports = []
    for i, (name, desc, rtype, row_attrs, col_attrs, rpt_metrics, graph_type) in enumerate([
        ("Executive Revenue Summary","Top-line revenue by region","grid",[("AU05","Region")],[],[("MU01","Total Revenue"),("MU21","Profit"),("MU22","Profit Margin")],None),
        ("Product Performance Matrix","Products × Quarters","grid",[("AU10","Category"),("AU09","Product")],[("AU15","Quarter")],[("MU01","Total Revenue"),("MU03","Total Quantity")],None),
        ("Monthly Trend","Revenue trend by month","graph",[("AU14","Month")],[],[("MU01","Total Revenue"),("MU02","Total Cost"),("MU21","Profit")],"line"),
        ("Customer Profitability","Customer scatter","grid_graph",[("AU01","Customer")],[],[("MU01","Total Revenue"),("MU21","Profit"),("MU22","Profit Margin")],"scatter"),
        ("Returns Drill-Down","Returns by product and reason","grid",[("AU10","Category"),("AU09","Product"),("AU26","Return Reason")],[],[("MU03","Total Quantity"),("MU08","Return Quantity"),("MU25","Return Rate")],None),
        ("Channel Mix","Revenue by channel type","grid",[("AU19","Channel Type"),("AU18","Channel")],[],[("MU01","Total Revenue"),("MU07","Total Commission"),("MU37","Commission Rate")],None),
        ("Inventory Status","Warehouse inventory","grid",[("AU24","Warehouse"),("AU09","Product")],[],[("MU10","Inventory On Hand"),("MU11","Inventory On Order"),("MU35","Inventory Weeks of Supply")],None),
        ("Marketing ROI","Campaign performance","grid_graph",[("AU18","Channel")],[],[("MU14","Marketing Spend"),("MU16","Total Clicks"),("MU17","Total Conversions"),("MU32","ROAS")],"combo"),
        ("Web Analytics","Site traffic","grid",[("AU25","Device Type"),("AU14","Month")],[],[("MU12","Total Page Views"),("MU13","Total Sessions"),("MU34","Bounce Rate")],None),
        ("Employee Revenue","Revenue by employee","grid",[("AU21","Department"),("AU20","Employee")],[],[("MU01","Total Revenue"),("MU03","Total Quantity"),("MU27","Avg Order Value")],None),
        ("Promotion Impact","Promo effectiveness","grid_graph",[("AU22","Promotion"),("AU23","Promo Type")],[],[("MU01","Total Revenue"),("MU04","Total Discount"),("MU28","Discount Rate")],"vertical_bar"),
        ("Fiscal Year Comparison","FY revenue","grid",[("AU17","Fiscal Year"),("AU29","Fiscal Quarter")],[],[("MU01","Total Revenue"),("MU21","Profit"),("MU24","Net Revenue")],None),
        ("Customer Segmentation","Segment analysis","grid",[("AU06","Segment"),("AU07","Customer Tier")],[],[("MU01","Total Revenue"),("MU18","Customer Count"),("MU26","Revenue per Customer"),("MU40","Customer Lifetime Value")],None),
        ("Geographic Breakdown","Revenue by geography","grid_graph",[("AU04","Country"),("AU05","Region"),("AU03","State")],[],[("MU01","Total Revenue"),("MU21","Profit")],"filled_map"),
        ("Revenue Ranking","Top customers","grid",[("AU01","Customer")],[],[("MU01","Total Revenue"),("MU21","Profit")],None),
    ], start=1):
        rpt = {"id": f"RPT_U{i:02d}", "name": name, "description": desc, "report_type": rtype,
               "grid": {"rows": [{"id": a[0], "name": a[1], "type": "attribute", "forms": ["ID","DESC"]} for a in row_attrs],
                        "columns": [{"id": a[0], "name": a[1], "type": "attribute", "forms": ["ID"]} for a in col_attrs],
                        "metrics_position": "columns"},
               "graph": None, "metrics": [{"id": m[0], "name": m[1]} for m in rpt_metrics],
               "filters": [], "sorts": [], "subtotals": [], "page_by": [], "thresholds": [], "prompts": []}
        if graph_type:
            rpt["graph"] = {"type": graph_type, "mstr_type": graph_type,
                            "attributes_on_axis": [{"id": row_attrs[0][0], "name": row_attrs[0][1]}],
                            "metrics_on_axis": [{"id": m[0], "name": m[1]} for m in rpt_metrics[:3]],
                            "color_by": ""}
        reports.append(rpt)

    # 8 dossiers including panel stacks, selectors, info windows
    dossiers = [
        _dossier("DOSS_U01", "CEO Dashboard", [
            _page("ceo_kpi", "KPI Wall", [
                _viz("ck1","Revenue","kpi",[],["MU01"]),_viz("ck2","Profit","kpi",[],["MU21"]),
                _viz("ck3","Margin","kpi",[],["MU22"]),_viz("ck4","Customers","kpi",[],["MU18"]),
                _viz("ck5","Revenue Trend","area",["AU14"],["MU01","MU02"]),
                _viz("ck6","Region Breakdown","treemap",["AU05"],["MU01"]),
            ]),
            _page("ceo_geo", "Geographic View", [
                _viz("cg1","Revenue Map","map",["AU03"],["MU01"]),
                _viz("cg2","Region Table","grid",["AU05","AU04"],["MU01","MU21","MU22"]),
            ]),
        ]),
        _dossier("DOSS_U02", "Sales Operations", [
            _page("so_main", "Sales Pipeline", [
                _viz("so1","Channel Revenue","stacked_vertical_bar",["AU18"],["MU01","MU02"]),
                _viz("so2","Monthly Waterfall","waterfall",["AU14"],["MU01"]),
                _viz("so3","Employee Leaderboard","grid",["AU20"],["MU01","MU03","MU27"]),
            ], selectors=[
                {"key": "sel_yr", "name": "Year Selector", "selector_type": "attribute_selector",
                 "attribute": {"id": "AU16", "name": "Year"}, "items": [{"name": "2024"},{"name": "2025"},{"name": "2026"}]},
            ]),
        ]),
        _dossier("DOSS_U03", "Product Intelligence", [
            _page("pi_cat", "Category Analysis", [
                _viz("pi1","Category Revenue","pie",["AU10"],["MU01"]),
                _viz("pi2","Brand Comparison","horizontal_bar",["AU12"],["MU01"]),
                _viz("pi3","Product Grid","grid",["AU09","AU10","AU11"],["MU01","MU03","MU25"]),
            ]),
            _page("pi_inv", "Inventory Health", [
                _viz("pi4","Stock Levels","stacked_vertical_bar",["AU24"],["MU10","MU11"]),
                _viz("pi5","Weeks of Supply","gauge",[],["MU35"]),
            ]),
        ]),
        _dossier("DOSS_U04", "Customer 360", [
            _page("c360_seg", "Segments", [
                _viz("c1","Segment Breakdown","stacked_vertical_bar",["AU06"],["MU01","MU02"]),
                _viz("c2","Tier Analysis","grid",["AU07"],["MU01","MU18","MU26","MU40"]),
                _viz("c3","Customer Scatter","scatter",["AU01"],["MU01","MU21"]),
            ], panel_stacks=[
                {"name": "ViewToggle", "panels": [
                    {"name": "Chart View", "visual_keys": ["c1","c3"]},
                    {"name": "Table View", "visual_keys": ["c2"]},
                ]},
            ]),
        ]),
        _dossier("DOSS_U05", "Marketing Analytics", [
            _page("mkt_perf", "Campaign Performance", [
                _viz("m1","Spend vs Revenue","combo",["AU18"],["MU14","MU01"]),
                _viz("m2","CTR by Channel","horizontal_bar",["AU18"],["MU29"]),
                _viz("m3","ROAS Trend","line",["AU14"],["MU32"]),
                _viz("m4","Funnel","funnel",[],["MU15","MU16","MU17"]),
            ]),
        ]),
        _dossier("DOSS_U06", "Web & Digital", [
            _page("web_traffic", "Traffic Overview", [
                _viz("w1","Page Views Trend","area",["AU14"],["MU12"]),
                _viz("w2","Device Split","donutChart",["AU25"],["MU12"]),  # donutChart mapped via ring
                _viz("w3","Bounce Rate","kpi",[],["MU34"]),
            ]),
        ]),
        _dossier("DOSS_U07", "Finance Dashboard", [
            _page("fin_main", "P&L Summary", [
                _viz("f1","Revenue vs Cost","line",["AU14"],["MU01","MU02","MU21"]),
                _viz("f2","Tax & Shipping","stacked_vertical_bar",["AU15"],["MU05","MU06"]),
                _viz("f3","Net Revenue Trend","line",["AU14"],["MU24"]),
            ], info_windows=[{"viz_key": "f1", "text": "Shows monthly P&L trend. Revenue (blue), Cost (red), Profit (green)."}]),
        ]),
        _dossier("DOSS_U08", "Returns & Quality", [
            _page("ret_overview", "Returns Overview", [
                _viz("r1","Return Rate Trend","line",["AU14"],["MU25"]),
                _viz("r2","Returns by Reason","horizontal_bar",["AU26"],["MU08"]),
                _viz("r3","Top Returned Products","grid",["AU09"],["MU08","MU09","MU25"]),
            ]),
        ]),
    ]

    relationships = [
        _rel("DIM_CUSTOMER","CUST_ID","FACT_SALES","CUST_ID"), _rel("DIM_PRODUCT","PROD_ID","FACT_SALES","PROD_ID"),
        _rel("DIM_DATE","DATE_KEY","FACT_SALES","DATE_KEY"), _rel("DIM_CHANNEL","CHANNEL_ID","FACT_SALES","CHANNEL_ID"),
        _rel("DIM_EMPLOYEE","EMP_ID","FACT_SALES","EMP_ID"), _rel("DIM_PROMOTION","PROMO_ID","FACT_SALES","PROMO_ID"),
        _rel("DIM_PRODUCT","PROD_ID","FACT_RETURNS","PROD_ID"), _rel("DIM_DATE","DATE_KEY","FACT_RETURNS","DATE_KEY"),
        _rel("FACT_SALES","SALE_ID","FACT_RETURNS","SALE_ID","one_to_many"),
        _rel("DIM_PRODUCT","PROD_ID","FACT_INVENTORY","PROD_ID"), _rel("DIM_DATE","DATE_KEY","FACT_INVENTORY","DATE_KEY"),
        _rel("DIM_WAREHOUSE","WAREHOUSE_ID","FACT_INVENTORY","WAREHOUSE_ID"),
        _rel("DIM_CUSTOMER","CUST_ID","FACT_WEB_VISITS","CUST_ID"), _rel("DIM_DATE","DATE_KEY","FACT_WEB_VISITS","DATE_KEY"),
        _rel("DIM_CHANNEL","CHANNEL_ID","FACT_MARKETING_SPEND","CHANNEL_ID"), _rel("DIM_DATE","DATE_KEY","FACT_MARKETING_SPEND","DATE_KEY"),
    ]

    hierarchies = [
        {"id":"HU01","name":"Geography","type":"user","levels":[
            {"attribute_id":"AU04","name":"Country","order":1},{"attribute_id":"AU05","name":"Region","order":2},
            {"attribute_id":"AU03","name":"State","order":3},{"attribute_id":"AU02","name":"City","order":4},
            {"attribute_id":"AU01","name":"Customer","order":5}]},
        {"id":"HU02","name":"Product","type":"user","levels":[
            {"attribute_id":"AU10","name":"Category","order":1},{"attribute_id":"AU11","name":"Subcategory","order":2},
            {"attribute_id":"AU09","name":"Product","order":3}]},
        {"id":"HU03","name":"Time","type":"system","levels":[
            {"attribute_id":"AU16","name":"Year","order":1},{"attribute_id":"AU15","name":"Quarter","order":2},
            {"attribute_id":"AU14","name":"Month","order":3},{"attribute_id":"AU13","name":"Date","order":4}]},
        {"id":"HU04","name":"Organization","type":"user","levels":[
            {"attribute_id":"AU21","name":"Department","order":1},{"attribute_id":"AU20","name":"Employee","order":2}]},
    ]

    security_filters = [
        {"id":"SFU01","name":"Region Filter - Americas","expression":"Region In (North America, South America)",
         "target_attributes":[{"id":"AU05","name":"Region"}],"users":[],"groups":[{"id":"g1","name":"Americas Team"}],"description":""},
        {"id":"SFU02","name":"Region Filter - EMEA","expression":"Region In (Europe, Middle East, Africa)",
         "target_attributes":[{"id":"AU05","name":"Region"}],"users":[],"groups":[{"id":"g2","name":"EMEA Team"}],"description":""},
        {"id":"SFU03","name":"Channel Filter - Digital","expression":"Channel Type In (Web, Mobile, Social)",
         "target_attributes":[{"id":"AU19","name":"Channel Type"}],"users":[],"groups":[{"id":"g3","name":"Digital Team"}],"description":""},
    ]

    prompts = [
        {"id":"PU01","name":"Select Year","type":"element","required":True,"allow_multi_select":False,
         "default_value":"2026","options":[{"id":"y23","name":"2023"},{"id":"y24","name":"2024"},{"id":"y25","name":"2025"},{"id":"y26","name":"2026"}],
         "pbi_type":"slicer","attribute_name":"Year","min_value":None,"max_value":None},
        {"id":"PU02","name":"Select Region","type":"element","required":False,"allow_multi_select":True,
         "default_value":"","options":[{"id":"r1","name":"North America"},{"id":"r2","name":"Europe"},{"id":"r3","name":"Asia Pacific"},{"id":"r4","name":"South America"}],
         "pbi_type":"slicer","attribute_name":"Region","min_value":None,"max_value":None},
        {"id":"PU03","name":"Revenue Min","type":"value","required":False,"allow_multi_select":False,
         "default_value":"0","options":[],"pbi_type":"what_if_parameter","attribute_name":"","min_value":0,"max_value":100000000},
        {"id":"PU04","name":"Date Range","type":"date","required":True,"allow_multi_select":False,
         "default_value":"2026-01-01","options":[],"pbi_type":"date_slicer","attribute_name":"Date","min_value":"2020-01-01","max_value":"2026-12-31"},
    ]

    custom_groups = [
        {"id":"CGU01","name":"Customer Tier Groups","type":"custom_group","elements":[
            {"name":"Enterprise","filter":{"expression":"Sum(Revenue) > 1000000"}},
            {"name":"Mid-Market","filter":{"expression":"Sum(Revenue) Between 100000 And 1000000"}},
            {"name":"SMB","filter":{"expression":"Sum(Revenue) Between 10000 And 100000"}},
            {"name":"Micro","filter":{"expression":"Sum(Revenue) < 10000"}}]},
        {"id":"CGU02","name":"Product Performance","type":"custom_group","elements":[
            {"name":"Star Products","filter":{"expression":"Sum(Quantity) > 10000 And (Sum(Revenue)-Sum(Cost))/Sum(Revenue) > 0.3"}},
            {"name":"Cash Cows","filter":{"expression":"Sum(Quantity) <= 10000 And (Sum(Revenue)-Sum(Cost))/Sum(Revenue) > 0.3"}},
            {"name":"Dogs","filter":{"expression":"(Sum(Revenue)-Sum(Cost))/Sum(Revenue) < 0.1"}}]},
    ]

    freeform_sql = [
        {"id":"FFU01","name":"VW_CUSTOMER_LIFETIME",
         "sql_statement":"SELECT c.CUST_ID, c.CUST_NAME, c.REGION, c.SEGMENT, MIN(s.DATE_KEY) AS FIRST_PURCHASE, MAX(s.DATE_KEY) AS LAST_PURCHASE, COUNT(DISTINCT s.SALE_ID) AS ORDER_COUNT, SUM(s.REVENUE) AS TOTAL_REVENUE, SUM(s.REVENUE-s.COST) AS TOTAL_PROFIT FROM FACT_SALES s JOIN DIM_CUSTOMER c ON s.CUST_ID=c.CUST_ID GROUP BY c.CUST_ID,c.CUST_NAME,c.REGION,c.SEGMENT",
         "db_connection":{"db_type":"oracle","server":"ora-prod","database":"SALESDB","schema":"SALES"},
         "columns":[{"name":"CUST_ID","data_type":"integer"},{"name":"CUST_NAME","data_type":"nVarChar"},
                    {"name":"REGION","data_type":"nVarChar"},{"name":"SEGMENT","data_type":"nVarChar"},
                    {"name":"FIRST_PURCHASE","data_type":"date"},{"name":"LAST_PURCHASE","data_type":"date"},
                    {"name":"ORDER_COUNT","data_type":"integer"},{"name":"TOTAL_REVENUE","data_type":"real"},
                    {"name":"TOTAL_PROFIT","data_type":"real"}]},
        {"id":"FFU02","name":"VW_MARKETING_FUNNEL",
         "sql_statement":"SELECT c.CHANNEL_NAME, d.YEAR, d.MONTH_NUM, SUM(m.IMPRESSIONS) AS IMPRESSIONS, SUM(m.CLICKS) AS CLICKS, SUM(m.CONVERSIONS) AS CONVERSIONS, SUM(m.SPEND_AMOUNT) AS SPEND, SUM(s.REVENUE) AS ATTRIBUTED_REVENUE FROM FACT_MARKETING_SPEND m JOIN DIM_CHANNEL c ON m.CHANNEL_ID=c.CHANNEL_ID JOIN DIM_DATE d ON m.DATE_KEY=d.DATE_KEY LEFT JOIN FACT_SALES s ON s.CHANNEL_ID=m.CHANNEL_ID AND s.DATE_KEY=m.DATE_KEY GROUP BY c.CHANNEL_NAME,d.YEAR,d.MONTH_NUM",
         "db_connection":{"db_type":"snowflake","server":"acme.snowflakecomputing.com","database":"ANALYTICS_DB","schema":"PUBLIC"},
         "columns":[{"name":"CHANNEL_NAME","data_type":"nVarChar"},{"name":"YEAR","data_type":"integer"},
                    {"name":"MONTH_NUM","data_type":"integer"},{"name":"IMPRESSIONS","data_type":"integer"},
                    {"name":"CLICKS","data_type":"integer"},{"name":"CONVERSIONS","data_type":"integer"},
                    {"name":"SPEND","data_type":"real"},{"name":"ATTRIBUTED_REVENUE","data_type":"real"}]},
    ]

    scorecards = [
        {"id":"SCU01","name":"Company Performance Scorecard","description":"Overall company KPIs",
         "objectives":[
             {"id":"OBJ_U01","name":"Revenue Growth 25%","target_value":50000000,"current_value":42000000,"status":"at_risk",
              "weight":0.3,"metric_id":"MU01","metric_name":"Total Revenue",
              "thresholds":[{"name":"Ahead","min":48000000,"max":None,"color":"#6BCB77","status":"on_track"},
                           {"name":"On Track","min":40000000,"max":48000000,"color":"#FFD93D","status":"at_risk"},
                           {"name":"Behind","min":None,"max":40000000,"color":"#FF6B6B","status":"behind"}],
              "children":[
                  {"id":"OBJ_U01a","name":"AMER Revenue","target_value":25000000,"current_value":22000000,"status":"at_risk","metric_id":"MU01","metric_name":"Total Revenue"},
                  {"id":"OBJ_U01b","name":"EMEA Revenue","target_value":15000000,"current_value":12000000,"status":"behind","metric_id":"MU01","metric_name":"Total Revenue"},
                  {"id":"OBJ_U01c","name":"APAC Revenue","target_value":10000000,"current_value":8000000,"status":"at_risk","metric_id":"MU01","metric_name":"Total Revenue"},
              ]},
             {"id":"OBJ_U02","name":"Profit Margin > 30%","target_value":0.30,"current_value":0.27,"status":"at_risk",
              "weight":0.25,"metric_id":"MU22","metric_name":"Profit Margin","thresholds":[],"children":[]},
             {"id":"OBJ_U03","name":"Return Rate < 3%","target_value":0.03,"current_value":0.045,"status":"behind",
              "weight":0.15,"metric_id":"MU25","metric_name":"Return Rate","thresholds":[],"children":[]},
             {"id":"OBJ_U04","name":"Customer Count > 50K","target_value":50000,"current_value":47200,"status":"on_track",
              "weight":0.15,"metric_id":"MU18","metric_name":"Customer Count","thresholds":[],"children":[]},
             {"id":"OBJ_U05","name":"ROAS > 5x","target_value":5.0,"current_value":4.2,"status":"at_risk",
              "weight":0.15,"metric_id":"MU32","metric_name":"ROAS","thresholds":[],"children":[]},
         ],
         "perspectives":[
             {"id":"PERSP01","name":"Financial","description":"Revenue, profit, cost metrics","objective_ids":["OBJ_U01","OBJ_U02"]},
             {"id":"PERSP02","name":"Customer","description":"Customer growth and satisfaction","objective_ids":["OBJ_U04"]},
             {"id":"PERSP03","name":"Operations","description":"Returns and fulfillment","objective_ids":["OBJ_U03"]},
             {"id":"PERSP04","name":"Growth","description":"Marketing effectiveness","objective_ids":["OBJ_U05"]},
         ],
         "kpis":[
             {"id":"KPI_U01","name":"Monthly Revenue","metric_id":"MU01","target":4200000,"unit":"$","format":"$#,##0","thresholds":[]},
             {"id":"KPI_U02","name":"Monthly Profit","metric_id":"MU21","target":1200000,"unit":"$","format":"$#,##0","thresholds":[]},
             {"id":"KPI_U03","name":"NPS Score","metric_id":"","target":70,"unit":"pts","format":"#,##0","thresholds":[]},
         ]},
        {"id":"SCU02","name":"Digital Marketing Scorecard","description":"Digital channel targets",
         "objectives":[
             {"id":"OBJ_D01","name":"CTR > 3%","target_value":0.03,"current_value":0.028,"status":"at_risk",
              "weight":0.3,"metric_id":"MU29","metric_name":"Click-Through Rate","thresholds":[],"children":[]},
             {"id":"OBJ_D02","name":"CPC < $2","target_value":2.0,"current_value":2.15,"status":"behind",
              "weight":0.3,"metric_id":"MU30","metric_name":"Cost per Click","thresholds":[],"children":[]},
             {"id":"OBJ_D03","name":"Conversions > 10K/month","target_value":10000,"current_value":8700,"status":"at_risk",
              "weight":0.4,"metric_id":"MU17","metric_name":"Total Conversions","thresholds":[],"children":[]},
         ],
         "perspectives":[],"kpis":[]},
    ]

    cubes = [
        {"id":"CUBE_U01","name":"Sales Summary","description":"Pre-aggregated sales",
         "attributes":[{"id":"AU05","name":"Region","forms":["ID"]},{"id":"AU10","name":"Category","forms":["ID"]},
                       {"id":"AU16","name":"Year","forms":["ID"]},{"id":"AU15","name":"Quarter","forms":["ID"]}],
         "metrics":[{"id":"MU01","name":"Total Revenue"},{"id":"MU02","name":"Total Cost"},{"id":"MU21","name":"Profit"}],
         "filter":{"expression":"Year >= 2024","qualifications":[]},"refresh_policy":"scheduled"},
        {"id":"CUBE_U02","name":"Marketing Cube","description":"Marketing metrics cube",
         "attributes":[{"id":"AU18","name":"Channel","forms":["ID","DESC"]},{"id":"AU16","name":"Year","forms":["ID"]},
                       {"id":"AU14","name":"Month","forms":["ID","DESC"]}],
         "metrics":[{"id":"MU14","name":"Marketing Spend"},{"id":"MU16","name":"Total Clicks"},{"id":"MU17","name":"Total Conversions"}],
         "filter":{"expression":"","qualifications":[]},"refresh_policy":"on_demand"},
    ]

    thresholds = [
        {"report_id":"RPT_U01","metric_name":"Profit Margin","conditions":[
            {"operator":"less_than","value":0.15,"format":{"background_color":"#FF6B6B","font_color":"#FFF"}},
            {"operator":"greater_than","value":0.30,"format":{"background_color":"#6BCB77","font_color":"#000"}}]},
        {"report_id":"RPT_U05","metric_name":"Return Rate","conditions":[
            {"operator":"greater_than","value":0.10,"format":{"background_color":"#FF6B6B","font_color":"#FFF"}}]},
    ]

    subtotals = [{"report_id":f"RPT_U{i:02d}","type":"grand_total","position":"bottom","function":"sum"} for i in [1,2,5,6,7,10,12,13]]

    for name, data in [("datasources",datasources),("attributes",attributes),("facts",facts),
                       ("metrics",metrics),("derived_metrics",derived),("reports",reports),
                       ("dossiers",dossiers),("cubes",cubes),("prompts",prompts),
                       ("hierarchies",hierarchies),("relationships",relationships),
                       ("security_filters",security_filters),("freeform_sql",freeform_sql),
                       ("filters",[]),("consolidations",[]),("custom_groups",custom_groups),
                       ("subtotals",subtotals),("thresholds",thresholds),("scorecards",scorecards)]:
        _w(d, name, data)
    print(f"  ✓ ultra_complex/ — {len(datasources)} tables, {len(metrics)+len(derived)} metrics, "
          f"{len(reports)} reports, {len(dossiers)} dossiers, {len(scorecards)} scorecards, "
          f"{len(freeform_sql)} freeform SQL, {len(security_filters)} RLS filters")


# ── Helpers for generating data consistently ─────────────────────

def _ds(did, name, db_type, cols, server="db-prod.company.com"):
    return {"id": did, "name": name, "physical_table": name,
            "db_connection": {"db_type": db_type, "server": server, "database": "SALESDB", "schema": "dbo" if db_type == "sql_server" else "SALES"},
            "columns": [{"name": c[0], "data_type": c[1]} for c in cols],
            "is_freeform_sql": False, "sql_statement": "", "type": "table"}

def _attr(aid, name, table, forms, geo=None):
    return {"id": aid, "name": name, "description": f"{name} attribute",
            "forms": [{"name": f[0], "category": f[0], "data_type": f[1], "column_name": f[2], "table": table} for f in forms],
            "data_type": forms[0][1], "geographic_role": geo, "sort_order": "ascending",
            "display_format": "", "parent_attributes": [], "child_attributes": [], "lookup_table": table}

def _fact(fid, name, table, col, dtype, fmt):
    return {"id": fid, "name": name, "description": f"{name} fact",
            "expressions": [{"table": table, "column": col}],
            "data_type": dtype, "default_aggregation": "sum", "format_string": fmt}

def _met(mid, name, expr, agg, fref_id, fref_name, fmt, mt="simple", deps=None):
    m = {"id": mid, "name": name, "description": f"{name} metric", "metric_type": mt,
         "expression": expr, "aggregation": agg, "format_string": fmt,
         "subtotal_type": agg if mt == "simple" else "none",
         "folder_path": "\\Metrics", "is_smart_metric": False, "dependencies": deps or []}
    if fref_id and fref_name:
        m["column_ref"] = {"fact_id": fref_id, "fact_name": fref_name}
    else:
        m["column_ref"] = None
    return m

def _der(did, name, expr, deps):
    return {"id": did, "name": name, "description": f"{name} derived metric",
            "metric_type": "derived", "expression": expr, "aggregation": "", "column_ref": None,
            "format_string": "#,##0.00", "subtotal_type": "none",
            "folder_path": "\\Metrics\\Derived", "is_smart_metric": True, "dependencies": deps}

def _rel(ft, fc, tt, tc, rtype="many_to_one"):
    return {"from_table": ft, "from_column": fc, "to_table": tt, "to_column": tc,
            "type": rtype, "active": True, "cross_filter": "single", "source": "attribute_fact_join"}

def _viz(key, name, vtype, attrs, metrics, x=0, y=0, w=600, h=350):
    attr_list = [{"id": a, "name": a} for a in attrs] if attrs else []
    met_list = [{"id": m, "name": m} for m in metrics] if metrics else []
    return {"key": key, "name": name, "viz_type": vtype,
            "data": {"attributes": attr_list, "metrics": met_list},
            "formatting": {}, "thresholds": [],
            "position": {"x": x, "y": y, "width": w, "height": h},
            "actions": [], "info_window": None}

def _page(key, name, vizs, selectors=None, panel_stacks=None, info_windows=None):
    p = {"key": key, "name": name, "visualizations": vizs,
         "selectors": selectors or [], "layout": {"width": 1920, "height": 1080}}
    if panel_stacks:
        p["panel_stacks"] = panel_stacks
    if info_windows:
        for iw in info_windows:
            for v in vizs:
                if v["key"] == iw["viz_key"]:
                    v["info_window"] = {"text": iw["text"]}
    return p

def _dossier(did, name, pages):
    return {"id": did, "name": name, "description": f"{name} dossier",
            "chapters": [{"key": f"{did}_ch01", "name": "Main", "pages": pages}]}


if __name__ == "__main__":
    print("Generating MicroStrategy example projects...")
    generate_simple()
    generate_medium()
    generate_complex()
    generate_ultra_complex()
    print("\nDone! All 4 example projects generated.")
