"""Tests for MicroStrategy expression to DAX converter."""

import pytest

from microstrategy_export.expression_converter import (
    convert_mstr_expression_to_dax,
    convert_metric_to_dax,
)


# ── Aggregation functions ────────────────────────────────────────

@pytest.mark.parametrize("mstr_expr, expected_fragment", [
    ("Sum(Revenue)", "SUM(Revenue)"),
    ("Avg(Cost)", "AVERAGE(Cost)"),
    ("Count(OrderID)", "COUNT(OrderID)"),
    ("Min(Revenue)", "MIN(Revenue)"),
    ("Max(Revenue)", "MAX(Revenue)"),
    ("StDev(Revenue)", "STDEV.S(Revenue)"),
    ("Median(Revenue)", "MEDIAN(Revenue)"),
])
def test_aggregation_functions(mstr_expr, expected_fragment):
    result = convert_mstr_expression_to_dax(mstr_expr)
    assert expected_fragment in result["dax"]
    assert result["fidelity"] == "full"


def test_distinctcount():
    result = convert_mstr_expression_to_dax("Count(Distinct Customer)")
    # Should either use DISTINCTCOUNT or COUNT(Distinct
    assert "DISTINCTCOUNT" in result["dax"] or "COUNT" in result["dax"]


# ── Null handling ────────────────────────────────────────────────

class TestNullHandling:

    def test_nulltozero(self):
        result = convert_mstr_expression_to_dax("NullToZero(Sum(Revenue))")
        assert "ISBLANK" in result["dax"]
        assert "0" in result["dax"]
        assert result["fidelity"] == "full"

    def test_zertonull(self):
        result = convert_mstr_expression_to_dax("ZeroToNull(Sum(Revenue))")
        assert "BLANK()" in result["dax"]
        assert "= 0" in result["dax"]

    def test_isnull(self):
        result = convert_mstr_expression_to_dax("IsNull(Revenue)")
        assert "ISBLANK" in result["dax"]

    def test_isnotnull(self):
        result = convert_mstr_expression_to_dax("IsNotNull(Revenue)")
        assert "NOT(ISBLANK" in result["dax"]


# ── String functions ─────────────────────────────────────────────

@pytest.mark.parametrize("mstr_expr, expected_fragment", [
    ("Concat(FirstName, LastName)", "CONCATENATE(FirstName, LastName)"),
    ("Length(Name)", "LEN(Name)"),
    ("SubStr(Name, 1, 3)", "MID(Name, 1, 3)"),
    ("Trim(Name)", "TRIM(Name)"),
    ("Upper(Name)", "UPPER(Name)"),
    ("Lower(Name)", "LOWER(Name)"),
])
def test_string_functions(mstr_expr, expected_fragment):
    result = convert_mstr_expression_to_dax(mstr_expr)
    assert expected_fragment in result["dax"]


# ── Date functions ───────────────────────────────────────────────

@pytest.mark.parametrize("mstr_expr, expected_fragment", [
    ("CurrentDate()", "TODAY()"),
    ("CurrentDateTime()", "NOW()"),
    ("Year(OrderDate)", "YEAR(OrderDate)"),
    ("Month(OrderDate)", "MONTH(OrderDate)"),
    ("Day(OrderDate)", "DAY(OrderDate)"),
])
def test_date_functions(mstr_expr, expected_fragment):
    result = convert_mstr_expression_to_dax(mstr_expr)
    assert expected_fragment in result["dax"]


def test_daysbetween():
    result = convert_mstr_expression_to_dax("DaysBetween(StartDate, EndDate)")
    assert "DATEDIFF" in result["dax"]
    assert "DAY" in result["dax"]


def test_monthsbetween():
    result = convert_mstr_expression_to_dax("MonthsBetween(StartDate, EndDate)")
    assert "DATEDIFF" in result["dax"]
    assert "MONTH" in result["dax"]


def test_adddays():
    result = convert_mstr_expression_to_dax("AddDays(OrderDate, 7)")
    assert "OrderDate" in result["dax"]
    assert "7" in result["dax"]


# ── Math functions ───────────────────────────────────────────────

@pytest.mark.parametrize("mstr_expr, expected_fragment", [
    ("Abs(Revenue)", "ABS(Revenue)"),
    ("Round(Revenue, 2)", "ROUND(Revenue, 2)"),
    ("Power(x, 2)", "POWER(x, 2)"),
    ("Sqrt(x)", "SQRT(x)"),
    ("Exp(x)", "EXP(x)"),
])
def test_math_functions(mstr_expr, expected_fragment):
    result = convert_mstr_expression_to_dax(mstr_expr)
    assert expected_fragment in result["dax"]


def test_ceiling():
    result = convert_mstr_expression_to_dax("Ceiling(Revenue)")
    assert "CEILING" in result["dax"]
    assert ", 1)" in result["dax"]


def test_floor():
    result = convert_mstr_expression_to_dax("Floor(Revenue)")
    assert "FLOOR" in result["dax"]
    assert ", 1)" in result["dax"]


def test_log():
    result = convert_mstr_expression_to_dax("Log(Revenue)")
    assert "LOG" in result["dax"]
    assert "10" in result["dax"]


# ── Logic functions ──────────────────────────────────────────────

def test_if_function():
    result = convert_mstr_expression_to_dax("If(Revenue > 1000, 'High', 'Low')")
    assert "IF" in result["dax"]


# ── Level metrics ────────────────────────────────────────────────

