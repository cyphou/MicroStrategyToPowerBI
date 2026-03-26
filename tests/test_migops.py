"""
Tests for v11.0 Migration Ops — change detection, drift report, reconciler,
and scheduled migration.
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest

from microstrategy_export.change_detector import (
    detect_changes,
    detect_changes_from_api,
    load_manifest,
    save_manifest,
    _hash_object,
    _index_objects,
)
from powerbi_import.drift_report import (
    detect_drift,
    save_drift_report,
    _collect_files,
    _hash_file,
)
from powerbi_import.reconciler import (
    STRATEGY_CONFLICT,
    reconcile,
    save_reconcile_report,
)


# ── Helpers ──────────────────────────────────────────────────────

def _write_json(directory, filename, data):
    """Write a JSON file into a directory."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _write_text(directory, filename, content):
    """Write a text file into a directory."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


# ── Change Detector Tests ────────────────────────────────────────

class TestChangeDetector(unittest.TestCase):
    """Tests for microstrategy_export/change_detector.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.current_dir = os.path.join(self.tmpdir, "current")
        self.previous_dir = os.path.join(self.tmpdir, "previous")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_changes(self):
        """Identical intermediate files → nothing changed."""
        reports = [{"id": "R1", "name": "Sales"}]
        _write_json(self.current_dir, "reports.json", reports)
        _write_json(self.previous_dir, "reports.json", reports)

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["added"], 0)
        self.assertEqual(manifest["summary"]["modified"], 0)
        self.assertEqual(manifest["summary"]["deleted"], 0)
        self.assertEqual(manifest["summary"]["unchanged"], 1)

    def test_added_object(self):
        """New object in current → added."""
        _write_json(self.current_dir, "reports.json", [
            {"id": "R1", "name": "Sales"},
            {"id": "R2", "name": "Finance"},
        ])
        _write_json(self.previous_dir, "reports.json", [
            {"id": "R1", "name": "Sales"},
        ])

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["added"], 1)
        self.assertEqual(manifest["summary"]["unchanged"], 1)
        self.assertEqual(manifest["added"][0]["id"], "R2")

    def test_modified_object(self):
        """Changed object → modified."""
        _write_json(self.current_dir, "metrics.json", [
            {"id": "M1", "name": "Revenue", "expression": "SUM(Sales)"},
        ])
        _write_json(self.previous_dir, "metrics.json", [
            {"id": "M1", "name": "Revenue", "expression": "SUM(Amount)"},
        ])

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["modified"], 1)
        self.assertEqual(manifest["summary"]["unchanged"], 0)

    def test_deleted_object(self):
        """Object in previous but not current → deleted."""
        _write_json(self.current_dir, "reports.json", [])
        _write_json(self.previous_dir, "reports.json", [
            {"id": "R1", "name": "Old Report"},
        ])

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["deleted"], 1)
        self.assertEqual(manifest["deleted"][0]["name"], "Old Report")

    def test_multiple_types(self):
        """Changes across multiple object types."""
        _write_json(self.current_dir, "reports.json", [{"id": "R1", "name": "A"}])
        _write_json(self.previous_dir, "reports.json", [])
        _write_json(self.current_dir, "metrics.json", [])
        _write_json(self.previous_dir, "metrics.json", [{"id": "M1", "name": "B"}])

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["added"], 1)
        self.assertEqual(manifest["summary"]["deleted"], 1)

    def test_missing_previous_dir(self):
        """No previous directory → all objects are added."""
        _write_json(self.current_dir, "reports.json", [
            {"id": "R1", "name": "Sales"},
        ])
        manifest = detect_changes(self.current_dir, "/nonexistent/path")
        self.assertEqual(manifest["summary"]["added"], 1)

    def test_missing_current_dir(self):
        """No current directory → all objects are deleted."""
        _write_json(self.previous_dir, "reports.json", [
            {"id": "R1", "name": "Sales"},
        ])
        manifest = detect_changes("/nonexistent/path", self.previous_dir)
        self.assertEqual(manifest["summary"]["deleted"], 1)

    def test_save_and_load_manifest(self):
        """Manifest round-trips through save/load."""
        manifest = detect_changes(self.current_dir, self.previous_dir)
        out = os.path.join(self.tmpdir, "out")
        save_manifest(manifest, out)
        loaded = load_manifest(out)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["summary"], manifest["summary"])

    def test_load_manifest_missing(self):
        """load_manifest returns None for missing directory."""
        self.assertIsNone(load_manifest("/nonexistent"))

    def test_hash_object_deterministic(self):
        """Same dict produces same hash."""
        obj = {"a": 1, "b": [2, 3]}
        self.assertEqual(_hash_object(obj), _hash_object(obj))

    def test_hash_object_order_independent(self):
        """Key order doesn't affect hash (json sort_keys)."""
        self.assertEqual(
            _hash_object({"a": 1, "b": 2}),
            _hash_object({"b": 2, "a": 1}),
        )

    def test_index_objects_by_id(self):
        """Objects are indexed by 'id' field."""
        objs = [{"id": "X", "name": "Foo"}, {"id": "Y", "name": "Bar"}]
        idx = _index_objects(objs)
        self.assertIn("X", idx)
        self.assertIn("Y", idx)

    def test_index_objects_by_name_fallback(self):
        """Objects without 'id' fall back to 'name'."""
        objs = [{"name": "Foo"}]
        idx = _index_objects(objs)
        self.assertIn("Foo", idx)

    def test_manifest_timestamps(self):
        """Manifest includes generated_at timestamp."""
        _write_json(self.current_dir, "reports.json", [])
        _write_json(self.previous_dir, "reports.json", [])
        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertIn("generated_at", manifest)

    def test_empty_files(self):
        """Both empty → no changes detected."""
        _write_json(self.current_dir, "reports.json", [])
        _write_json(self.previous_dir, "reports.json", [])
        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["total_current"], 0)

    def test_malformed_json_treated_as_empty(self):
        """Corrupted JSON file is treated as an empty list."""
        _write_text(self.current_dir, "reports.json", "NOT VALID JSON")
        _write_json(self.previous_dir, "reports.json", [{"id": "R1", "name": "X"}])
        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["deleted"], 1)

    def test_complex_change_scenario(self):
        """Mix of added, modified, deleted, unchanged across types."""
        # Reports: R1 unchanged, R2 modified, R3 deleted, R4 added
        _write_json(self.current_dir, "reports.json", [
            {"id": "R1", "name": "A", "v": 1},
            {"id": "R2", "name": "B", "v": 2},  # was v=1
            {"id": "R4", "name": "D", "v": 1},
        ])
        _write_json(self.previous_dir, "reports.json", [
            {"id": "R1", "name": "A", "v": 1},
            {"id": "R2", "name": "B", "v": 1},
            {"id": "R3", "name": "C", "v": 1},
        ])

        manifest = detect_changes(self.current_dir, self.previous_dir)
        self.assertEqual(manifest["summary"]["added"], 1)
        self.assertEqual(manifest["summary"]["modified"], 1)
        self.assertEqual(manifest["summary"]["deleted"], 1)
        self.assertEqual(manifest["summary"]["unchanged"], 1)


