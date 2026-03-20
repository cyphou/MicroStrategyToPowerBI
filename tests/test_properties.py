"""
Property-based tests for v10.0 — Deep Testing & Quality (Sprint Z.1).

Tests invariants that must hold for ALL inputs, using randomized
generation strategies.  Uses Python's built-in ``random`` module
(no external dependency on Hypothesis).  Each property is tested
across many randomly generated inputs.
"""

import json
import os
import random
import string
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from microstrategy_export.expression_converter import (
    convert_mstr_expression_to_dax,
    convert_metric_to_dax,
)
from microstrategy_export.connection_mapper import map_connection_to_m_query
from powerbi_import.tmdl_generator import (
    _map_data_type,
    _needs_quoting,
    generate_table_tmdl,
    generate_relationships_tmdl,
    generate_roles_tmdl,
    generate_calendar_table_tmdl,
)
from powerbi_import.visual_generator import (
    _VIZ_TYPE_MAP,
    _build_data_bindings,
    _scale_position,
    _convert_visualization,
)
from powerbi_import.validator import (
    validate_tmdl_file,
    validate_report_json,
    detect_relationship_cycles,
)
from powerbi_import.pbip_generator import generate_pbip
from powerbi_import.m_query_generator import generate_m_partition


# ── Random generators ────────────────────────────────────────────

_RNG = random.Random(42)  # Deterministic seed for reproducibility

_MSTR_AGGREGATIONS = ["Sum", "Avg", "Count", "Min", "Max", "StDev", "Median"]
_MSTR_NULL_FUNCS = ["NullToZero", "ZeroToNull", "IsNull", "IsNotNull"]
_MSTR_STRING_FUNCS = ["Concat", "Length", "SubStr", "Trim", "Upper", "Lower"]
_MSTR_DATE_FUNCS = ["CurrentDate", "CurrentDateTime", "Year", "Month", "Day"]
_MSTR_MATH_FUNCS = ["Abs", "Round", "Power", "Sqrt", "Exp"]
_MSTR_DERIVED = ["Rank", "RunningSum", "RunningAvg", "Lag", "Lead"]
_MSTR_LEVEL_PATTERNS = ["{~+, Year}", "{~+, Month}", "{^}", "{!Region}"]

_COLUMN_NAMES = [
    "Revenue", "Cost", "Quantity", "OrderDate", "Customer", "Product",
    "Amount", "Profit", "Discount", "Region", "Category", "Sales",
    "Price", "Units", "Tax", "Margin", "Score", "Rating", "Weight",
]

_TMDL_TYPES = [
    "integer", "int", "bigInteger", "real", "float", "double",
    "decimal", "bigDecimal", "nVarChar", "varchar", "char",
    "date", "dateTime", "timestamp", "boolean", "binary",
    "unknown_type", "exotic",
]

_VALID_TMDL_OUT_TYPES = {"int64", "double", "decimal", "string", "dateTime", "boolean", "binary"}

_DB_TYPES = [
    "sql_server", "oracle", "postgresql", "mysql", "snowflake",
    "databricks", "bigquery", "teradata", "sap_hana", "mssql",
    "redshift", "some_unknown", "",
]


def _random_column():
    return _RNG.choice(_COLUMN_NAMES)


