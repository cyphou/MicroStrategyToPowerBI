"""
Tests for v7.0 features — AI-Assisted Migration (Sprints V + W).
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Sprint V — LLM Expression Converter
# ═══════════════════════════════════════════════════════════════════


class TestDAXValidation:
    """DAX syntax validation (Sprint V.1)."""

    def _validate(self, dax):
        from powerbi_import.ai_converter import validate_dax_syntax
        return validate_dax_syntax(dax)

    def test_valid_simple(self):
        r = self._validate("SUM([Revenue])")
        assert r["valid"] is True

    def test_valid_calculate(self):
        r = self._validate('CALCULATE(SUM([Sales]), Table[Year] = 2024)')
        assert r["valid"] is True

    def test_valid_if(self):
        r = self._validate('IF([Amount] > 0, DIVIDE([Cost], [Amount]), 0)')
        assert r["valid"] is True

    def test_valid_switch(self):
        r = self._validate('SWITCH(TRUE(), [Score] <= 50, "Low", "High")')
        assert r["valid"] is True

    def test_invalid_empty(self):
        r = self._validate("")
        assert r["valid"] is False

    def test_invalid_sql_select(self):
        r = self._validate("SELECT * FROM Sales")
        assert r["valid"] is False
        assert any("SQL" in e for e in r["errors"])

    def test_invalid_unbalanced_parens(self):
        r = self._validate("SUM([Revenue]")
        assert r["valid"] is False
        assert any("parenthes" in e.lower() for e in r["errors"])

    def test_invalid_extra_closing(self):
        r = self._validate("SUM([Revenue]))")
        assert r["valid"] is False

    def test_valid_with_comments(self):
        r = self._validate("/* AI comment */\nSUM([Amount])")
        assert r["valid"] is True

    def test_valid_var_return(self):
        r = self._validate("VAR __x = SUM([A])\nRETURN __x / 100")
        assert r["valid"] is True

    def test_valid_literal_only(self):
        r = self._validate("42")
        assert r["valid"] is True


class TestStripCodeFences:
    """Code fence removal from LLM output."""

    def test_strip_dax_fences(self):
        from powerbi_import.ai_converter import _strip_code_fences
        text = "```dax\nSUM([Revenue])\n```"
        assert _strip_code_fences(text) == "SUM([Revenue])"

    def test_strip_plain_fences(self):
        from powerbi_import.ai_converter import _strip_code_fences
        text = "```\nIF([A]>0,1,0)\n```"
        assert _strip_code_fences(text) == "IF([A]>0,1,0)"

    def test_no_fences(self):
        from powerbi_import.ai_converter import _strip_code_fences
        text = "SUM([Revenue])"
        assert _strip_code_fences(text) == "SUM([Revenue])"


class TestAnnotateDAX:
    """DAX annotation for AI-assisted expressions."""

    def test_annotate_ai(self):
        from powerbi_import.ai_converter import annotate_dax
        result = annotate_dax("SUM([A])", ai_assisted=True, confidence=0.85)
        assert "[AI-ASSISTED]" in result
        assert "85%" in result
        assert "SUM([A])" in result

    def test_no_annotate_non_ai(self):
        from powerbi_import.ai_converter import annotate_dax
        result = annotate_dax("SUM([A])", ai_assisted=False)
        assert "[AI-ASSISTED]" not in result
        assert result == "SUM([A])"


class TestAIConverterInit:
    """AIConverter initialization and config."""

    def test_init_defaults(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter()
        assert c.tokens_used == 0
        assert c.token_budget == 500_000
        assert isinstance(c._cache, dict)

    def test_init_custom_budget(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(token_budget=1000)
        assert c.token_budget == 1000

    def test_init_with_cache_dir(self):
        from powerbi_import.ai_converter import AIConverter
        with tempfile.TemporaryDirectory() as td:
            c = AIConverter(cache_dir=td)
            assert c._cache_path == os.path.join(td, "ai_cache.json")

    def test_load_existing_cache(self):
        from powerbi_import.ai_converter import AIConverter
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, "ai_cache.json")
            with open(cache_path, "w") as f:
                json.dump({"abc123": {"dax": "SUM([A])", "confidence": 0.9}}, f)
            c = AIConverter(cache_dir=td)
            assert len(c._cache) == 1

    def test_get_stats(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(token_budget=10000)
        stats = c.get_stats()
        assert stats["tokens_used"] == 0
        assert stats["token_budget"] == 10000
        assert stats["budget_remaining"] == 10000
        assert stats["cache_entries"] == 0


class TestAIConverterNoCredentials:
    """AIConverter behavior without credentials."""

    def test_no_endpoint_returns_manual_review(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(endpoint="", api_key="")
        result = c.convert('ApplySimple("COMPLEX SQL", Col1)')
        assert result["fidelity"] == "manual_review"
        assert result["ai_assisted"] is False
        assert "not configured" in result["warnings"][0].lower()

    def test_budget_exhausted(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(endpoint="http://test", api_key="key", token_budget=0)
        result = c.convert("SomeExpr")
        assert result["fidelity"] == "manual_review"
        assert "budget" in result["warnings"][0].lower()


class TestAIConverterCache:
    """AIConverter caching behavior."""

    def test_cache_hit(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter()
        key = c._cache_key('ApplySimple("test", Col1)')
        c._cache[key] = {"dax": "SUM([Col1])", "confidence": 0.9}
        result = c.convert('ApplySimple("test", Col1)')
        assert result["dax"] == "SUM([Col1])"
        assert result["ai_assisted"] is True
        assert any("CACHED" in w for w in result["warnings"])

    def test_cache_key_deterministic(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter()
        k1 = c._cache_key("SomeExpr")
        k2 = c._cache_key("SomeExpr")
        assert k1 == k2

    def test_cache_key_different_for_different_expr(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter()
        k1 = c._cache_key("Expr1")
        k2 = c._cache_key("Expr2")
        assert k1 != k2

    def test_save_cache_to_disk(self):
        from powerbi_import.ai_converter import AIConverter
        with tempfile.TemporaryDirectory() as td:
            c = AIConverter(cache_dir=td)
            c._cache["testkey"] = {"dax": "SUM([X])", "confidence": 0.8}
            c._save_cache()
            assert os.path.isfile(os.path.join(td, "ai_cache.json"))


class TestAIConverterBatch:
    """AIConverter batch conversion."""

    def test_batch_deduplicates(self):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter()
        # Pre-fill cache
        key = c._cache_key("Expr1")
        c._cache[key] = {"dax": "SUM([A])", "confidence": 0.9}

        expressions = [
            ("Expr1", {}),
            ("Expr1", {}),  # duplicate
            ("Expr1", {"table": "T"}),  # same expr, different context
        ]
        results = c.convert_batch(expressions)
        assert len(results) == 3
        # All should be the same cached result
        assert all(r["dax"] == "SUM([A])" for r in results)


class TestAIConverterWithMock:
    """AIConverter with mocked LLM API."""

    def _make_converter(self, mock_response_dax="SUM([Revenue])"):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(endpoint="http://mock.openai.com", api_key="test-key",
                        deployment="gpt4o", token_budget=100000)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": mock_response_dax}}],
            "usage": {"total_tokens": 150},
        }
        return c, mock_resp

    @patch("powerbi_import.ai_converter.requests.post")
    def test_successful_conversion(self, mock_post):
        c, mock_resp = self._make_converter("DIVIDE([Cost], [Revenue])")
        mock_post.return_value = mock_resp

        result = c.convert('ApplySimple("CASE WHEN #0 > 0 THEN #1/#0 END", Revenue, Cost)')
        assert result["ai_assisted"] is True
        assert "DIVIDE" in result["dax"]
        assert result["fidelity"] == "ai_assisted"
        assert c.tokens_used == 150

    @patch("powerbi_import.ai_converter.requests.post")
    def test_strips_code_fences(self, mock_post):
        c, mock_resp = self._make_converter("```dax\nSUM([A])\n```")
        mock_post.return_value = mock_resp

        result = c.convert("SomeExpr")
        assert result["dax"] == "SUM([A])"

    @patch("powerbi_import.ai_converter.requests.post")
    def test_invalid_dax_gets_manual_review(self, mock_post):
        c, mock_resp = self._make_converter("SELECT * FROM Sales")
        mock_post.return_value = mock_resp

        result = c.convert("SomeExpr")
        assert result["fidelity"] == "manual_review"

    @patch("powerbi_import.ai_converter.requests.post")
    def test_api_error_returns_manual_review(self, mock_post):
        from powerbi_import.ai_converter import AIConverter
        c = AIConverter(endpoint="http://mock", api_key="k", deployment="d")
        mock_post.side_effect = RuntimeError("Connection failed")

        result = c.convert("SomeExpr")
        assert result["fidelity"] == "manual_review"
        assert result["ai_assisted"] is False

    @patch("powerbi_import.ai_converter.requests.post")
    def test_confidence_scoring(self, mock_post):
        c, mock_resp = self._make_converter("CALCULATE(SUM([Sales]), Table[Year] = 2024)")
        mock_post.return_value = mock_resp

        result = c.convert("SomeExpr")
        assert 0.0 <= result["confidence"] <= 1.0
        # Valid DAX with known functions should score reasonably well
        assert result["confidence"] >= 0.5

    @patch("powerbi_import.ai_converter.requests.post")
    def test_result_cached_after_success(self, mock_post):
        c, mock_resp = self._make_converter("SUM([Amount])")
        mock_post.return_value = mock_resp

        c.convert("TestExpr")
        assert len(c._cache) == 1
        # Second call should use cache (no API call)
        mock_post.reset_mock()
        result2 = c.convert("TestExpr")
        mock_post.assert_not_called()
        assert result2["dax"] == "SUM([Amount])"


class TestExpressionConverterIntegration:
    """Integration: expression_converter → AI fallback."""

    def test_set_ai_converter(self):
        from microstrategy_export.expression_converter import set_ai_converter
        set_ai_converter(None)  # Should not raise

    @patch("powerbi_import.ai_converter.requests.post")
    def test_manual_review_triggers_ai_fallback(self, mock_post):
        from microstrategy_export.expression_converter import (
            convert_mstr_expression_to_dax, set_ai_converter,
        )
        from powerbi_import.ai_converter import AIConverter

        # Setup mock AI converter
        c = AIConverter(endpoint="http://mock", api_key="k", deployment="d")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "DIVIDE([PartialCount], [TotalCount])"}}],
            "usage": {"total_tokens": 100},
        }
        mock_post.return_value = mock_resp
        set_ai_converter(c)

        try:
            # ApplyAgg always returns manual_review in rule-based converter
            result = convert_mstr_expression_to_dax(
                'ApplyAgg("SUM(CASE WHEN #0 = 1 THEN #1 END)", Flag, Amount)'
            )
            assert result["ai_assisted"] is True
            assert "DIVIDE" in result["dax"]
        finally:
            set_ai_converter(None)

    def test_no_ai_converter_returns_manual_review(self):
        from microstrategy_export.expression_converter import (
            convert_mstr_expression_to_dax, set_ai_converter,
        )
        set_ai_converter(None)

        result = convert_mstr_expression_to_dax(
            'ApplyAgg("SUM(CASE WHEN #0 = 1 THEN #1 END)", Flag, Amount)'
        )
        assert result["fidelity"] == "manual_review"


# ═══════════════════════════════════════════════════════════════════
# Sprint W — Semantic Field Matching
# ═══════════════════════════════════════════════════════════════════


class TestNormalization:
    """Column name normalization."""

    def _normalize(self, name):
        from powerbi_import.semantic_matcher import _normalize
        return _normalize(name)

    def test_lowercase(self):
        assert "revenue" in self._normalize("Revenue")

    def test_underscore_split(self):
        n = self._normalize("customer_name")
        assert "customer" in n
        assert "name" in n

    def test_camelcase_split(self):
        n = self._normalize("customerName")
        assert "customer" in n
        assert "name" in n

    def test_abbreviation_expansion(self):
        n = self._normalize("CUST_ID")
        assert "customer" in n
        assert "identifier" in n

    def test_qty_expansion(self):
        n = self._normalize("order_qty")
        assert "quantity" in n

    def test_mixed_case_abbrev(self):
        n = self._normalize("CustAmt")
        assert "customer" in n
        assert "amount" in n


class TestLevenshtein:
    """Levenshtein distance computation."""

    def _lev(self, a, b):
        from powerbi_import.semantic_matcher import _levenshtein
        return _levenshtein(a, b)

    def test_identical(self):
        assert self._lev("abc", "abc") == 0

    def test_empty(self):
        assert self._lev("abc", "") == 3

    def test_one_edit(self):
        assert self._lev("cat", "car") == 1

    def test_two_edits(self):
        assert self._lev("kitten", "sitting") == 3

    def test_symmetric(self):
        assert self._lev("abc", "xyz") == self._lev("xyz", "abc")


class TestFindBestMatch:
    """Fuzzy column matching."""

    def test_exact_match(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("Revenue", ["Revenue", "Cost", "Quantity"])
        assert results[0]["name"] == "Revenue"
        assert results[0]["score"] == 1.0

    def test_case_insensitive(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("revenue", ["Revenue", "Cost"])
        assert results[0]["name"] == "Revenue"
        assert results[0]["score"] == 1.0

    def test_abbreviation_match(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("CustName", ["CustomerName", "OrderDate", "Amount"])
        assert results[0]["name"] == "CustomerName"
        assert results[0]["score"] >= 0.5

    def test_underscore_vs_camelcase(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("customer_id", ["CustomerId", "OrderId", "ProductName"])
        assert results[0]["name"] == "CustomerId"

    def test_no_match_below_threshold(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("XYZ", ["Revenue", "Cost"], threshold=0.8)
        assert len(results) == 0

    def test_top_n_limit(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("Amount",
                                  ["Amount", "TotalAmount", "NetAmount", "GrossAmount", "Qty"],
                                  top_n=2, threshold=0.3)
        assert len(results) <= 2

    def test_empty_candidates(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("Name", [])
        assert results == []

    def test_empty_name(self):
        from powerbi_import.semantic_matcher import find_best_match
        results = find_best_match("", ["A", "B"])
        assert results == []


class TestMatchSchemas:
    """Schema-level column matching."""

    def test_match_schemas(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas(
            ["CustName", "OrderAmt", "ShipDt"],
            ["CustomerName", "OrderAmount", "ShipDate", "ProductId"],
            threshold=0.3,
        )
        assert result["CustName"]["name"] == "CustomerName"
        assert result["OrderAmt"]["name"] == "OrderAmount"
        assert result["ShipDt"]["name"] == "ShipDate"

    def test_unmatched_returns_none(self):
        from powerbi_import.semantic_matcher import match_schemas
        result = match_schemas(["XYZ123"], ["Revenue"], threshold=0.8)
        assert result["XYZ123"] is None


class TestSuggestFixes:
    """Fix suggestions for manual-review items."""

    def test_suggest_column_replacements(self):
        from powerbi_import.semantic_matcher import suggest_fixes
        items = [{"expression": "IF([CustAmt] > 0, [CustAmt], 0)", "warnings": []}]
        columns = ["CustomerAmount", "OrderDate", "ProductName"]
        results = suggest_fixes(items, columns)
        assert len(results) == 1
        assert "CustAmt" in results[0]["suggestions"]
        assert results[0]["suggestions"]["CustAmt"][0]["name"] == "CustomerAmount"

    def test_no_refs_in_expression(self):
        from powerbi_import.semantic_matcher import suggest_fixes
        items = [{"expression": "BLANK()", "warnings": []}]
        results = suggest_fixes(items, ["A", "B"])
        assert len(results) == 1
        assert results[0]["suggestions"] == {}


class TestCorrectionStore:
    """Learned correction persistence."""

    def test_record_and_lookup(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        store = CorrectionStore()
        store.record("CustName", "CustomerName")
        assert store.lookup("CustName") == "CustomerName"

    def test_case_insensitive_lookup(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        store = CorrectionStore()
        store.record("custname", "CustomerName")
        # Lookup uses normalization — same normalized form
        result = store.lookup("custname")
        assert result == "CustomerName"

    def test_persist_to_disk(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "corrections.json")
            store = CorrectionStore(store_path=path)
            store.record("Amt", "Amount")
            assert os.path.isfile(path)

            # Reload
            store2 = CorrectionStore(store_path=path)
            assert store2.lookup("Amt") == "Amount"

    def test_get_all(self):
        from powerbi_import.semantic_matcher import CorrectionStore
        store = CorrectionStore()
        store.record("A", "Alpha")
        store.record("B", "Beta")
        all_items = store.get_all()
        assert len(all_items) == 2


# ═══════════════════════════════════════════════════════════════════
# CLI flags (v7.0)
# ═══════════════════════════════════════════════════════════════════


class TestCLIv7Args:
    """v7.0 CLI argument parsing."""

    def _parse(self, *cli_args):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from migrate import build_parser
        parser = build_parser()
        return parser.parse_args(list(cli_args))

    def test_ai_assist_flag(self):
        args = self._parse("--from-export", "test/", "--ai-assist")
        assert args.ai_assist is True

    def test_ai_endpoint(self):
        args = self._parse("--from-export", "test/",
                           "--ai-endpoint", "https://myoai.openai.azure.com/")
        assert args.ai_endpoint == "https://myoai.openai.azure.com/"

    def test_ai_key(self):
        args = self._parse("--from-export", "test/", "--ai-key", "sk-123")
        assert args.ai_key == "sk-123"

    def test_ai_deployment(self):
        args = self._parse("--from-export", "test/", "--ai-deployment", "gpt4o")
        assert args.ai_deployment == "gpt4o"

    def test_ai_budget_default(self):
        args = self._parse("--from-export", "test/")
        assert args.ai_budget == 500000

    def test_ai_budget_custom(self):
        args = self._parse("--from-export", "test/", "--ai-budget", "100000")
        assert args.ai_budget == 100000

    def test_version_is_7(self):
        from migrate import build_parser
        parser = build_parser()
        for action in parser._actions:
            if hasattr(action, 'version') and action.version:
                assert "19.0.0" in action.version
                return
        pytest.fail("No version action found")


# ═══════════════════════════════════════════════════════════════════
# Few-shot examples integrity
# ═══════════════════════════════════════════════════════════════════


class TestFewShotExamples:
    """Verify few-shot examples are well-formed."""

    def test_examples_have_both_fields(self):
        from powerbi_import.ai_converter import _FEW_SHOT_EXAMPLES
        for ex in _FEW_SHOT_EXAMPLES:
            assert "mstr" in ex, f"Missing 'mstr' in example"
            assert "dax" in ex, f"Missing 'dax' in example"

    def test_examples_dax_is_valid(self):
        from powerbi_import.ai_converter import _FEW_SHOT_EXAMPLES, validate_dax_syntax
        for ex in _FEW_SHOT_EXAMPLES:
            r = validate_dax_syntax(ex["dax"])
            assert r["valid"], f"Invalid DAX in example: {ex['dax']}: {r['errors']}"

    def test_at_least_10_examples(self):
        from powerbi_import.ai_converter import _FEW_SHOT_EXAMPLES
        assert len(_FEW_SHOT_EXAMPLES) >= 10
