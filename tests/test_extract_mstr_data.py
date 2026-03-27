"""Tests for extract_mstr_data orchestrator module."""

import json
import os
import shutil
import sys
import tempfile

import pytest
from unittest.mock import MagicMock, patch, call

from microstrategy_export.extract_mstr_data import MstrExtractor, _write_json


# ── _write_json helper ───────────────────────────────────────────

class TestWriteJson:

    def test_write_json_creates_file(self, tmp_path):
        path = str(tmp_path)
        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", path):
            _write_json("test.json", [1, 2, 3])
        result = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert result == [1, 2, 3]

    def test_write_json_with_dict(self, tmp_path):
        path = str(tmp_path)
        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", path):
            _write_json("test.json", {"key": "value"})
        result = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert result == {"key": "value"}

    def test_write_json_unicode(self, tmp_path):
        path = str(tmp_path)
        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", path):
            _write_json("test.json", [{"name": "Données françaises"}])
        result = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert result[0]["name"] == "Données françaises"

    def test_write_json_empty_list(self, tmp_path):
        path = str(tmp_path)
        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", path):
            _write_json("test.json", [])
        result = json.loads((tmp_path / "test.json").read_text(encoding="utf-8"))
        assert result == []


# ── MstrExtractor.from_export (offline mode) ─────────────────────

class TestFromExport:

    def test_from_export_creates_instance(self, tmp_path):
        export_dir = str(tmp_path / "mstr_export")
        os.makedirs(export_dir)
        ext = MstrExtractor.from_export(export_dir)
        assert ext.client is None
        assert ext._export_dir == export_dir

    def test_from_export_sets_project_name(self, tmp_path):
        export_dir = str(tmp_path / "MyProject")
        os.makedirs(export_dir)
        ext = MstrExtractor.from_export(export_dir)
        assert ext.project_name == "MyProject"

    def test_from_export_trailing_slash(self, tmp_path):
        export_dir = str(tmp_path / "MyProject")
        os.makedirs(export_dir)
        ext = MstrExtractor.from_export(export_dir + "/")
        assert ext.project_name == "MyProject"


# ── _load_from_export ─────────────────────────────────────────────

class TestLoadFromExport:

    def test_load_from_export_copies_json(self, tmp_path):
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        (export_dir / "metrics.json").write_text('[{"id": "1"}]', encoding="utf-8")
        (export_dir / "attributes.json").write_text('[]', encoding="utf-8")
        # Non-JSON files should be ignored
        (export_dir / "readme.txt").write_text("ignore me", encoding="utf-8")

        out_dir = tmp_path / "output"
        out_dir.mkdir()

        ext = MstrExtractor.from_export(str(export_dir))

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(out_dir)):
            result = ext._load_from_export()

        assert result is True
        assert (out_dir / "metrics.json").exists()
        assert (out_dir / "attributes.json").exists()
        assert not (out_dir / "readme.txt").exists()

    def test_load_from_export_returns_true(self, tmp_path):
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        ext = MstrExtractor.from_export(str(export_dir))
        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)):
            assert ext._load_from_export() is True


# ── extract_all (offline path) ────────────────────────────────────

class TestExtractAllOffline:

    def test_extract_all_offline_calls_load(self, tmp_path):
        export_dir = tmp_path / "export"
        export_dir.mkdir()
        ext = MstrExtractor.from_export(str(export_dir))
        with patch.object(ext, "_load_from_export", return_value=True) as mock_load:
            result = ext.extract_all()
        mock_load.assert_called_once()
        assert result is True


# ── extract_all (live API mock) ───────────────────────────────────

class TestExtractAllLive:

    def _make_extractor(self):
        """Create an extractor with a mock client (bypass __init__ auth)."""
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "TestProject"
        return ext

    def test_extract_all_calls_all_stages(self, tmp_path):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema") as m_schema, \
             patch.object(ext, "_extract_metrics") as m_metrics, \
             patch.object(ext, "_extract_reports") as m_reports, \
             patch.object(ext, "_extract_dossiers") as m_dossiers, \
             patch.object(ext, "_extract_cubes") as m_cubes, \
             patch.object(ext, "_extract_filters") as m_filters, \
             patch.object(ext, "_extract_prompts") as m_prompts, \
             patch.object(ext, "_extract_security_filters") as m_sec:
            result = ext.extract_all()

        assert result is True
        m_schema.assert_called_once()
        m_metrics.assert_called_once()
        m_reports.assert_called_once()
        m_dossiers.assert_called_once()
        m_cubes.assert_called_once()
        m_filters.assert_called_once()
        m_prompts.assert_called_once()
        m_sec.assert_called_once()

    def test_extract_all_closes_client(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=Exception("boom")):
            ext.extract_all()
        ext.client.close.assert_called_once()

    def test_extract_all_returns_false_on_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=RuntimeError("bad")):
            result = ext.extract_all()
        assert result is False


# ── extract_schema_only ───────────────────────────────────────────

