"""
Tests for v9.0 features — Real-Time & Streaming (Sprint Y).

Covers:
  - realtime_extractor.py: source detection & classification
  - streaming_generator.py: push datasets, Eventstreams, refresh schedules
  - deploy/refresh_config.py: PBI refresh schedule generation
"""

import json
import os
import tempfile

import pytest

# ── Common test data ─────────────────────────────────────────────


def _sample_data(n_tables=2, db_type="sql_server"):
    """Build minimal intermediate JSON data dict for testing."""
    datasources = []
    for i in range(1, n_tables + 1):
        datasources.append({
            "name": f"Table{i}",
            "physical_table": f"dbo_Table{i}",
            "columns": [
                {"name": "ID", "data_type": "integer"},
                {"name": "Name", "data_type": "varchar"},
                {"name": "Amount", "data_type": "double"},
                {"name": "EventDate", "data_type": "date"},
            ],
            "db_connection": {
                "db_type": db_type,
                "host": "myserver",
                "database": "mydb",
                "schema": "dbo",
            },
        })
    return {
        "datasources": datasources,
        "attributes": [],
        "facts": [],
        "metrics": [{"name": "SumAmount", "expression": "Sum(Amount)"}],
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


# ═════════════════════════════════════════════════════════════════
#  realtime_extractor tests
# ═════════════════════════════════════════════════════════════════

class TestRealtimeExtractor:
    """Tests for microstrategy_export.realtime_extractor."""

    def test_empty_data(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        result = detect_realtime_sources({})
        assert result["objects"] == []
        assert result["summary"]["total"] == 0

    def test_batch_dossier(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{"id": "D1", "name": "Sales Dashboard"}]}
        result = detect_realtime_sources(data)
        assert len(result["objects"]) == 1
        assert result["objects"][0]["refresh_class"] == "batch"
        assert result["summary"]["batch"] == 1

    def test_streaming_dossier_auto_refresh_short_interval(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{
            "id": "D2", "name": "Live Monitor",
            "auto_refresh": True,
            "refresh_interval": 30,  # 30 seconds → streaming
        }]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "streaming"

    def test_near_realtime_dossier(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{
            "id": "D3", "name": "Hourly KPIs",
            "auto_refresh": True,
            "refresh_interval": 900,  # 15 min → near-realtime
        }]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "near_realtime"

    def test_subscription_makes_streaming(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{
            "id": "D4", "name": "Alert Dashboard",
            "subscriptions": [{"type": "email", "schedule": "on_event"}],
        }]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "streaming"

    def test_report_default_batch(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"reports": [{"id": "R1", "name": "Weekly Report"}]}
        result = detect_realtime_sources(data)
        obj = result["objects"][0]
        assert obj["object_type"] == "report"
        assert obj["refresh_class"] == "batch"

    def test_cube_manual_is_batch(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"cubes": [{"id": "C1", "name": "Sales Cube", "refresh_policy": "manual"}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "batch"

    def test_cube_event_driven_is_streaming(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"cubes": [{"id": "C2", "name": "RT Cube", "refresh_policy": "event"}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "streaming"

    def test_cube_push_policy_streaming(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"cubes": [{"id": "C3", "name": "Push Cube", "refreshPolicy": "push"}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "streaming"

    def test_mixed_objects(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {
            "dossiers": [
                {"id": "D1", "name": "Batch Dashboard"},
                {"id": "D2", "name": "Live", "refresh_interval": 10, "auto_refresh": True},
            ],
            "reports": [
                {"id": "R1", "name": "Standard Report"},
            ],
            "cubes": [
                {"id": "C1", "name": "Fast Cube", "refresh_interval": 300},
            ],
        }
        result = detect_realtime_sources(data)
        assert result["summary"]["total"] == 4
        classes = {o["name"]: o["refresh_class"] for o in result["objects"]}
        assert classes["Batch Dashboard"] == "batch"
        assert classes["Live"] == "streaming"
        assert classes["Standard Report"] == "batch"
        assert classes["Fast Cube"] == "near_realtime"

    def test_schedule_info_minutes(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{
            "id": "D5", "name": "Scheduled",
            "scheduleInfo": {"refreshIntervalMinutes": 10},
        }]}
        result = detect_realtime_sources(data)
        obj = result["objects"][0]
        assert obj["refresh_interval_seconds"] == 600
        assert obj["refresh_class"] == "near_realtime"

    def test_event_based_flag(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"reports": [{"id": "R2", "name": "Event Report", "event_based": True}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "streaming"

    def test_auto_refresh_interval_field(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{
            "id": "D6", "name": "Auto",
            "autoRefreshInterval": 1800,
        }]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_interval_seconds"] == 1800
        assert result["objects"][0]["refresh_class"] == "near_realtime"

    def test_boundary_one_hour(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        # Exactly 3600 → near_realtime (≤ threshold)
        data = {"dossiers": [{"id": "D7", "name": "Hourly", "refresh_interval": 3600}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "near_realtime"

    def test_boundary_above_one_hour(self):
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        data = {"dossiers": [{"id": "D8", "name": "Slow", "refresh_interval": 3601}]}
        result = detect_realtime_sources(data)
        assert result["objects"][0]["refresh_class"] == "batch"


# ═════════════════════════════════════════════════════════════════
#  streaming_generator tests
# ═════════════════════════════════════════════════════════════════

class TestStreamingGenerator:
    """Tests for powerbi_import.streaming_generator."""

    def _rt_result(self, objects):
        summary = {"batch": 0, "near_realtime": 0, "streaming": 0, "total": len(objects)}
        for o in objects:
            summary[o["refresh_class"]] += 1
        return {"objects": objects, "summary": summary}

    def test_no_streaming_objects(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data()
        rt = self._rt_result([{
            "id": "D1", "name": "Batch",
            "object_type": "dossier", "refresh_class": "batch",
            "refresh_interval_seconds": None, "details": {},
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td)
            assert stats["push_datasets"] == 0
            assert stats["eventstream_definitions"] == 0

    def test_push_dataset_generated(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data()
        rt = self._rt_result([{
            "id": "D2", "name": "Live Monitor",
            "object_type": "dossier", "refresh_class": "streaming",
            "refresh_interval_seconds": 30, "details": {},
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td)
            assert stats["push_datasets"] == 1
            path = os.path.join(td, "push_datasets.json")
            assert os.path.isfile(path)
            with open(path) as f:
                datasets = json.load(f)
            assert len(datasets) == 1
            assert datasets[0]["defaultMode"] == "Push"
            assert len(datasets[0]["tables"]) > 0

    def test_push_dataset_columns_include_timestamp(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data(n_tables=1)
        rt = self._rt_result([{
            "id": "D3", "name": "RT",
            "object_type": "dossier", "refresh_class": "streaming",
            "refresh_interval_seconds": 10, "details": {},
        }])
        with tempfile.TemporaryDirectory() as td:
            generate_streaming_artifacts(data, rt, td)
            with open(os.path.join(td, "push_datasets.json")) as f:
                ds = json.load(f)[0]
            col_names = [c["name"] for c in ds["tables"][0]["columns"]]
            assert "_PushTimestamp" in col_names

    def test_eventstream_generated(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data()
        rt = self._rt_result([{
            "id": "D4", "name": "Stream",
            "object_type": "dossier", "refresh_class": "streaming",
            "refresh_interval_seconds": 5, "details": {},
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td, workspace_id="WS123")
            assert stats["eventstream_definitions"] == 1
            path = os.path.join(td, "eventstreams.json")
            with open(path) as f:
                es = json.load(f)
            assert es[0]["workspaceId"] == "WS123"
            assert len(es[0]["destinations"]) == 2

    def test_refresh_schedule_for_near_realtime(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data()
        rt = self._rt_result([{
            "id": "D5", "name": "NearRT",
            "object_type": "dossier", "refresh_class": "near_realtime",
            "refresh_interval_seconds": 900, "details": {},
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td)
            assert stats["refresh_schedules"] == 1
            path = os.path.join(td, "refresh_schedules.json")
            with open(path) as f:
                schedules = json.load(f)
            assert schedules[0]["schedule"]["frequencyMinutes"] == 15  # min 15

    def test_summary_json_written(self):
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        data = _sample_data()
        rt = self._rt_result([])
        with tempfile.TemporaryDirectory() as td:
            generate_streaming_artifacts(data, rt, td)
            path = os.path.join(td, "streaming_summary.json")
            assert os.path.isfile(path)

    def test_type_mapping_integer(self):
        from powerbi_import.streaming_generator import _PUSH_TYPE_MAP
        assert _PUSH_TYPE_MAP["integer"] == "Int64"
        assert _PUSH_TYPE_MAP["double"] == "Double"
        assert _PUSH_TYPE_MAP["varchar"] == "String"
        assert _PUSH_TYPE_MAP["date"] == "DateTime"
        assert _PUSH_TYPE_MAP["boolean"] == "Bool"
        assert _PUSH_TYPE_MAP["decimal"] == "Decimal"

    def test_safe_name_sanitization(self):
        from powerbi_import.streaming_generator import _safe_name
        assert _safe_name("Sales & Revenue") == "Sales___Revenue"
        assert _safe_name("") == ""
        assert len(_safe_name("A" * 100)) <= 64


# ═════════════════════════════════════════════════════════════════
#  deploy/refresh_config tests
# ═════════════════════════════════════════════════════════════════

class TestRefreshConfig:
    """Tests for powerbi_import.deploy.refresh_config."""

    def _rt_result(self, objects):
        summary = {"batch": 0, "near_realtime": 0, "streaming": 0, "total": len(objects)}
        for o in objects:
            summary[o["refresh_class"]] += 1
        return {"objects": objects, "summary": summary}

    def test_empty_objects(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_refresh_config(rt, td)
            assert stats["total"] == 0
            path = os.path.join(td, "refresh_config.json")
            assert os.path.isfile(path)
            with open(path) as f:
                assert json.load(f) == []

    def test_batch_config(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([{
            "id": "R1", "name": "Weekly",
            "object_type": "report", "refresh_class": "batch",
            "refresh_interval_seconds": None,
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_refresh_config(rt, td)
            assert stats["batch"] == 1
            with open(os.path.join(td, "refresh_config.json")) as f:
                configs = json.load(f)
            assert configs[0]["refresh_class"] == "batch"
            assert configs[0]["schedule"]["times"] == ["06:00"]

    def test_near_realtime_config(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([{
            "id": "D1", "name": "Frequent",
            "object_type": "dossier", "refresh_class": "near_realtime",
            "refresh_interval_seconds": 900,
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_refresh_config(rt, td)
            assert stats["near_realtime"] == 1
            with open(os.path.join(td, "refresh_config.json")) as f:
                configs = json.load(f)
            cfg = configs[0]
            assert cfg["refresh_class"] == "near_realtime"
            assert cfg["frequencyMinutes"] == 15
            assert len(cfg["schedule"]["times"]) == 96  # 24*60/15

    def test_streaming_config_no_schedule(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([{
            "id": "D2", "name": "Live",
            "object_type": "dossier", "refresh_class": "streaming",
            "refresh_interval_seconds": 10,
        }])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_refresh_config(rt, td)
            assert stats["streaming"] == 1
            with open(os.path.join(td, "refresh_config.json")) as f:
                configs = json.load(f)
            cfg = configs[0]
            assert cfg["refresh_class"] == "streaming"
            assert cfg["recommendation"] == "push_dataset"
            assert cfg["schedule"] is None

    def test_mixed_objects(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([
            {"id": "1", "name": "A", "object_type": "report",
             "refresh_class": "batch", "refresh_interval_seconds": None},
            {"id": "2", "name": "B", "object_type": "dossier",
             "refresh_class": "near_realtime", "refresh_interval_seconds": 600},
            {"id": "3", "name": "C", "object_type": "dossier",
             "refresh_class": "streaming", "refresh_interval_seconds": 5},
        ])
        with tempfile.TemporaryDirectory() as td:
            stats = generate_refresh_config(rt, td)
            assert stats["total"] == 3
            assert stats["batch"] == 1
            assert stats["near_realtime"] == 1
            assert stats["streaming"] == 1

    def test_near_realtime_default_interval(self):
        from powerbi_import.deploy.refresh_config import generate_refresh_config
        rt = self._rt_result([{
            "id": "D3", "name": "Default",
            "object_type": "dossier", "refresh_class": "near_realtime",
            "refresh_interval_seconds": None,
        }])
        with tempfile.TemporaryDirectory() as td:
            generate_refresh_config(rt, td)
            with open(os.path.join(td, "refresh_config.json")) as f:
                configs = json.load(f)
            # Default 30 min
            assert configs[0]["frequencyMinutes"] == 30

    def test_time_slots_hourly(self):
        from powerbi_import.deploy.refresh_config import _build_time_slots
        slots = _build_time_slots(60)
        assert len(slots) == 24
        assert slots[0] == "00:00"
        assert slots[-1] == "23:00"

    def test_time_slots_15min(self):
        from powerbi_import.deploy.refresh_config import _build_time_slots
        slots = _build_time_slots(15)
        assert len(slots) == 96
        assert "00:15" in slots


# ═════════════════════════════════════════════════════════════════
#  Integration: full pipeline test
# ═════════════════════════════════════════════════════════════════

class TestStreamingIntegration:
    """End-to-end integration test for the v9.0 real-time pipeline."""

    def test_full_pipeline(self):
        """detect_realtime_sources → generate_streaming_artifacts → refresh_config"""
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        from powerbi_import.streaming_generator import generate_streaming_artifacts
        from powerbi_import.deploy.refresh_config import generate_refresh_config

        data = _sample_data()
        data["dossiers"] = [
            {"id": "D1", "name": "Batch Dashboard"},
            {"id": "D2", "name": "Live Monitor",
             "refresh_interval": 15, "subscriptions": [{"type": "email"}]},
            {"id": "D3", "name": "Hourly KPIs",
             "auto_refresh": True, "refresh_interval": 900},
        ]
        data["cubes"] = [
            {"id": "C1", "name": "RT Cube", "refresh_policy": "event"},
        ]

        # Step 1: Detect
        rt = detect_realtime_sources(data)
        assert rt["summary"]["streaming"] == 2  # Live Monitor + RT Cube
        assert rt["summary"]["near_realtime"] == 1  # Hourly KPIs
        assert rt["summary"]["batch"] == 1  # Batch Dashboard

        # Step 2: Generate streaming artifacts
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td)
            assert stats["push_datasets"] == 2
            assert stats["eventstream_definitions"] == 2
            assert stats["refresh_schedules"] == 1

            # Step 3: Generate refresh config
            rc = generate_refresh_config(rt, td)
            assert rc["total"] == 4

            # Verify files exist
            for fname in ["push_datasets.json", "eventstreams.json",
                          "refresh_schedules.json", "streaming_summary.json",
                          "refresh_config.json"]:
                assert os.path.isfile(os.path.join(td, fname)), f"Missing {fname}"

    def test_all_batch_no_streaming_files(self):
        """When all objects are batch, no push_datasets or eventstreams files are created."""
        from microstrategy_export.realtime_extractor import detect_realtime_sources
        from powerbi_import.streaming_generator import generate_streaming_artifacts

        data = _sample_data()
        data["dossiers"] = [{"id": "D1", "name": "Batch Only"}]
        data["reports"] = [{"id": "R1", "name": "Standard"}]

        rt = detect_realtime_sources(data)
        with tempfile.TemporaryDirectory() as td:
            stats = generate_streaming_artifacts(data, rt, td)
            assert stats["push_datasets"] == 0
            assert not os.path.isfile(os.path.join(td, "push_datasets.json"))
            assert not os.path.isfile(os.path.join(td, "eventstreams.json"))
