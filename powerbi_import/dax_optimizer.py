"""
DAX optimizer — AST-based rewrite rules for generated DAX measures.

Provides pattern-based transformations to make generated DAX more
idiomatic and efficient:

  EE.1  Lightweight AST parser (function / operator / literal nodes)
  EE.2  IF→SWITCH rewriter (chained IFs with ≥3 branches)
  EE.3  ISBLANK→COALESCE rewriter
  EE.4  Time Intelligence injection (YTD / QTD / MTD / PY / YoY)
  EE.5  CALCULATE simplification (redundant wrapping, nested CALCULATE)
  EE.6  Optimization report (summary stats)
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── AST node types ───────────────────────────────────────────────

_FUNCTION_RE = re.compile(
    r"([A-Z_][A-Z0-9_.]*)\s*\(", re.IGNORECASE
)

# ── Pattern matchers ─────────────────────────────────────────────

# Chained IF → SWITCH
_CHAINED_IF_RE = re.compile(
    r"IF\s*\(\s*(.+?)\s*,\s*(.+?)\s*,\s*IF\s*\(",
    re.IGNORECASE,
)

# ISBLANK guard: IF(ISBLANK(x), default, x) → COALESCE(x, default)
_ISBLANK_GUARD_RE = re.compile(
    r"IF\s*\(\s*ISBLANK\s*\(\s*(.+?)\s*\)\s*,\s*(.+?)\s*,\s*\1\s*\)",
    re.IGNORECASE,
)
# Reverse form: IF(ISBLANK(x), x, replacement) is not useful — skip
# Also handle NOT(ISBLANK(x)): IF(NOT(ISBLANK(x)), x, default) → COALESCE(x, default)
_NOT_ISBLANK_GUARD_RE = re.compile(
    r"IF\s*\(\s*NOT\s*\(\s*ISBLANK\s*\(\s*(.+?)\s*\)\s*\)\s*,\s*\1\s*,\s*(.+?)\s*\)",
    re.IGNORECASE,
)

# Nested CALCULATE(CALCULATE(...))
_NESTED_CALCULATE_RE = re.compile(
    r"CALCULATE\s*\(\s*CALCULATE\s*\(",
    re.IGNORECASE,
)

# Redundant CALCULATE with no filter: CALCULATE(expr) → expr
_REDUNDANT_CALCULATE_RE = re.compile(
    r"CALCULATE\s*\(\s*([^,()]+(?:\([^)]*\))?)\s*\)",
    re.IGNORECASE,
)

# Date-based measure detection for Time Intelligence
_DATE_PATTERNS = [
    re.compile(r"\bDATEADD\b", re.IGNORECASE),
    re.compile(r"\bStartOf(?:Year|Month|Quarter)\b", re.IGNORECASE),
    re.compile(r"\bEndOf(?:Year|Month|Quarter)\b", re.IGNORECASE),
    re.compile(r"\bDate\b", re.IGNORECASE),
    re.compile(r"\[Date\]", re.IGNORECASE),
    re.compile(r"'Date'", re.IGNORECASE),
]


# ── Public API ───────────────────────────────────────────────────

def optimize_measures(measures, *, auto_time_intelligence=False):
    """Optimize a list of DAX measures.

    Args:
        measures: list of dicts with at least ``name`` and ``expression``.
        auto_time_intelligence: If True, inject YTD/PY/YoY variants for
            date-based measures.

    Returns:
        tuple: (optimized_measures, report_dict)
        where optimized_measures is a new list (original is not mutated),
        and report_dict summarises the optimisations applied.
    """
    results = []
    report = {
        "total_measures": len(measures),
        "measures_optimized": 0,
        "patterns_applied": [],
        "time_intelligence_added": 0,
        "details": [],
    }

    for measure in measures:
        name = measure.get("name", "")
        expr = measure.get("expression", "")
        if not expr:
            results.append(dict(measure))
            continue

        original = expr
        patterns = []

        # Rule 1: ISBLANK guard → COALESCE
        expr, n = _rewrite_isblank_to_coalesce(expr)
        if n:
            patterns.append(f"ISBLANK→COALESCE ×{n}")

        # Rule 2: Chained IF → SWITCH
        expr, changed = _rewrite_chained_if_to_switch(expr)
        if changed:
            patterns.append("IF→SWITCH")

        # Rule 3: Nested CALCULATE simplification
        expr, n = _simplify_nested_calculate(expr)
        if n:
            patterns.append(f"CALCULATE-flatten ×{n}")

        # Rule 4: Redundant CALCULATE removal
        expr, n = _remove_redundant_calculate(expr)
        if n:
            patterns.append(f"CALCULATE-remove ×{n}")

        optimized = dict(measure, expression=expr)
        results.append(optimized)

        if patterns:
            report["measures_optimized"] += 1
            report["patterns_applied"].extend(patterns)
            report["details"].append({
                "measure": name,
                "patterns": patterns,
                "before_length": len(original),
                "after_length": len(expr),
            })

    # Time Intelligence injection
    if auto_time_intelligence:
        ti_measures = _inject_time_intelligence(results)
        report["time_intelligence_added"] = len(ti_measures)
        results.extend(ti_measures)

    return results, report


def optimize_expression(expression):
    """Optimise a single DAX expression string.

    Returns:
        tuple: (optimized_expression, list_of_patterns_applied)
    """
    patterns = []
    expr = expression

    expr, n = _rewrite_isblank_to_coalesce(expr)
    if n:
        patterns.append("ISBLANK→COALESCE")

    expr, changed = _rewrite_chained_if_to_switch(expr)
    if changed:
        patterns.append("IF→SWITCH")

    expr, n = _simplify_nested_calculate(expr)
    if n:
        patterns.append("CALCULATE-flatten")

    expr, n = _remove_redundant_calculate(expr)
    if n:
        patterns.append("CALCULATE-remove")

    return expr, patterns


# ── Rewrite rules ────────────────────────────────────────────────

def _rewrite_isblank_to_coalesce(expr):
    """IF(ISBLANK(x), default, x) → COALESCE(x, default)."""
    count = 0
    # Forward form
    new, n = _ISBLANK_GUARD_RE.subn(r"COALESCE(\1, \2)", expr)
    count += n
    expr = new
    # NOT form
    new, n = _NOT_ISBLANK_GUARD_RE.subn(r"COALESCE(\1, \2)", expr)
    count += n
    return new, count


def _rewrite_chained_if_to_switch(expr):
    """Rewrite chained IF(c1, v1, IF(c2, v2, IF(...))) to SWITCH(TRUE(), ...)."""
    branches = _extract_if_branches(expr)
    if branches is None or len(branches) < 3:
        return expr, False

    conditions = branches[:-1]  # all (condition, value) pairs
    default = branches[-1]      # last value (the else)

    parts = ["SWITCH(TRUE()"]
    for cond, val in conditions:
        parts.append(f", {cond.strip()}, {val.strip()}")
    if default is not None:
        if isinstance(default, tuple):
            # It's another (condition, value) but the last branch
            parts.append(f", {default[0].strip()}, {default[1].strip()}")
        else:
            parts.append(f", {default.strip()}")
    parts.append(")")
    return "".join(parts), True


def _extract_if_branches(expr):
    """Extract branches from chained IF expressions.

    Returns list of (condition, value) tuples + final default, or None
    if the expression isn't a simple chained IF.
    """
    expr = expr.strip()
    if not expr.upper().startswith("IF("):
        return None

    branches = []
    remaining = expr

    while True:
        m = re.match(r"IF\s*\(\s*", remaining, re.IGNORECASE)
        if not m:
            break
        remaining = remaining[m.end():]

        # Extract condition (first argument)
        cond, remaining = _extract_argument(remaining)
        if cond is None:
            return None

        # Extract value (second argument)
        val, remaining = _extract_argument(remaining)
        if val is None:
            return None

        branches.append((cond, val))

        # The rest is the else part
        remaining = remaining.strip()
        if remaining.upper().startswith("IF("):
            continue
        else:
            # Final default value — extract it
            default, remaining = _extract_last_argument(remaining)
            if default is not None:
                branches.append(default)
            break

    return branches if len(branches) >= 3 else None


def _extract_argument(s):
    """Extract one comma-separated argument from *s*, handling nested parens."""
    s = s.strip()
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return None, s
            depth -= 1
        elif ch == "," and depth == 0:
            return s[:i], s[i + 1:]
        i += 1
    return None, s


def _extract_last_argument(s):
    """Extract the last argument before closing paren(s)."""
    s = s.strip()
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return s[:i].strip() if i > 0 else None, s[i + 1:]
            depth -= 1
        i += 1
    return s.strip() if s.strip() else None, ""


def _simplify_nested_calculate(expr):
    """Flatten CALCULATE(CALCULATE(expr, f1), f2) → CALCULATE(expr, f1, f2)."""
    count = 0
    # Iteratively flatten (handle double nesting)
    prev = None
    while prev != expr:
        prev = expr
        # Find CALCULATE(CALCULATE( and merge
        m = _NESTED_CALCULATE_RE.search(expr)
        if m:
            # Find the inner CALCULATE's arguments
            inner_start = m.end()
            inner_end = _find_matching_paren(expr, inner_start - 1)
            if inner_end and inner_end < len(expr):
                inner_args = expr[inner_start:inner_end]
                # Find the outer CALCULATE's remaining args
                rest_start = inner_end + 1
                outer_end = _find_matching_paren(expr, m.start() + len("CALCULATE(") - 1)
                if outer_end:
                    rest_args = expr[rest_start:outer_end].strip()
                    if rest_args.startswith(","):
                        rest_args = rest_args[1:].strip()
                    merged = f"CALCULATE({inner_args}"
                    if rest_args:
                        merged += f", {rest_args}"
                    merged += ")"
                    expr = expr[:m.start()] + merged + expr[outer_end + 1:]
                    count += 1
    return expr, count


def _remove_redundant_calculate(expr):
    """Remove CALCULATE(expr) with no filter argument."""
    count = 0
    prev = None
    while prev != expr:
        prev = expr
        # Find CALCULATE( with balanced parens and no comma at depth 0
        for m in _REDUNDANT_CALCULATE_RE.finditer(expr):
            full_match = m.group(0)
            inner = m.group(1).strip()
            # Make sure there's really no comma at the top level
            if "," not in _top_level_text(full_match[len("CALCULATE("):-1]):
                expr = expr[:m.start()] + inner + expr[m.end():]
                count += 1
                break  # restart iteration after modification
    return expr, count


def _top_level_text(s):
    """Return only top-level characters (depth=0) from *s*."""
    result = []
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            result.append(ch)
    return "".join(result)


def _find_matching_paren(expr, open_pos):
    """Find the index of the closing paren matching the ``(`` at *open_pos*."""
    if open_pos >= len(expr) or expr[open_pos] != "(":
        return None
    depth = 0
    for i in range(open_pos, len(expr)):
        if expr[i] == "(":
            depth += 1
        elif expr[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


# ── Time Intelligence injection ──────────────────────────────────

def _inject_time_intelligence(measures):
    """Auto-generate YTD/PY/YoY variants for date-aware measures."""
    new_measures = []
    for m in measures:
        name = m.get("name", "")
        expr = m.get("expression", "")
        if not _is_date_measure(expr):
            continue

        # YTD variant
        new_measures.append({
            "name": f"{name} YTD",
            "expression": f"TOTALYTD({expr}, 'Date'[Date])",
            "description": f"Year-to-date variant of {name}",
            "_auto_generated": True,
        })

        # PY variant
        new_measures.append({
            "name": f"{name} PY",
            "expression": f"CALCULATE({expr}, SAMEPERIODLASTYEAR('Date'[Date]))",
            "description": f"Prior year variant of {name}",
            "_auto_generated": True,
        })

        # YoY % growth
        new_measures.append({
            "name": f"{name} YoY %",
            "expression": (
                f"VAR _current = {expr}\n"
                f"VAR _py = CALCULATE({expr}, SAMEPERIODLASTYEAR('Date'[Date]))\n"
                f"RETURN DIVIDE(_current - _py, _py)"
            ),
            "description": f"Year-over-year growth % for {name}",
            "_auto_generated": True,
        })

    return new_measures


def _is_date_measure(expr):
    """Heuristic: does this expression reference date-related patterns?"""
    return any(p.search(expr) for p in _DATE_PATTERNS)


# ── Optimization report ──────────────────────────────────────────

def format_report(report):
    """Format an optimization report as a human-readable string."""
    lines = [
        f"DAX Optimization Report",
        f"  Total measures:      {report['total_measures']}",
        f"  Measures optimized:  {report['measures_optimized']}",
        f"  Patterns applied:    {len(report['patterns_applied'])}",
        f"  Time Intelligence:   +{report['time_intelligence_added']} measures",
    ]
    if report["details"]:
        lines.append("")
        lines.append("  Details:")
        for d in report["details"]:
            saved = d["before_length"] - d["after_length"]
            lines.append(
                f"    {d['measure']}: {', '.join(d['patterns'])} "
                f"({d['before_length']}→{d['after_length']} chars, "
                f"{saved:+d})"
            )
    return "\n".join(lines)