class TestLevelMetrics:

    def test_allexcept_single(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue) {~+, Year}")
        assert "CALCULATE" in result["dax"]
        assert "ALLEXCEPT" in result["dax"]
        assert "Year" in result["dax"]

    def test_allexcept_multiple(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue) {~+, Year, Region}")
        assert "CALCULATE" in result["dax"]
        assert "ALLEXCEPT" in result["dax"]
        assert "Year" in result["dax"]
        assert "Region" in result["dax"]

    def test_grand_total(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue) {^}")
        assert "CALCULATE" in result["dax"]
        assert "ALL(" in result["dax"]

    def test_exclude_filter(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue) {!Region}")
        assert "CALCULATE" in result["dax"]
        assert "REMOVEFILTERS" in result["dax"]

    def test_level_metric_is_approximated(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue) {~+, Year}")
        assert result["fidelity"] == "approximated"


# ── Derived metrics (OLAP functions) ─────────────────────────────

class TestDerivedMetrics:

    def test_rank(self):
        result = convert_mstr_expression_to_dax("Rank(Sum(Revenue)) {Customer}")
        assert "RANKX" in result["dax"]
        assert "ALL" in result["dax"]

    def test_running_sum(self):
        result = convert_mstr_expression_to_dax("RunningSum(Sum(Revenue)) {Month}")
        assert result["fidelity"] == "approximated"
        assert "RunningSum" in result["warnings"][0]

    def test_lag(self):
        result = convert_mstr_expression_to_dax("Lag(Sum(Revenue), 1) {Year}")
        assert "OFFSET" in result["dax"]
        assert "-1" in result["dax"]
        assert result["fidelity"] == "full"

    def test_lead(self):
        result = convert_mstr_expression_to_dax("Lead(Sum(Revenue), 2) {Year}")
        assert "OFFSET" in result["dax"]
        assert "2" in result["dax"]

    def test_moving_avg(self):
        result = convert_mstr_expression_to_dax("MovingAvg(Sum(Revenue), 3) {Month}")
        assert "AVERAGEX" in result["dax"]
        assert "WINDOW" in result["dax"]
        assert result["fidelity"] == "full"


# ── ApplySimple patterns ────────────────────────────────────────

class TestApplySimple:

    def test_case_when(self):
        expr = 'ApplySimple("CASE WHEN #0 > 1000 THEN \'High\' ELSE \'Low\' END", Revenue)'
        result = convert_mstr_expression_to_dax(expr)
        assert "IF" in result["dax"]
        assert result["fidelity"] == "approximated"

    def test_coalesce(self):
        expr = 'ApplySimple("COALESCE(#0, #1)", Revenue, 0)'
        result = convert_mstr_expression_to_dax(expr)
        assert "COALESCE" in result["dax"]

    def test_nvl(self):
        expr = 'ApplySimple("NVL(#0, #1)", Revenue, 0)'
        result = convert_mstr_expression_to_dax(expr)
        assert "COALESCE" in result["dax"]

    def test_extract_year(self):
        expr = 'ApplySimple("EXTRACT(YEAR FROM #0)", OrderDate)'
        result = convert_mstr_expression_to_dax(expr)
        assert "YEAR" in result["dax"]

    def test_unknown_sql_flagged(self):
        expr = 'ApplySimple("DECODE(#0, 1, \'A\', \'B\')", Status)'
        result = convert_mstr_expression_to_dax(expr)
        assert result["fidelity"] == "manual_review"
        assert "MANUAL REVIEW" in result["dax"]

    def test_apply_agg_manual_review(self):
        expr = 'ApplyAgg("LISTAGG(#0)", Name)'
        result = convert_mstr_expression_to_dax(expr)
        assert result["fidelity"] == "manual_review"


# ── convert_metric_to_dax (full metric dict) ────────────────────

class TestConvertMetricToDax:

    def test_simple_metric_sum(self):
        metric = {
            "name": "Total Revenue",
            "metric_type": "simple",
            "expression": "Sum(Revenue)",
            "aggregation": "sum",
            "column_ref": "FACT_SALES[REVENUE]",
        }
        result = convert_metric_to_dax(metric)
        assert "SUM" in result["dax"]

    def test_compound_metric(self):
        metric = {
            "name": "Profit",
            "metric_type": "compound",
            "expression": "Sum(Revenue) - Sum(Cost)",
            "aggregation": "",
            "column_ref": None,
        }
        result = convert_metric_to_dax(metric)
        assert "SUM" in result["dax"]

    def test_derived_metric(self):
        metric = {
            "name": "Revenue Rank",
            "metric_type": "derived",
            "expression": "Rank(Sum(Revenue)) {Customer}",
            "aggregation": "",
            "column_ref": None,
        }
        result = convert_metric_to_dax(metric)
        assert "RANKX" in result["dax"]


# ── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_expression(self):
        result = convert_mstr_expression_to_dax("")
        assert result["dax"] == ""
        assert result["fidelity"] == "full"

    def test_none_expression(self):
        result = convert_mstr_expression_to_dax(None)
        assert result["dax"] == ""
        assert result["fidelity"] == "full"

    def test_whitespace_only(self):
        result = convert_mstr_expression_to_dax("   ")
        assert result["dax"] == ""
        assert result["fidelity"] == "full"

    def test_plain_text_passthrough(self):
        result = convert_mstr_expression_to_dax("1 + 2")
        assert "1 + 2" in result["dax"]

    def test_fidelity_full_for_simple(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue)")
        assert result["fidelity"] == "full"

    def test_warnings_list_type(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue)")
        assert isinstance(result["warnings"], list)

    def test_result_keys(self):
        result = convert_mstr_expression_to_dax("Sum(Revenue)")
        assert "dax" in result
        assert "fidelity" in result
        assert "warnings" in result
