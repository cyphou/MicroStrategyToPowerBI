"""
Semantic field matcher.

Provides fuzzy matching for column/attribute names across MicroStrategy
and Power BI schemas.  Used during merge scenarios and for auto-fixing
manual-review items by suggesting top-N candidate matches.

Includes:
- Abbreviation expansion (CUST → Customer, QTY → Quantity)
- Levenshtein distance matching
- Token-overlap scoring
- Learning from user corrections (local correction dictionary)

Zero external dependencies — pure Python implementation.
"""

import json
import logging
import os
import re
from collections import Counter

logger = logging.getLogger(__name__)

# ── Known abbreviation expansions ────────────────────────────────

_ABBREVIATIONS = {
    "cust": "customer",
    "cstmr": "customer",
    "amt": "amount",
    "qty": "quantity",
    "prod": "product",
    "inv": "invoice",
    "desc": "description",
    "dt": "date",
    "dte": "date",
    "num": "number",
    "nbr": "number",
    "no": "number",
    "id": "identifier",
    "idx": "index",
    "addr": "address",
    "cat": "category",
    "grp": "group",
    "dept": "department",
    "emp": "employee",
    "mgr": "manager",
    "org": "organization",
    "rev": "revenue",
    "prc": "price",
    "pct": "percent",
    "perc": "percent",
    "avg": "average",
    "tot": "total",
    "ttl": "total",
    "cnt": "count",
    "yr": "year",
    "mo": "month",
    "mth": "month",
    "wk": "week",
    "day": "day",
    "hr": "hour",
    "min": "minute",
    "sec": "second",
    "curr": "currency",
    "ccy": "currency",
    "rgn": "region",
    "reg": "region",
    "st": "state",
    "cty": "city",
    "ctry": "country",
    "zip": "zipcode",
    "ph": "phone",
    "tel": "telephone",
    "fax": "facsimile",
    "src": "source",
    "tgt": "target",
    "dest": "destination",
    "stat": "status",
    "sts": "status",
    "typ": "type",
    "cd": "code",
    "val": "value",
    "flg": "flag",
    "ind": "indicator",
    "lvl": "level",
    "nm": "name",
    "lnm": "lastname",
    "fnm": "firstname",
    "acct": "account",
    "bal": "balance",
    "trx": "transaction",
    "txn": "transaction",
    "ord": "order",
    "shp": "shipment",
    "dlvr": "delivery",
    "mfg": "manufacturing",
    "whse": "warehouse",
    "loc": "location",
    "sku": "sku",
    "upc": "upc",
    "seq": "sequence",
    "ref": "reference",
    "cmt": "comment",
    "rmk": "remark",
    "attr": "attribute",
    "dim": "dimension",
    "meas": "measure",
    "fct": "fact",
}


# ── Public API ───────────────────────────────────────────────────


def find_best_match(name, candidates, *, threshold=0.4, top_n=3):
    """Find the best matching candidate(s) for a column name.

    Args:
        name: Source column/attribute name to match.
        candidates: List of target column/attribute name strings.
        threshold: Minimum similarity score (0-1) to include in results.
        top_n: Maximum number of matches to return.

    Returns:
        list of dicts: [{"name": str, "score": float, "method": str}, ...]
        Sorted by descending score.
    """
    if not name or not candidates:
        return []

    norm_name = _normalize(name)
    results = []

    for cand in candidates:
        norm_cand = _normalize(cand)
        score, method = _compute_similarity(norm_name, norm_cand)
        if score >= threshold:
            results.append({"name": cand, "score": score, "method": method})

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


def match_schemas(source_columns, target_columns, *, threshold=0.5):
    """Match all source columns to target columns.

    Args:
        source_columns: list of source column name strings.
        target_columns: list of target column name strings.

    Returns:
        dict mapping source_name → best match dict or None.
    """
    mapping = {}
    for src in source_columns:
        matches = find_best_match(src, target_columns, threshold=threshold, top_n=1)
        mapping[src] = matches[0] if matches else None
    return mapping


def suggest_fixes(manual_review_items, available_columns, *, top_n=3):
    """For each manual-review item, suggest column/measure replacements.

    Args:
        manual_review_items: list of dicts with ``expression`` and ``warnings``.
        available_columns: list of known column/measure names.
        top_n: Number of suggestions per item.

    Returns:
        list of dicts with ``original``, ``suggestions``.
    """
    results = []
    for item in manual_review_items:
        expr = item.get("expression", "")
        # Extract column references from expression
        refs = re.findall(r'\[([^\[\]]+)\]', expr)
        suggestions = {}
        for ref in refs:
            matches = find_best_match(ref, available_columns, threshold=0.3, top_n=top_n)
            if matches:
                suggestions[ref] = matches
        results.append({
            "original": expr,
            "references": refs,
            "suggestions": suggestions,
        })
    return results


# ── Correction learning ──────────────────────────────────────────


class CorrectionStore:
    """Persistent store for user corrections to improve future matching."""

    def __init__(self, store_path=None):
        self._path = store_path
        self._corrections = {}
        if store_path and os.path.isfile(store_path):
            try:
                with open(store_path, "r", encoding="utf-8") as f:
                    self._corrections = json.load(f)
                logger.info("Loaded %d learned corrections", len(self._corrections))
            except (json.JSONDecodeError, OSError):
                pass

    def record(self, source_name, correct_target):
        """Record a user correction."""
        key = _normalize(source_name)
        self._corrections[key] = correct_target
        self._save()

    def lookup(self, source_name):
        """Look up a previously learned correction."""
        key = _normalize(source_name)
        return self._corrections.get(key)

    def get_all(self):
        """Return all learned corrections."""
        return dict(self._corrections)

    def _save(self):
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._corrections, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.debug("Could not save corrections: %s", e)


# ── Normalization & similarity ───────────────────────────────────


def _normalize(name):
    """Normalize a column name for comparison.

    Steps: lowercase → split on separators → split camelCase → expand abbreviations → rejoin.
    """
    s = name.strip()
    # Split on common separators: underscore, dash, dot, space
    tokens = re.split(r'[_\-. ]+', s)
    # Further split camelCase tokens
    expanded = []
    for token in tokens:
        # Handle camelCase and PascalCase:
        # "CustAmt" → "Cust", "Amt"; "customerName" → "customer", "Name"
        parts = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)', token)
        if not parts:
            parts = [token]
        for p in parts:
            p_lower = p.lower()
            if p_lower:
                # Expand abbreviation if known
                expanded.append(_ABBREVIATIONS.get(p_lower, p_lower))
    return " ".join(expanded)


def _compute_similarity(norm_a, norm_b):
    """Compute similarity between two normalized name strings.

    Returns (score, method) where score is 0-1.
    """
    # Exact match
    if norm_a == norm_b:
        return 1.0, "exact"

    # Token overlap (Jaccard-like)
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union)
        if jaccard >= 0.8:
            return jaccard, "token_overlap"

    # Levenshtein distance (normalized)
    lev_dist = _levenshtein(norm_a, norm_b)
    max_len = max(len(norm_a), len(norm_b), 1)
    lev_sim = 1.0 - (lev_dist / max_len)

    # Token overlap score (softer)
    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union)
        # Blend: 60% token overlap + 40% Levenshtein
        blended = 0.6 * jaccard + 0.4 * lev_sim
        return blended, "blended"

    return lev_sim, "levenshtein"


def _levenshtein(s1, s2):
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]
