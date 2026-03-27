"""Tests for scorecard extractor module."""

import json
import os
import tempfile

import pytest
from unittest.mock import MagicMock

from microstrategy_export.scorecard_extractor import (
    extract_scorecards,
    _extract_objectives,
    _extract_perspectives,
    _extract_kpis,
    _extract_thresholds,
    parse_offline_scorecards,
)


# ── Fixtures ─────────────────────────────────────────────────────

def _make_client(documents=None, details=None):
    """Create a mock client that returns given documents and details."""
    client = MagicMock()
    docs = documents or []
    dets = details or {}

    def mock_get(url):
        if "documents?" in url:
            return docs
        for doc_id, detail in dets.items():
            if f"/api/documents/{doc_id}" in url:
                return detail
        return {}

    client.get = mock_get
    return client


# ── extract_scorecards ───────────────────────────────────────────

class TestExtractScorecards:

    def test_empty_project(self):
        client = _make_client(documents=[])
        result = extract_scorecards(client, "PROJ1")
        assert result == []

    def test_single_scorecard(self):
        docs = [{"id": "SC1", "name": "Sales Scorecard", "description": "KPIs"}]
        details = {
            "SC1": {
                "objectives": [
                    {
                        "id": "OBJ1",
                        "name": "Increase Revenue",
                        "target": {"value": 1000000},
                        "current": {"value": 850000},
                        "status": "at-risk",
                        "weight": 0.6,
                        "metric_id": "M1",
                        "metric_name": "Total Revenue",
                        "thresholds": [],
                        "children": [],
                    }
                ],
                "perspectives": [],
                "kpis": [
                    {
                        "id": "KPI1",
                        "name": "Revenue Growth",
                        "metric_id": "M1",
                        "target": {"value": 15},
                        "unit": "%",
                        "format": "0.0%",
                        "thresholds": [],
                    }
                ],
            }
        }
        client = _make_client(documents=docs, details=details)
        result = extract_scorecards(client, "PROJ1")

        assert len(result) == 1
        sc = result[0]
        assert sc["id"] == "SC1"
        assert sc["name"] == "Sales Scorecard"
        assert sc["description"] == "KPIs"
        assert len(sc["objectives"]) == 1
        assert len(sc["kpis"]) == 1

    def test_scorecard_with_nested_objectives(self):
        docs = [{"id": "SC2", "name": "Strategy"}]
        details = {
            "SC2": {
                "objectives": [
                    {
                        "id": "OBJ1",
                        "name": "Growth",
                        "target": {"value": 100},
                        "current": {"value": 80},
                        "status": "on-track",
                        "children": [
                            {
                                "id": "SUB1",
                                "name": "Market Expansion",
                                "target": {"value": 50},
                                "current": {"value": 45},
                                "status": "on-track",
                                "metric_id": "M2",
                            }
                        ],
                        "thresholds": [],
                    }
                ],
            }
        }
        client = _make_client(documents=docs, details=details)
        result = extract_scorecards(client, "PROJ1")

        obj = result[0]["objectives"][0]
        assert len(obj["children"]) == 1
        assert obj["children"][0]["name"] == "Market Expansion"

    def test_scorecard_api_error(self):
        """API failure should return empty list."""
        client = MagicMock()
        client.get.side_effect = Exception("Connection refused")
        result = extract_scorecards(client, "PROJ1")
        assert result == []

    def test_scorecard_detail_error_continues(self):
        """Failure fetching detail for one scorecard should not stop others."""
        docs = [
            {"id": "SC1", "name": "Good"},
            {"id": "SC2", "name": "Bad"},
        ]
        call_count = [0]

        def mock_get(url):
            if "documents?" in url:
                return docs
            call_count[0] += 1
            if "SC2" in url:
                raise Exception("Server error")
            return {"objectives": [], "kpis": []}

        client = MagicMock()
        client.get = mock_get
        result = extract_scorecards(client, "PROJ1")

        assert len(result) == 2
        assert result[0]["name"] == "Good"
        assert result[1]["name"] == "Bad"

    def test_documents_as_dict(self):
        """API may return dict with 'documents' key."""
        client = MagicMock()
        client.get = lambda url: (
            {"documents": [{"id": "SC1", "name": "Test"}]}
            if "documents?" in url
            else {}
        )
        result = extract_scorecards(client, "PROJ1")
        assert len(result) == 1

    def test_multiple_scorecards(self):
        docs = [
            {"id": "SC1", "name": "First"},
            {"id": "SC2", "name": "Second"},
            {"id": "SC3", "name": "Third"},
        ]
        client = _make_client(documents=docs, details={
            "SC1": {}, "SC2": {}, "SC3": {},
        })
        result = extract_scorecards(client, "PROJ1")
        assert len(result) == 3
        names = [s["name"] for s in result]
        assert names == ["First", "Second", "Third"]


# ── _extract_objectives ──────────────────────────────────────────

