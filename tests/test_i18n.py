"""
Tests for v8.0 — Multi-Language & Localization (i18n).

Covers:
- Culture parsing and validation
- RTL detection
- Locale-aware format strings (currency, date, number)
- Culture TMDL generation
- Translation TMDL generation
- Culture extraction from data
- Visual generator RTL support
- PBIP generator culture wiring
- CLI --cultures flag parsing
"""

import json
import os
import pytest

from powerbi_import.i18n import (
    parse_cultures,
    get_primary_culture,
    is_rtl_culture,
    get_currency_format,
    get_number_format,
    get_date_format,
    convert_format_string_for_culture,
    generate_culture_tmdl,
    generate_translations_tmdl,
    extract_cultures_from_data,
)


# ── parse_cultures ───────────────────────────────────────────────

class TestParseCultures:
    def test_none_returns_default(self):
        assert parse_cultures(None) == ["en-US"]

    def test_empty_string_returns_default(self):
        assert parse_cultures("") == ["en-US"]

    def test_single_valid_culture(self):
        assert parse_cultures("fr-FR") == ["fr-FR"]

    def test_multiple_valid_cultures(self):
        result = parse_cultures("en-US,fr-FR,de-DE")
        assert result == ["en-US", "fr-FR", "de-DE"]

    def test_whitespace_stripped(self):
        result = parse_cultures("en-US , fr-FR , de-DE")
        assert result == ["en-US", "fr-FR", "de-DE"]

    def test_unsupported_culture_skipped(self):
        result = parse_cultures("en-US,xx-XX")
        assert result == ["en-US"]

    def test_all_unsupported_returns_default(self):
        result = parse_cultures("xx-XX,yy-YY")
        assert result == ["en-US"]

    def test_prefix_matching(self):
        result = parse_cultures("fr")
        assert len(result) == 1
        assert result[0].startswith("fr-")

    def test_preserves_order(self):
        result = parse_cultures("ja-JP,en-US,fr-FR")
        assert result == ["ja-JP", "en-US", "fr-FR"]


# ── get_primary_culture ──────────────────────────────────────────

class TestGetPrimaryCulture:
    def test_returns_first(self):
        assert get_primary_culture(["fr-FR", "de-DE"]) == "fr-FR"

    def test_none_returns_default(self):
        assert get_primary_culture(None) == "en-US"

    def test_empty_list_returns_default(self):
        assert get_primary_culture([]) == "en-US"


# ── is_rtl_culture ───────────────────────────────────────────────

class TestIsRtlCulture:
    @pytest.mark.parametrize("culture", ["ar-SA", "he-IL", "fa-IR", "ur-PK"])
    def test_rtl_cultures(self, culture):
        assert is_rtl_culture(culture) is True

    @pytest.mark.parametrize("culture", ["en-US", "fr-FR", "de-DE", "ja-JP", "zh-CN"])
    def test_ltr_cultures(self, culture):
        assert is_rtl_culture(culture) is False

    def test_none(self):
        assert is_rtl_culture(None) is False

    def test_empty(self):
        assert is_rtl_culture("") is False

    def test_unknown_arabic_prefix(self):
        assert is_rtl_culture("ar-EG") is True


# ── Format helpers ───────────────────────────────────────────────

class TestCurrencyFormat:
    def test_usd(self):
        assert get_currency_format("en-US") == "$#,##0.00"

    def test_eur(self):
        result = get_currency_format("fr-FR")
        assert "€" in result

    def test_gbp(self):
        assert "£" in get_currency_format("en-GB")

    def test_jpy(self):
        assert "¥" in get_currency_format("ja-JP")

    def test_unknown_defaults_to_dollar(self):
        assert get_currency_format("xx-XX") == "$#,##0.00"


class TestDateFormat:
    def test_us(self):
        assert get_date_format("en-US") == "M/d/yyyy"

    def test_german(self):
        assert get_date_format("de-DE") == "dd.MM.yyyy"

    def test_japanese(self):
        assert get_date_format("ja-JP") == "yyyy/MM/dd"

    def test_korean(self):
        assert get_date_format("ko-KR") == "yyyy-MM-dd"

    def test_unknown_defaults_to_iso(self):
        assert get_date_format("xx-XX") == "yyyy-MM-dd"


class TestNumberFormat:
    def test_returns_standard_pattern(self):
        result = get_number_format("en-US")
        assert "#" in result or "0" in result


# ── convert_format_string_for_culture ────────────────────────────

