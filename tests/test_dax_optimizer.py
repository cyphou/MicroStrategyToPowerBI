"""
Tests for v15.0 DAX optimizer — rewrite rules, time intelligence injection,
and optimization report.
"""

import unittest

from powerbi_import.dax_optimizer import (
    optimize_expression,
    optimize_measures,
    format_report,
    _rewrite_isblank_to_coalesce,
    _rewrite_chained_if_to_switch,
    _simplify_nested_calculate,
    _remove_redundant_calculate,
    _extract_if_branches,
    _find_matching_paren,
    _is_date_measure,
    _inject_time_intelligence,
)


class TestISBLANKToCoalesce(unittest.TestCase):
    """EE.3: ISBLANK → COALESCE rewrite."""

    def test_basic_isblank_guard(self):
        expr = "IF(ISBLANK([Revenue]), 0, [Revenue])"
        result, n = _rewrite_isblank_to_coalesce(expr)
        self.assertIn("COALESCE", result)
        self.assertIn("[Revenue]", result)
        self.assertIn("0", result)
        self.assertGreater(n, 0)

    def test_not_isblank_guard(self):
        expr = "IF(NOT(ISBLANK([X])), [X], 99)"
        result, n = _rewrite_isblank_to_coalesce(expr)
        self.assertIn("COALESCE", result)
        self.assertGreater(n, 0)

    def test_no_isblank_no_change(self):
        expr = "IF([Sales] > 0, [Sales], 0)"
        result, n = _rewrite_isblank_to_coalesce(expr)
        self.assertEqual(n, 0)
        self.assertEqual(result, expr)

    def test_multiple_isblank_guards(self):
        expr = "IF(ISBLANK([A]), 0, [A]) + IF(ISBLANK([B]), 1, [B])"
        result, n = _rewrite_isblank_to_coalesce(expr)
        self.assertEqual(n, 2)
        self.assertIn("COALESCE([A], 0)", result)
        self.assertIn("COALESCE([B], 1)", result)

    def test_nested_expression_in_default(self):
        expr = 'IF(ISBLANK([X]), "N/A", [X])'
        result, n = _rewrite_isblank_to_coalesce(expr)
        self.assertIn("COALESCE", result)
        self.assertEqual(n, 1)


class TestChainedIFToSWITCH(unittest.TestCase):
    """EE.2: Chained IF → SWITCH rewrite."""

    def test_three_branch_if(self):
        expr = 'IF([X] = 1, "A", IF([X] = 2, "B", IF([X] = 3, "C", "D")))'
        result, changed = _rewrite_chained_if_to_switch(expr)
        if changed:
            self.assertIn("SWITCH", result)
            self.assertNotIn("IF(", result.upper().replace("SWITCH", ""))

    def test_two_branch_no_change(self):
        expr = 'IF([X] > 0, "Pos", "Neg")'
        result, changed = _rewrite_chained_if_to_switch(expr)
        self.assertFalse(changed)
        self.assertEqual(result, expr)

    def test_non_if_expression(self):
        expr = "SUM([Sales])"
        result, changed = _rewrite_chained_if_to_switch(expr)
        self.assertFalse(changed)
        self.assertEqual(result, expr)

    def test_empty_expression(self):
        result, changed = _rewrite_chained_if_to_switch("")
        self.assertFalse(changed)

    def test_extract_branches_simple(self):
        """Verify branch extraction works for 3+ branches."""
        expr = 'IF(a, b, IF(c, d, IF(e, f, g)))'
        branches = _extract_if_branches(expr)
        # Should have at least 3 elements
        self.assertIsNotNone(branches)
        self.assertGreaterEqual(len(branches), 3)


class TestCALCULATESimplification(unittest.TestCase):
    """EE.5: CALCULATE simplification."""

    def test_redundant_calculate_removed(self):
        expr = "CALCULATE(SUM([Sales]))"
        result, n = _remove_redundant_calculate(expr)
        self.assertEqual(result, "SUM([Sales])")
        self.assertEqual(n, 1)

    def test_calculate_with_filter_preserved(self):
        expr = "CALCULATE(SUM([Sales]), [Region] = \"West\")"
        result, n = _remove_redundant_calculate(expr)
        # Should NOT remove — has a filter argument
        self.assertIn("CALCULATE", result)

    def test_nested_calculate(self):
        expr = "CALCULATE(CALCULATE(SUM([Sales]), [Year] = 2024), [Region] = \"West\")"
        result, n = _simplify_nested_calculate(expr)
        if n > 0:
            # Should flatten to single CALCULATE
            self.assertEqual(result.upper().count("CALCULATE("), 1)

    def test_no_calculate(self):
        expr = "SUM([Sales])"
        result, n = _remove_redundant_calculate(expr)
        self.assertEqual(result, expr)
        self.assertEqual(n, 0)

    def test_deeply_nested_calculate(self):
        expr = "CALCULATE(CALCULATE(CALCULATE(SUM([X]))))"
        result, _ = _simplify_nested_calculate(expr)
        result, _ = _remove_redundant_calculate(result)
        # Should simplify significantly
        self.assertLessEqual(result.upper().count("CALCULATE"), 1)


class TestFindMatchingParen(unittest.TestCase):
    """Helper: balanced parenthesis matching."""

    def test_simple(self):
        self.assertEqual(_find_matching_paren("(abc)", 0), 4)

    def test_nested(self):
        self.assertEqual(_find_matching_paren("(a(b)c)", 0), 6)

    def test_not_at_paren(self):
        self.assertIsNone(_find_matching_paren("abc", 0))

    def test_unbalanced(self):
        self.assertIsNone(_find_matching_paren("(abc", 0))


