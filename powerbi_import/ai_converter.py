"""
AI-assisted expression converter.

Uses Azure OpenAI (or compatible API) as a fallback for MicroStrategy
expressions that the rule-based converter cannot handle.  Includes prompt
engineering, DAX syntax validation, confidence scoring, caching, cost
control, and human-in-the-loop annotation.

Zero external dependencies beyond ``requests`` (already required).
"""

import hashlib
import json
import logging
import os
import re
import time

import requests

logger = logging.getLogger(__name__)

# ── Configuration defaults ───────────────────────────────────────

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_MAX_TOKENS = 512
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_BUDGET = 500_000  # tokens per run

# ── DAX validation regex (lightweight syntax check) ──────────────

_DAX_INVALID_PATTERNS = [
    re.compile(r"\bSELECT\b", re.IGNORECASE),
    re.compile(r"\bFROM\b\s+\w+\.\w+", re.IGNORECASE),
    re.compile(r"\bWHERE\b", re.IGNORECASE),
    re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE),
    re.compile(r"\bINSERT\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\b\s+\w+\s+SET\b", re.IGNORECASE),
    re.compile(r"\bDELETE\b\s+FROM\b", re.IGNORECASE),
]

_DAX_KNOWN_FUNCTIONS = {
    "SUM", "AVERAGE", "COUNT", "COUNTROWS", "MIN", "MAX", "CALCULATE",
    "FILTER", "ALL", "ALLSELECTED", "VALUES", "DISTINCT", "RELATED",
    "RELATEDTABLE", "IF", "SWITCH", "DIVIDE", "BLANK", "ISBLANK",
    "CONCATENATE", "FORMAT", "YEAR", "MONTH", "DAY", "TODAY", "NOW",
    "DATEADD", "DATEDIFF", "STARTOFMONTH", "ENDOFMONTH", "STARTOFYEAR",
    "ENDOFYEAR", "STARTOFQUARTER", "ENDOFQUARTER", "EDATE",
    "RANKX", "TOPN", "EARLIER", "EARLIEST", "COALESCE",
    "UPPER", "LOWER", "TRIM", "SEARCH", "SUBSTITUTE", "LEFT", "RIGHT",
    "MID", "LEN", "ROUND", "INT", "ABS", "POWER", "SQRT", "MOD",
    "WINDOW", "OFFSET", "SUMX", "AVERAGEX", "COUNTX", "MINX", "MAXX",
    "PERCENTILE.INC", "PERCENTILE.EXC", "MEDIAN",
    "UNION", "INTERSECT", "EXCEPT", "TREATAS", "USERELATIONSHIP",
    "SELECTEDVALUE", "HASONEVALUE", "ISINSCOPE", "CONTAINSSTRING",
    "CONTAINSSTRINGEXACT", "PATHITEM", "PATHCONTAINS",
    "VAR", "RETURN", "TRUE", "FALSE", "AND", "OR", "NOT",
    "STDEV.S", "STDEV.P", "VAR.S", "VAR.P",
    "GEOMEANX", "PRODUCTX", "DISTINCTCOUNT",
}

# ── System prompt ────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert data analyst specializing in converting MicroStrategy \
metric expressions to DAX (Data Analysis Expressions) for Power BI.

RULES:
1. Output ONLY the DAX expression — no explanation, no markdown, no code fences.
2. The DAX must be syntactically valid and idiomatic.
3. Use [ColumnName] for column references and [MeasureName] for measure references.
4. Never generate SQL — the target is DAX exclusively.
5. Prefer CALCULATE + filter context manipulation over nested IF chains.
6. For window operations use WINDOW / OFFSET / RANKX as appropriate.
7. If you are uncertain, produce the best approximation and append a \
   single-line DAX comment: // AI: <reason for uncertainty>.
