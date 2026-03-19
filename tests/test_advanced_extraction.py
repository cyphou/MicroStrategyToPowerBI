"""Tests for advanced extraction: cubes, prompts, security filters."""

import pytest

from microstrategy_export.cube_extractor import extract_cube_definition
from microstrategy_export.prompt_extractor import extract_prompts
from microstrategy_export.security_extractor import extract_security_filters


class TestCubeExtractor:

    def _build_summary_map(self, api_cubes):
        return {s["id"]: s for s in api_cubes.get("list", [])}

    def test_extracts_cube(self, mock_client, api_cubes):
        defs = api_cubes.get("definitions", {})
        summary_map = self._build_summary_map(api_cubes)
        for cube_id, cube_def in defs.items():
            summary = summary_map.get(cube_id, cube_def)
            result = extract_cube_definition(cube_def, summary)
            assert "name" in result
            assert "attributes" in result or "metrics" in result

    def test_cube_has_attributes(self, mock_client, api_cubes):
        defs = api_cubes.get("definitions", {})
        summary_map = self._build_summary_map(api_cubes)
        for cube_id, cube_def in defs.items():
            summary = summary_map.get(cube_id, cube_def)
            result = extract_cube_definition(cube_def, summary)
            attrs = result.get("attributes", [])
            assert len(attrs) >= 1

    def test_cube_has_metrics(self, mock_client, api_cubes):
        defs = api_cubes.get("definitions", {})
        summary_map = self._build_summary_map(api_cubes)
        for cube_id, cube_def in defs.items():
            summary = summary_map.get(cube_id, cube_def)
            result = extract_cube_definition(cube_def, summary)
            metrics = result.get("metrics", [])
            assert len(metrics) >= 1


class TestPromptExtractor:

    def test_extracts_prompts(self, mock_client, api_prompts):
        prompts = extract_prompts(api_prompts)
        assert len(prompts) >= 1

    def test_prompt_has_type(self, mock_client, api_prompts):
        prompts = extract_prompts(api_prompts)
        for p in prompts:
            assert "type" in p or "prompt_type" in p
            assert "name" in p

    def test_prompt_pbi_mapping(self, mock_client, api_prompts):
        prompts = extract_prompts(api_prompts)
        for p in prompts:
            pbi_type = p.get("pbi_type", "")
            if pbi_type:
                assert pbi_type in (
                    "slicer", "what_if_parameter", "field_parameter",
                    "hierarchy_slicer", "date_slicer", "manual_review")


class TestSecurityExtractor:

    def test_extracts_security_filters(self, mock_client):
        filters = extract_security_filters(mock_client)
        assert isinstance(filters, list)

    def test_security_filter_has_expression(self, mock_client):
        filters = extract_security_filters(mock_client)
        for sf in filters:
            assert "expression" in sf or "name" in sf