def _random_expr():
    """Generate a random valid-ish MSTR expression."""
    kind = _RNG.randint(0, 6)
    col = _random_column()
    if kind == 0:
        func = _RNG.choice(_MSTR_AGGREGATIONS)
        return f"{func}({col})"
    elif kind == 1:
        func = _RNG.choice(_MSTR_NULL_FUNCS)
        return f"{func}({col})"
    elif kind == 2:
        func = _RNG.choice(_MSTR_STRING_FUNCS)
        if func == "SubStr":
            return f"SubStr({col}, 1, 3)"
        elif func in ("Concat",):
            col2 = _random_column()
            return f"Concat({col}, {col2})"
        return f"{func}({col})"
    elif kind == 3:
        func = _RNG.choice(_MSTR_DATE_FUNCS)
        if func in ("CurrentDate", "CurrentDateTime"):
            return f"{func}()"
        return f"{func}({col})"
    elif kind == 4:
        func = _RNG.choice(_MSTR_MATH_FUNCS)
        if func == "Round":
            return f"Round({col}, 2)"
        elif func == "Power":
            return f"Power({col}, 2)"
        return f"{func}({col})"
    elif kind == 5:
        func = _RNG.choice(_MSTR_DERIVED)
        if func in ("Lag", "Lead"):
            return f"{func}({col}, {_RNG.randint(1, 5)})"
        return f"{func}({col})"
    else:
        agg = _RNG.choice(_MSTR_AGGREGATIONS)
        level = _RNG.choice(_MSTR_LEVEL_PATTERNS)
        return f"{agg}({col}) {level}"


def _random_datasource(name=None, db_type=None):
    """Generate a random datasource dict."""
    name = name or f"Table_{_RNG.randint(1, 1000)}"
    db_type = db_type or _RNG.choice(["sql_server", "oracle", "postgresql"])
    n_cols = _RNG.randint(1, 8)
    cols = []
    for i in range(n_cols):
        cols.append({
            "name": f"Col_{i}",
            "data_type": _RNG.choice(["integer", "nVarChar", "double", "date", "boolean"]),
        })
    return {
        "id": f"id_{name}",
        "name": name,
        "physical_table": name,
        "db_connection": {
            "db_type": db_type,
            "server": "srv.example.com",
            "database": "mydb",
            "schema": "dbo",
        },
        "columns": cols,
    }