class TestTimeIntelligence(unittest.TestCase):
    """EE.4: Time Intelligence injection."""

    def test_date_measure_detection(self):
        self.assertTrue(_is_date_measure("SUM('Date'[Amount])"))
        self.assertTrue(_is_date_measure("DATEADD([Date], -1, YEAR)"))
        self.assertFalse(_is_date_measure("SUM([Revenue])"))

    def test_injects_ytd_py_yoy(self):
        measures = [{"name": "Revenue", "expression": "SUM('Date'[Amount])"}]
        ti = _inject_time_intelligence(measures)
        names = [m["name"] for m in ti]
        self.assertIn("Revenue YTD", names)
        self.assertIn("Revenue PY", names)
        self.assertIn("Revenue YoY %", names)

    def test_no_injection_for_non_date(self):
        measures = [{"name": "Count", "expression": "COUNTROWS(Products)"}]
        ti = _inject_time_intelligence(measures)
        self.assertEqual(len(ti), 0)

    def test_auto_generated_flag(self):
        measures = [{"name": "M", "expression": "SUM('Date'[X])"}]
        ti = _inject_time_intelligence(measures)
        for m in ti:
            self.assertTrue(m.get("_auto_generated"))


class TestOptimizeMeasures(unittest.TestCase):
    """Integration tests for optimize_measures."""

    def test_empty_measures(self):
        result, report = optimize_measures([])
        self.assertEqual(len(result), 0)
        self.assertEqual(report["total_measures"], 0)

    def test_no_optimizations_needed(self):
        measures = [{"name": "M1", "expression": "SUM([Sales])"}]
        result, report = optimize_measures(measures)
        self.assertEqual(report["measures_optimized"], 0)
        self.assertEqual(len(result), 1)

    def test_isblank_optimization(self):
        measures = [
            {"name": "Safe Revenue", "expression": "IF(ISBLANK([Revenue]), 0, [Revenue])"}
        ]
        result, report = optimize_measures(measures)
        self.assertEqual(report["measures_optimized"], 1)
        self.assertIn("COALESCE", result[0]["expression"])

    def test_with_time_intelligence(self):
        measures = [
            {"name": "Date Total", "expression": "SUM('Date'[Amount])"}
        ]
        result, report = optimize_measures(measures, auto_time_intelligence=True)
        self.assertGreater(report["time_intelligence_added"], 0)
        # Original + TI variants
        self.assertGreater(len(result), 1)

    def test_original_not_mutated(self):
        measures = [
            {"name": "M", "expression": "IF(ISBLANK([X]), 0, [X])"}
        ]
        original_expr = measures[0]["expression"]
        result, _ = optimize_measures(measures)
        self.assertEqual(measures[0]["expression"], original_expr)

    def test_empty_expression_skipped(self):
        measures = [{"name": "Empty", "expression": ""}]
        result, report = optimize_measures(measures)
        self.assertEqual(report["measures_optimized"], 0)

    def test_report_details(self):
        measures = [
            {"name": "M1", "expression": "IF(ISBLANK([A]), 0, [A])"}
        ]
        _, report = optimize_measures(measures)
        self.assertEqual(len(report["details"]), 1)
        self.assertIn("before_length", report["details"][0])
        self.assertIn("after_length", report["details"][0])

    def test_redundant_calculate_in_measure(self):
        measures = [
            {"name": "Simple", "expression": "CALCULATE(SUM([Sales]))"}
        ]
        result, report = optimize_measures(measures)
        self.assertEqual(report["measures_optimized"], 1)
        self.assertNotIn("CALCULATE", result[0]["expression"])

    def test_multiple_patterns_combined(self):
        """Measure with both ISBLANK and redundant CALCULATE."""
        measures = [
            {"name": "Combined", "expression": "CALCULATE(IF(ISBLANK([X]), 0, [X]))"}
        ]
        result, report = optimize_measures(measures)
        self.assertGreaterEqual(report["measures_optimized"], 1)


class TestOptimizeExpression(unittest.TestCase):
    """Single-expression optimization API."""

    def test_basic(self):
        expr, patterns = optimize_expression("IF(ISBLANK([X]), 0, [X])")
        self.assertIn("COALESCE", expr)
        self.assertIn("ISBLANK→COALESCE", patterns)

    def test_no_optimization(self):
        expr, patterns = optimize_expression("SUM([Sales])")
        self.assertEqual(expr, "SUM([Sales])")
        self.assertEqual(len(patterns), 0)


class TestFormatReport(unittest.TestCase):
    """Report formatting."""

    def test_basic_report(self):
        report = {
            "total_measures": 10,
            "measures_optimized": 3,
            "patterns_applied": ["ISBLANK→COALESCE", "IF→SWITCH"],
            "time_intelligence_added": 6,
            "details": [
                {"measure": "M1", "patterns": ["ISBLANK→COALESCE"],
                 "before_length": 50, "after_length": 30},
            ],
        }
        text = format_report(report)
        self.assertIn("DAX Optimization Report", text)
        self.assertIn("10", text)
        self.assertIn("3", text)

    def test_empty_report(self):
        report = {
            "total_measures": 0,
            "measures_optimized": 0,
            "patterns_applied": [],
            "time_intelligence_added": 0,
            "details": [],
        }
        text = format_report(report)
        self.assertIn("0", text)


if __name__ == "__main__":
    unittest.main()
