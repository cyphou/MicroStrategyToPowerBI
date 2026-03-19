"""Tests for validator.py — TMDL, PBIR, cycle detection, and project validation."""

import json
import os
import pathlib

import pytest

from powerbi_import.validator import (
    validate_project,
    validate_tmdl_file,
    validate_report_json,
    validate_page_json,
    detect_relationship_cycles,
    validate_dax_references,
)


# ═══════════════════════════════════════════════════════════════════
#  TMDL File Validation
# ═══════════════════════════════════════════════════════════════════


class TestValidateTmdlFile:
    """Test validate_tmdl_file() for individual table TMDL parsing."""

    def test_valid_table_with_columns(self, tmp_path):
        tmdl = (
            "table Sales\n"
            "\tcolumn OrderID\n"
            "\t\tdataType: int64\n"
            "\t\tsourceColumn: OrderID\n"
            "\t\tlineageTag: abc-123\n"
            "\tcolumn Amount\n"
            "\t\tdataType: double\n"
            "\t\tsourceColumn: Amount\n"
        )
        p = tmp_path / "Sales.tmdl"
        p.write_text(tmdl, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert info["name"] == "Sales"
        assert "OrderID" in info["columns"]
        assert "Amount" in info["columns"]

    def test_valid_table_with_measures(self, tmp_path):
        tmdl = (
            "table Sales\n"
            "\tmeasure 'Total Sales'\n"
            "\t\texpression = SUM(Sales[Amount])\n"
        )
        p = tmp_path / "Sales.tmdl"
        p.write_text(tmdl, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert "Total Sales" in info["measures"]

    def test_missing_table_declaration(self, tmp_path):
        p = tmp_path / "orphan.tmdl"
        p.write_text("column ABC", encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert any("missing table declaration" in e for e in errors)
        assert info is None

    def test_invalid_datatype(self, tmp_path):
        tmdl = (
            "table T1\n"
            "\tcolumn C1\n"
            "\t\tdataType: bigint\n"
        )
        p = tmp_path / "T1.tmdl"
        p.write_text(tmdl, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert any("invalid dataType 'bigint'" in e for e in errors)

    def test_all_valid_datatypes(self, tmp_path):
        lines = ["table AllTypes"]
        for i, dt in enumerate(("int64", "double", "decimal", "string", "dateTime", "boolean")):
            lines.append(f"\tcolumn C{i}")
            lines.append(f"\t\tdataType: {dt}")
        p = tmp_path / "AllTypes.tmdl"
        p.write_text("\n".join(lines), encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert len(info["columns"]) == 6

    def test_no_columns_or_measures_warning(self, tmp_path):
        p = tmp_path / "empty.tmdl"
        p.write_text("table EmptyTable\n", encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert any("no columns or measures" in w for w in warnings)

    def test_unreadable_file(self, tmp_path):
        fake = tmp_path / "nope.tmdl"
        errors, warnings, info = validate_tmdl_file(str(fake))
        assert len(errors) == 1
        assert "cannot read" in errors[0]
        assert info is None

    def test_quoted_table_name(self, tmp_path):
        tmdl = "table 'My Table'\n\tcolumn ID\n\t\tdataType: int64\n"
        p = tmp_path / "MyTable.tmdl"
        p.write_text(tmdl, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert info["name"] == "My Table"

    def test_columns_and_measures_coexist(self, tmp_path):
        tmdl = (
            "table Dual\n"
            "\tcolumn A\n"
            "\t\tdataType: string\n"
            "\tmeasure M1\n"
            "\t\texpression = COUNTROWS(Dual)\n"
        )
        p = tmp_path / "Dual.tmdl"
        p.write_text(tmdl, encoding="utf-8")
        errors, warnings, info = validate_tmdl_file(str(p))
        assert errors == []
        assert "A" in info["columns"]
        assert "M1" in info["measures"]


# ═══════════════════════════════════════════════════════════════════
#  Report JSON Validation
# ═══════════════════════════════════════════════════════════════════


class TestValidateReportJson:
    """Test validate_report_json() for PBIR v4.0 manifest."""

    def test_valid_report(self, tmp_path):
        report = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
            "version": "4.0",
        }
        p = tmp_path / "report.json"
        p.write_text(json.dumps(report), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert errors == []

    def test_missing_schema_key(self, tmp_path):
        p = tmp_path / "report.json"
        p.write_text(json.dumps({"version": "4.0"}), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert any("$schema" in e for e in errors)

    def test_missing_version_key(self, tmp_path):
        # version is no longer required in PBIR v2.0.0 report.json
        p = tmp_path / "report.json"
        p.write_text(json.dumps({"$schema": "x"}), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert errors == []

    def test_wrong_version(self, tmp_path):
        # version field is no longer validated in PBIR v2.0.0
        p = tmp_path / "report.json"
        p.write_text(json.dumps({"$schema": "x", "version": "3.0"}), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert errors == []

    def test_version_40_ok(self, tmp_path):
        p = tmp_path / "report.json"
        p.write_text(json.dumps({"$schema": "x", "version": "4.0"}), encoding="utf-8")
        errors = validate_report_json(str(p))
        assert errors == []

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "report.json"
        p.write_text("{broken", encoding="utf-8")
        errors = validate_report_json(str(p))
        assert any("invalid JSON" in e for e in errors)

    def test_empty_json_object(self, tmp_path):
        p = tmp_path / "report.json"
        p.write_text("{}", encoding="utf-8")
        errors = validate_report_json(str(p))
        assert len(errors) == 1  # missing $schema only (version no longer required)


# ═══════════════════════════════════════════════════════════════════
#  Page JSON Validation
# ═══════════════════════════════════════════════════════════════════


class TestValidatePageJson:
    """Test validate_page_json() for visual containers."""

    def _page(self, **kwargs):
        base = {
            "displayName": "Page 1",
            "visuals": [
                {"position": {"x": 0, "y": 0, "width": 100, "height": 100},
                 "visual": {"visualType": "barChart"}},
            ],
        }
        base.update(kwargs)
        return base

    def test_valid_page(self, tmp_path):
        p = tmp_path / "page.json"
        p.write_text(json.dumps(self._page()), encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert errors == []

    def test_missing_display_name(self, tmp_path):
        pg = self._page()
        del pg["displayName"]
        p = tmp_path / "page.json"
        p.write_text(json.dumps(pg), encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert any("displayName" in e for e in errors)

    def test_missing_visuals(self, tmp_path):
        # In PBIR v2.0.0, visuals are in separate files, not inline
        # page.json without visuals is valid
        pg = self._page()
        del pg["visuals"]
        p = tmp_path / "page.json"
        p.write_text(json.dumps(pg), encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert errors == []

    def test_visual_missing_position(self, tmp_path):
        # Set up visual in subfolder visuals/<id>/visual.json
        page_dir = tmp_path / "mypage"
        page_dir.mkdir()
        p = page_dir / "page.json"
        p.write_text(json.dumps({"displayName": "Page 1"}), encoding="utf-8")
        vis_dir = page_dir / "visuals" / "v1"
        vis_dir.mkdir(parents=True)
        (vis_dir / "visual.json").write_text(
            json.dumps({"visual": {"visualType": "bar"}}), encoding="utf-8"
        )
        errors, warnings = validate_page_json(str(p))
        assert any("position" in e for e in errors)

    def test_position_missing_dimension(self, tmp_path):
        page_dir = tmp_path / "mypage"
        page_dir.mkdir()
        p = page_dir / "page.json"
        p.write_text(json.dumps({"displayName": "Page 1"}), encoding="utf-8")
        vis_dir = page_dir / "visuals" / "v1"
        vis_dir.mkdir(parents=True)
        (vis_dir / "visual.json").write_text(
            json.dumps({"position": {"x": 0, "y": 0, "width": 100}}), encoding="utf-8"
        )
        errors, warnings = validate_page_json(str(p))
        assert any("height" in e for e in errors)

    def test_multiple_visuals(self, tmp_path):
        pg = self._page()
        pg["visuals"] = [
            {"position": {"x": 0, "y": 0, "width": 100, "height": 100}},
            {"position": {"x": 100, "y": 0, "width": 200, "height": 200}},
        ]
        p = tmp_path / "page.json"
        p.write_text(json.dumps(pg), encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert errors == []

    def test_invalid_json_page(self, tmp_path):
        p = tmp_path / "page.json"
        p.write_text("not json", encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert any("invalid JSON" in e for e in errors)

    def test_empty_visuals_list(self, tmp_path):
        pg = self._page()
        pg["visuals"] = []
        p = tmp_path / "page.json"
        p.write_text(json.dumps(pg), encoding="utf-8")
        errors, warnings = validate_page_json(str(p))
        assert errors == []


# ═══════════════════════════════════════════════════════════════════
#  Relationship Cycle Detection
# ═══════════════════════════════════════════════════════════════════


class TestCycleDetection:
    """Test detect_relationship_cycles() DFS algo."""

    def test_no_relationships(self):
        assert detect_relationship_cycles([]) == []

    def test_no_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
        ]
        assert detect_relationship_cycles(rels) == []

    def test_simple_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
            {"from_table": "C", "to_table": "A"},
        ]
        errors = detect_relationship_cycles(rels)
        assert len(errors) == 1
        assert "Circular" in errors[0]

    def test_self_cycle(self):
        rels = [{"from_table": "A", "to_table": "A"}]
        errors = detect_relationship_cycles(rels)
        assert len(errors) == 1
        assert "Circular" in errors[0]

    def test_diamond_no_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "A", "to_table": "C"},
            {"from_table": "B", "to_table": "D"},
            {"from_table": "C", "to_table": "D"},
        ]
        assert detect_relationship_cycles(rels) == []

    def test_disconnected_no_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "C", "to_table": "D"},
        ]
        assert detect_relationship_cycles(rels) == []

    def test_complex_cycle(self):
        rels = [
            {"from_table": "A", "to_table": "B"},
            {"from_table": "B", "to_table": "C"},
            {"from_table": "C", "to_table": "D"},
            {"from_table": "D", "to_table": "B"},  # cycle B→C→D→B
        ]
        errors = detect_relationship_cycles(rels)
        assert len(errors) >= 1
        assert any("Circular" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════
#  DAX Reference Validation
# ═══════════════════════════════════════════════════════════════════


class TestDaxReferences:
    """Test validate_dax_references() heuristic."""

    def test_empty_tables(self):
        assert validate_dax_references({}) == []

    def test_tables_no_issues(self):
        tables = {
            "Sales": {"columns": {"Amount", "Qty"}, "measures": {"Total"}},
        }
        assert validate_dax_references(tables) == []


# ═══════════════════════════════════════════════════════════════════
#  Full Project Validation
# ═══════════════════════════════════════════════════════════════════


class TestValidateProject:
    """Test validate_project() on assembled directories."""

    @pytest.fixture
    def valid_project(self, tmp_path):
        """Create a minimal valid .pbip project on disk."""
        name = "Test"
        # .pbip
        pbip = {"version": "1.0", "artifacts": [{"report": {"path": f"{name}.Report"},
                "semanticModel": {"path": f"{name}.SemanticModel"}}]}
        (tmp_path / f"{name}.pbip").write_text(json.dumps(pbip), encoding="utf-8")

        # SemanticModel
        sm = tmp_path / f"{name}.SemanticModel"
        sm.mkdir()
        (sm / ".platform").write_text(json.dumps({"metadata": {}}), encoding="utf-8")
        (sm / "definition.pbism").write_text(json.dumps({"version": "4.0"}), encoding="utf-8")
        defn = sm / "definition"
        defn.mkdir()
        (defn / "model.tmdl").write_text("model Test\n", encoding="utf-8")
        tables = defn / "tables"
        tables.mkdir()
        (tables / "Sales.tmdl").write_text(
            "table Sales\n\tcolumn ID\n\t\tdataType: int64\n\t\tsourceColumn: ID\n",
            encoding="utf-8",
        )
        (defn / "relationships.tmdl").write_text("", encoding="utf-8")
        (defn / "roles.tmdl").write_text("role Viewer\n", encoding="utf-8")

        # Report
        rpt = tmp_path / f"{name}.Report"
        rpt.mkdir()
        (rpt / ".platform").write_text(json.dumps({"metadata": {}}), encoding="utf-8")
        rpt_def = rpt / "definition"
        rpt_def.mkdir()
        (rpt_def / "report.json").write_text(json.dumps({
            "$schema": "https://…", "version": "4.0"
        }), encoding="utf-8")
        pages = rpt_def / "pages"
        pages.mkdir()
        p1 = pages / "page1"
        p1.mkdir()
        (p1 / "page.json").write_text(json.dumps({
            "displayName": "Page 1",
            "visuals": [
                {"position": {"x": 0, "y": 0, "width": 100, "height": 100}},
            ],
        }), encoding="utf-8")

        return tmp_path

    def test_valid_project_passes(self, valid_project):
        result = validate_project(str(valid_project))
        assert result["valid"] is True
        assert result["files_checked"] > 0
        assert result["errors"] == []

    def test_missing_pbip_file(self, tmp_path):
        result = validate_project(str(tmp_path))
        assert result["valid"] is False
        assert any("Missing .pbip" in e for e in result["errors"])

    def test_missing_semantic_model(self, tmp_path):
        (tmp_path / "X.pbip").write_text(json.dumps({"version": "1.0", "artifacts": []}), encoding="utf-8")
        (tmp_path / "X.Report").mkdir()
        rpt_def = tmp_path / "X.Report" / "definition"
        rpt_def.mkdir()
        (tmp_path / "X.Report" / ".platform").write_text(json.dumps({"metadata": {}}), encoding="utf-8")
        (rpt_def / "report.json").write_text(json.dumps({"$schema": "x", "version": "4.0"}), encoding="utf-8")
        result = validate_project(str(tmp_path))
        assert result["valid"] is False
        assert any("Missing .SemanticModel" in e for e in result["errors"])

    def test_missing_report(self, tmp_path):
        (tmp_path / "X.pbip").write_text(json.dumps({"version": "1.0", "artifacts": []}), encoding="utf-8")
        sm = tmp_path / "X.SemanticModel"
        sm.mkdir()
        (sm / ".platform").write_text(json.dumps({"metadata": {}}), encoding="utf-8")
        (sm / "definition.pbism").write_text(json.dumps({"version": "4.0"}), encoding="utf-8")
        defn = sm / "definition"
        defn.mkdir()
        (defn / "model.tmdl").write_text("model M\n", encoding="utf-8")
        result = validate_project(str(tmp_path))
        assert result["valid"] is False
        assert any("Missing .Report" in e for e in result["errors"])

    def test_invalid_tmdl_in_project(self, valid_project):
        # Inject an invalid TMDL file
        tables_dir = valid_project / "Test.SemanticModel" / "definition" / "tables"
        (tables_dir / "Bad.tmdl").write_text("no table here", encoding="utf-8")
        result = validate_project(str(valid_project))
        assert result["valid"] is False
        assert any("missing table declaration" in e for e in result["errors"])

    def test_invalid_datatype_in_project(self, valid_project):
        tables_dir = valid_project / "Test.SemanticModel" / "definition" / "tables"
        (tables_dir / "T2.tmdl").write_text(
            "table T2\n\tcolumn Foo\n\t\tdataType: nvarchar\n",
            encoding="utf-8",
        )
        result = validate_project(str(valid_project))
        assert result["valid"] is False
        assert any("invalid dataType" in e for e in result["errors"])

    def test_report_json_wrong_version_in_project(self, valid_project):
        # version field is no longer validated in PBIR v2.0.0
        rpt_json = valid_project / "Test.Report" / "definition" / "report.json"
        rpt_json.write_text(json.dumps({"$schema": "x", "version": "3.0"}), encoding="utf-8")
        result = validate_project(str(valid_project))
        assert result["valid"] is True

    def test_page_missing_display_name_in_project(self, valid_project):
        page_json = valid_project / "Test.Report" / "definition" / "pages" / "page1" / "page.json"
        page_json.write_text(json.dumps({
            "visuals": [
                {"position": {"x": 0, "y": 0, "width": 100, "height": 100}},
            ],
        }), encoding="utf-8")
        result = validate_project(str(valid_project))
        assert result["valid"] is False
        assert any("displayName" in e for e in result["errors"])

    def test_cycle_detected_in_project(self, valid_project):
        rel_path = valid_project / "Test.SemanticModel" / "definition" / "relationships.tmdl"
        content = (
            "relationship R1\n"
            "\tfromColumn: Sales.ID\n"
            "\ttoColumn: Orders.SaleID\n"
            "relationship R2\n"
            "\tfromColumn: Orders.SaleID\n"
            "\ttoColumn: Sales.ID\n"
        )
        tables_dir = valid_project / "Test.SemanticModel" / "definition" / "tables"
        (tables_dir / "Orders.tmdl").write_text(
            "table Orders\n\tcolumn SaleID\n\t\tdataType: int64\n",
            encoding="utf-8",
        )
        rel_path.write_text(content, encoding="utf-8")
        result = validate_project(str(valid_project))
        assert any("Circular" in e for e in result["errors"])

    def test_files_checked_count(self, valid_project):
        result = validate_project(str(valid_project))
        # pbip + .platform + pbism + model.tmdl + Sales.tmdl + relationships + roles
        # + rpt .platform + report.json + page.json = 10
        assert result["files_checked"] >= 8


# ═══════════════════════════════════════════════════════════════════
#  Assessment Tests
# ═══════════════════════════════════════════════════════════════════

from powerbi_import.assessment import assess_project


class TestAssessment:
    """Test assess_project() pre-migration assessment."""

    @pytest.fixture
    def sample_data(self):
        return {
            "datasources": [{"id": "ds1"}],
            "attributes": [{"id": "a1"}, {"id": "a2"}],
            "facts": [{"id": "f1"}],
            "metrics": [
                {"id": "m1", "metric_type": "simple", "expression": "Sum(Revenue)"},
                {"id": "m2", "metric_type": "compound", "expression": "ApplySimple(...)"},
            ],
            "derived_metrics": [
                {"id": "dm1", "expression": "RunningSum(Sales)"},
            ],
            "reports": [{"id": "r1"}],
            "dossiers": [{"id": "d1", "chapters": []}],
            "cubes": [],
            "prompts": [{"id": "p1"}],
            "security_filters": [{"id": "sf1"}],
            "custom_groups": [{"id": "cg1"}],
            "freeform_sql": [{"id": "fs1"}],
            "hierarchies": [{"id": "h1"}],
            "relationships": [{"id": "rel1"}],
            "filters": [],
        }

    def test_object_counts(self, sample_data):
        result = assess_project(sample_data)
        s = result["summary"]
        assert s["object_counts"]["attributes"] == 2
        assert s["object_counts"]["reports"] == 1
        assert s["object_counts"]["derived_metrics"] == 1
        assert s["total_objects"] > 0

    def test_complexity_score_not_zero(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["complexity_score"] > 0

    def test_complexity_level_present(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["complexity_level"] in ("low", "medium", "high", "very_high")

    def test_feature_detection_apply_simple(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["feature_support"].get("apply_simple_complex_sql") == "unsupported"

    def test_feature_detection_running_sum(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["feature_support"].get("olap_running_sum") == "approximated"

    def test_feature_detection_custom_groups(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["feature_support"].get("custom_groups") == "manual_review"

    def test_feature_detection_rls(self, sample_data):
        result = assess_project(sample_data)
        assert result["summary"]["feature_support"].get("row_level_security") == "approximated"

    def test_fidelity_estimate(self, sample_data):
        result = assess_project(sample_data)
        assert 0.0 <= result["summary"]["estimated_fidelity"] <= 1.0

    def test_recommendations_not_empty(self, sample_data):
        result = assess_project(sample_data)
        assert len(result["summary"]["recommendations"]) > 0

    def test_recommendation_apply_simple(self, sample_data):
        result = assess_project(sample_data)
        assert any("ApplySimple" in r for r in result["summary"]["recommendations"])

    def test_recommendation_custom_groups(self, sample_data):
        result = assess_project(sample_data)
        assert any("Custom groups" in r for r in result["summary"]["recommendations"])

    def test_recommendation_rls(self, sample_data):
        result = assess_project(sample_data)
        assert any("Security filters" in r or "RLS" in r for r in result["summary"]["recommendations"])

    def test_empty_project(self):
        result = assess_project({})
        s = result["summary"]
        assert s["total_objects"] == 0
        assert s["complexity_score"] == 0
        assert s["estimated_fidelity"] == 0.0

    def test_low_complexity(self):
        data = {
            "attributes": [{"id": "a"}],
            "facts": [{"id": "f"}],
            "metrics": [{"id": "m", "metric_type": "simple"}],
            "reports": [{"id": "r"}],
        }
        result = assess_project(data)
        assert result["summary"]["complexity_level"] == "low"

    def test_writes_json_report(self, sample_data, tmp_path):
        assess_project(sample_data, output_dir=str(tmp_path))
        rpt = tmp_path / "assessment_report.json"
        assert rpt.exists()
        report = json.loads(rpt.read_text(encoding="utf-8"))
        assert "summary" in report

    def test_writes_html_report(self, sample_data, tmp_path):
        assess_project(sample_data, output_dir=str(tmp_path))
        html = tmp_path / "assessment_report.html"
        assert html.exists()
        content = html.read_text(encoding="utf-8")
        assert "Pre-Migration Assessment" in content

    def test_html_contains_counts(self, sample_data, tmp_path):
        assess_project(sample_data, output_dir=str(tmp_path))
        html = (tmp_path / "assessment_report.html").read_text(encoding="utf-8")
        assert "attributes" in html

    def test_no_output_dir_no_file(self, sample_data, tmp_path):
        result = assess_project(sample_data)
        # Should work, just not write files
        assert "summary" in result

    def test_fidelity_penalty_unsupported(self):
        """Unsupported features reduce fidelity."""
        data = {
            "metrics": [{"id": "m", "expression": "ApplySimple(x)"}],
            "reports": [{"id": "r"}],
        }
        result = assess_project(data)
        assert result["summary"]["estimated_fidelity"] < 1.0

    def test_complexity_capped_at_100(self):
        """Very large projects cap at 100."""
        data = {
            "dossiers": [{"id": f"d{i}", "chapters": []} for i in range(50)],
            "custom_groups": [{"id": f"cg{i}"} for i in range(50)],
        }
        result = assess_project(data)
        assert result["summary"]["complexity_score"] == 100
        assert result["summary"]["complexity_level"] == "very_high"

    def test_no_risks_recommendation(self):
        """Clean project gets a confidence message."""
        data = {
            "attributes": [{"id": "a"}],
            "facts": [{"id": "f"}],
            "metrics": [],
        }
        result = assess_project(data)
        assert any("No major migration risks" in r for r in result["summary"]["recommendations"])
