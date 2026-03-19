"""Tests for metric extractor module."""

import pytest

from microstrategy_export.metric_extractor import (
    extract_metrics,
    extract_thresholds,
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
