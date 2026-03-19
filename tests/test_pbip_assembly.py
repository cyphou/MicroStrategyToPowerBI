"""Tests for PBIP assembly (pbip_generator) and migration report."""

import json
import os
import pathlib

import pytest

from powerbi_import.pbip_generator import generate_pbip
from powerbi_import.migration_report import (
    generate_migration_report,
    FULLY_MIGRATED,
    APPROXIMATED,
    MANUAL_REVIEW,
    UNSUPPORTED,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
INTERMEDIATE_DIR = FIXTURES_DIR / "intermediate_json"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def data():
    """Load all 18 intermediate JSON files into a dict."""
    file_map = {
        "datasources": "datasources.json",
        "attributes": "attributes.json",
        "facts": "facts.json",
        "metrics": "metrics.json",
        "derived_metrics": "derived_metrics.json",
        "reports": "reports.json",
        "dossiers": "dossiers.json",
        "cubes": "cubes.json",
        "filters": "filters.json",
        "prompts": "prompts.json",
        "custom_groups": "custom_groups.json",
        "consolidations": "consolidations.json",
        "hierarchies": "hierarchies.json",
        "relationships": "relationships.json",
        "security_filters": "security_filters.json",
        "freeform_sql": "freeform_sql.json",
        "thresholds": "thresholds.json",
        "subtotals": "subtotals.json",
    }
    d = {}
    for key, filename in file_map.items():
        path = INTERMEDIATE_DIR / filename
        raw = _load_json(path)
        d[key] = raw if isinstance(raw, list) else [raw]
    return d


# ═══════════════════════════════════════════════════════════════════
#  PBIP Generator Tests
# ═══════════════════════════════════════════════════════════════════


class TestPbipScaffold:
    """Test .pbip project folder structure."""

    def test_pbip_file_created(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="Test")
        assert (tmp_path / "Test.pbip").exists()

    def test_pbip_file_json_valid(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="Test")
        with open(tmp_path / "Test.pbip") as f:
            pbip = json.load(f)
        assert pbip["version"] == "1.0"
        assert len(pbip["artifacts"]) == 1
        assert pbip["artifacts"][0]["report"]["path"] == "Test.Report"
        assert "semanticModel" not in pbip["artifacts"][0]
        assert "$schema" in pbip
        assert "settings" in pbip

    def test_gitignore_created(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="Test")
        gi = tmp_path / ".gitignore"
        assert gi.exists()
        content = gi.read_text()
        assert ".pbi/" in content


class TestSemanticModelScaffold:
    """Test SemanticModel folder structure."""

    def test_sm_folder_exists(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        assert (tmp_path / "R.SemanticModel").is_dir()

    def test_platform_file(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        p = tmp_path / "R.SemanticModel" / ".platform"
        assert p.exists()
        obj = json.loads(p.read_text())
        assert obj["metadata"]["type"] == "SemanticModel"

    def test_pbism_file(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        p = tmp_path / "R.SemanticModel" / "definition.pbism"
        assert p.exists()
        obj = json.loads(p.read_text())
        assert obj["version"] == "4.2"
        assert "$schema" in obj
        assert obj["settings"]["qnaEnabled"] is True

    def test_model_tmdl(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        p = tmp_path / "R.SemanticModel" / "definition" / "model.tmdl"
        assert p.exists()
        content = p.read_text()
        assert "model Model" in content
        assert "culture: en-US" in content

    def test_tables_dir_exists(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        tables = tmp_path / "R.SemanticModel" / "definition" / "tables"
        assert tables.is_dir()
        assert len(list(tables.glob("*.tmdl"))) >= 5

    def test_relationships_tmdl(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        rel = tmp_path / "R.SemanticModel" / "definition" / "relationships.tmdl"
        # relationships.tmdl is only written if relationships exist
        if data.get("relationships"):
            assert rel.exists()

    def test_roles_tmdl(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        roles = tmp_path / "R.SemanticModel" / "definition" / "roles.tmdl"
        if data.get("security_filters"):
            assert roles.exists()


class TestReportScaffold:
    """Test Report folder structure."""

    def test_report_folder_exists(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        assert (tmp_path / "R.Report").is_dir()

    def test_report_platform_file(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        p = tmp_path / "R.Report" / ".platform"
        assert p.exists()
        obj = json.loads(p.read_text())
        assert obj["metadata"]["type"] == "Report"

    def test_report_json_exists(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        rj = tmp_path / "R.Report" / "definition" / "report.json"
        assert rj.exists()

    def test_pages_dir_has_pages(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        pages = tmp_path / "R.Report" / "definition" / "pages"
        assert pages.is_dir()
        page_dirs = [d for d in pages.iterdir() if d.is_dir()]
        assert len(page_dirs) >= 1

    def test_page_json_inside_page_folder(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="R")
        pages = tmp_path / "R.Report" / "definition" / "pages"
        page_dir = next(pages.iterdir())
        assert (page_dir / "page.json").exists()


class TestGenerateStats:
    """Test stats dict returned by generate_pbip."""

    def test_returns_dict(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert isinstance(stats, dict)

    def test_has_table_count(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert stats["tables"] >= 5

    def test_has_measure_count(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert stats["measures"] >= 1

    def test_has_page_count(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert stats["pages"] >= 1

    def test_has_visual_count(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert stats["visuals"] >= 1

    def test_warnings_is_list(self, data, tmp_path):
        stats = generate_pbip(data, str(tmp_path))
        assert isinstance(stats["warnings"], list)


class TestPbipEmptyData:
    """Edge case: empty or minimal data."""

    def test_empty_data_still_creates_scaffold(self, tmp_path):
        stats = generate_pbip({}, str(tmp_path), report_name="Empty")
        assert (tmp_path / "Empty.pbip").exists()
        assert (tmp_path / "Empty.SemanticModel").is_dir()
        assert (tmp_path / "Empty.Report").is_dir()
        assert stats["tables"] == 0

    def test_minimal_datasource(self, tmp_path):
        data = {"datasources": [{"name": "Tbl", "columns": []}]}
        stats = generate_pbip(data, str(tmp_path), report_name="Min")
        assert stats["tables"] >= 1


class TestPbipReportName:
    """Test report name affects folder naming."""

    def test_custom_name(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="Sales Dashboard")
        assert (tmp_path / "Sales Dashboard.pbip").exists()
        assert (tmp_path / "Sales Dashboard.SemanticModel").is_dir()
        assert (tmp_path / "Sales Dashboard.Report").is_dir()

    def test_logical_id_is_guid(self, data, tmp_path):
        import uuid
        generate_pbip(data, str(tmp_path), report_name="My Report")
        p = json.loads(
            (tmp_path / "My Report.SemanticModel" / ".platform").read_text()
        )
        # logicalId must be a valid GUID
        lid = p["config"]["logicalId"]
        parsed = uuid.UUID(lid)
        assert str(parsed) == lid


# ═══════════════════════════════════════════════════════════════════
#  Migration Report Tests
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_stats():
    return {
        "tables": 6,
        "columns": 30,
        "measures": 8,
        "relationships": 4,
        "hierarchies": 2,
        "roles": 1,
        "pages": 3,
        "visuals": 12,
        "slicers": 2,
        "warnings": [],
    }


class TestMigrationReportGeneration:
    """Test report file creation."""

    def test_json_report_created(self, data, sample_stats, tmp_path):
        generate_migration_report(data, sample_stats, str(tmp_path))
        assert (tmp_path / "migration_report.json").exists()

    def test_html_report_created(self, data, sample_stats, tmp_path):
        generate_migration_report(data, sample_stats, str(tmp_path))
        assert (tmp_path / "migration_report.html").exists()

    def test_json_report_valid(self, data, sample_stats, tmp_path):
        generate_migration_report(data, sample_stats, str(tmp_path))
        with open(tmp_path / "migration_report.json") as f:
            report = json.load(f)
        assert "summary" in report
        assert "objects" in report

    def test_html_report_has_title(self, data, sample_stats, tmp_path):
        generate_migration_report(data, sample_stats, str(tmp_path),
                                  report_name="My Report")
        html = (tmp_path / "migration_report.html").read_text()
        assert "My Report" in html


class TestMigrationReportSummary:
    """Test the summary section of the report."""

    def test_total_objects(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        assert report["summary"]["total_objects"] > 0

    def test_fidelity_score(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        score = report["summary"]["fidelity_score"]
        assert 0 <= score <= 1.0

    def test_fidelity_counts_present(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        fc = report["summary"]["fidelity_counts"]
        for level in [FULLY_MIGRATED, APPROXIMATED, MANUAL_REVIEW, UNSUPPORTED]:
            assert level in fc

    def test_generation_stats_in_summary(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        gen = report["summary"]["generation"]
        assert gen["tables"] == 6
        assert gen["measures"] == 8
        assert gen["pages"] == 3

    def test_type_counts(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        tc = report["summary"]["type_counts"]
        assert "metric" in tc or "attribute" in tc


class TestMigrationReportObjects:
    """Test the per-object details."""

    def test_objects_have_required_keys(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        for obj in report["objects"]:
            assert "type" in obj
            assert "name" in obj
            assert "fidelity" in obj

    def test_metrics_classified(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        metric_objs = [o for o in report["objects"] if o["type"] == "metric"]
        assert len(metric_objs) >= 1
        fidelities = {o["fidelity"] for o in metric_objs}
        assert fidelities <= {FULLY_MIGRATED, APPROXIMATED, MANUAL_REVIEW, UNSUPPORTED}

    def test_attributes_fully_migrated(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        attr_objs = [o for o in report["objects"] if o["type"] == "attribute"]
        assert all(o["fidelity"] == FULLY_MIGRATED for o in attr_objs)

    def test_security_filters_approximated(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        sf_objs = [o for o in report["objects"] if o["type"] == "security_filter"]
        if sf_objs:
            assert all(o["fidelity"] == APPROXIMATED for o in sf_objs)

    def test_custom_groups_manual_review(self, data, sample_stats, tmp_path):
        report = generate_migration_report(data, sample_stats, str(tmp_path))
        cg_objs = [o for o in report["objects"] if o["type"] == "custom_group"]
        if cg_objs:
            assert all(o["fidelity"] == MANUAL_REVIEW for o in cg_objs)


class TestMigrationReportEdgeCases:
    """Edge cases for report generation."""

    def test_empty_data(self, tmp_path):
        report = generate_migration_report({}, {"tables": 0}, str(tmp_path))
        assert report["summary"]["total_objects"] == 0
        assert report["summary"]["fidelity_score"] == 0

    def test_all_fully_migrated(self, tmp_path):
        data = {
            "attributes": [{"id": "1", "name": "A"}],
            "facts": [{"id": "2", "name": "F"}],
        }
        report = generate_migration_report(data, {"tables": 1}, str(tmp_path))
        assert report["summary"]["fidelity_score"] == 1.0

    def test_html_escapes_special_chars(self, tmp_path):
        data = {"attributes": [{"id": "1", "name": "<script>alert(1)</script>"}]}
        generate_migration_report(data, {}, str(tmp_path), report_name="Test")
        html = (tmp_path / "migration_report.html").read_text()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ═══════════════════════════════════════════════════════════════════
#  Full End-to-End Pipeline Test
# ═══════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Test the full pipeline: intermediate JSON → .pbip + report."""

    def test_full_pipeline(self, data, tmp_path):
        """Generate .pbip then migration report."""
        out = str(tmp_path / "output")
        stats = generate_pbip(data, out, report_name="E2E Test")

        # PBIP scaffold
        assert os.path.exists(os.path.join(out, "E2E Test.pbip"))
        assert os.path.isdir(os.path.join(out, "E2E Test.SemanticModel"))
        assert os.path.isdir(os.path.join(out, "E2E Test.Report"))

        # Migration report
        report = generate_migration_report(data, stats, out, report_name="E2E Test")
        assert (tmp_path / "output" / "migration_report.json").exists()
        assert (tmp_path / "output" / "migration_report.html").exists()
        assert report["summary"]["total_objects"] > 0

    def test_pipeline_stats_consistency(self, data, tmp_path):
        """Stats from generate_pbip feed correctly into report."""
        out = str(tmp_path)
        stats = generate_pbip(data, out, report_name="Cons")
        report = generate_migration_report(data, stats, out, report_name="Cons")
        gen = report["summary"]["generation"]
        assert gen["tables"] == stats["tables"]
        assert gen["measures"] == stats["measures"]
        assert gen["pages"] == stats["pages"]
        assert gen["visuals"] == stats["visuals"]

    def test_importer_class_e2e(self, all_intermediate_json, tmp_path):
        """Test through the PowerBIImporter class."""
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter(source_dir=str(all_intermediate_json))
        result = importer.import_all(
            report_name="ImporterTest",
            output_dir=str(tmp_path),
        )
        assert result
        assert result["tables"] >= 5
        assert result["pages"] >= 1
        assert result["status"] == "complete"
        # Check file structure
        assert (tmp_path / "ImporterTest.pbip").exists()
        assert (tmp_path / "ImporterTest.SemanticModel").is_dir()
        assert (tmp_path / "ImporterTest.Report").is_dir()
