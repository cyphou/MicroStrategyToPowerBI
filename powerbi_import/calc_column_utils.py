"""
Calculated column utilities.

Classifies MicroStrategy calculated objects into:
- **Lakehouse-eligible**: Can be pre-computed as PySpark ``withColumn()``
  calls in the ETL notebook (simple arithmetic, string ops, date ops).
- **DAX-only**: Must remain as DAX measures (aggregations, iterators,
  filter-context functions, table references).

Also converts eligible MSTR expressions to PySpark ``withColumn()`` code.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Expressions that force DAX-only classification ───────────────

_DAX_ONLY_PATTERNS = re.compile(
    r"\b("
    r"CALCULATE|SUMX|AVERAGEX|COUNTX|MINX|MAXX|RANKX|FILTER|ALL|"
    r"ALLEXCEPT|ALLSELECTED|VALUES|DISTINCT|RELATEDTABLE|"
    r"RELATED|USERELATIONSHIP|CROSSFILTER|EARLIER|EARLIEST|"
    r"TOTALYTD|TOTALQTD|TOTALMTD|SAMEPERIODLASTYEAR|"
    r"DATEADD|DATESYTD|DATESQTD|DATESMTD|PARALLELPERIOD|"
    r"SELECTEDVALUE|HASONEVALUE|ISFILTERED|ISCROSSFILTERED|"
    r"SWITCH|LOOKUPVALUE|TREATAS"
    r")\s*\(",
    re.IGNORECASE,
)

# ── Simple ops that can be pre-computed in PySpark ───────────────

_PYSPARK_FUNC_MAP = {
    # Arithmetic
    "abs": "F.abs({0})",
    "round": "F.round({0}, {1})",
    "ceiling": "F.ceil({0})",
    "floor": "F.floor({0})",
    "power": "F.pow({0}, {1})",
    "sqrt": "F.sqrt({0})",
    "log": "F.log({0})",
    "log10": "F.log10({0})",
    "exp": "F.exp({0})",
    "sign": "F.signum({0})",
    # String
    "upper": "F.upper({0})",
    "lower": "F.lower({0})",
    "trim": "F.trim({0})",
    "ltrim": "F.ltrim({0})",
    "rtrim": "F.rtrim({0})",
    "length": "F.length({0})",
    "left": "F.substring({0}, 1, {1})",
    "right": "F.substring({0}, F.length({0}) - {1} + 1, {1})",
    "replace": "F.regexp_replace({0}, {1}, {2})",
    "concat": "F.concat({0}, {1})",
    "substring": "F.substring({0}, {1}, {2})",
    # Date
    "year": "F.year({0})",
    "month": "F.month({0})",
    "day": "F.dayofmonth({0})",
    "hour": "F.hour({0})",
    "minute": "F.minute({0})",
    "second": "F.second({0})",
    "dayofweek": "F.dayofweek({0})",
    "weekofyear": "F.weekofyear({0})",
    "date_add": "F.date_add({0}, {1})",
    "datediff": "F.datediff({0}, {1})",
    "current_date": "F.current_date()",
    # Type casting
    "int": "F.col({0}).cast('int')",
    "double": "F.col({0}).cast('double')",
    "string": "F.col({0}).cast('string')",
    # Conditional
    "iif": "F.when({0}, {1}).otherwise({2})",
    "coalesce": "F.coalesce({0}, {1})",
    "nullif": "F.when({0} == {1}, F.lit(None)).otherwise({0})",
}

# ── Classification tokens that indicate aggregation ──────────────

_AGG_TOKENS = frozenset({
    "sum", "avg", "count", "min", "max", "stdev", "variance",
    "median", "count_distinct", "first", "last",
})


# ── Public API ───────────────────────────────────────────────────


def classify_expression(expression):
    """Classify a metric expression as ``lakehouse`` or ``dax_only``.

    Args:
        expression: DAX or MSTR expression string.

    Returns:
        ``"lakehouse"`` if the expression can be pre-computed in PySpark,
        ``"dax_only"`` if it must remain in the DAX layer.
    """
    if not expression:
        return "dax_only"

    expr_upper = expression.upper()

    # Any advanced DAX function → DAX-only
    if _DAX_ONLY_PATTERNS.search(expression):
        return "dax_only"

    # Aggregation tokens → DAX-only (must be computed at query time)
    for token in _AGG_TOKENS:
        if re.search(rf"\b{token}\s*\(", expr_upper, re.IGNORECASE):
            return "dax_only"

    return "lakehouse"


def classify_metrics(metrics):
    """Classify a list of metric dicts.

    Each metric is expected to have at least ``name`` and ``expression`` keys.

    Returns:
        dict with ``lakehouse`` (list) and ``dax_only`` (list) partitions.
    """
    lakehouse = []
    dax_only = []
    for m in metrics:
        cat = classify_expression(m.get("expression", ""))
        if cat == "lakehouse":
            lakehouse.append(m)
        else:
            dax_only.append(m)
    logger.info(
        "Classified %d metrics: %d lakehouse-eligible, %d DAX-only",
        len(metrics), len(lakehouse), len(dax_only),
    )
    return {"lakehouse": lakehouse, "dax_only": dax_only}


def expression_to_pyspark(expression, column_name="result"):
    """Convert a simple MSTR/DAX expression to a PySpark ``withColumn()`` call.

    Only handles expressions classified as ``lakehouse``.  For complex
    expressions, returns a ``# MANUAL`` comment placeholder.

    Args:
        expression: The expression string.
        column_name: Target column name for ``withColumn()``.

    Returns:
        PySpark code string (single ``df = df.withColumn(...)`` line).
    """
    if not expression:
        return f'# MANUAL: no expression for column "{column_name}"'

    # Try to detect simple function calls like ABS([Col])
    match = re.match(r"(\w+)\s*\((.*)\)$", expression.strip(), re.DOTALL)
    if match:
        func = match.group(1).lower()
        args_str = match.group(2).strip()
        if func in _PYSPARK_FUNC_MAP:
            # Split top-level arguments
            args = _split_args(args_str)
            pyspark_args = [_arg_to_pyspark(a) for a in args]
            template = _PYSPARK_FUNC_MAP[func]
            try:
                pyspark_expr = template.format(*pyspark_args)
            except (IndexError, KeyError):
                pyspark_expr = template.format(*pyspark_args, *["None"] * 5)
            return f'df = df.withColumn("{column_name}", {pyspark_expr})'

    # Simple arithmetic:  [ColA] + [ColB]
    arith = _try_arithmetic(expression, column_name)
    if arith:
        return arith

    return f'# MANUAL: convert "{expression}" to PySpark for column "{column_name}"'


# ── Helpers ──────────────────────────────────────────────────────


def _split_args(args_str):
    """Split top-level comma-separated arguments, respecting parens."""
    depth = 0
    parts = []
    current = []
    for ch in args_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return parts


def _arg_to_pyspark(arg):
    """Convert a single argument reference to a PySpark expression."""
    arg = arg.strip()
    # Column reference like [Column Name]
    col_match = re.match(r"^\[(.+)]$", arg)
    if col_match:
        return f'F.col("{col_match.group(1)}")'
    # Numeric literal
    try:
        float(arg)
        return f"F.lit({arg})"
    except (ValueError, TypeError):
        pass
    # String literal
    if arg.startswith('"') and arg.endswith('"'):
        return f"F.lit({arg})"
    return f'F.col("{arg}")'


def _try_arithmetic(expression, column_name):
    """Attempt to convert simple arithmetic to PySpark."""
    # Pattern: [Col] op [Col] or [Col] op literal
    parts = re.findall(r"\[([^\]]+)]|([\+\-\*/])|(\d+(?:\.\d+)?)", expression)
    if not parts:
        return None
    pyspark_parts = []
    for col, op, num in parts:
        if col:
            pyspark_parts.append(f'F.col("{col}")')
        elif op:
            pyspark_parts.append(op)
        elif num:
            pyspark_parts.append(f"F.lit({num})")
    if pyspark_parts:
        expr = " ".join(pyspark_parts)
        return f'df = df.withColumn("{column_name}", {expr})'
    return None
