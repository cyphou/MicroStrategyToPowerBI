"""
Tests for Phase F–L: v2.0 features.

Covers: wizard, DAX depth, parallel extraction, incremental state,
cassette harness, dashboard generation.
"""

import json
import os
import sys
import types
import tempfile
import shutil
import pytest

# ── Ensure source dirs on path ──────────────────────────────────

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'microstrategy_export'))
sys.path.insert(0, os.path.join(ROOT, 'powerbi_import'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))


# ════════════════════════════════════════════════════════════════════
# Phase G: Wizard
# ════════════════════════════════════════════════════════════════════

class TestWizard:
    """Tests for wizard.py helper functions."""

    def test_save_config_creates_file(self, tmp_path):
        from wizard import _save_config
        answers = {
            "server": "https://mstr.example.com",
            "username": "admin",
            "project": "Sales",
            "auth_mode": "standard",
            "batch": True,
            "output_dir": "out/",
        }
        config_path = str(tmp_path / "cfg.json")
        _save_config(answers, config_path)

        assert os.path.exists(config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        assert cfg["server"] == "https://mstr.example.com"
        assert cfg["batch"] is True
        # Password should NOT be in config
        assert "password" not in cfg

    def test_save_config_with_deployment(self, tmp_path):
        from wizard import _save_config
        answers = {
            "deploy": "ws-123",
            "fabric": True,
            "tenant_id": "t-1",
            "client_id": "c-1",
        }
        config_path = str(tmp_path / "cfg2.json")
        _save_config(answers, config_path)
        with open(config_path, "r") as f:
            cfg = json.load(f)
        assert cfg["deployment"]["workspace_id"] == "ws-123"
        assert cfg["deployment"]["fabric"] is True


# ════════════════════════════════════════════════════════════════════
# Phase H: DAX Depth – new function mappings & ApplySimple patterns
# ════════════════════════════════════════════════════════════════════

class TestDaxDepth:
    """Tests for expanded DAX conversion in expression_converter.py."""

    def test_initcap_maps_to_proper(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("InitCap(CustomerName)")
        assert "PROPER" in r["dax"]

    def test_daysinmonth(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("DaysInMonth(OrderDate)")
        assert "ENDOFMONTH" in r["dax"]
        assert "DAY" in r["dax"]

    def test_weekstartdate(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("WeekStartDate(OrderDate)")
        assert "WEEKDAY" in r["dax"]

    def test_weekenddate(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("WeekEndDate(OrderDate)")
        assert "WEEKDAY" in r["dax"]

    def test_lpad_conversion(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("LPad(Code, 5, '0')")
        assert "REPT" in r["dax"]

    def test_rpad_conversion(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("RPad(Code, 10, 'X')")
        assert "REPT" in r["dax"]

    def test_reverse_placeholder(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("Reverse(Text)")
        assert "REVERSE" in r["dax"]  # comment-based

    def test_apply_simple_isnull(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("ISNULL(#0, #1)", Revenue, 0)')
        assert "COALESCE" in r["dax"]

    def test_apply_simple_ifnull(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("IFNULL(#0, #1)", Cost, 0)')
        assert "COALESCE" in r["dax"]

    def test_apply_simple_nvl2(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("NVL2(#0, #1, #2)", Status, Active, Inactive)')
        assert "ISBLANK" in r["dax"]

    def test_apply_simple_nullif(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("NULLIF(#0, #1)", Revenue, 0)')
        assert "BLANK" in r["dax"]

    def test_apply_simple_greatest(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("GREATEST(#0, #1)", A, B)')
        assert "MAX" in r["dax"]

    def test_apply_simple_least(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("LEAST(#0, #1)", A, B)')
        assert "MIN" in r["dax"]

    def test_apply_simple_concat(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("CONCAT(#0, #1)", FirstName, LastName)')
        assert "&" in r["dax"]

    def test_apply_simple_substr(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("SUBSTR(#0, 1, 3)", Code)')
        assert "MID" in r["dax"]

    def test_apply_simple_replace(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("REPLACE(#0, \'old\', \'new\')", Name)')
        assert "SUBSTITUTE" in r["dax"]

    def test_apply_simple_upper(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("UPPER(#0)", Name)')
        assert "UPPER" in r["dax"]

    def test_apply_simple_lower(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("LOWER(#0)", Name)')
        assert "LOWER" in r["dax"]

    def test_apply_simple_trim(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TRIM(#0)", Name)')
        assert "TRIM" in r["dax"]

    def test_apply_simple_length(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("LENGTH(#0)", Name)')
        assert "LEN" in r["dax"]

    def test_apply_simple_instr(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("INSTR(#0, \'abc\')", Name)')
        assert "SEARCH" in r["dax"]

    def test_apply_simple_initcap(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("INITCAP(#0)", Name)')
        assert "PROPER" in r["dax"]

    def test_apply_simple_to_date(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TO_DATE(#0, \'YYYY-MM-DD\')", DateStr)')
        assert "DATEVALUE" in r["dax"]

    def test_apply_simple_to_char(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TO_CHAR(#0, \'YYYY\')", OrderDate)')
        assert "FORMAT" in r["dax"]

    def test_apply_simple_last_day(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("LAST_DAY(#0)", OrderDate)')
        assert "ENDOFMONTH" in r["dax"]

    def test_apply_simple_add_months(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("ADD_MONTHS(#0, #1)", OrderDate, 3)')
        assert "EDATE" in r["dax"]

    def test_apply_simple_trunc_mm(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TRUNC(#0, \'MM\')", OrderDate)')
        assert "STARTOFMONTH" in r["dax"]

    def test_apply_simple_trunc_yyyy(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TRUNC(#0, \'YYYY\')", OrderDate)')
        assert "STARTOFYEAR" in r["dax"]

    def test_apply_simple_trunc_q(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("TRUNC(#0, \'Q\')", OrderDate)')
        assert "STARTOFQUARTER" in r["dax"]

    def test_apply_simple_cast_int(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("CAST(#0 AS INTEGER)", Price)')
        assert "INT" in r["dax"]

    def test_apply_simple_cast_float(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("CAST(#0 AS FLOAT)", Price)')
        assert "VALUE" in r["dax"]

    def test_apply_simple_cast_date(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("CAST(#0 AS DATE)", DateStr)')
        assert "DATEVALUE" in r["dax"]

    def test_apply_simple_abs(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("ABS(#0)", Diff)')
        assert "ABS" in r["dax"]

    def test_apply_simple_round(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("ROUND(#0, 2)", Price)')
        assert "ROUND" in r["dax"]

    def test_apply_simple_power(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("POWER(#0, #1)", Base, Exp)')
        assert "POWER" in r["dax"]

    def test_apply_simple_mod(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("MOD(#0, #1)", Num, Div)')
        assert "MOD" in r["dax"]

    def test_apply_simple_sign(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("SIGN(#0)", Amount)')
        assert "SIGN" in r["dax"]

    def test_apply_simple_case_numeric(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("ApplySimple(\"CASE WHEN #0 > 100 THEN 1 ELSE 0 END\", Revenue)")
        assert "IF" in r["dax"]

    def test_apply_simple_case_is_null(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax("ApplySimple(\"CASE WHEN #0 IS NULL THEN 'N/A' ELSE 'OK' END\", Status)")
        assert "ISBLANK" in r["dax"]

    def test_apply_simple_lpad(self):
        from expression_converter import convert_mstr_expression_to_dax
        r = convert_mstr_expression_to_dax('ApplySimple("LPAD(#0, 5, \'0\')", Code)')
        assert "REPT" in r["dax"]

    def test_new_function_map_percentile(self):
        """New function map entries."""
        from expression_converter import _FUNCTION_MAP
        assert _FUNCTION_MAP.get("percentile") == "PERCENTILE.INC"
        assert _FUNCTION_MAP.get("datediff") == "DATEDIFF"
        assert _FUNCTION_MAP.get("dateadd") == "DATEADD"
        assert _FUNCTION_MAP.get("quarterstartdate") == "STARTOFQUARTER"
        assert _FUNCTION_MAP.get("quarterenddate") == "ENDOFQUARTER"
        assert _FUNCTION_MAP.get("number") == "VALUE"
        assert _FUNCTION_MAP.get("text") == "FORMAT"


# ════════════════════════════════════════════════════════════════════
# Phase I: Parallel extraction
# ════════════════════════════════════════════════════════════════════

class TestParallel:
    """Tests for parallel.py."""

    def test_parallel_extract_basic(self):
        from parallel import parallel_extract

        items = [{"id": str(i), "name": f"item_{i}"} for i in range(10)]
        def extract_fn(item):
            return {"id": item["id"], "value": int(item["id"]) * 2}

        results, errors = parallel_extract(items, extract_fn, max_workers=2, label="test")
        assert len(results) == 10
        assert len(errors) == 0

    def test_parallel_extract_handles_errors(self):
        from parallel import parallel_extract

        items = [{"id": "1", "name": "good"}, {"id": "2", "name": "bad"}]
        def extract_fn(item):
            if item["id"] == "2":
                raise ValueError("boom")
            return item

        results, errors = parallel_extract(items, extract_fn, max_workers=1, label="test")
        assert len(results) == 1
        assert len(errors) == 1
        assert "boom" in errors[0]["error"]

    def test_parallel_extract_empty(self):
        from parallel import parallel_extract
        results, errors = parallel_extract([], lambda x: x, label="empty")
        assert results == []
        assert errors == []

    def test_parallel_generate(self, tmp_path):
        from parallel import parallel_generate

        items = [(f"Report_{i}", {"data": i}) for i in range(3)]
        def gen_fn(data, sub_dir, report_name=""):
            os.makedirs(sub_dir, exist_ok=True)
            with open(os.path.join(sub_dir, "test.txt"), "w") as f:
                f.write(report_name)

        s, f = parallel_generate(items, gen_fn, str(tmp_path), max_workers=2, label="gen")
        assert s == 3
        assert f == 0
        assert os.path.exists(tmp_path / "Report_0" / "test.txt")

    def test_stream_json_items(self, tmp_path):
        from parallel import stream_json_items

        data = [{"id": i} for i in range(5)]
        fpath = str(tmp_path / "test.json")
        with open(fpath, "w") as f:
            json.dump(data, f)

        items = list(stream_json_items(fpath))
        assert len(items) == 5
        assert items[0]["id"] == 0


# ════════════════════════════════════════════════════════════════════
# Phase J: Incremental migration
# ════════════════════════════════════════════════════════════════════

class TestIncremental:
    """Tests for incremental.py."""

    def test_new_object_is_changed(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        assert state.is_changed("report", "r1", {"name": "Report A"})

    def test_unchanged_object_not_changed(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        defn = {"name": "Report A", "id": "r1"}
        state.mark_migrated("report", "r1", "Report A", defn)
        assert not state.is_changed("report", "r1", defn)

    def test_modified_object_is_changed(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        defn_v1 = {"name": "Report A", "version": 1}
        state.mark_migrated("report", "r1", "Report A", defn_v1)

        defn_v2 = {"name": "Report A", "version": 2}
        assert state.is_changed("report", "r1", defn_v2)

    def test_save_and_reload(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        state.mark_migrated("report", "r1", "Report A", {"a": 1})
        state.save()

        state2 = MigrationState(str(tmp_path))
        assert not state2.is_changed("report", "r1", {"a": 1})
        assert state2.total_tracked == 1

    def test_get_changed_objects(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        defn1 = {"id": "r1", "name": "A", "v": 1}
        state.mark_migrated("report", "r1", "A", defn1)

        objects = [
            {"id": "r1", "name": "A", "v": 1},  # unchanged
            {"id": "r2", "name": "B", "v": 1},  # new
        ]
        changed = state.get_changed_objects(objects, "report")
        assert len(changed) == 1
        assert changed[0]["id"] == "r2"

    def test_stale_objects(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        state.mark_migrated("report", "r1", "A", {"a": 1})
        state.mark_migrated("report", "r2", "B", {"b": 1})

        stale = state.get_stale_objects({"r1"}, "report")
        assert len(stale) == 1
        assert stale[0][0] == "report:r2"

    def test_mark_removed(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        state.mark_migrated("report", "r1", "A", {"a": 1})
        state.mark_removed("report", "r1")
        assert state.total_tracked == 0

    def test_summary(self, tmp_path):
        from incremental import MigrationState

        state = MigrationState(str(tmp_path))
        state.mark_migrated("report", "r1", "A", {})
        state.mark_migrated("dossier", "d1", "B", {})
        summary = state.summary
        assert summary["report"] == 1
        assert summary["dossier"] == 1


# ════════════════════════════════════════════════════════════════════
# Phase K: Cassette harness
# ════════════════════════════════════════════════════════════════════

class TestCassetteHarness:
    """Tests for cassette recording and playback."""

    def test_record_and_load(self, tmp_path, monkeypatch):
        import tests.cassette_harness as ch
        monkeypatch.setattr(ch, "_CASSETTES_DIR", str(tmp_path))

        rec = ch.CassetteRecorder("test_scenario")
        rec.record("GET", "/api/reports", [{"id": "r1"}])
        rec.record("GET", "/api/reports/r1", {"id": "r1", "name": "Sales"})
        rec.save()

        loaded = ch.CassetteRecorder.load("test_scenario")
        assert loaded.request_count == 2

    def test_play_returns_response(self, tmp_path, monkeypatch):
        import tests.cassette_harness as ch
        monkeypatch.setattr(ch, "_CASSETTES_DIR", str(tmp_path))

        rec = ch.CassetteRecorder("test_play")
        rec.record("GET", "/api/reports", [{"id": "r1"}])
        rec.save()

        loaded = ch.CassetteRecorder.load("test_play")
        resp = loaded.play("GET", "/api/reports")
        assert resp["body"] == [{"id": "r1"}]
        assert resp["status_code"] == 200

    def test_play_missing_raises(self, tmp_path, monkeypatch):
        import tests.cassette_harness as ch
        monkeypatch.setattr(ch, "_CASSETTES_DIR", str(tmp_path))

        rec = ch.CassetteRecorder("test_missing")
        rec.record("GET", "/api/reports", [])
        rec.save()

        loaded = ch.CassetteRecorder.load("test_missing")
        with pytest.raises(KeyError):
            loaded.play("GET", "/api/unknown")

    def test_load_nonexistent_raises(self, tmp_path, monkeypatch):
        import tests.cassette_harness as ch
        monkeypatch.setattr(ch, "_CASSETTES_DIR", str(tmp_path))

        with pytest.raises(FileNotFoundError):
            ch.CassetteRecorder.load("does_not_exist")


# ════════════════════════════════════════════════════════════════════
# Phase L: Dashboard
# ════════════════════════════════════════════════════════════════════

class TestDashboard:
    """Tests for dashboard.py."""

    def _sample_report_data(self):
        return {
            "summary": {
                "report_name": "Sales Migration",
                "total_objects": 10,
                "fidelity_score": 0.85,
                "fidelity_counts": {
                    "fully_migrated": 6,
                    "approximated": 3,
                    "manual_review": 1,
                    "unsupported": 0,
                },
                "type_counts": {"metric": 4, "report": 3, "dossier": 2, "attribute": 1},
                "generation": {
                    "tables": 5, "columns": 20, "measures": 10,
                    "relationships": 3, "pages": 4, "visuals": 15,
                },
            },
            "objects": [
                {"type": "metric", "name": "Revenue", "fidelity": "fully_migrated", "note": ""},
                {"type": "metric", "name": "Cost", "fidelity": "fully_migrated", "note": ""},
                {"type": "metric", "name": "Profit", "fidelity": "approximated", "note": "Derived"},
                {"type": "report", "name": "Sales Dashboard", "fidelity": "fully_migrated", "note": ""},
                {"type": "report", "name": "Complex Report", "fidelity": "manual_review", "note": "Freeform SQL"},
                {"type": "dossier", "name": "Executive Overview", "fidelity": "fully_migrated", "note": ""},
            ],
        }

    def test_generate_dashboard_creates_file(self, tmp_path):
        from dashboard import generate_dashboard

        path = generate_dashboard(self._sample_report_data(), str(tmp_path))
        assert os.path.exists(path)
        assert path.endswith("dashboard.html")

    def test_dashboard_contains_score(self, tmp_path):
        from dashboard import generate_dashboard

        path = generate_dashboard(self._sample_report_data(), str(tmp_path))
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "85%" in html
        assert "Sales Migration" in html

    def test_dashboard_contains_heatmap(self, tmp_path):
        from dashboard import generate_dashboard

        path = generate_dashboard(self._sample_report_data(), str(tmp_path))
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "Fidelity Heatmap" in html
        assert "metric" in html

    def test_dashboard_contains_object_table(self, tmp_path):
        from dashboard import generate_dashboard

        path = generate_dashboard(self._sample_report_data(), str(tmp_path))
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "Revenue" in html
        assert "Complex Report" in html

    def test_dashboard_with_state_data(self, tmp_path):
        from dashboard import generate_dashboard

        state_data = {
            "objects": {
                "report:r1": {"name": "A", "migrated_at": "2026-03-19T10:00:00Z", "type": "report"},
                "report:r2": {"name": "B", "migrated_at": "2026-03-18T10:00:00Z", "type": "report"},
            },
        }
        path = generate_dashboard(self._sample_report_data(), str(tmp_path), state_data=state_data)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "Migration Timeline" in html

    def test_dashboard_filter_script(self, tmp_path):
        from dashboard import generate_dashboard

        path = generate_dashboard(self._sample_report_data(), str(tmp_path))
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        assert "filterTable" in html


# ════════════════════════════════════════════════════════════════════
# Phase F: CLI --version flag
# ════════════════════════════════════════════════════════════════════

class TestCLI:
    """Test CLI argument parsing additions."""

    def test_version_flag(self):
        from migrate import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--version"])
        assert exc.value.code == 0

    def test_incremental_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--incremental"])
        assert args.incremental is True

    def test_parallel_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", ".", "--parallel", "4"])
        assert args.parallel == 4

    def test_parallel_default(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--from-export", "."])
        assert args.parallel == 1