class TestExtractSchemaOnly:

    def _make_extractor(self):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "TestProject"
        return ext

    def test_extract_schema_only_success(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"):
            result = ext.extract_schema_only()
        assert result is True

    def test_extract_schema_only_closes_client(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"):
            ext.extract_schema_only()
        ext.client.close.assert_called_once()

    def test_extract_schema_only_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=RuntimeError("err")):
            result = ext.extract_schema_only()
        assert result is False


# ── extract_report ────────────────────────────────────────────────

class TestExtractReport:

    def _make_extractor(self):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "TestProject"
        return ext

    def test_extract_report_found(self):
        ext = self._make_extractor()
        ext.client.search_objects.return_value = [{"id": "RPT1", "name": "Sales Report"}]
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"), \
             patch.object(ext, "_extract_report_definitions") as m_rd:
            result = ext.extract_report("Sales Report")
        assert result is True
        m_rd.assert_called_once()

    def test_extract_report_not_found(self):
        ext = self._make_extractor()
        ext.client.search_objects.return_value = []
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"):
            result = ext.extract_report("Missing Report")
        assert result is False

    def test_extract_report_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=RuntimeError("err")):
            result = ext.extract_report("X")
        assert result is False

    def test_extract_report_closes_client(self):
        ext = self._make_extractor()
        ext.client.search_objects.return_value = [{"id": "R1", "name": "R"}]
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"), \
             patch.object(ext, "_extract_report_definitions"):
            ext.extract_report("R")
        ext.client.close.assert_called_once()


# ── extract_report_by_id ─────────────────────────────────────────

class TestExtractReportById:

    def _make_extractor(self):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "TestProject"
        return ext

    def test_extract_report_by_id_success(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"), \
             patch.object(ext, "_extract_report_definitions") as m_rd:
            result = ext.extract_report_by_id("RPT123")
        assert result is True
        args = m_rd.call_args[0][0]
        assert args[0]["id"] == "RPT123"

    def test_extract_report_by_id_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=Exception("fail")):
            result = ext.extract_report_by_id("RPT123")
        assert result is False


# ── extract_dossier / extract_dossier_by_id ───────────────────────