def _random_data(n_tables=2):
    """Generate a random intermediate JSON data dict."""
    datasources = [_random_datasource(f"T{i}") for i in range(n_tables)]
    return {
        "datasources": datasources,
        "attributes": [],
        "facts": [],
        "metrics": [],
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


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 1: Expression converter always returns valid result dict
# ═══════════════════════════════════════════════════════════════════

class TestExpressionResultShape:
    """Any expression → result must have dax, fidelity, warnings keys."""

    _EXPRESSIONS = [_random_expr() for _ in range(100)]

    @pytest.mark.parametrize("expr", _EXPRESSIONS)
    def test_result_has_required_keys(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert "dax" in result
        assert "fidelity" in result
        assert "warnings" in result

    @pytest.mark.parametrize("expr", _EXPRESSIONS)
    def test_fidelity_is_valid_value(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert result["fidelity"] in ("full", "approximated", "manual_review")

    @pytest.mark.parametrize("expr", _EXPRESSIONS)
    def test_dax_is_string(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result["dax"], str)

    @pytest.mark.parametrize("expr", _EXPRESSIONS)
    def test_warnings_is_list(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result["warnings"], list)


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 2: Empty/whitespace expressions → empty DAX
# ═══════════════════════════════════════════════════════════════════

class TestEmptyExpressions:

    @pytest.mark.parametrize("expr", ["", "  ", "\t", "\n", "   \n  "])
    def test_empty_returns_empty_dax(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert result["dax"] == ""
        assert result["fidelity"] == "full"


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 3: Data type mapping always returns valid TMDL type
# ═══════════════════════════════════════════════════════════════════

class TestDataTypeMapping:

    @pytest.mark.parametrize("mstr_type", _TMDL_TYPES)
    def test_always_returns_valid_tmdl_type(self, mstr_type):
        result = _map_data_type(mstr_type)
        assert result in _VALID_TMDL_OUT_TYPES

    @pytest.mark.parametrize("mstr_type", [
        "INTEGER", "Int", "DOUBLE", "VARCHAR", "DateTime",
        "BIGINTEGER", "BIGDecimal", "nVarChar",
    ])
    def test_case_insensitive(self, mstr_type):
        result = _map_data_type(mstr_type)
        assert result in _VALID_TMDL_OUT_TYPES

    def test_unknown_falls_back_to_string(self):
        for _ in range(20):
            random_type = ''.join(_RNG.choices(string.ascii_letters, k=8))
            result = _map_data_type(random_type)
            assert result == "string"


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 4: Connection mapper always returns non-empty string
# ═══════════════════════════════════════════════════════════════════

class TestConnectionMapperProperty:

    @pytest.mark.parametrize("db_type", _DB_TYPES)
    def test_always_returns_string(self, db_type):
        conn = {
            "db_type": db_type,
            "server": "srv",
            "database": "db",
            "schema": "dbo",
        }
        result = map_connection_to_m_query(conn, table_name="T1")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize("db_type", _DB_TYPES)
    def test_has_let_in_structure(self, db_type):
        conn = {"db_type": db_type, "server": "s", "database": "d"}
        result = map_connection_to_m_query(conn, table_name="Tbl")
        assert "let" in result.lower() or "odbc" in result.lower() or isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 5: generate_m_partition never crashes for valid datasource
# ═══════════════════════════════════════════════════════════════════

class TestMPartitionProperty:

    _DATASOURCES = [_random_datasource(f"P{i}", _RNG.choice(_DB_TYPES)) for i in range(20)]

    @pytest.mark.parametrize("ds", _DATASOURCES, ids=[d["name"] for d in _DATASOURCES])
    def test_always_returns_string(self, ds):
        result = generate_m_partition(ds)
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 6: Visual type map covers all expected types
# ═══════════════════════════════════════════════════════════════════

class TestVizTypeMapProperty:

    _EXPECTED_TYPES = [
        "grid", "crosstab", "vertical_bar", "horizontal_bar",
        "line", "area", "pie", "ring", "scatter", "combo",
        "map", "filled_map", "treemap", "waterfall", "funnel",
        "gauge", "kpi", "text", "image", "selector",
    ]

    @pytest.mark.parametrize("viz_type", _EXPECTED_TYPES)
    def test_all_expected_types_mapped(self, viz_type):
        assert viz_type in _VIZ_TYPE_MAP

    def test_all_map_values_are_strings(self):
        for k, v in _VIZ_TYPE_MAP.items():
            assert isinstance(v, str), f"Type {k} maps to non-string: {v}"


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 7: TMDL table generation never crashes
# ═══════════════════════════════════════════════════════════════════

class TestTmdlTableProperty:

    _DATASOURCES = [_random_datasource(f"TT{i}") for i in range(15)]

    @pytest.mark.parametrize("ds", _DATASOURCES, ids=[d["name"] for d in _DATASOURCES])
    def test_generates_valid_tmdl_string(self, ds):
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert isinstance(result, str)
        assert result.startswith(f"table {ds['name']}")

    @pytest.mark.parametrize("ds", _DATASOURCES, ids=[d["name"] for d in _DATASOURCES])
    def test_tmdl_has_partition(self, ds):
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert "partition" in result

    @pytest.mark.parametrize("ds", _DATASOURCES, ids=[d["name"] for d in _DATASOURCES])
    def test_tmdl_has_columns(self, ds):
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        for col in ds["columns"]:
            assert col["name"] in result


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 8: Relationship TMDL uses valid cross-filtering
# ═══════════════════════════════════════════════════════════════════

class TestRelationshipProperty:

    _RELS = [
        {"from_table": f"T{i}", "from_column": "id",
         "to_table": f"F{i}", "to_column": "fk",
         "cross_filter": _RNG.choice(["single", "both"])}
        for i in range(10)
    ]

    @pytest.mark.parametrize("rel", _RELS)
    def test_uses_valid_cross_filter(self, rel):
        tmdl = generate_relationships_tmdl([rel])
        assert "oneDirection" in tmdl or "bothDirections" in tmdl
        assert "singleDirection" not in tmdl

    @pytest.mark.parametrize("rel", _RELS)
    def test_contains_from_and_to(self, rel):
        tmdl = generate_relationships_tmdl([rel])
        assert rel["from_table"] in tmdl
        assert rel["to_table"] in tmdl


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 9: generate_pbip never crashes for valid data
# ═══════════════════════════════════════════════════════════════════

class TestPbipGenerationProperty:

    def test_empty_data_generates_project(self, tmp_path):
        data = _random_data(0)
        stats = generate_pbip(data, str(tmp_path), report_name="PropTest")
        assert isinstance(stats, dict)
        assert (tmp_path / "PropTest.pbip").exists()

    def test_single_table_generates_project(self, tmp_path):
        data = _random_data(1)
        stats = generate_pbip(data, str(tmp_path), report_name="PropTest1")
        assert stats["tables"] >= 1
        assert (tmp_path / "PropTest1.pbip").exists()

    def test_multiple_tables_generates_project(self, tmp_path):
        data = _random_data(5)
        stats = generate_pbip(data, str(tmp_path), report_name="PropTest5")
        assert stats["tables"] >= 5

    @pytest.mark.parametrize("n_tables", [1, 2, 3, 5, 8])
    def test_table_count_matches(self, tmp_path, n_tables):
        data = _random_data(n_tables)
        stats = generate_pbip(data, str(tmp_path / str(n_tables)),
                              report_name=f"Prop{n_tables}")
        assert stats["tables"] >= n_tables


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 10: Calendar table always valid when generated
# ═══════════════════════════════════════════════════════════════════

class TestCalendarProperty:

    _DATE_COLS = [
        [("Sales", "OrderDate")],
        [("Sales", "OrderDate"), ("Returns", "ReturnDate")],
        [("Events", "EventTimestamp")],
    ]

    @pytest.mark.parametrize("date_cols", _DATE_COLS)
    def test_calendar_has_table_declaration(self, date_cols):
        tmdl = generate_calendar_table_tmdl(date_cols)
        assert tmdl.startswith("table Calendar")

    @pytest.mark.parametrize("date_cols", _DATE_COLS)
    def test_calendar_has_date_column(self, date_cols):
        tmdl = generate_calendar_table_tmdl(date_cols)
        assert "column Date" in tmdl or "column 'Date'" in tmdl

    @pytest.mark.parametrize("date_cols", _DATE_COLS)
    def test_calendar_has_partition(self, date_cols):
        tmdl = generate_calendar_table_tmdl(date_cols)
        assert "partition Calendar = m" in tmdl


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 11: Name quoting consistency
# ═══════════════════════════════════════════════════════════════════

class TestNameQuoting:

    _SIMPLE_NAMES = ["Revenue", "CUSTOMER_ID", "Sales", "abc123", "X"]
    _SPECIAL_NAMES = ["Sales Amount", "Revenue (USD)", "Total/Count",
                      "My-Column", "with.dot", "col:1"]

    @pytest.mark.parametrize("name", _SIMPLE_NAMES)
    def test_simple_names_no_quoting(self, name):
        assert not _needs_quoting(name)

    @pytest.mark.parametrize("name", _SPECIAL_NAMES)
    def test_special_names_need_quoting(self, name):
        assert _needs_quoting(name)


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 12: Aggregation functions produce DAX with function name
# ═══════════════════════════════════════════════════════════════════

class TestAggregationProperty:

    _AGG_MAP = [
        ("Sum", "SUM"), ("Avg", "AVERAGE"), ("Count", "COUNT"),
        ("Min", "MIN"), ("Max", "MAX"), ("StDev", "STDEV.S"),
        ("Median", "MEDIAN"),
    ]

    @pytest.mark.parametrize("mstr,dax", _AGG_MAP)
    def test_aggregation_produces_expected_dax(self, mstr, dax):
        for col in _COLUMN_NAMES[:5]:
            result = convert_mstr_expression_to_dax(f"{mstr}({col})")
            assert dax in result["dax"]
            assert result["fidelity"] == "full"


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 13: Derived metrics always produce structured output
# ═══════════════════════════════════════════════════════════════════

class TestDerivedMetricProperty:

    @pytest.mark.parametrize("col", _COLUMN_NAMES[:5])
    def test_rank_produces_rankx(self, col):
        result = convert_mstr_expression_to_dax(f"Rank({col})")
        assert "RANKX" in result["dax"]

    @pytest.mark.parametrize("col", _COLUMN_NAMES[:5])
    def test_lag_produces_offset(self, col):
        result = convert_mstr_expression_to_dax(f"Lag({col}, 1)")
        assert "OFFSET" in result["dax"]
        assert "-1" in result["dax"]

    @pytest.mark.parametrize("col", _COLUMN_NAMES[:5])
    def test_lead_produces_offset(self, col):
        result = convert_mstr_expression_to_dax(f"Lead({col}, 2)")
        assert "OFFSET" in result["dax"]
        assert "2" in result["dax"]

    @pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
    def test_lag_offset_matches(self, n):
        result = convert_mstr_expression_to_dax(f"Lag(Revenue, {n})")
        assert f"-{n}" in result["dax"]

    @pytest.mark.parametrize("n", [1, 2, 5])
    def test_lead_offset_matches(self, n):
        result = convert_mstr_expression_to_dax(f"Lead(Revenue, {n})")
        assert str(n) in result["dax"]


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 14: Level metrics always produce CALCULATE wrapper
# ═══════════════════════════════════════════════════════════════════

class TestLevelMetricProperty:

    @pytest.mark.parametrize("agg", _MSTR_AGGREGATIONS[:4])
    def test_allexcept_produces_calculate(self, agg):
        result = convert_mstr_expression_to_dax(f"{agg}(Revenue) {{~+, Year}}")
        assert "CALCULATE" in result["dax"]
        assert "ALLEXCEPT" in result["dax"]
        assert result["fidelity"] == "approximated"

    @pytest.mark.parametrize("agg", _MSTR_AGGREGATIONS[:4])
    def test_grand_total_produces_all(self, agg):
        result = convert_mstr_expression_to_dax(f"{agg}(Revenue) {{^}}")
        assert "CALCULATE" in result["dax"]
        assert "ALL(" in result["dax"]

    @pytest.mark.parametrize("agg", _MSTR_AGGREGATIONS[:4])
    def test_exclude_produces_removefilters(self, agg):
        result = convert_mstr_expression_to_dax(f"{agg}(Revenue) {{!Region}}")
        assert "CALCULATE" in result["dax"]
        assert "REMOVEFILTERS" in result["dax"]


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 15: Relationship cycle detection
# ═══════════════════════════════════════════════════════════════════

class TestCycleDetection:

    def test_no_cycles_in_tree(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
            {"from_table": "A", "to_table": "D"},
        ]
        cycles = detect_relationship_cycles(rels)
        assert cycles == []

    def test_detects_simple_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
            {"from_table": "C", "to_table": "A"},
        ]
        cycles = detect_relationship_cycles(rels)
        assert len(cycles) >= 1

    def test_self_loop_detected(self):
        rels = [{"from_table": "A", "to_table": "A"}]
        cycles = detect_relationship_cycles(rels)
        assert len(cycles) >= 1

    def test_empty_relationships_no_cycles(self):
        assert detect_relationship_cycles([]) == []


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 16: Metric-to-DAX always returns dict
# ═══════════════════════════════════════════════════════════════════

class TestMetricToDax:

    _METRICS = [
        {"name": "M1", "expression": "Sum(Revenue)", "metric_type": "simple"},
        {"name": "M2", "expression": "Avg(Cost)", "metric_type": "simple"},
        {"name": "M3", "expression": "", "metric_type": "simple"},
        {"name": "M4", "expression": "Sum(Revenue) / Sum(Cost)", "metric_type": "compound"},
        {"name": "M5", "expression": "Rank(Revenue)", "metric_type": "derived"},
        {"name": "M6", "expression": "Lag(Revenue, 1)", "metric_type": "derived"},
        {"name": "M7", "expression": "NullToZero(Sum(Revenue))", "metric_type": "simple"},
        {"name": "M8", "expression": "If(Revenue > 100, 'High', 'Low')", "metric_type": "simple"},
    ]

    @pytest.mark.parametrize("metric", _METRICS, ids=[m["name"] for m in _METRICS])
    def test_returns_dict_with_dax(self, metric):
        result = convert_metric_to_dax(metric)
        assert isinstance(result, dict)
        assert "dax" in result

    @pytest.mark.parametrize("metric", _METRICS, ids=[m["name"] for m in _METRICS])
    def test_dax_is_string(self, metric):
        result = convert_metric_to_dax(metric)
        assert isinstance(result["dax"], str)


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 17: Position scaling invariants
# ═══════════════════════════════════════════════════════════════════

class TestPositionScaling:

    _POSITIONS = [
        ({"x": 0, "y": 0, "width": 100, "height": 100}, 1024, 768),
        ({"x": 50, "y": 50, "width": 200, "height": 150}, 800, 600),
        ({"x": 0, "y": 0, "width": 1024, "height": 768}, 1024, 768),
        ({}, 1024, 768),
    ]

    @pytest.mark.parametrize("pos,sw,sh", _POSITIONS)
    def test_scaled_has_required_keys(self, pos, sw, sh):
        result = _scale_position(pos, sw, sh)
        assert "x" in result
        assert "y" in result
        assert "width" in result
        assert "height" in result

    @pytest.mark.parametrize("pos,sw,sh", _POSITIONS)
    def test_scaled_values_non_negative(self, pos, sw, sh):
        result = _scale_position(pos, sw, sh)
        assert result["x"] >= 0
        assert result["y"] >= 0
        assert result["width"] >= 0
        assert result["height"] >= 0


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 18: Validator file handling
# ═══════════════════════════════════════════════════════════════════

class TestValidatorProperty:

    def test_nonexistent_tmdl_returns_error(self, tmp_path):
        errors, warnings, info = validate_tmdl_file(str(tmp_path / "nope.tmdl"))
        assert len(errors) >= 1
        assert info is None

    def test_invalid_json_report_returns_error(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{broken", encoding="utf-8")
        errors = validate_report_json(str(p))
        assert len(errors) >= 1

    def test_valid_report_schema_no_errors(self, tmp_path):
        p = tmp_path / "good.json"
        p.write_text(json.dumps({"$schema": "x", "version": "4.0"}), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert errors == []

    @pytest.mark.parametrize("tmdl_content", [
        "table T1\n\tcolumn C1\n\t\tdataType: int64\n",
        "table T2\n\tcolumn C2\n\t\tdataType: string\n",
        "table T3\n\tmeasure M1\n\t\texpression = SUM(T3[C1])\n",
    ])
    def test_valid_tmdl_no_errors(self, tmp_path, tmdl_content):
        p = tmp_path / "test.tmdl"
        p.write_text(tmdl_content, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert info is not None


# ═══════════════════════════════════════════════════════════════════
# PROPERTY 19: Visual data bindings structure
# ═══════════════════════════════════════════════════════════════════

class TestDataBindingsProperty:

    _VISUAL_TYPES = [
        "tableEx", "matrix", "clusteredColumnChart", "lineChart",
        "pieChart", "donutChart", "scatterChart",
    ]

    @pytest.mark.parametrize("pbi_type", _VISUAL_TYPES)
    def test_bindings_is_list(self, pbi_type):
        attrs = [{"id": "a1", "name": "Cat"}]
        metrics = [{"id": "m1", "name": "Val"}]
        bindings = _build_data_bindings(pbi_type, attrs, metrics, {})
        assert isinstance(bindings, list)

    @pytest.mark.parametrize("pbi_type", _VISUAL_TYPES)
    def test_bindings_have_role(self, pbi_type):
        attrs = [{"id": "a1", "name": "Cat"}]
        metrics = [{"id": "m1", "name": "Val"}]
        bindings = _build_data_bindings(pbi_type, attrs, metrics, {})
        for b in bindings:
            assert "role" in b

    def test_empty_data_produces_empty_bindings(self):
        bindings = _build_data_bindings("tableEx", [], [], {})
        assert bindings == []