"""

# ── Few-shot examples (curated) ─────────────────────────────────

_FEW_SHOT_EXAMPLES = [
    {
        "mstr": 'ApplySimple("CASE WHEN #0 > 0 THEN #1 / #0 ELSE 0 END", Revenue, Cost)',
        "dax": "IF([Revenue] > 0, DIVIDE([Cost], [Revenue]), 0)",
    },
    {
        "mstr": 'ApplySimple("COALESCE(#0, #1)", OrderDate, ShipDate)',
        "dax": "COALESCE([OrderDate], [ShipDate])",
    },
    {
        "mstr": 'ApplySimple("DATEDIFF(dd, #0, #1)", StartDate, EndDate)',
        "dax": "DATEDIFF([StartDate], [EndDate], DAY)",
    },
    {
        "mstr": 'ApplySimple("CAST(#0 AS VARCHAR) + \' - \' + CAST(#1 AS VARCHAR)", Region, Product)',
        "dax": '[Region] & " - " & [Product]',
    },
    {
        "mstr": 'ApplySimple("CASE WHEN #0 IS NULL THEN \'Unknown\' WHEN #0 < 0 THEN \'Negative\' ELSE \'Positive\' END", Amount)',
        "dax": 'SWITCH(TRUE(), ISBLANK([Amount]), "Unknown", [Amount] < 0, "Negative", "Positive")',
    },
    {
        "mstr": 'ApplyAgg("SUM(CASE WHEN #0 = \'Active\' THEN 1 ELSE 0 END)", Status)',
        "dax": 'CALCULATE(COUNTROWS(Table), Table[Status] = "Active")',
    },
    {
        "mstr": 'ApplyOLAP("ROW_NUMBER() OVER (PARTITION BY #0 ORDER BY #1 DESC)", Category, Revenue)',
        "dax": "RANKX(ALLSELECTED([Category]), [Revenue],, DESC, SKIP)",
    },
    {
        "mstr": 'ApplySimple("ROUND(#0 * 100.0 / NULLIF(#1, 0), 2)", PartialCount, TotalCount)',
        "dax": "ROUND(DIVIDE([PartialCount] * 100, [TotalCount]), 2)",
    },
    {
        "mstr": 'ApplySimple("DATEADD(MONTH, #1, #0)", BaseDate, MonthOffset)',
        "dax": "EDATE([BaseDate], [MonthOffset])",
    },
    {
        "mstr": 'ApplySimple("IIF(#0 BETWEEN 0 AND 50, \'Low\', IIF(#0 BETWEEN 51 AND 100, \'Medium\', \'High\'))", Score)',
        "dax": 'SWITCH(TRUE(), [Score] >= 0 && [Score] <= 50, "Low", [Score] >= 51 && [Score] <= 100, "Medium", "High")',
    },
]


# ── Public API ───────────────────────────────────────────────────


class AIConverter:
    """LLM-backed expression converter with caching and budget control."""

    def __init__(self, *, endpoint=None, api_key=None, model=None,
                 deployment=None, api_version="2024-02-01",
                 token_budget=None, cache_dir=None):
        """
        Args:
            endpoint: Azure OpenAI endpoint (e.g. https://myinstance.openai.azure.com/)
            api_key: API key.
            model: Model name (for OpenAI-compatible endpoints).
            deployment: Deployment name (Azure OpenAI).
            api_version: Azure OpenAI API version.
            token_budget: Maximum total tokens for this converter instance.
            cache_dir: Directory for persistent response cache.
        """
        self.endpoint = (endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.model = model or os.environ.get("AZURE_OPENAI_MODEL", _DEFAULT_MODEL)
        self.deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
        self.api_version = api_version
        self.token_budget = token_budget if token_budget is not None else _DEFAULT_BUDGET
        self.tokens_used = 0
        self._cache = {}
        self._cache_dir = cache_dir

        # Load persistent cache
        if cache_dir:
            self._cache_path = os.path.join(cache_dir, "ai_cache.json")
            if os.path.isfile(self._cache_path):
                try:
                    with open(self._cache_path, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                    logger.info("Loaded %d cached AI conversions", len(self._cache))
                except (json.JSONDecodeError, OSError):
                    pass
        else:
            self._cache_path = None

    # ── Core conversion ──────────────────────────────────────────

    def convert(self, mstr_expression, context=None):
        """Convert a MicroStrategy expression to DAX via LLM.

        Args:
            mstr_expression: The original MSTR expression string.
            context: Optional dict with table/column context.

        Returns:
            dict with ``dax``, ``fidelity``, ``warnings``, ``ai_assisted``.
        """
        context = context or {}

        # Check cache first
        cache_key = self._cache_key(mstr_expression)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            logger.debug("Cache hit for: %s", mstr_expression[:60])
            return {
                "dax": cached["dax"],
                "fidelity": cached.get("fidelity", "ai_assisted"),
                "warnings": cached.get("warnings", []) + ["[AI-CACHED]"],
                "ai_assisted": True,
                "confidence": cached.get("confidence", 0.0),
            }

        # Budget check
        if self.tokens_used >= self.token_budget:
            logger.warning("AI token budget exhausted (%d/%d)", self.tokens_used, self.token_budget)
            return {
                "dax": f"/* AI BUDGET EXHAUSTED — manual review required */\nBLANK()",
                "fidelity": "manual_review",
                "warnings": ["AI token budget exhausted"],
                "ai_assisted": False,
                "confidence": 0.0,
            }

        # Check credentials
        if not self.endpoint or not self.api_key:
            return {
                "dax": f"/* AI ASSIST UNAVAILABLE — no endpoint configured */\nBLANK()",
                "fidelity": "manual_review",
                "warnings": ["AI converter not configured (no endpoint/key)"],
                "ai_assisted": False,
                "confidence": 0.0,
            }

        # Build prompt
        messages = self._build_messages(mstr_expression, context)

        # Call LLM
        try:
            response = self._call_llm(messages)
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return {
                "dax": f"/* AI CALL FAILED: {e} */\nBLANK()",
                "fidelity": "manual_review",
                "warnings": [f"AI call failed: {e}"],
                "ai_assisted": False,
                "confidence": 0.0,
            }

        dax = response["dax"]
        tokens = response.get("tokens_used", 0)
        self.tokens_used += tokens

        # Validate DAX
        validation = validate_dax_syntax(dax)
        confidence = self._score_confidence(dax, validation, mstr_expression)

        fidelity = "ai_assisted"
        warnings = [f"[AI-ASSISTED] confidence={confidence:.0%}"]
        if not validation["valid"]:
            fidelity = "manual_review"
            warnings.extend(validation["errors"])

        result = {
            "dax": dax,
            "fidelity": fidelity,
            "warnings": warnings,
            "ai_assisted": True,
            "confidence": confidence,
        }

        # Cache successful conversions
        if validation["valid"]:
            self._cache[cache_key] = {
                "dax": dax,
                "fidelity": fidelity,
                "confidence": confidence,
                "warnings": [],
            }
            self._save_cache()

        return result

    # ── Batch conversion ─────────────────────────────────────────

    def convert_batch(self, expressions):
        """Convert multiple expressions, deduplicating identical patterns.

        Args:
            expressions: list of (mstr_expression, context) tuples.

        Returns:
            list of result dicts (same order as input).
        """
        # Deduplicate by expression
        unique = {}
        for expr, ctx in expressions:
            key = self._cache_key(expr)
            if key not in unique:
                unique[key] = (expr, ctx)

        # Convert unique expressions
        results_map = {}
        for key, (expr, ctx) in unique.items():
            results_map[key] = self.convert(expr, ctx)

        # Map back to original order
        return [results_map[self._cache_key(expr)] for expr, _ctx in expressions]

    # ── Message construction ─────────────────────────────────────

    def _build_messages(self, mstr_expression, context):
        """Build the chat messages with system prompt + few-shot + query."""
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

        # Few-shot examples
        for ex in _FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": f"Convert: {ex['mstr']}"})
            messages.append({"role": "assistant", "content": ex["dax"]})

        # Context hint
        context_hint = ""
        if context.get("metric_name"):
            context_hint += f"Metric name: {context['metric_name']}. "
        if context.get("table"):
            context_hint += f"Table: {context['table']}. "
        if context.get("columns"):
            context_hint += f"Available columns: {', '.join(context['columns'][:20])}. "

        user_msg = f"Convert: {mstr_expression}"
        if context_hint:
            user_msg = f"{context_hint}\n{user_msg}"

        messages.append({"role": "user", "content": user_msg})
        return messages

    # ── LLM API call ─────────────────────────────────────────────

    def _call_llm(self, messages):
        """Call Azure OpenAI chat completions endpoint."""
        if self.deployment:
            # Azure OpenAI
            url = (
                f"{self.endpoint}/openai/deployments/{self.deployment}"
                f"/chat/completions?api-version={self.api_version}"
            )
            headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        else:
            # OpenAI-compatible
            url = f"{self.endpoint}/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

        payload = {
            "messages": messages,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "temperature": _DEFAULT_TEMPERATURE,
        }
        if not self.deployment:
            payload["model"] = self.model

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)

        # Clean up response — strip markdown code fences if present
        content = _strip_code_fences(content)

        return {"dax": content, "tokens_used": tokens}

    # ── Confidence scoring ───────────────────────────────────────

    def _score_confidence(self, dax, validation, original_expr):
        """Score confidence of LLM-generated DAX (0.0–1.0)."""
        score = 0.5  # Base

        # Syntax validation bonus
        if validation["valid"]:
            score += 0.2

        # Known DAX function usage
        functions_used = re.findall(r'\b([A-Z][A-Z_.]+)\s*\(', dax)
        known = sum(1 for f in functions_used if f in _DAX_KNOWN_FUNCTIONS)
        if functions_used:
            score += 0.15 * (known / len(functions_used))

        # Penalty for comments indicating uncertainty
        if "// AI:" in dax or "MANUAL" in dax.upper():
            score -= 0.15

        # Penalty for BLANK() fallback
        if dax.strip().endswith("BLANK()") and len(dax) < 20:
            score -= 0.3

        # Length sanity — too short or too long is suspicious
        if len(dax) < 5:
            score -= 0.2
        elif len(dax) > 2000:
            score -= 0.1

        return max(0.0, min(1.0, score))

    # ── Cache management ─────────────────────────────────────────

    def _cache_key(self, expression):
        """Deterministic cache key for an expression."""
        return hashlib.sha256(expression.strip().encode()).hexdigest()[:16]

    def _save_cache(self):
        """Persist cache to disk."""
        if not self._cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.debug("Could not save AI cache: %s", e)

    def get_stats(self):
        """Return converter usage statistics."""
        return {
            "tokens_used": self.tokens_used,
            "token_budget": self.token_budget,
            "budget_remaining": max(0, self.token_budget - self.tokens_used),
            "cache_entries": len(self._cache),
            "budget_pct_used": (self.tokens_used / self.token_budget * 100)
                               if self.token_budget else 0,
        }


# ── DAX validation ───────────────────────────────────────────────


def validate_dax_syntax(dax):
    """Lightweight DAX syntax validation (no full parser).

    Checks:
    - Balanced parentheses
    - No SQL keywords
    - Contains at least one DAX function or column reference
    - No empty output

    Returns:
        dict with ``valid`` (bool) and ``errors`` (list of str).
    """
    errors = []

    if not dax or not dax.strip():
        return {"valid": False, "errors": ["Empty DAX expression"]}

    # Strip comments for validation
    clean = re.sub(r'/\*.*?\*/', '', dax, flags=re.DOTALL)
    clean = re.sub(r'//.*$', '', clean, flags=re.MULTILINE)

    # Balanced parentheses
    depth = 0
    for ch in clean:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if depth < 0:
            errors.append("Unbalanced parentheses (extra closing)")
            break
    if depth > 0:
        errors.append(f"Unbalanced parentheses ({depth} unclosed)")

    # No SQL keywords
    for pat in _DAX_INVALID_PATTERNS:
        if pat.search(clean):
            errors.append(f"Contains SQL keyword: {pat.pattern}")

    # Should reference columns or functions
    has_col_ref = bool(re.search(r'\[.+?\]', clean))
    has_func = bool(re.search(r'\b[A-Z][A-Z_.]+\s*\(', clean))
    has_literal = bool(re.search(r'\d+|"[^"]*"', clean))
    if not (has_col_ref or has_func or has_literal):
        errors.append("No column references, functions, or literals found")

    return {"valid": len(errors) == 0, "errors": errors}


# ── Utilities ────────────────────────────────────────────────────


def _strip_code_fences(text):
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```dax or ```)
        lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def annotate_dax(dax, ai_assisted=False, confidence=0.0):
    """Add annotation comment to AI-assisted DAX for human review.

    Args:
        dax: DAX expression.
        ai_assisted: Whether it was AI-generated.
        confidence: Confidence score 0-1.

    Returns:
        Annotated DAX string.
    """
    if not ai_assisted:
        return dax
    return f"/* [AI-ASSISTED] confidence={confidence:.0%} */\n{dax}"