class TestConvertFormatStringForCulture:
    def test_currency_en_us(self):
        result = convert_format_string_for_culture("currency", "en-US")
        assert "$" in result

    def test_currency_fr_fr(self):
        result = convert_format_string_for_culture("currency", "fr-FR")
        assert "€" in result

    def test_fixed(self):
        result = convert_format_string_for_culture("fixed", "de-DE")
        assert "#,##0.00" == result

    def test_percent(self):
        assert convert_format_string_for_culture("percent", "en-US") == "0.00%"

    def test_scientific(self):
        assert convert_format_string_for_culture("scientific", "en-US") == "0.00E+00"

    def test_general(self):
        assert convert_format_string_for_culture("general", "en-US") == ""

    def test_date_en_us(self):
        result = convert_format_string_for_culture("date", "en-US")
        assert result == "M/d/yyyy"

    def test_date_de_de(self):
        result = convert_format_string_for_culture("date", "de-DE")
        assert result == "dd.MM.yyyy"

    def test_time(self):
        assert convert_format_string_for_culture("time", "en-US") == "HH:mm:ss"

    def test_datetime_includes_date_and_time(self):
        result = convert_format_string_for_culture("datetime", "en-US")
        assert "M/d/yyyy" in result
        assert "HH:mm:ss" in result

    def test_raw_pattern_passthrough(self):
        assert convert_format_string_for_culture("#,##0.0", "en-US") == "#,##0.0"

    def test_empty_returns_empty(self):
        assert convert_format_string_for_culture("", "en-US") == ""

    def test_none_returns_empty(self):
        assert convert_format_string_for_culture(None, "en-US") == ""


# ── generate_culture_tmdl ────────────────────────────────────────

class TestGenerateCultureTmdl:
    def test_single_culture_returns_empty(self):
        assert generate_culture_tmdl(["en-US"]) == ""

    def test_none_returns_empty(self):
        assert generate_culture_tmdl(None) == ""

    def test_multi_culture_contains_culture_block(self):
        result = generate_culture_tmdl(["en-US", "fr-FR"])
        assert "culture fr-FR" in result
        assert "linguisticMetadata" in result

    def test_primary_culture_not_in_output(self):
        result = generate_culture_tmdl(["en-US", "fr-FR", "de-DE"])
        assert "culture en-US" not in result
        assert "culture fr-FR" in result
        assert "culture de-DE" in result

    def test_three_cultures(self):
        result = generate_culture_tmdl(["en-US", "fr-FR", "ja-JP"])
        assert result.count("culture ") == 2

    def test_language_code_in_metadata(self):
        result = generate_culture_tmdl(["en-US", "ja-JP"])
        assert '"Language":"ja"' in result


# ── generate_translations_tmdl ───────────────────────────────────

class TestGenerateTranslationsTmdl:
    def test_single_culture_returns_empty(self):
        assert generate_translations_tmdl(["en-US"], [], []) == ""

    def test_table_translations(self):
        tables = [{"name": "Sales", "columns": [{"name": "Region"}]}]
        result = generate_translations_tmdl(["en-US", "fr-FR"], tables, [])
        assert "translation Sales" in result
        assert "translatedCaption: Sales" in result
        assert "translation Region" in result

    def test_measure_translations(self):
        measures = [{"name": "Revenue"}]
        result = generate_translations_tmdl(["en-US", "fr-FR"], [], measures)
        assert "translation Revenue" in result

    def test_no_data_still_has_culture_header(self):
        result = generate_translations_tmdl(["en-US", "fr-FR"], [], [])
        assert "culture fr-FR" in result


# ── extract_cultures_from_data ───────────────────────────────────

class TestExtractCulturesFromData:
    def test_empty_data_returns_default(self):
        assert extract_cultures_from_data({}) == ["en-US"]

    def test_extracts_from_datasource_locale(self):
        data = {"datasources": [{"db_connection": {"locale": "fr-FR"}}]}
        result = extract_cultures_from_data(data)
        assert "fr-FR" in result

    def test_extracts_from_dossier_language(self):
        data = {"dossiers": [{"language": "de-DE"}]}
        result = extract_cultures_from_data(data)
        assert "de-DE" in result

    def test_extracts_from_report_language(self):
        data = {"reports": [{"language": "ja-JP"}]}
        result = extract_cultures_from_data(data)
        assert "ja-JP" in result

    def test_deduplicates(self):
        data = {
            "datasources": [{"db_connection": {"locale": "fr-FR"}}],
            "dossiers": [{"language": "fr-FR"}],
        }
        result = extract_cultures_from_data(data)
        assert result.count("fr-FR") == 1

    def test_sorted(self):
        data = {
            "dossiers": [{"language": "fr-FR"}],
            "reports": [{"language": "de-DE"}],
        }
        result = extract_cultures_from_data(data)
        assert result == sorted(result)


# ── Visual generator RTL support ─────────────────────────────────

