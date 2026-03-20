"""
MicroStrategy expression to DAX converter.

Converts MicroStrategy metric expressions, conditional logic, level metrics,
and Apply functions to DAX equivalents.
"""

import re
import logging

logger = logging.getLogger(__name__)


# ── Function mapping: MicroStrategy → DAX ────────────────────────

_FUNCTION_MAP = {
    # Aggregation
    "sum": "SUM",
    "avg": "AVERAGE",
    "count": "COUNT",
    "min": "MIN",
    "max": "MAX",
    "stdev": "STDEV.S",
    "stdevp": "STDEV.P",
    "var": "VAR.S",
    "varp": "VAR.P",
    "median": "MEDIAN",
    "product": "PRODUCTX",
    "geomean": "GEOMEANX",
    # Distinct
    "distinctcount": "DISTINCTCOUNT",
    # Logic
    "if": "IF",
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "between": None,  # Custom handling
    "in": None,  # Custom handling
    # Null handling
    "nulltozero": None,  # Custom: IF(ISBLANK(x), 0, x)
    "zertonull": None,  # Custom: IF(x = 0, BLANK(), x)
    "isnull": "ISBLANK",
    "isnotnull": None,  # Custom: NOT(ISBLANK(x))
    "coalesce": "COALESCE",
    # String
    "concat": "CONCATENATE",
    "length": "LEN",
    "substr": "MID",
    "leftstr": "LEFT",
    "rightstr": "RIGHT",
    "trim": "TRIM",
    "ltrim": "TRIM",
    "rtrim": "TRIM",
    "upper": "UPPER",
    "lower": "LOWER",
    "position": "SEARCH",
    "replace": "SUBSTITUTE",
    # Date
    "currentdate": "TODAY",
    "currentdatetime": "NOW",
    "year": "YEAR",
    "month": "MONTH",
    "day": "DAY",
    "hour": "HOUR",
    "minute": "MINUTE",
    "second": "SECOND",
    "dayofweek": "WEEKDAY",
    "weekofyear": "WEEKNUM",
    "quarter": "QUARTER",
    "daysbetween": None,  # Custom: DATEDIFF
    "monthsbetween": None,  # Custom: DATEDIFF
    "yearsbetween": None,  # Custom: DATEDIFF
    "adddays": None,  # Custom: date + n
    "addmonths": "EDATE",
    "monthstartdate": "STARTOFMONTH",
    "monthenddate": "ENDOFMONTH",
    "yearstartdate": "STARTOFYEAR",
    "yearenddate": "ENDOFYEAR",
    # Math
    "abs": "ABS",
    "round": "ROUND",
    "ceiling": None,  # Custom: CEILING(x, 1)
    "floor": None,  # Custom: FLOOR(x, 1)
    "truncate": "TRUNC",
    "power": "POWER",
    "sqrt": "SQRT",
    "ln": "LN",
    "log": None,  # Custom: LOG(x, 10)
    "log2": None,  # Custom: LOG(x, 2)
    "exp": "EXP",
    "mod": "MOD",
    "int": "INT",
    "sign": "SIGN",
    # Statistical (additional)
    "percentile": "PERCENTILE.INC",
    "correlation": None,  # Custom
    "intercept": None,  # Custom
    "slope": None,  # Custom
    "rSquare": None,  # Custom
    "forecast": None,  # Custom
    # Rank/Window (additional)
    "firstinrange": None,  # Custom
    "lastinrange": None,  # Custom
    "olap_rank": None,  # Custom
    "olap_count": None,  # Custom
    "olap_sum": None,  # Custom
    "olap_avg": None,  # Custom
    # Text (additional)
    "initcap": None,  # Custom
    "lpad": None,  # Custom
    "rpad": None,  # Custom
    "reverse": None,  # Custom
    # Date (additional)
    "datediff": "DATEDIFF",
    "dateadd": "DATEADD",
    "daysinmonth": None,  # Custom
    "weekstartdate": None,  # Custom
    "weekenddate": None,  # Custom
    "quarterstartdate": "STARTOFQUARTER",
    "quarterenddate": "ENDOFQUARTER",
    # Type conversion
    "number": "VALUE",
    "text": "FORMAT",
}

