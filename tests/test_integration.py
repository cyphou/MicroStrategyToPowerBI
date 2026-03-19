"""End-to-end integration tests: intermediate JSON → generate_pbip → validate_project."""

import json
import os
import pathlib

import pytest

from powerbi_import.pbip_generator import generate_pbip
from powerbi_import.validator import validate_project
from powerbi_import.assessment import assess_project

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
#  E2E: generate → validate
# ═══════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Full pipeline: load fixtures → generate .pbip → validate project."""

    def test_generated_project_validates(self, data, tmp_path):
        """The generated .pbip project should pass validation."""
        generate_pbip(data, str(tmp_path), report_name="E2E")
        result = validate_project(str(tmp_path))
        # Allow warnings but no errors
        assert result["valid"] is True, f"Errors: {result['errors']}"
        assert result["files_checked"] > 0

    def test_generated_project_has_no_errors(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="E2E")
        result = validate_project(str(tmp_path))
        assert result["errors"] == []

    def test_generated_project_file_count(self, data, tmp_path):
        generate_pbip(data, str(tmp_path), report_name="E2E")
        result = validate_project(str(tmp_path))
        # At least .pbip + 2 .platform + pbism + model.tmdl
        # + at least 1 table + relationships + report.json
        assert result["files_checked"] >= 8

    def test_generated_tmdl_datatypes_valid(self, data, tmp_path):
        """All generated TMDL files should have valid data types."""
        generate_pbip(data, str(tmp_path), report_name="E2E")
        result = validate_project(str(tmp_path))
        datatype_errors = [e for e in result["errors"] if "invalid dataType" in e]
        assert datatype_errors == [], f"Invalid dataTypes: {datatype_errors}"

    def test_generated_report_version_40(self, data, tmp_path):
        """Generated report.json must be PBIR v4.0."""
        generate_pbip(data, str(tmp_path), report_name="E2E")
        report_json = tmp_path / "E2E.Report" / "definition" / "report.json"
        assert report_json.exists()
        rpt = json.loads(report_json.read_text(encoding="utf-8"))
        assert rpt.get("version") == "4.0"

    def test_no_relationship_cycles(self, data, tmp_path):
        """Generated relationships should not contain cycles."""
        generate_pbip(data, str(tmp_path), report_name="E2E")
        result = validate_project(str(tmp_path))
        cycle_errors = [e for e in result["errors"] if "Circular" in e]
        assert cycle_errors == []


# ═══════════════════════════════════════════════════════════════════
#  E2E: assessment on fixture data
# ═══════════════════════════════════════════════════════════════════


class TestAssessmentOnFixtures:
    """Run assessment on fixture intermediate data."""

    def test_assessment_runs(self, data):
        result = assess_project(data)
        assert result["total_objects"] > 0

    def test_assessment_writes_report(self, data, tmp_path):
        assess_project(data, output_dir=str(tmp_path))
        assert (tmp_path / "assessment_report.json").exists()
        assert (tmp_path / "assessment_report.html").exists()

    def test_assessment_fidelity_positive(self, data):
        result = assess_project(data)
        assert result["estimated_fidelity"] > 0.0

    def test_assessment_has_recommendations(self, data):
        result = assess_project(data)
        assert len(result["recommendations"]) >= 1
