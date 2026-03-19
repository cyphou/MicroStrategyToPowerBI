"""Tests for dossier extractor module."""

import pytest

from microstrategy_export.dossier_extractor import extract_dossier_definition


class TestExtractDossierDefinition:

    def _build_summary_map(self, api_dossiers):
        return {s["id"]: s for s in api_dossiers.get("list", [])}

    def test_extracts_dossier(self, mock_client, api_dossiers):
        defs = api_dossiers.get("definitions", {})
        summary_map = self._build_summary_map(api_dossiers)
        for dossier_id, dossier_def in defs.items():
            summary = summary_map.get(dossier_id, dossier_def)
            result = extract_dossier_definition(dossier_def, summary)
            assert "name" in result
            assert "chapters" in result

    def test_dossier_has_chapters(self, mock_client, api_dossiers):
        defs = api_dossiers.get("definitions", {})
        summary_map = self._build_summary_map(api_dossiers)
        for dossier_id, dossier_def in defs.items():
            summary = summary_map.get(dossier_id, dossier_def)
            result = extract_dossier_definition(dossier_def, summary)
            chapters = result.get("chapters", [])
            assert len(chapters) >= 1

    def test_chapter_has_pages(self, mock_client, api_dossiers):
        defs = api_dossiers.get("definitions", {})
        summary_map = self._build_summary_map(api_dossiers)
        for dossier_id, dossier_def in defs.items():
            summary = summary_map.get(dossier_id, dossier_def)
            result = extract_dossier_definition(dossier_def, summary)
            for chapter in result.get("chapters", []):
                pages = chapter.get("pages", [])
                assert len(pages) >= 1

    def test_page_has_visualizations(self, mock_client, api_dossiers):
        defs = api_dossiers.get("definitions", {})
        summary_map = self._build_summary_map(api_dossiers)
        for dossier_id, dossier_def in defs.items():
            summary = summary_map.get(dossier_id, dossier_def)
            result = extract_dossier_definition(dossier_def, summary)
            for chapter in result.get("chapters", []):
                for page in chapter.get("pages", []):
                    vizs = page.get("visualizations", [])
                    assert len(vizs) >= 1
