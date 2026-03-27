"""Tests for metric extractor module."""

import pytest

from microstrategy_export.metric_extractor import (
    extract_metrics,
    extract_thresholds,
    _parse_metric,
    _classify_metric_type,
    _extract_expression_text,
    _extract_aggregation,
    _extract_column_ref,
    _extract_format_string,
    _extract_folder_path,
    _is_smart_metric,
    _has_metric_references,
    _extract_metric_dependencies,
    _extract_threshold_conditions,
    _extract_threshold_format,
)


class TestExtractMetrics:

    def test_returns_tuple(self, mock_client):
        result = extract_metrics(mock_client)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_simple_metrics_extracted(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        assert len(metrics) >= 1

    def test_metric_has_required_fields(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        for m in metrics:
            assert "name" in m
            assert "expression" in m or "metric_type" in m

    def test_metric_type_classification(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        types = {m.get("metric_type") for m in metrics}
        # Should have at least simple or compound
        assert types & {"simple", "compound"}

    def test_simple_metric_has_expression_text(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        total_revenue = next((m for m in metrics if m["name"] == "Total Revenue"), None)
        assert total_revenue is not None
        assert "Sum(Revenue)" in total_revenue.get("expression", "")

    def test_compound_metric_detected(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        compound = [m for m in metrics if m["metric_type"] == "compound"]
        assert len(compound) >= 1

    def test_compound_metric_has_dependencies(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        profit = next((m for m in metrics if m["name"] == "Profit"), None)
        assert profit is not None
        assert len(profit.get("dependencies", [])) >= 1

    def test_metric_has_format_string(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        total_revenue = next((m for m in metrics if m["name"] == "Total Revenue"), None)
        assert total_revenue.get("format_string", "") != ""

    def test_metric_has_id(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        for m in metrics:
            assert "id" in m
            assert len(m["id"]) > 0

    def test_metric_aggregation(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        for m in metrics:
            assert "aggregation" in m

    def test_metric_folder_path(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        for m in metrics:
            assert "folder_path" in m

    def test_derived_metrics_list(self, mock_client):
        metrics, derived = extract_metrics(mock_client)
        assert isinstance(derived, list)
        # Derived metrics may exist depending on fixture data
        for d in derived:
            assert d.get("metric_type") == "derived"


class TestExtractThresholds:

    def test_threshold_extraction(self, mock_client, api_reports):
        # Thresholds come from report definitions
        report_defs = api_reports.get("definitions", {})
        for report_id, report_def in report_defs.items():
            thresholds = extract_thresholds(report_def)
            assert isinstance(thresholds, list)

    def test_empty_thresholds(self):
        result = extract_thresholds({"thresholds": []})
        assert result == []

    def test_threshold_with_no_key(self):
        result = extract_thresholds({})
        assert result == []


# ── _classify_metric_type ────────────────────────────────────────

class TestClassifyMetricType:

    def test_explicit_simple(self):
        assert _classify_metric_type({"metricType": "simple"}) == "simple"

    def test_explicit_compound(self):
        assert _classify_metric_type({"metricType": "compound"}) == "compound"

    def test_explicit_derived(self):
        assert _classify_metric_type({"metricType": "derived"}) == "derived"

    def test_subtype_derived(self):
        assert _classify_metric_type({"subtype": 786432}) == "derived"

    def test_subtype_smart(self):
        assert _classify_metric_type({"subType": 786433}) == "derived"

    def test_olap_keyword_rank(self):
        detail = {"expression": {"text": "Rank(Revenue) {Region}"}}
        assert _classify_metric_type(detail) == "derived"

    def test_olap_keyword_runningsum(self):
        detail = {"expression": {"text": "RunningSum(Sales)"}}
        assert _classify_metric_type(detail) == "derived"

    def test_olap_keyword_movingavg(self):
        detail = {"expression": {"text": "MovingAvg(Cost, 3)"}}
        assert _classify_metric_type(detail) == "derived"

    def test_olap_keyword_lag(self):
        detail = {"expression": {"text": "Lag(Revenue, 1)"}}
        assert _classify_metric_type(detail) == "derived"

    def test_olap_keyword_ntile(self):
        detail = {"expression": {"text": "NTile(Metric, 4)"}}
        assert _classify_metric_type(detail) == "derived"

    def test_compound_arithmetic(self):
        detail = {"expression": {"text": "Sum(Revenue) - Sum(Cost)"}}
        assert _classify_metric_type(detail) == "compound"

    def test_simple_no_expression(self):
        assert _classify_metric_type({}) == "simple"

    def test_simple_basic_agg(self):
        detail = {"expression": {"text": "Sum(Revenue)"}}
        assert _classify_metric_type(detail) == "simple"


# ── _extract_expression_text ─────────────────────────────────────

class TestExtractExpressionText:

    def test_string_expression(self):
        assert _extract_expression_text({"expression": "Sum(Revenue)"}) == "Sum(Revenue)"

    def test_dict_with_text(self):
        assert _extract_expression_text({"expression": {"text": "Avg(Cost)"}}) == "Avg(Cost)"

    def test_dict_with_expressionText(self):
        detail = {"expression": {"expressionText": "Count(Orders)"}}
        assert _extract_expression_text(detail) == "Count(Orders)"

    def test_tokens_top_level_not_in_expression(self):
        # tokens path is only reached if expression is not a str or dict
        # In practice, expression is either str or dict, so tokens at top-level
        # with expression={} results in empty (dict branch takes priority)
        detail = {"tokens": [{"value": "Sum"}]}
        result = _extract_expression_text(detail)
        # tokens at top level are ignored because expression defaults to {}
        assert result == ""

    def test_expression_with_text_key_preferred_over_tokens(self):
        detail = {"expression": {"text": "Avg(Cost)", "tokens": [{"value": "ignored"}]}}
        assert _extract_expression_text(detail) == "Avg(Cost)"

    def test_empty(self):
        assert _extract_expression_text({}) == ""


# ── _extract_aggregation ─────────────────────────────────────────

class TestExtractAggregation:

    def test_from_metric_function(self):
        assert _extract_aggregation({"metricFunction": "SUM"}) == "sum"

    def test_from_function_key(self):
        assert _extract_aggregation({"function": "AVG"}) == "avg"

    def test_infer_from_expression_sum(self):
        assert _extract_aggregation({"expression": {"text": "Sum(Revenue)"}}) == "sum"

    def test_infer_from_expression_count(self):
        assert _extract_aggregation({"expression": {"text": "Count(Orders)"}}) == "count"

    def test_infer_from_expression_median(self):
        assert _extract_aggregation({"expression": {"text": "median(col)"}}) == "median"

    def test_default_sum(self):
        assert _extract_aggregation({}) == "sum"


# ── _extract_column_ref ──────────────────────────────────────────

class TestExtractColumnRef:

    def test_from_facts(self):
        detail = {"facts": [{"tableName": "FACT_SALES", "columnName": "Revenue"}]}
        assert _extract_column_ref(detail) == "FACT_SALES[Revenue]"

    def test_from_target_facts(self):
        detail = {"target": {"facts": [{"tableName": "T", "name": "Amount"}]}}
        assert _extract_column_ref(detail) == "T[Amount]"

    def test_empty(self):
        assert _extract_column_ref({}) == ""

    def test_column_with_name_fallback(self):
        detail = {"facts": [{"name": "Cost"}]}
        assert _extract_column_ref(detail) == "Table[Cost]"


# ── _extract_format_string ───────────────────────────────────────

class TestExtractFormatString:

    def test_top_level(self):
        assert _extract_format_string({"formatString": "#,##0.00"}) == "#,##0.00"

    def test_nested_format(self):
        detail = {"format": {"formatString": "$#,##0"}}
        assert _extract_format_string(detail) == "$#,##0"

    def test_empty(self):
        assert _extract_format_string({}) == ""


# ── _extract_folder_path ─────────────────────────────────────────

class TestExtractFolderPath:

    def test_with_ancestors(self):
        summary = {"ancestors": [{"name": "Public Objects"}, {"name": "Metrics"}]}
        assert _extract_folder_path(summary) == "Public Objects/Metrics"

    def test_empty_ancestors(self):
        assert _extract_folder_path({}) == ""

    def test_ancestors_with_empty_names(self):
        summary = {"ancestors": [{"name": "Root"}, {"name": ""}, {"name": "Sales"}]}
        assert _extract_folder_path(summary) == "Root/Sales"


# ── _is_smart_metric ─────────────────────────────────────────────

class TestIsSmartMetric:

    def test_smart_subtype(self):
        assert _is_smart_metric({"subtype": 786433}) is True

    def test_not_smart(self):
        assert _is_smart_metric({"subtype": 0}) is False

    def test_subType_key(self):
        assert _is_smart_metric({"subType": 786433}) is True


# ── _has_metric_references ───────────────────────────────────────

class TestHasMetricReferences:

    def test_arithmetic(self):
        assert _has_metric_references("Sum(Revenue) - Sum(Cost)") is True

    def test_division(self):
        assert _has_metric_references("MetricA / MetricB") is True

    def test_simple(self):
        assert _has_metric_references("Sum(Revenue)") is False

    def test_empty(self):
        assert _has_metric_references("") is False


# ── _extract_metric_dependencies ─────────────────────────────────

class TestExtractMetricDependencies:

    def test_string_deps(self):
        detail = {"dependencies": ["dep1", "dep2"]}
        result = _extract_metric_dependencies(detail)
        assert len(result) == 2
        assert result[0] == {"id": "dep1", "name": ""}

    def test_dict_deps_metric_type(self):
        detail = {"dependentObjects": [{"id": "M1", "name": "Revenue", "type": 4}]}
        result = _extract_metric_dependencies(detail)
        assert len(result) == 1
        assert result[0]["name"] == "Revenue"

    def test_dict_deps_non_metric_type(self):
        detail = {"dependentObjects": [{"id": "A1", "name": "Region", "type": 12}]}
        result = _extract_metric_dependencies(detail)
        assert len(result) == 0  # Only metric type (4) is included

    def test_empty(self):
        assert _extract_metric_dependencies({}) == []


# ── _parse_metric ────────────────────────────────────────────────

class TestParseMetric:

    def test_full_metric(self):
        detail = {
            "id": "M1",
            "name": "Total Revenue",
            "description": "Sum of all revenue",
            "expression": {"text": "Sum(Revenue)"},
            "formatString": "#,##0.00",
            "facts": [{"tableName": "FACT_SALES", "columnName": "Revenue"}],
        }
        summary = {"id": "M1", "name": "Total Revenue", "ancestors": [{"name": "Metrics"}]}
        result = _parse_metric(detail, summary)

        assert result["id"] == "M1"
        assert result["name"] == "Total Revenue"
        assert result["metric_type"] == "simple"
        assert result["expression"] == "Sum(Revenue)"
        assert result["format_string"] == "#,##0.00"
        assert "FACT_SALES" in result["column_ref"]

    def test_derived_metric(self):
        detail = {
            "id": "D1", "name": "Revenue Rank",
            "expression": {"text": "Rank(Revenue) {Region}"},
            "subtype": 786433,
        }
        result = _parse_metric(detail, {"id": "D1"})
        assert result["metric_type"] == "derived"
        assert result["is_smart_metric"] is True


# ── _extract_threshold_conditions ────────────────────────────────

class TestExtractThresholdConditions:

    def test_conditions(self):
        threshold = {
            "conditions": [
                {"operator": ">=", "value": 100, "type": "value"},
                {"operator": "<", "value": 50, "type": "value"},
            ]
        }
        result = _extract_threshold_conditions(threshold)
        assert len(result) == 2
        assert result[0]["operator"] == ">="
        assert result[1]["value"] == 50

    def test_empty_conditions(self):
        assert _extract_threshold_conditions({}) == []
        assert _extract_threshold_conditions({"conditions": []}) == []


# ── _extract_threshold_format ────────────────────────────────────

class TestExtractThresholdFormat:

    def test_format(self):
        threshold = {
            "format": {
                "backgroundColor": "#FF0000",
                "fontColor": "#FFFFFF",
                "fontWeight": "bold",
                "icon": "warning",
            }
        }
        result = _extract_threshold_format(threshold)
        assert result["background_color"] == "#FF0000"
        assert result["font_color"] == "#FFFFFF"
        assert result["font_weight"] == "bold"
        assert result["icon"] == "warning"

    def test_empty_format(self):
        result = _extract_threshold_format({})
        assert result["background_color"] == ""
        assert result["font_color"] == ""

    def test_partial_format(self):
        threshold = {"format": {"backgroundColor": "green"}}
        result = _extract_threshold_format(threshold)
        assert result["background_color"] == "green"
        assert result["icon"] == ""


# ── extract_metrics with error handling ──────────────────────────

class TestExtractMetricsErrors:

    def test_metric_detail_failure_continues(self):
        """If get_metric() fails for one metric, it should still include it."""
        from unittest.mock import MagicMock
        client = MagicMock()
        client.get_metrics.return_value = [
            {"id": "M1", "name": "Good"},
            {"id": "M2", "name": "Bad"},
        ]

        def get_metric_side_effect(metric_id):
            if metric_id == "M2":
                raise Exception("API error")
            return {
                "id": "M1", "name": "Good",
                "expression": {"text": "Sum(Revenue)"},
            }

        client.get_metric.side_effect = get_metric_side_effect
        metrics, derived = extract_metrics(client)
        # Both should be present — M2 falls back to summary
        assert len(metrics) + len(derived) == 2