class TestChangeDetectorAPI(unittest.TestCase):
    """Tests for API-based change detection."""

    def test_detect_changes_from_api_mock(self):
        """API detection with a mock client."""
        class MockClient:
            def search_objects(self, project_id, object_type, limit):
                if object_type == 3:  # reports
                    return [
                        {"id": "R1", "name": "Sales", "modificationTime": "2026-03-27T12:00:00Z"},
                        {"id": "R2", "name": "Old", "modificationTime": "2025-01-01T00:00:00Z"},
                    ]
                return []

        manifest = detect_changes_from_api(
            client=MockClient(),
            project_id="P1",
            since_timestamp="2026-03-01T00:00:00Z",
            output_dir=None,
        )
        self.assertEqual(manifest["summary"]["modified"], 1)
        self.assertEqual(manifest["modified"][0]["name"], "Sales")

    def test_api_detection_no_changes(self):
        """All objects older than cutoff → empty result."""
        class MockClient:
            def search_objects(self, project_id, object_type, limit):
                return [{"id": "X", "name": "Old", "modificationTime": "2020-01-01T00:00:00Z"}]

        manifest = detect_changes_from_api(
            MockClient(), "P1", "2025-01-01T00:00:00Z", None,
        )
        self.assertEqual(manifest["summary"]["modified"], 0)

    def test_api_detection_handles_error(self):
        """Client exceptions are caught gracefully."""
        class FailClient:
            def search_objects(self, **kwargs):
                raise ConnectionError("offline")

        manifest = detect_changes_from_api(
            FailClient(), "P1", "2025-01-01T00:00:00Z", None,
        )
        self.assertEqual(manifest["summary"]["modified"], 0)