class TestVisualGeneratorRtl:
    def test_scale_position_ltr(self):
        from powerbi_import.visual_generator import _scale_position
        pos = {"x": 0, "y": 0, "width": 512, "height": 384}
        result = _scale_position(pos, 1024, 768)
        assert result["x"] == 0
        assert result["width"] == 640

    def test_scale_position_rtl_mirrors_x(self):
        from powerbi_import.visual_generator import _scale_position
        pos = {"x": 0, "y": 0, "width": 512, "height": 384}
        result = _scale_position(pos, 1024, 768, rtl=True)
        # Mirrored: x = 1280 - (0 + 640) = 640
        assert result["x"] == 640
        assert result["width"] == 640

    def test_scale_position_rtl_right_side_to_left(self):
        from powerbi_import.visual_generator import _scale_position
        pos = {"x": 512, "y": 0, "width": 512, "height": 384}
        result = _scale_position(pos, 1024, 768, rtl=True)
        # Scaled: x=640, w=640. Mirrored: x = 1280 - (640+640) = 0
        assert result["x"] == 0

    def test_scale_position_empty_pos(self):
        from powerbi_import.visual_generator import _scale_position
        result = _scale_position({}, 1024, 768, rtl=True)
        assert result["x"] == 0  # full-width, RTL mirror still x=0
        assert result["width"] == 1280

    def test_build_page_json_ltr(self):
        from powerbi_import.visual_generator import _build_page_json
        page = _build_page_json("p1", "Page 1", [])
        assert "textDirection" not in page

    def test_build_page_json_rtl(self):
        from powerbi_import.visual_generator import _build_page_json
        page = _build_page_json("p1", "Page 1", [], rtl=True)
        assert page["textDirection"] == "RTL"


# ── PBIP generator culture wiring ────────────────────────────────