class TestExtractDossier:

    def _make_extractor(self):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "TestProject"
        return ext

    def test_extract_dossier_found(self):
        ext = self._make_extractor()
        ext.client.search_objects.return_value = [{"id": "D1", "name": "Dashboard"}]
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"), \
             patch.object(ext, "_extract_dossier_definitions") as m_dd:
            result = ext.extract_dossier("Dashboard")
        assert result is True
        m_dd.assert_called_once()

    def test_extract_dossier_not_found(self):
        ext = self._make_extractor()
        ext.client.search_objects.return_value = []
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"):
            result = ext.extract_dossier("Missing")
        assert result is False

    def test_extract_dossier_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=RuntimeError("err")):
            result = ext.extract_dossier("X")
        assert result is False

    def test_extract_dossier_by_id_success(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema"), \
             patch.object(ext, "_extract_metrics"), \
             patch.object(ext, "_extract_dossier_definitions") as m_dd:
            result = ext.extract_dossier_by_id("D123")
        assert result is True

    def test_extract_dossier_by_id_error(self):
        ext = self._make_extractor()
        with patch.object(ext, "_extract_schema", side_effect=Exception("fail")):
            result = ext.extract_dossier_by_id("D123")
        assert result is False


# ── _extract_schema ───────────────────────────────────────────────

class TestExtractSchemaInternal:

    def test_extract_schema_writes_json_files(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            # Patch the relative imports used inside _extract_schema
            with patch.dict("sys.modules", {
                "schema_extractor": MagicMock(
                    extract_tables=MagicMock(return_value=[{"id": "T1"}]),
                    extract_attributes=MagicMock(return_value=[]),
                    extract_facts=MagicMock(return_value=[]),
                    extract_hierarchies=MagicMock(return_value=[]),
                    extract_custom_groups=MagicMock(return_value=[]),
                    extract_freeform_sql=MagicMock(return_value=[]),
                    infer_relationships=MagicMock(return_value=[]),
                ),
            }):
                ext._extract_schema()

        # Should write 7 json files
        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "datasources.json" in written_files
        assert "attributes.json" in written_files
        assert "facts.json" in written_files
        assert "hierarchies.json" in written_files
        assert "relationships.json" in written_files


# ── _extract_metrics ──────────────────────────────────────────────

class TestExtractMetricsInternal:

    def test_extract_metrics_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            with patch.dict("sys.modules", {
                "metric_extractor": MagicMock(
                    extract_metrics=MagicMock(return_value=([], [])),
                    extract_thresholds=MagicMock(return_value=[]),
                ),
            }):
                ext._extract_metrics()

        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "metrics.json" in written_files
        assert "derived_metrics.json" in written_files
        assert "thresholds.json" in written_files


# ── _extract_reports ──────────────────────────────────────────────

class TestExtractReportsInternal:

    def test_extract_reports_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            with patch.dict("sys.modules", {
                "report_extractor": MagicMock(
                    extract_report_definition=MagicMock(return_value={"id": "R1"}),
                ),
            }):
                ext._extract_reports()

        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "reports.json" in written_files

    def test_report_extraction_handles_errors(self, tmp_path):
        """Report extraction should continue past individual failures."""
        ext = MstrExtractor.__new__(MstrExtractor)
        client = MagicMock()
        client.get_reports.return_value = [
            {"id": "R1", "name": "Good Report"},
            {"id": "R2", "name": "Bad Report"},
        ]
        client.get_report_definition.side_effect = [
            {"id": "R1", "name": "Good Report", "grid": {}},
            Exception("API error"),
        ]
        client.get_report_prompts.return_value = []
        ext.client = client
        ext.project_name = "Test"

        results = []

        def capture_write(filename, data):
            if filename == "reports.json":
                results.extend(data)

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json", side_effect=capture_write):
            with patch.dict("sys.modules", {
                "report_extractor": MagicMock(
                    extract_report_definition=MagicMock(return_value={"id": "R1", "name": "Good"}),
                ),
            }):
                ext._extract_reports()

        assert len(results) == 2
        assert "error" in results[1]


# ── _extract_dossiers ────────────────────────────────────────────

class TestExtractDossiersInternal:

    def test_extract_dossiers_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            with patch.dict("sys.modules", {
                "dossier_extractor": MagicMock(
                    extract_dossier_definition=MagicMock(return_value={"id": "D1"}),
                ),
            }):
                ext._extract_dossiers()

        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "dossiers.json" in written_files

    def test_dossier_extraction_handles_errors(self, tmp_path):
        ext = MstrExtractor.__new__(MstrExtractor)
        client = MagicMock()
        client.get_dossiers.return_value = [
            {"id": "D1", "name": "Bad Dossier"},
        ]
        client.get_dossier_definition.side_effect = Exception("fail")
        ext.client = client
        ext.project_name = "Test"

        results = []

        def capture_write(filename, data):
            if filename == "dossiers.json":
                results.extend(data)

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json", side_effect=capture_write):
            with patch.dict("sys.modules", {
                "dossier_extractor": MagicMock(
                    extract_dossier_definition=MagicMock(return_value={"id": "D1"}),
                ),
            }):
                ext._extract_dossiers()

        assert len(results) == 1
        assert "error" in results[0]


# ── _extract_cubes ───────────────────────────────────────────────

class TestExtractCubesInternal:

    def test_extract_cubes_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            with patch.dict("sys.modules", {
                "cube_extractor": MagicMock(
                    extract_cube_definition=MagicMock(return_value={"id": "C1"}),
                ),
            }):
                ext._extract_cubes()

        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "cubes.json" in written_files

    def test_cube_extraction_handles_errors(self, tmp_path):
        ext = MstrExtractor.__new__(MstrExtractor)
        client = MagicMock()
        client.get_cubes.return_value = [{"id": "C1", "name": "Bad Cube"}]
        client.get_cube_definition.side_effect = Exception("fail")
        ext.client = client
        ext.project_name = "Test"

        results = []

        def capture_write(filename, data):
            if filename == "cubes.json":
                results.extend(data)

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json", side_effect=capture_write):
            with patch.dict("sys.modules", {
                "cube_extractor": MagicMock(
                    extract_cube_definition=MagicMock(return_value={"id": "C1"}),
                ),
            }):
                ext._extract_cubes()

        assert results == []  # Errors just skip the cube


# ── _extract_filters ─────────────────────────────────────────────

class TestExtractFiltersInternal:

    def test_extract_filters_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)):
            ext._extract_filters()

        assert (tmp_path / "filters.json").exists()


# ── _extract_prompts ─────────────────────────────────────────────

class TestExtractPromptsInternal:

    def test_extract_prompts_creates_empty_if_missing(self, tmp_path):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)):
            ext._extract_prompts()

        assert (tmp_path / "prompts.json").exists()

    def test_extract_prompts_does_not_overwrite(self, tmp_path):
        (tmp_path / "prompts.json").write_text('[{"id": "P1"}]', encoding="utf-8")

        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = MagicMock()
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)):
            ext._extract_prompts()

        data = json.loads((tmp_path / "prompts.json").read_text(encoding="utf-8"))
        assert data == [{"id": "P1"}]


# ── _extract_security_filters ────────────────────────────────────

class TestExtractSecurityFiltersInternal:

    def test_extract_security_filters_writes_json(self, tmp_path, mock_client):
        ext = MstrExtractor.__new__(MstrExtractor)
        ext.client = mock_client
        ext.project_name = "Test"

        with patch("microstrategy_export.extract_mstr_data._OUTPUT_DIR", str(tmp_path)), \
             patch("microstrategy_export.extract_mstr_data._write_json") as mock_write:
            with patch.dict("sys.modules", {
                "security_extractor": MagicMock(
                    extract_security_filters=MagicMock(return_value=[]),
                ),
            }):
                ext._extract_security_filters()

        written_files = [c[0][0] for c in mock_write.call_args_list]
        assert "security_filters.json" in written_files