# ── Drift Report Tests ───────────────────────────────────────────

class TestDriftReport(unittest.TestCase):
    """Tests for powerbi_import/drift_report.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.current = os.path.join(self.tmpdir, "live")
        self.previous = os.path.join(self.tmpdir, "baseline")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_drift(self):
        """Identical directories → clean."""
        _write_text(self.current, "model.tmdl", "table Foo")
        _write_text(self.previous, "model.tmdl", "table Foo")
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["drifted"], 0)
        self.assertEqual(report["summary"]["unchanged"], 1)

    def test_modified_file(self):
        """Modified TMDL file → drift detected."""
        _write_text(self.current, "model.tmdl", "table Foo MODIFIED")
        _write_text(self.previous, "model.tmdl", "table Foo")
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["drifted"], 1)

    def test_added_file(self):
        """File in current but not baseline → added locally."""
        _write_text(self.current, "extra.tmdl", "added")
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["added_locally"], 1)

    def test_deleted_file(self):
        """File in baseline but not current → deleted locally."""
        _write_text(self.previous, "old.json", '{"x":1}')
        os.makedirs(self.current, exist_ok=True)
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["deleted_locally"], 1)

    def test_untracked_extension_ignored(self):
        """Files with non-tracked extensions are ignored."""
        _write_text(self.current, "readme.txt", "hello")
        _write_text(self.previous, "readme.txt", "world")
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["drifted"], 0)
        self.assertEqual(report["summary"]["unchanged"], 0)

    def test_save_drift_report_creates_files(self):
        """save_drift_report writes JSON + HTML."""
        report = detect_drift(self.current, self.previous)
        out = os.path.join(self.tmpdir, "out")
        json_path, html_path = save_drift_report(report, out)
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(os.path.exists(html_path))

    def test_html_contains_status(self):
        """HTML report contains CLEAN or CONFLICT."""
        _write_text(self.current, "a.tmdl", "x")
        _write_text(self.previous, "a.tmdl", "x")
        report = detect_drift(self.current, self.previous)
        out = os.path.join(self.tmpdir, "out")
        _, html_path = save_drift_report(report, out)
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("CLEAN", html)

    def test_html_shows_conflicts(self):
        """HTML report shows CONFLICT count for drifted files."""
        _write_text(self.current, "a.tmdl", "changed")
        _write_text(self.previous, "a.tmdl", "original")
        report = detect_drift(self.current, self.previous)
        out = os.path.join(self.tmpdir, "out")
        _, html_path = save_drift_report(report, out)
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        self.assertIn("CONFLICT", html)

    def test_empty_directories(self):
        """Both empty → clean report."""
        os.makedirs(self.current, exist_ok=True)
        os.makedirs(self.previous, exist_ok=True)
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["drifted"], 0)

    def test_nonexistent_directories(self):
        """Nonexistent directories → clean report."""
        report = detect_drift("/nonexistent1", "/nonexistent2")
        self.assertEqual(report["summary"]["drifted"], 0)

    def test_nested_files(self):
        """Drift detection works for nested directory structures."""
        _write_text(
            os.path.join(self.current, "sub"), "data.json", '{"v":2}'
        )
        _write_text(
            os.path.join(self.previous, "sub"), "data.json", '{"v":1}'
        )
        report = detect_drift(self.current, self.previous)
        self.assertEqual(report["summary"]["drifted"], 1)
        self.assertIn("sub/data.json", report["drifted"][0]["file"])

    def test_collect_files_returns_hashes(self):
        """_collect_files returns a dict with relative paths and hashes."""
        _write_text(self.current, "model.tmdl", "test content")
        files = _collect_files(self.current)
        self.assertIn("model.tmdl", files)
        self.assertEqual(len(files["model.tmdl"]), 64)  # SHA-256 hex length

    def test_hash_file_deterministic(self):
        """Same file content → same hash."""
        path = os.path.join(self.tmpdir, "test.tmdl")
        with open(path, "w") as f:
            f.write("deterministic content")
        self.assertEqual(_hash_file(path), _hash_file(path))


# ── Reconciler Tests ─────────────────────────────────────────────

class TestReconciler(unittest.TestCase):
    """Tests for powerbi_import/reconciler.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.source = os.path.join(self.tmpdir, "source")
        self.target = os.path.join(self.tmpdir, "target")
        self.baseline = os.path.join(self.tmpdir, "baseline")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_files(self):
        """Empty directories → empty report."""
        os.makedirs(self.source, exist_ok=True)
        os.makedirs(self.target, exist_ok=True)
        os.makedirs(self.baseline, exist_ok=True)
        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["conflicts"], 0)
        self.assertEqual(rec["summary"]["auto_applied"], 0)

    def test_source_changed_user_untouched(self):
        """Source updated file, user didn't edit → auto accept source."""
        _write_text(self.baseline, "model.tmdl", "old content")
        _write_text(self.target, "model.tmdl", "old content")
        _write_text(self.source, "model.tmdl", "new content")

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["auto_applied"], 1)
        self.assertEqual(rec["auto_applied"][0]["action"], "accept_source")

    def test_source_unchanged_user_edited(self):
        """Source same, user edited → keep user version."""
        _write_text(self.baseline, "model.tmdl", "original")
        _write_text(self.target, "model.tmdl", "user edit")
        _write_text(self.source, "model.tmdl", "original")

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["auto_applied"], 1)
        self.assertEqual(rec["auto_applied"][0]["action"], "keep_target")

    def test_both_changed_differently(self):
        """Source and user both changed file differently → conflict."""
        _write_text(self.baseline, "model.tmdl", "original")
        _write_text(self.target, "model.tmdl", "user version")
        _write_text(self.source, "model.tmdl", "source version")

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["conflicts"], 1)

    def test_both_changed_identically(self):
        """Source and user made the same change → no conflict."""
        _write_text(self.baseline, "model.tmdl", "original")
        _write_text(self.target, "model.tmdl", "same change")
        _write_text(self.source, "model.tmdl", "same change")

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["conflicts"], 0)
        self.assertEqual(rec["auto_applied"][0]["action"], "identical")

    def test_new_file_from_source(self):
        """Brand new file from source → added."""
        os.makedirs(self.baseline, exist_ok=True)
        os.makedirs(self.target, exist_ok=True)
        _write_text(self.source, "new.json", '{"new": true}')

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["new_files"], 1)

    def test_source_removed_user_untouched(self):
        """Source removed file, user didn't edit → safe to remove."""
        _write_text(self.baseline, "old.tmdl", "content")
        _write_text(self.target, "old.tmdl", "content")
        os.makedirs(self.source, exist_ok=True)

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["removed_files"], 1)

    def test_source_removed_user_edited(self):
        """Source removed file, user edited → conflict."""
        _write_text(self.baseline, "old.tmdl", "content")
        _write_text(self.target, "old.tmdl", "user edit")
        os.makedirs(self.source, exist_ok=True)

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["conflicts"], 1)

    def test_user_deleted_source_changed(self):
        """User deleted file, source also changed → keep deleted."""
        _write_text(self.baseline, "old.tmdl", "content")
        _write_text(self.source, "old.tmdl", "new content")
        os.makedirs(self.target, exist_ok=True)

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["removed_files"], 1)

    def test_user_added_file(self):
        """User-added file not in source or baseline → keep."""
        os.makedirs(self.source, exist_ok=True)
        os.makedirs(self.baseline, exist_ok=True)
        _write_text(self.target, "custom.json", '{"custom": true}')

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["auto_applied"], 1)
        self.assertEqual(rec["auto_applied"][0]["action"], "keep_target")

    def test_dry_run_does_not_modify(self):
        """dry_run=True produces report without copying files."""
        _write_text(self.baseline, "model.tmdl", "old")
        _write_text(self.target, "model.tmdl", "old")
        _write_text(self.source, "model.tmdl", "new")

        rec = reconcile(self.source, self.target, self.baseline, dry_run=True)
        self.assertTrue(rec["dry_run"])
        # Target should still have old content (dry run)
        with open(os.path.join(self.target, "model.tmdl")) as f:
            self.assertEqual(f.read(), "old")

    def test_apply_copies_source_file(self):
        """Non-dry-run copies source file to target."""
        _write_text(self.baseline, "data.json", '{"v":1}')
        _write_text(self.target, "data.json", '{"v":1}')
        _write_text(self.source, "data.json", '{"v":2}')

        reconcile(self.source, self.target, self.baseline, dry_run=False)
        with open(os.path.join(self.target, "data.json")) as f:
            self.assertEqual(f.read(), '{"v":2}')

    def test_save_reconcile_report(self):
        """Report saves to JSON file."""
        os.makedirs(self.source, exist_ok=True)
        os.makedirs(self.target, exist_ok=True)
        os.makedirs(self.baseline, exist_ok=True)
        rec = reconcile(self.source, self.target, self.baseline)
        out = os.path.join(self.tmpdir, "out")
        path = save_reconcile_report(rec, out)
        self.assertTrue(os.path.exists(path))

    def test_complex_scenario(self):
        """Multi-file scenario with mix of outcomes."""
        # a.tmdl: source changed, user untouched → accept source
        _write_text(self.baseline, "a.tmdl", "old_a")
        _write_text(self.target, "a.tmdl", "old_a")
        _write_text(self.source, "a.tmdl", "new_a")

        # b.json: both changed differently → conflict
        _write_text(self.baseline, "b.json", '{"v":1}')
        _write_text(self.target, "b.json", '{"user":true}')
        _write_text(self.source, "b.json", '{"source":true}')

        # c.tmdl: new from source → add
        _write_text(self.source, "c.tmdl", "new file")

        rec = reconcile(self.source, self.target, self.baseline)
        self.assertEqual(rec["summary"]["auto_applied"], 1)  # a.tmdl
        self.assertEqual(rec["summary"]["conflicts"], 1)     # b.json
        self.assertEqual(rec["summary"]["new_files"], 1)     # c.tmdl