class TestExtractObjectives:

    def test_empty_detail(self):
        assert _extract_objectives({}) == []

    def test_objectives_from_objectives_key(self):
        detail = {
            "objectives": [
                {
                    "id": "O1", "name": "Grow Revenue",
                    "target": {"value": 100}, "current": {"value": 80},
                    "status": "on-track", "weight": 0.5,
                    "metric_id": "M1", "metric_name": "Revenue",
                    "thresholds": [], "children": [],
                }
            ]
        }
        result = _extract_objectives(detail)
        assert len(result) == 1
        assert result[0]["name"] == "Grow Revenue"
        assert result[0]["target_value"] == 100
        assert result[0]["current_value"] == 80

    def test_objectives_from_chapters_fallback(self):
        detail = {
            "chapters": [
                {"key": "C1", "name": "Chapter Obj", "thresholds": []}
            ]
        }
        result = _extract_objectives(detail)
        assert len(result) == 1
        assert result[0]["id"] == "C1"

    def test_objective_with_sub_objectives(self):
        detail = {
            "objectives": [
                {
                    "id": "O1", "name": "Parent",
                    "sub_objectives": [
                        {"id": "S1", "name": "Sub 1", "target": {"value": 10}, "current": {"value": 8}},
                    ],
                    "thresholds": [],
                }
            ]
        }
        result = _extract_objectives(detail)
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "Sub 1"

    def test_objective_metricName_fallback(self):
        detail = {
            "objectives": [
                {"id": "O1", "name": "Test", "metricName": "Revenue", "metricId": "M1", "thresholds": []}
            ]
        }
        result = _extract_objectives(detail)
        assert result[0]["metric_name"] == "Revenue"
        assert result[0]["metric_id"] == "M1"


# ── _extract_perspectives ────────────────────────────────────────

class TestExtractPerspectives:

    def test_empty(self):
        assert _extract_perspectives({}) == []

    def test_perspectives_extracted(self):
        detail = {
            "perspectives": [
                {
                    "id": "P1", "name": "Financial", "description": "Money stuff",
                    "objectives": [{"id": "O1"}, {"id": "O2"}],
                }
            ]
        }
        result = _extract_perspectives(detail)
        assert len(result) == 1
        assert result[0]["name"] == "Financial"
        assert result[0]["objective_ids"] == ["O1", "O2"]

    def test_perspective_no_objectives(self):
        detail = {"perspectives": [{"id": "P1", "name": "Empty"}]}
        result = _extract_perspectives(detail)
        assert result[0]["objective_ids"] == []


# ── _extract_kpis ────────────────────────────────────────────────

class TestExtractKpis:

    def test_empty(self):
        assert _extract_kpis({}) == []

    def test_kpis_from_kpis_key(self):
        detail = {
            "kpis": [
                {
                    "id": "K1", "name": "Revenue Growth",
                    "metric_id": "M1", "target": {"value": 15},
                    "unit": "%", "format": "0.0%",
                    "thresholds": [
                        {"name": "On Track", "min": 10, "max": 100, "color": "green", "status": "on-track"},
                    ],
                }
            ]
        }
        result = _extract_kpis(detail)
        assert len(result) == 1
        assert result[0]["name"] == "Revenue Growth"
        assert result[0]["target"] == 15
        assert len(result[0]["thresholds"]) == 1

    def test_kpis_from_metrics_fallback(self):
        detail = {
            "metrics": [
                {"id": "M1", "name": "Profit Margin", "target": {"value": 20}}
            ]
        }
        result = _extract_kpis(detail)
        assert len(result) == 1
        assert result[0]["metric_id"] == "M1"

    def test_kpi_metricId_fallback(self):
        detail = {
            "kpis": [{"id": "K1", "name": "Test", "metricId": "M99"}]
        }
        result = _extract_kpis(detail)
        assert result[0]["metric_id"] == "M99"


# ── _extract_thresholds ──────────────────────────────────────────

class TestExtractThresholds:

    def test_empty(self):
        assert _extract_thresholds({}) == []

    def test_thresholds_from_thresholds_key(self):
        obj = {
            "thresholds": [
                {"name": "On Track", "min": 80, "max": 100, "color": "#00FF00", "status": "on-track"},
                {"name": "At Risk", "min": 50, "max": 80, "color": "#FFFF00", "status": "at-risk"},
            ]
        }
        result = _extract_thresholds(obj)
        assert len(result) == 2
        assert result[0]["name"] == "On Track"
        assert result[0]["min_value"] == 80
        assert result[0]["max_value"] == 100
        assert result[0]["color"] == "#00FF00"

    def test_thresholds_from_bands_fallback(self):
        obj = {
            "bands": [
                {"status": "behind", "minValue": 0, "maxValue": 50, "color": "red"},
            ]
        }
        result = _extract_thresholds(obj)
        assert len(result) == 1
        assert result[0]["name"] == "behind"
        assert result[0]["min_value"] == 0
        assert result[0]["max_value"] == 50


# ── parse_offline_scorecards ─────────────────────────────────────

class TestParseOfflineScorecards:

    def test_file_not_found(self, tmp_path):
        result = parse_offline_scorecards(str(tmp_path / "nonexistent.json"))
        assert result == []

    def test_list_format(self, tmp_path):
        path = tmp_path / "scorecards.json"
        path.write_text(json.dumps([{"id": "SC1", "name": "Test"}]), encoding="utf-8")
        result = parse_offline_scorecards(str(path))
        assert len(result) == 1
        assert result[0]["id"] == "SC1"

    def test_dict_format(self, tmp_path):
        path = tmp_path / "scorecards.json"
        path.write_text(
            json.dumps({"scorecards": [{"id": "SC1"}, {"id": "SC2"}]}),
            encoding="utf-8",
        )
        result = parse_offline_scorecards(str(path))
        assert len(result) == 2

    def test_empty_list(self, tmp_path):
        path = tmp_path / "scorecards.json"
        path.write_text("[]", encoding="utf-8")
        result = parse_offline_scorecards(str(path))
        assert result == []