# Derived metric patterns (OLAP functions)
_RE_RANK = re.compile(r'Rank\s*\((.+?)(?:,\s*(ASC|DESC))?(?:,\s*(DENSE))?\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_RUNNING_SUM = re.compile(r'RunningSum\s*\((.+?)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_RUNNING_AVG = re.compile(r'RunningAvg\s*\((.+?)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_MOVING_AVG = re.compile(r'MovingAvg\s*\((.+?),\s*(\d+)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_MOVING_SUM = re.compile(r'MovingSum\s*\((.+?),\s*(\d+)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_LAG = re.compile(r'Lag\s*\((.+?),\s*(\d+)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_LEAD = re.compile(r'Lead\s*\((.+?),\s*(\d+)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_NTILE = re.compile(r'NTile\s*\((.+?),\s*(\d+)\)\s*(\{.+?\})?', re.IGNORECASE)

# FirstInRange / LastInRange
_RE_FIRST_IN_RANGE = re.compile(r'FirstInRange\s*\((.+?),\s*(.+?)\)\s*(\{.+?\})?', re.IGNORECASE)
_RE_LAST_IN_RANGE = re.compile(r'LastInRange\s*\((.+?),\s*(.+?)\)\s*(\{.+?\})?', re.IGNORECASE)

# Banding patterns (MicroStrategy band groups)
_RE_BAND = re.compile(
    r'Band\s*\((.+?),\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)',
    re.IGNORECASE,
)

# Nested metric reference: [MetricName]
_RE_NESTED_METRIC = re.compile(r'\[([^\[\]]+)\]')

# ApplyLogic / ApplyComparison
_RE_APPLY_LOGIC = re.compile(r'ApplyLogic\s*\("(.+?)"\s*(?:,\s*(.+?))?\)', re.IGNORECASE | re.DOTALL)
_RE_APPLY_COMPARISON = re.compile(r'ApplyComparison\s*\("(.+?)"\s*(?:,\s*(.+?))?\)', re.IGNORECASE | re.DOTALL)
_RE_APPLY_OLAP = re.compile(r'ApplyOLAP\s*\("(.+?)"\s*(?:,\s*(.+?))?\)', re.IGNORECASE | re.DOTALL)

# Conditional metric: If(Condition, MetricA, MetricB)
_RE_CONDITIONAL = re.compile(
    r'\bIf\s*\((.+?),\s*(.+?),\s*(.+?)\)\s*$',
    re.IGNORECASE | re.DOTALL,
)

# Level metric pattern: {~+, Attr} or {!Attr} or {^}
_RE_LEVEL_METRIC = re.compile(r'\{([~!^+,\s\w]+)\}')

# ApplySimple pattern
_RE_APPLY_SIMPLE = re.compile(r'ApplySimple\s*\("(.+?)"\s*(?:,\s*(.+?))?\)', re.IGNORECASE | re.DOTALL)
_RE_APPLY_AGG = re.compile(r'ApplyAgg\s*\("(.+?)"\s*(?:,\s*(.+?))?\)', re.IGNORECASE | re.DOTALL)

# Common ApplySimple SQL patterns → DAX
_APPLY_SIMPLE_PATTERNS = [
    (re.compile(r"CASE\s+WHEN\s+#0\s*([><=!]+)\s*(.+?)\s+THEN\s+'(.+?)'\s+ELSE\s+'(.+?)'\s+END", re.IGNORECASE),
     lambda m: f'IF([{{0}}] {m.group(1)} {m.group(2)}, "{m.group(3)}", "{m.group(4)}")'),
    (re.compile(r"COALESCE\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "COALESCE({0}, {1})"),
    (re.compile(r"NVL\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "COALESCE({0}, {1})"),
    (re.compile(r"EXTRACT\s*\(\s*YEAR\s+FROM\s+#0\s*\)", re.IGNORECASE),
     lambda m: "YEAR({0})"),
    (re.compile(r"EXTRACT\s*\(\s*MONTH\s+FROM\s+#0\s*\)", re.IGNORECASE),
     lambda m: "MONTH({0})"),
    (re.compile(r"EXTRACT\s*\(\s*DAY\s+FROM\s+#0\s*\)", re.IGNORECASE),
     lambda m: "DAY({0})"),
    (re.compile(r"TRUNC\s*\(\s*#0\s*\)", re.IGNORECASE),
     lambda m: "TRUNC({0})"),
    (re.compile(r"CAST\s*\(\s*#0\s+AS\s+VARCHAR\s*\)", re.IGNORECASE),
     lambda m: 'FORMAT({0}, "")'),
    # ── Phase H additions: 30+ more SQL → DAX patterns ────────────
    # ISNULL / IFNULL / NVL2
    (re.compile(r"ISNULL\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "COALESCE({0}, {1})"),
    (re.compile(r"IFNULL\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "COALESCE({0}, {1})"),
    (re.compile(r"NVL2\s*\(#0\s*,\s*#1\s*,\s*#2\)", re.IGNORECASE),
     lambda m: "IF(NOT(ISBLANK({0})), {1}, {2})"),
    # DECODE (simple 2-branch)
    (re.compile(r"DECODE\s*\(#0\s*,\s*'(.+?)'\s*,\s*'(.+?)'\s*,\s*'(.+?)'\)", re.IGNORECASE),
     lambda m: f'IF([{{0}}] = "{m.group(1)}", "{m.group(2)}", "{m.group(3)}")'),
    # NULLIF
    (re.compile(r"NULLIF\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "IF({0} = {1}, BLANK(), {0})"),
    # GREATEST / LEAST (2 args)
    (re.compile(r"GREATEST\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "MAX({0}, {1})"),
    (re.compile(r"LEAST\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "MIN({0}, {1})"),
    # String patterns
    (re.compile(r"CONCAT\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "{0} & {1}"),
    (re.compile(r"CONCAT\s*\(#0\s*,\s*'(.+?)'\s*,\s*#1\)", re.IGNORECASE),
     lambda m: '{0} & "' + m.group(1) + '" & {1}'),
    (re.compile(r"SUBSTR(?:ING)?\s*\(#0\s*,\s*(\d+)\s*,\s*(\d+)\)", re.IGNORECASE),
     lambda m: f"MID({{0}}, {m.group(1)}, {m.group(2)})"),
    (re.compile(r"REPLACE\s*\(#0\s*,\s*'(.+?)'\s*,\s*'(.+?)'\)", re.IGNORECASE),
     lambda m: f'SUBSTITUTE({{0}}, "{m.group(1)}", "{m.group(2)}")'),
    (re.compile(r"UPPER\s*\(#0\)", re.IGNORECASE),
     lambda m: "UPPER({0})"),
    (re.compile(r"LOWER\s*\(#0\)", re.IGNORECASE),
     lambda m: "LOWER({0})"),
    (re.compile(r"TRIM\s*\(#0\)", re.IGNORECASE),
     lambda m: "TRIM({0})"),
    (re.compile(r"LENGTH\s*\(#0\)", re.IGNORECASE),
     lambda m: "LEN({0})"),
    (re.compile(r"INSTR\s*\(#0\s*,\s*'(.+?)'\)", re.IGNORECASE),
     lambda m: f'SEARCH("{m.group(1)}", {{0}})'),
    (re.compile(r"INITCAP\s*\(#0\)", re.IGNORECASE),
     lambda m: "PROPER({0})"),
    (re.compile(r"LPAD\s*\(#0\s*,\s*(\d+)\s*,\s*'(.)'\)", re.IGNORECASE),
     lambda m: f'REPT("{m.group(2)}", {m.group(1)} - LEN({{0}})) & {{0}}'),
    # Date patterns
    (re.compile(r"TO_DATE\s*\(#0\s*,\s*'(.+?)'\)", re.IGNORECASE),
     lambda m: f'DATEVALUE({{0}})'),
    (re.compile(r"TO_CHAR\s*\(#0\s*,\s*'(.+?)'\)", re.IGNORECASE),
     lambda m: f'FORMAT({{0}}, "{m.group(1)}")'),
    (re.compile(r"DATEADD\s*\(\s*(DAY|MONTH|YEAR|QUARTER)\s*,\s*#1\s*,\s*#0\s*\)", re.IGNORECASE),
     lambda m: f"DATEADD({{0}}, {{1}}, {m.group(1).upper()})"),
    (re.compile(r"DATEDIFF\s*\(\s*(DAY|MONTH|YEAR)\s*,\s*#0\s*,\s*#1\s*\)", re.IGNORECASE),
     lambda m: f"DATEDIFF({{0}}, {{1}}, {m.group(1).upper()})"),
    (re.compile(r"ADD_MONTHS\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "EDATE({0}, {1})"),
    (re.compile(r"LAST_DAY\s*\(#0\)", re.IGNORECASE),
     lambda m: "ENDOFMONTH({0})"),
    (re.compile(r"TRUNC\s*\(#0\s*,\s*'MM'\)", re.IGNORECASE),
     lambda m: "STARTOFMONTH({0})"),
    (re.compile(r"TRUNC\s*\(#0\s*,\s*'YYYY'\)", re.IGNORECASE),
     lambda m: "STARTOFYEAR({0})"),
    (re.compile(r"TRUNC\s*\(#0\s*,\s*'Q'\)", re.IGNORECASE),
     lambda m: "STARTOFQUARTER({0})"),
    # Numeric cast patterns
    (re.compile(r"CAST\s*\(\s*#0\s+AS\s+(?:INT(?:EGER)?|NUMERIC|DECIMAL)\s*\)", re.IGNORECASE),
     lambda m: "INT({0})"),
    (re.compile(r"CAST\s*\(\s*#0\s+AS\s+(?:FLOAT|DOUBLE|REAL)\s*\)", re.IGNORECASE),
     lambda m: "VALUE({0})"),
    (re.compile(r"CAST\s*\(\s*#0\s+AS\s+DATE\s*\)", re.IGNORECASE),
     lambda m: "DATEVALUE({0})"),
    # Math patterns
    (re.compile(r"ABS\s*\(#0\)", re.IGNORECASE),
     lambda m: "ABS({0})"),
    (re.compile(r"ROUND\s*\(#0\s*,\s*(\d+)\)", re.IGNORECASE),
     lambda m: f"ROUND({{0}}, {m.group(1)})"),
    (re.compile(r"POWER\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "POWER({0}, {1})"),
    (re.compile(r"MOD\s*\(#0\s*,\s*#1\)", re.IGNORECASE),
     lambda m: "MOD({0}, {1})"),
    (re.compile(r"SIGN\s*\(#0\)", re.IGNORECASE),
     lambda m: "SIGN({0})"),
    # CASE WHEN with numeric output
    (re.compile(r"CASE\s+WHEN\s+#0\s*([><=!]+)\s*(.+?)\s+THEN\s+(\d+(?:\.\d+)?)\s+ELSE\s+(\d+(?:\.\d+)?)\s+END", re.IGNORECASE),
     lambda m: f'IF([{{0}}] {m.group(1)} {m.group(2)}, {m.group(3)}, {m.group(4)})'),
    # CASE WHEN with IS NULL
    (re.compile(r"CASE\s+WHEN\s+#0\s+IS\s+NULL\s+THEN\s+'(.+?)'\s+ELSE\s+'(.+?)'\s+END", re.IGNORECASE),
     lambda m: f'IF(ISBLANK([{{0}}]), "{m.group(1)}", "{m.group(2)}")'),
    (re.compile(r"CASE\s+WHEN\s+#0\s+IS\s+NOT\s+NULL\s+THEN\s+'(.+?)'\s+ELSE\s+'(.+?)'\s+END", re.IGNORECASE),
     lambda m: f'IF(NOT(ISBLANK([{{0}}])), "{m.group(1)}", "{m.group(2)}")'),
]


def convert_mstr_expression_to_dax(expression, context=None):
    """Convert a MicroStrategy metric expression to DAX.

    Args:
        expression: MicroStrategy expression string
        context: Optional dict with table/column context for resolving references

    Returns:
        dict with keys:
            - dax: The converted DAX expression
            - fidelity: "full", "approximated", or "manual_review"
            - warnings: List of conversion warnings
    """
    if not expression or not expression.strip():
        return {"dax": "", "fidelity": "full", "warnings": []}

    expr = expression.strip()
    warnings = []
    fidelity = "full"
    context = context or {}

    # Try derived metric patterns first
    result = _try_derived_metric(expr, context)
    if result:
        return result

    # Try Apply functions
    result = _try_apply_functions(expr, context)
    if result:
        return result

    # Try level metric conversion
    level_match = _RE_LEVEL_METRIC.search(expr)
    if level_match:
        return _convert_level_metric(expr, level_match, context)

    # Standard function conversion
    dax = _convert_standard_expression(expr, context)

    return {"dax": dax, "fidelity": fidelity, "warnings": warnings}


def convert_metric_to_dax(metric_def, context=None):
    """Convert a full metric definition to a DAX measure expression.

    Args:
        metric_def: Metric dict from metric_extractor
        context: Table/column context

    Returns:
        dict with dax, fidelity, warnings
    """
    expression = metric_def.get("expression", "")
    metric_type = metric_def.get("metric_type", "simple")
    context = context or {}
    context["metric_name"] = metric_def.get("name", "")

    if metric_type == "derived":
        return convert_mstr_expression_to_dax(expression, context)

    # Simple metric: typically an aggregation
    agg = metric_def.get("aggregation", "sum").lower()
    column_ref = metric_def.get("column_ref", "")

    # Resolve dict column_ref to a proper column name string
    if isinstance(column_ref, dict):
        column_ref = column_ref.get("fact_name") or column_ref.get("attribute_name") or ""

    if column_ref and agg in _FUNCTION_MAP:
        dax_func = _FUNCTION_MAP[agg]
        if dax_func:
            # Use unqualified column reference — TMDL resolves within the table
            col_ref_str = f"[{column_ref}]" if column_ref else ""
            dax = f"{dax_func}({col_ref_str})"
            return {"dax": dax, "fidelity": "full", "warnings": []}

    # Fall back to expression conversion
    return convert_mstr_expression_to_dax(expression, context)


# ── Derived metric converters ────────────────────────────────────

def _try_derived_metric(expr, context):
    """Try to convert derived/OLAP metric expressions."""

    # Rank — supports ASC/DESC and DENSE options
    m = _RE_RANK.match(expr)
    if m:
        inner = m.group(1).strip()
        order_dir = (m.group(2) or "DESC").upper()
        is_dense = bool(m.group(3))
        attrs = _parse_level_spec(m.group(4)) if m.group(4) else []
        inner_dax = _convert_standard_expression(inner, context)
        rank_type = "DENSE" if is_dense else "SKIP"
        if attrs:
            return {
                "dax": f"RANKX(ALL({attrs[0]}), {inner_dax},, {order_dir}, {rank_type})",
                "fidelity": "full",
                "warnings": [],
            }
        return {
            "dax": f"RANKX(ALLSELECTED(), {inner_dax},, {order_dir}, {rank_type})",
            "fidelity": "approximated",
            "warnings": ["Rank dimension not specified — using ALLSELECTED()"],
        }

    # RunningSum — DAX WINDOW pattern
    m = _RE_RUNNING_SUM.match(expr)
    if m:
        inner = m.group(1).strip()
        attrs = _parse_level_spec(m.group(2)) if m.group(2) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else ["RunningSum — verify sort column reference"]
        return {
            "dax": (
                f"CALCULATE(\n"
                f"    {inner_dax},\n"
                f"    WINDOW(1, ABS, 0, REL, ALLSELECTED(), ORDERBY([{sort_col}], ASC))\n"
                f")"
            ),
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # RunningAvg — DAX WINDOW pattern
    m = _RE_RUNNING_AVG.match(expr)
    if m:
        inner = m.group(1).strip()
        attrs = _parse_level_spec(m.group(2)) if m.group(2) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else ["RunningAvg — verify sort column reference"]
        return {
            "dax": (
                f"VAR __rows = WINDOW(1, ABS, 0, REL, ALLSELECTED(), ORDERBY([{sort_col}], ASC))\n"
                f"RETURN\n"
                f"    DIVIDE(SUMX(__rows, {inner_dax}), COUNTROWS(__rows))"
            ),
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # MovingAvg — DAX WINDOW sliding range
    m = _RE_MOVING_AVG.match(expr)
    if m:
        inner = m.group(1).strip()
        window_size = m.group(2)
        attrs = _parse_level_spec(m.group(3)) if m.group(3) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        offset_back = int(window_size) - 1
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else [f"MovingAvg({window_size}) — verify sort column reference"]
        return {
            "dax": (
                f"VAR __rows = WINDOW(-{offset_back}, REL, 0, REL, ALLSELECTED(), ORDERBY([{sort_col}], ASC))\n"
                f"RETURN\n"
                f"    AVERAGEX(__rows, {inner_dax})"
            ),
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # Lag — DAX OFFSET
    m = _RE_LAG.match(expr)
    if m:
        inner = m.group(1).strip()
        offset = m.group(2)
        attrs = _parse_level_spec(m.group(3)) if m.group(3) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else [f"Lag({offset}) — verify sort column reference"]
        return {
            "dax": f"CALCULATE({inner_dax}, OFFSET(-{offset}, ALLSELECTED(), ORDERBY([{sort_col}], ASC)))",
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # Lead — DAX OFFSET
    m = _RE_LEAD.match(expr)
    if m:
        inner = m.group(1).strip()
        offset = m.group(2)
        attrs = _parse_level_spec(m.group(3)) if m.group(3) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else [f"Lead({offset}) — verify sort column reference"]
        return {
            "dax": f"CALCULATE({inner_dax}, OFFSET({offset}, ALLSELECTED(), ORDERBY([{sort_col}], ASC)))",
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # NTile — proper RANKX/COUNTROWS pattern
    m = _RE_NTILE.match(expr)
    if m:
        inner = m.group(1).strip()
        tiles = m.group(2)
        attrs = _parse_level_spec(m.group(3)) if m.group(3) else []
        inner_dax = _convert_standard_expression(inner, context)
        table_ref = f"ALL({attrs[0]})" if attrs else "ALLSELECTED()"
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else [f"NTile({tiles}) — verify table reference"]
        return {
            "dax": (
                f"VAR __rank = RANKX({table_ref}, {inner_dax})\n"
                f"VAR __count = COUNTROWS({table_ref})\n"
                f"RETURN\n"
                f"    INT(CEILING(DIVIDE(__rank, __count) * {tiles}, 1))"
            ),
            "fidelity": fidelity,
            "warnings": warnings,
        }

    # FirstInRange
    m = _RE_FIRST_IN_RANGE.match(expr)
    if m:
        metric = m.group(1).strip()
        sort_col = m.group(2).strip()
        metric_dax = _convert_standard_expression(metric, context)
        return {
            "dax": f"CALCULATE({metric_dax}, TOPN(1, ALLSELECTED(), [{sort_col}], ASC))",
            "fidelity": "full",
            "warnings": [],
        }

    # LastInRange
    m = _RE_LAST_IN_RANGE.match(expr)
    if m:
        metric = m.group(1).strip()
        sort_col = m.group(2).strip()
        metric_dax = _convert_standard_expression(metric, context)
        return {
            "dax": f"CALCULATE({metric_dax}, TOPN(1, ALLSELECTED(), [{sort_col}], DESC))",
            "fidelity": "full",
            "warnings": [],
        }

    # Band
    m = _RE_BAND.match(expr)
    if m:
        inner = m.group(1).strip()
        start = m.group(2)
        stop = m.group(3)
        step = m.group(4)
        inner_dax = _convert_standard_expression(inner, context)
        return {
            "dax": (
                f"VAR __val = {inner_dax}\n"
                f"RETURN\n"
                f"    IF(__val < {start}, \"Below {start}\",\n"
                f"        IF(__val >= {stop}, \"{stop}+\",\n"
                f"            INT((__val - {start}) / {step}) * {step} + {start}\n"
                f"        )\n"
                f"    )"
            ),
            "fidelity": "approximated",
            "warnings": [f"Band({start},{stop},{step}) — verify banding ranges and labels"],
        }

    # MovingSum — DAX WINDOW sliding range
    m = _RE_MOVING_SUM.match(expr)
    if m:
        inner = m.group(1).strip()
        window_size = m.group(2)
        attrs = _parse_level_spec(m.group(3)) if m.group(3) else []
        inner_dax = _convert_standard_expression(inner, context)
        sort_col = attrs[0] if attrs else "SortColumn"
        offset_back = int(window_size) - 1
        fidelity = "full" if attrs else "approximated"
        warnings = [] if attrs else [f"MovingSum({window_size}) — verify sort column reference"]
        return {
            "dax": (
                f"VAR __rows = WINDOW(-{offset_back}, REL, 0, REL, ALLSELECTED(), ORDERBY([{sort_col}], ASC))\n"
                f"RETURN\n"
                f"    SUMX(__rows, {inner_dax})"
            ),
            "fidelity": fidelity,
            "warnings": warnings,
        }

    return None


def _try_apply_functions(expr, context):
    """Try to convert ApplySimple/ApplyAgg expressions."""

    m = _RE_APPLY_SIMPLE.match(expr)
    if m:
        sql_template = m.group(1)
        args_str = m.group(2) or ""
        args = [a.strip() for a in args_str.split(',') if a.strip()] if args_str else []

        # Try known SQL patterns
        for pattern, converter in _APPLY_SIMPLE_PATTERNS:
            pm = pattern.match(sql_template)
            if pm:
                dax = converter(pm)
                # Substitute argument placeholders
                for i, arg in enumerate(args):
                    dax = dax.replace(f"{{{i}}}", f"[{arg}]")
                return {
                    "dax": dax,
                    "fidelity": "approximated",
                    "warnings": [f"ApplySimple SQL converted: {sql_template[:50]}..."],
                }

        # Unknown SQL — flag for manual review
        return {
            "dax": f"/* MANUAL REVIEW: ApplySimple(\"{sql_template}\") */\nBLANK()",
            "fidelity": "manual_review",
            "warnings": [f"ApplySimple with unconvertible SQL: {sql_template[:80]}"],
        }

    m = _RE_APPLY_AGG.match(expr)
    if m:
        return {
            "dax": f"/* MANUAL REVIEW: {expr[:80]} */\nBLANK()",
            "fidelity": "manual_review",
            "warnings": [f"ApplyAgg expression requires manual conversion: {expr[:80]}"],
        }

    # ApplyLogic
    m = _RE_APPLY_LOGIC.match(expr)
    if m:
        sql = m.group(1)
        args_str = m.group(2) or ""
        args = [a.strip() for a in args_str.split(',') if a.strip()] if args_str else []
        dax = _convert_apply_logic(sql, args)
        return dax

    # ApplyComparison
    m = _RE_APPLY_COMPARISON.match(expr)
    if m:
        sql = m.group(1)
        args_str = m.group(2) or ""
        args = [a.strip() for a in args_str.split(',') if a.strip()] if args_str else []
        return {
            "dax": _substitute_apply_args(sql, args),
            "fidelity": "approximated",
            "warnings": [f"ApplyComparison converted: {sql[:60]}"],
        }

    # ApplyOLAP — attempt conversion of common patterns
    m = _RE_APPLY_OLAP.match(expr)
    if m:
        sql = m.group(1)
        args_str = m.group(2) or ""
        args = [a.strip() for a in args_str.split(',') if a.strip()] if args_str else []
        result = _convert_apply_olap(sql, args)
        if result:
            return result
        return {
            "dax": f"/* MANUAL REVIEW: {expr[:80]} */\nBLANK()",
            "fidelity": "manual_review",
            "warnings": [f"ApplyOLAP expression requires manual conversion: {expr[:80]}"],
        }

    return None


def _convert_level_metric(expr, level_match, context):
    """Convert a level metric expression to CALCULATE + ALLEXCEPT."""
    level_spec = level_match.group(1).strip()
    base_expr = expr[:level_match.start()].strip()

    base_dax = _convert_standard_expression(base_expr, context)
    attrs = _parse_level_spec('{' + level_spec + '}')

    if '^' in level_spec:
        # Grand total: ALL
        return {
            "dax": f"CALCULATE({base_dax}, ALL(Table))",
            "fidelity": "approximated",
            "warnings": ["Level metric {^} — replace Table with actual table name"],
        }

    if '!' in level_spec:
        # Exclude filters
        excluded = [a.strip().lstrip('!') for a in level_spec.split(',') if '!' in a or a.strip()]
        removes = ', '.join(f"Table[{a}]" for a in excluded if a)
        return {
            "dax": f"CALCULATE({base_dax}, REMOVEFILTERS({removes}))",
            "fidelity": "approximated",
            "warnings": ["Level metric exclude — replace Table references"],
        }

    if attrs:
        # Specific level: ALLEXCEPT
        cols = ', '.join(f"Table[{a}]" for a in attrs)
        return {
            "dax": f"CALCULATE({base_dax}, ALLEXCEPT(Table, {cols}))",
            "fidelity": "approximated",
            "warnings": ["Level metric — replace Table references with actual table"],
        }

    return {
        "dax": base_dax,
        "fidelity": "full",
        "warnings": [],
    }


def _convert_standard_expression(expr, context):
    """Convert standard function calls in an expression to DAX."""
    result = expr

    # Replace known function names (case-insensitive)
    for mstr_func, dax_func in _FUNCTION_MAP.items():
        if dax_func:
            pattern = re.compile(rf'\b{re.escape(mstr_func)}\s*\(', re.IGNORECASE)
            result = pattern.sub(f'{dax_func}(', result)

    # Handle special functions
    result = _handle_special_functions(result, context)

    return result


def _handle_special_functions(expr, context):
    """Handle functions that need custom DAX conversion."""

    # NullToZero(x) → IF(ISBLANK(x), 0, x)
    expr = re.sub(
        r'NullToZero\s*\((.+?)\)',
        lambda m: f'IF(ISBLANK({m.group(1)}), 0, {m.group(1)})',
        expr, flags=re.IGNORECASE
    )

    # ZeroToNull(x) → IF(x = 0, BLANK(), x)
    expr = re.sub(
        r'ZeroToNull\s*\((.+?)\)',
        lambda m: f'IF({m.group(1)} = 0, BLANK(), {m.group(1)})',
        expr, flags=re.IGNORECASE
    )

    # IsNotNull(x) → NOT(ISBLANK(x))
    expr = re.sub(
        r'IsNotNull\s*\((.+?)\)',
        lambda m: f'NOT(ISBLANK({m.group(1)}))',
        expr, flags=re.IGNORECASE
    )

    # DaysBetween(a, b) → DATEDIFF(a, b, DAY)
    expr = re.sub(
        r'DaysBetween\s*\((.+?),\s*(.+?)\)',
        lambda m: f'DATEDIFF({m.group(1)}, {m.group(2)}, DAY)',
        expr, flags=re.IGNORECASE
    )

    # MonthsBetween(a, b) → DATEDIFF(a, b, MONTH)
    expr = re.sub(
        r'MonthsBetween\s*\((.+?),\s*(.+?)\)',
        lambda m: f'DATEDIFF({m.group(1)}, {m.group(2)}, MONTH)',
        expr, flags=re.IGNORECASE
    )

    # YearsBetween(a, b) → DATEDIFF(a, b, YEAR)
    expr = re.sub(
        r'YearsBetween\s*\((.+?),\s*(.+?)\)',
        lambda m: f'DATEDIFF({m.group(1)}, {m.group(2)}, YEAR)',
        expr, flags=re.IGNORECASE
    )

    # Ceiling(x) → CEILING(x, 1)
    expr = re.sub(
        r'CEILING\s*\(([^,)]+)\)',
        lambda m: f'CEILING({m.group(1)}, 1)',
        expr, flags=re.IGNORECASE
    )

    # Floor(x) → FLOOR(x, 1)
    expr = re.sub(
        r'FLOOR\s*\(([^,)]+)\)',
        lambda m: f'FLOOR({m.group(1)}, 1)',
        expr, flags=re.IGNORECASE
    )

    # Log(x) → LOG(x, 10)
    expr = re.sub(
        r'\bLog\s*\(([^,)]+)\)',
        lambda m: f'LOG({m.group(1)}, 10)',
        expr, flags=re.IGNORECASE
    )

    # AddDays(d, n) → d + n
    expr = re.sub(
        r'AddDays\s*\((.+?),\s*(.+?)\)',
        lambda m: f'({m.group(1)} + {m.group(2)})',
        expr, flags=re.IGNORECASE
    )

    # Phase H additional functions
    expr = _handle_additional_functions(expr, context)

    return expr


def _handle_additional_functions(expr, context):
    """Handle additional special functions added in Phase H."""

    # InitCap(x) → PROPER(x)
    expr = re.sub(
        r'InitCap\s*\((.+?)\)',
        lambda m: f'PROPER({m.group(1)})',
        expr, flags=re.IGNORECASE
    )

    # LPad(x, n, c) → REPT(c, n - LEN(x)) & x
    expr = re.sub(
        r'LPad\s*\((.+?),\s*(\d+),\s*["\'](.)["\']\)',
        lambda m: f'REPT("{m.group(3)}", {m.group(2)} - LEN({m.group(1)})) & {m.group(1)}',
        expr, flags=re.IGNORECASE
    )

    # RPad(x, n, c) → x & REPT(c, n - LEN(x))
    expr = re.sub(
        r'RPad\s*\((.+?),\s*(\d+),\s*["\'](.)["\']\)',
        lambda m: f'{m.group(1)} & REPT("{m.group(3)}", {m.group(2)} - LEN({m.group(1)}))',
        expr, flags=re.IGNORECASE
    )

    # Reverse(x) → not native in DAX, leave as comment
    expr = re.sub(
        r'Reverse\s*\((.+?)\)',
        lambda m: f'/* REVERSE not supported in DAX */ {m.group(1)}',
        expr, flags=re.IGNORECASE
    )

    # DaysInMonth(d) → DAY(ENDOFMONTH(d))
    expr = re.sub(
        r'DaysInMonth\s*\((.+?)\)',
        lambda m: f'DAY(ENDOFMONTH({m.group(1)}))',
        expr, flags=re.IGNORECASE
    )

    # WeekStartDate(d) → d - WEEKDAY(d, 2) + 1
    expr = re.sub(
        r'WeekStartDate\s*\((.+?)\)',
        lambda m: f'({m.group(1)} - WEEKDAY({m.group(1)}, 2) + 1)',
        expr, flags=re.IGNORECASE
    )

    # WeekEndDate(d) → d - WEEKDAY(d, 2) + 7
    expr = re.sub(
        r'WeekEndDate\s*\((.+?)\)',
        lambda m: f'({m.group(1)} - WEEKDAY({m.group(1)}, 2) + 7)',
        expr, flags=re.IGNORECASE
    )

    return expr


def _parse_level_spec(spec_str):
    """Parse a level metric specification string like '{~+, Year, Region}'.

    Returns list of attribute names.
    """
    if not spec_str:
        return []
    # Remove braces
    inner = spec_str.strip('{}').strip()
    # Split by comma, filter out operators
    parts = [p.strip() for p in inner.split(',')]
    attrs = [p for p in parts if p and p not in ('~', '~+', '!', '^', '+')]
    return attrs


# ── Apply function helpers ───────────────────────────────────────


def _convert_apply_logic(sql, args):
    """Convert ApplyLogic SQL to DAX."""
    # Common ApplyLogic patterns: AND/OR with #0, #1
    dax = sql
    # Replace SQL logical operators
    dax = re.sub(r'\bAND\b', '&&', dax, flags=re.IGNORECASE)
    dax = re.sub(r'\bOR\b', '||', dax, flags=re.IGNORECASE)
    dax = _substitute_apply_args(dax, args)

    return {
        "dax": dax,
        "fidelity": "approximated",
        "warnings": [f"ApplyLogic converted: {sql[:60]}"],
    }


def _substitute_apply_args(template, args):
    """Replace #0, #1, ... placeholders with [arg] references."""
    result = template
    for i, arg in enumerate(args):
        result = result.replace(f"#{i}", f"[{arg}]")
    return result


def _convert_apply_olap(sql, args):
    """Convert common ApplyOLAP SQL expressions to DAX.

    Handles ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD patterns found in
    MicroStrategy ApplyOLAP expressions.
    """
    sql_upper = sql.upper().strip()
    arg_refs = [f"[{a}]" for a in args]

    # ROW_NUMBER() OVER (ORDER BY #0)
    rn = re.match(r'ROW_NUMBER\s*\(\)\s*OVER\s*\((.+?)\)', sql, re.IGNORECASE)
    if rn:
        over_clause = rn.group(1)
        order_col = arg_refs[0] if arg_refs else "[SortColumn]"
        order_dir = "DESC" if re.search(r'DESC', over_clause, re.IGNORECASE) else "ASC"
        partition_m = re.search(r'PARTITION\s+BY\s+#(\d+)', over_clause, re.IGNORECASE)
        if partition_m:
            p_idx = int(partition_m.group(1))
            part_col = arg_refs[p_idx] if p_idx < len(arg_refs) else "[Partition]"
            return {
                "dax": f"RANKX(FILTER(ALLSELECTED(), {part_col} = EARLIER({part_col})), {order_col},, {order_dir}, DENSE)",
                "fidelity": "approximated",
                "warnings": ["ROW_NUMBER partitioned — verify partition column"],
            }
        return {
            "dax": f"RANKX(ALLSELECTED(), {order_col},, {order_dir}, DENSE)",
            "fidelity": "full",
            "warnings": [],
        }

    # RANK() OVER (ORDER BY #0)
    rank_m = re.match(r'(?:DENSE_)?RANK\s*\(\)\s*OVER\s*\((.+?)\)', sql, re.IGNORECASE)
    if rank_m:
        over_clause = rank_m.group(1)
        is_dense = sql_upper.startswith('DENSE')
        order_col = arg_refs[0] if arg_refs else "[SortColumn]"
        order_dir = "DESC" if re.search(r'DESC', over_clause, re.IGNORECASE) else "ASC"
        rank_type = "DENSE" if is_dense else "SKIP"
        return {
            "dax": f"RANKX(ALLSELECTED(), {order_col},, {order_dir}, {rank_type})",
            "fidelity": "full",
            "warnings": [],
        }

    # LAG(#0, n) OVER (ORDER BY #1)
    lag_m = re.match(r'LAG\s*\(#0\s*,\s*(\d+)\)\s*OVER\s*\((.+?)\)', sql, re.IGNORECASE)
    if lag_m:
        offset = lag_m.group(1)
        over_clause = lag_m.group(2)
        val_col = arg_refs[0] if arg_refs else "[Value]"
        sort_col = arg_refs[1] if len(arg_refs) > 1 else "[SortColumn]"
        return {
            "dax": f"CALCULATE({val_col}, OFFSET(-{offset}, ALLSELECTED(), ORDERBY({sort_col}, ASC)))",
            "fidelity": "full",
            "warnings": [],
        }

    # LEAD(#0, n) OVER (ORDER BY #1)
    lead_m = re.match(r'LEAD\s*\(#0\s*,\s*(\d+)\)\s*OVER\s*\((.+?)\)', sql, re.IGNORECASE)
    if lead_m:
        offset = lead_m.group(1)
        val_col = arg_refs[0] if arg_refs else "[Value]"
        sort_col = arg_refs[1] if len(arg_refs) > 1 else "[SortColumn]"
        return {
            "dax": f"CALCULATE({val_col}, OFFSET({offset}, ALLSELECTED(), ORDERBY({sort_col}, ASC)))",
            "fidelity": "full",
            "warnings": [],
        }

    # SUM(#0) OVER (ORDER BY #1 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    cum_m = re.match(r'SUM\s*\(#0\)\s*OVER\s*\(.*?ORDER\s+BY\s+#(\d+).*?UNBOUNDED\s+PRECEDING', sql, re.IGNORECASE)
    if cum_m:
        val_col = arg_refs[0] if arg_refs else "[Value]"
        s_idx = int(cum_m.group(1))
        sort_col = arg_refs[s_idx] if s_idx < len(arg_refs) else "[SortColumn]"
        return {
            "dax": f"CALCULATE({val_col}, WINDOW(1, ABS, 0, REL, ALLSELECTED(), ORDERBY({sort_col}, ASC)))",
            "fidelity": "full",
            "warnings": [],
        }

    return None


# ── Nested metric resolution ────────────────────────────────────


def resolve_nested_metrics(expression, metric_lookup):
    """Resolve nested metric references like [MetricName] to their DAX.

    Args:
        expression: DAX expression string (may contain [MetricName] refs).
        metric_lookup: dict mapping metric names → DAX expressions.

    Returns:
        Resolved expression (one level deep to avoid infinite recursion).
    """
    def _replacer(m):
        name = m.group(1)
        if name in metric_lookup:
            return f"({metric_lookup[name]})"
        return m.group(0)  # leave as-is if not found

    return _RE_NESTED_METRIC.sub(_replacer, expression)


# ── Cross-table context helper ───────────────────────────────────


def qualify_column_references(expression, table_name):
    """Qualify bare column references with a table name.

    Turns ``SUM(Revenue)`` into ``SUM('TableName'[Revenue])``
    where Revenue is a bare word inside an aggregation function.

    Args:
        expression: DAX expression string.
        table_name: Table name to qualify bare columns with.

    Returns:
        Expression with qualified column references.
    """
    # Match: FUNC(bareword) where bareword is not already Table[Col]
    def _qualify(m):
        func = m.group(1)
        arg = m.group(2).strip()
        # Already qualified?
        if '[' in arg or "'" in arg:
            return m.group(0)
        return f"{func}('{table_name}'[{arg}])"

    return re.sub(
        r'(\b(?:SUM|AVERAGE|COUNT|MIN|MAX|DISTINCTCOUNT|STDEV\.S|STDEV\.P|MEDIAN)\b)\s*\((\w+)\)',
        _qualify,
        expression,
        flags=re.IGNORECASE,
    )