# ── Scheduled Migration Tests ────────────────────────────────────

class TestScheduledMigration(unittest.TestCase):
    """Tests for scripts/scheduled_migration.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_load_default_config(self):
        """Default config has expected keys."""
        import sys
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "scripts"
        ))
        from scheduled_migration import load_schedule_config
        config = load_schedule_config(None)
        self.assertIn("current_extract_dir", config)
        self.assertIn("output_dir", config)
        self.assertIn("reconcile", config)

    def test_load_config_with_overrides(self):
        """Config file overrides defaults."""
        import sys
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "scripts"
        ))
        from scheduled_migration import load_schedule_config
        config_path = os.path.join(self.tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({"deploy": True, "output_dir": "/custom"}, f)
        config = load_schedule_config(config_path)
        self.assertTrue(config["deploy"])
        self.assertEqual(config["output_dir"], "/custom")

    def test_load_config_missing_file(self):
        """Missing config file returns defaults without error."""
        import sys
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "scripts"
        ))
        from scheduled_migration import load_schedule_config
        config = load_schedule_config("/nonexistent.json")
        self.assertFalse(config["deploy"])

    def test_run_scheduled_migration_end_to_end(self):
        """Full pipeline smoke test with empty directories."""
        import sys
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..", "scripts"
        ))
        from scheduled_migration import run_scheduled_migration

        config_path = os.path.join(self.tmpdir, "config.json")
        report_dir = os.path.join(self.tmpdir, "reports")
        current = os.path.join(self.tmpdir, "current")
        previous = os.path.join(self.tmpdir, "previous")
        output = os.path.join(self.tmpdir, "output")
        out_prev = os.path.join(self.tmpdir, "output_prev")
        baseline = os.path.join(self.tmpdir, "baseline")

        for d in [current, previous, output, out_prev, baseline]:
            os.makedirs(d, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump({
                "current_extract_dir": current,
                "previous_extract_dir": previous,
                "output_dir": output,
                "previous_output_dir": out_prev,
                "baseline_dir": baseline,
                "report_dir": report_dir,
                "reconcile": True,
                "dry_run": True,
            }, f)

        results = run_scheduled_migration(config_path)
        self.assertEqual(results["status"], "success")
        self.assertIn("change_detection", results["steps"])
        self.assertIn("drift_detection", results["steps"])


# ── Integration Tests ────────────────────────────────────────────

class TestMigOpsIntegration(unittest.TestCase):
    """End-to-end integration tests for the v11.0 pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_full_change_drift_reconcile_pipeline(self):
        """detect_changes → detect_drift → reconcile → reports."""
        # Setup: previous extraction + previous output
        prev_extract = os.path.join(self.tmpdir, "prev_extract")
        cur_extract = os.path.join(self.tmpdir, "cur_extract")
        prev_output = os.path.join(self.tmpdir, "prev_output")
        live_output = os.path.join(self.tmpdir, "live_output")
        report_dir = os.path.join(self.tmpdir, "reports")

        # Previous: 1 report
        _write_json(prev_extract, "reports.json", [{"id": "R1", "name": "Sales", "v": 1}])
        _write_text(prev_output, "model.tmdl", "table Sales\n  column Revenue")

        # Current: report modified + user edited output
        _write_json(cur_extract, "reports.json", [{"id": "R1", "name": "Sales", "v": 2}])
        _write_text(live_output, "model.tmdl", "table Sales\n  column Revenue\n  // user comment")

        # Step 1: Change detection
        manifest = detect_changes(cur_extract, prev_extract)
        save_manifest(manifest, report_dir)
        self.assertEqual(manifest["summary"]["modified"], 1)

        # Step 2: Drift detection
        drift = detect_drift(live_output, prev_output)
        save_drift_report(drift, report_dir)
        self.assertEqual(drift["summary"]["drifted"], 1)

        # Step 3: Reconcile (dry run)
        rec = reconcile(live_output, live_output, prev_output, dry_run=True)
        save_reconcile_report(rec, report_dir)

        # Verify all reports generated
        self.assertTrue(os.path.exists(os.path.join(report_dir, "change_manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(report_dir, "drift_report.json")))
        self.assertTrue(os.path.exists(os.path.join(report_dir, "drift_report.html")))
        self.assertTrue(os.path.exists(os.path.join(report_dir, "reconcile_report.json")))


if __name__ == "__main__":
    unittest.main()
