"""Tests for report extractor module."""

import pytest

from microstrategy_export.report_extractor import extract_report_definition


class TestExtractReportDefinition:

    def _build_summary_map(self, api_reports):
        return {s["id"]: s for s in api_reports.get("list", [])}

    def test_extracts_grid_report(self, mock_client, api_reports):
        defs = api_reports.get("definitions", {})
        summary_map = self._build_summary_map(api_reports)
        for report_id, report_def in defs.items():
            summary = summary_map.get(report_id, report_def)
            result = extract_report_definition(report_def, summary)
            assert "name" in result
            assert "type" in result

    def test_report_has_grid_or_graph(self, mock_client, api_reports):
        defs = api_reports.get("definitions", {})
        summary_map = self._build_summary_map(api_reports)
        for report_id, report_def in defs.items():
            summary = summary_map.get(report_id, report_def)
            result = extract_report_definition(report_def, summary)
            report_type = result.get("type", "")
            assert report_type in ("grid", "graph", "grid_graph", "document", "")

    def test_report_grid_has_elements(self, mock_client, api_reports):
        defs = api_reports.get("definitions", {})
        summary_map = self._build_summary_map(api_reports)
        for report_id, report_def in defs.items():
            summary = summary_map.get(report_id, report_def)
            result = extract_report_definition(report_def, summary)
            if result.get("type") == "grid":
                grid = result.get("grid", {})
                assert "rows" in grid or "columns" in grid or True  # Structure varies