class TestPbipGeneratorCultures:
    def test_generate_pbip_with_cultures(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = {
            "datasources": [{"name": "Sales", "db_type": "sql_server",
                            "db_connection": {"host": "localhost", "database": "testdb"},
                            "columns": [{"name": "Region", "data_type": "string"}]}],
            "attributes": [],
            "facts": [],
            "metrics": [],
            "derived_metrics": [],
            "hierarchies": [],
            "relationships": [],
            "security_filters": [],
            "freeform_sql": [],
            "dossiers": [],
            "reports": [],
            "filters": [],
            "prompts": [],
            "custom_groups": [],
            "consolidations": [],
            "thresholds": [],
            "subtotals": [],
        }
        stats = generate_pbip(data, str(tmp_path), report_name="Test",
                              cultures=["en-US", "fr-FR"])
        assert stats["tables"] >= 1

        # Check model.tmdl uses primary culture
        model_path = tmp_path / "Test.SemanticModel" / "definition" / "model.tmdl"
        content = model_path.read_text(encoding="utf-8")
        assert "en-US" in content

        # Check cultures.tmdl exists for multi-culture
        cultures_path = tmp_path / "Test.SemanticModel" / "definition" / "cultures.tmdl"
        assert cultures_path.exists()
        culture_content = cultures_path.read_text(encoding="utf-8")
        assert "culture fr-FR" in culture_content

    def test_generate_pbip_single_culture_no_cultures_file(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = {
            "datasources": [{"name": "Sales", "db_type": "sql_server",
                            "db_connection": {"host": "localhost", "database": "testdb"},
                            "columns": [{"name": "Amount", "data_type": "double"}]}],
            "attributes": [], "facts": [], "metrics": [], "derived_metrics": [],
            "hierarchies": [], "relationships": [], "security_filters": [],
            "freeform_sql": [], "dossiers": [], "reports": [], "filters": [],
            "prompts": [], "custom_groups": [], "consolidations": [],
            "thresholds": [], "subtotals": [],
        }
        generate_pbip(data, str(tmp_path), report_name="Test",
                      cultures=["en-US"])
        cultures_path = tmp_path / "Test.SemanticModel" / "definition" / "cultures.tmdl"
        assert not cultures_path.exists()

    def test_generate_pbip_rtl_culture_page(self, tmp_path):
        from powerbi_import.pbip_generator import generate_pbip
        data = {
            "datasources": [{"name": "Sales", "db_type": "sql_server",
                            "db_connection": {"host": "localhost", "database": "testdb"},
                            "columns": [{"name": "Amount", "data_type": "double"}]}],
            "attributes": [], "facts": [], "metrics": [], "derived_metrics": [],
            "hierarchies": [], "relationships": [], "security_filters": [],
            "freeform_sql": [],
            "dossiers": [{
                "name": "Arabic Dashboard",
                "chapters": [{
                    "name": "Ch1",
                    "pages": [{
                        "key": "page1",
                        "name": "Overview",
                        "layout": {"width": 1024, "height": 768},
                        "visualizations": [{
                            "key": "v1",
                            "viz_type": "vertical_bar",
                            "data": {"attributes": [{"name": "Region"}],
                                    "metrics": [{"name": "Sales"}]},
                            "position": {"x": 0, "y": 0, "width": 512, "height": 384},
                            "formatting": {},
                        }],
                        "selectors": [],
                        "panel_stacks": [],
                    }],
                }],
            }],
            "reports": [], "filters": [], "prompts": [], "custom_groups": [],
            "consolidations": [], "thresholds": [], "subtotals": [],
        }
        generate_pbip(data, str(tmp_path), report_name="ArabicTest",
                      cultures=["ar-SA"])

        # Find the page.json and check for RTL
        pages_dir = tmp_path / "ArabicTest.Report" / "definition" / "pages"
        if pages_dir.exists():
            for page_dir in pages_dir.iterdir():
                page_json_path = page_dir / "page.json"
                if page_json_path.exists():
                    page_data = json.loads(page_json_path.read_text(encoding="utf-8"))
                    assert page_data.get("textDirection") == "RTL"


# ── generate_all_visuals with cultures ───────────────────────────

class TestGenerateAllVisualsWithCultures:
    def test_ltr_culture_no_text_direction(self, tmp_path):
        from powerbi_import.visual_generator import generate_all_visuals
        data = {
            "dossiers": [{
                "chapters": [{
                    "name": "Ch1",
                    "pages": [{
                        "key": "p1", "name": "Page",
                        "layout": {"width": 1024, "height": 768},
                        "visualizations": [],
                        "selectors": [],
                        "panel_stacks": [],
                    }],
                }],
            }],
            "reports": [],
        }
        generate_all_visuals(data, str(tmp_path), cultures=["en-US"])
        page_json = json.loads(
            (tmp_path / "pages" / "p1" / "page.json").read_text(encoding="utf-8"))
        assert "textDirection" not in page_json

    def test_rtl_culture_sets_text_direction(self, tmp_path):
        from powerbi_import.visual_generator import generate_all_visuals
        data = {
            "dossiers": [{
                "chapters": [{
                    "name": "Ch1",
                    "pages": [{
                        "key": "p1", "name": "Page",
                        "layout": {"width": 1024, "height": 768},
                        "visualizations": [],
                        "selectors": [],
                        "panel_stacks": [],
                    }],
                }],
            }],
            "reports": [],
        }
        generate_all_visuals(data, str(tmp_path), cultures=["ar-SA"])
        page_json = json.loads(
            (tmp_path / "pages" / "p1" / "page.json").read_text(encoding="utf-8"))
        assert page_json["textDirection"] == "RTL"

    def test_cultures_none_backward_compatible(self, tmp_path):
        from powerbi_import.visual_generator import generate_all_visuals
        data = {"dossiers": [], "reports": []}
        stats = generate_all_visuals(data, str(tmp_path))
        assert stats["pages"] == 0

    def test_cultures_empty_list_backward_compatible(self, tmp_path):
        from powerbi_import.visual_generator import generate_all_visuals
        data = {"dossiers": [], "reports": []}
        stats = generate_all_visuals(data, str(tmp_path), cultures=[])
        assert stats["pages"] == 0


# ── tmdl_generator culture-aware format ──────────────────────────

class TestTmdlGeneratorCultureFormat:
    def test_convert_format_string_culture_none_uses_default(self):
        from powerbi_import.tmdl_generator import _convert_format_string
        result = _convert_format_string("currency")
        assert "$" in result

    def test_convert_format_string_with_culture(self):
        from powerbi_import.tmdl_generator import _convert_format_string
        result = _convert_format_string("currency", culture="fr-FR")
        assert "€" in result

    def test_convert_format_string_date_culture(self):
        from powerbi_import.tmdl_generator import _convert_format_string
        result = _convert_format_string("date", culture="de-DE")
        assert result == "dd.MM.yyyy"


# ── CLI --cultures flag ──────────────────────────────────────────

class TestCliCulturesFlag:
    def test_parser_has_cultures_flag(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--cultures", "en-US,fr-FR,de-DE"])
        assert args.cultures == "en-US,fr-FR,de-DE"

    def test_parser_cultures_default_none(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args([])
        assert args.cultures is None

    def test_parser_culture_singular_still_works(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(["--culture", "fr-FR"])
        assert args.culture == "fr-FR"


# ── Version check ────────────────────────────────────────────────

class TestVersion:
    def test_version_8(self):
        from migrate import build_parser
        parser = build_parser()
        for action in parser._actions:
            if hasattr(action, 'version') and action.version:
                assert "19.0.0" in action.version
                return
        pytest.fail("No version action found")
