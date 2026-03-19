"""
TMDL semantic model generator.

Generates Tabular Model Definition Language (.tmdl) files from
intermediate JSON extracted from MicroStrategy.
"""

import logging
import os
import re

from microstrategy_export.connection_mapper import map_connection_to_m_query
from microstrategy_export.expression_converter import convert_metric_to_dax, convert_mstr_expression_to_dax

logger = logging.getLogger(__name__)

# ── MSTR data type → TMDL data type mapping ──────────────────────

_DATA_TYPE_MAP = {
    "integer": "int64",
    "int": "int64",
    "biginteger": "int64",
    "long": "int64",
    "smallint": "int64",
    "tinyint": "int64",
    "real": "double",
    "float": "double",
    "double": "double",
    "numeric": "double",
    "decimal": "decimal",
    "bigdecimal": "decimal",
    "money": "decimal",
    "nvarchar": "string",
    "varchar": "string",
    "char": "string",
    "nchar": "string",
    "text": "string",
    "longvarchar": "string",
    "date": "dateTime",
    "datetime": "dateTime",
    "timestamp": "dateTime",
    "time": "dateTime",
    "boolean": "boolean",
    "bit": "boolean",
    "binary": "binary",
    "varbinary": "binary",
    "blob": "binary",
}

# Geographic role mapping: MSTR role → TMDL dataCategory
_GEO_ROLE_MAP = {
    "city": "City",
    "state_province": "StateOrProvince",
    "state": "StateOrProvince",
    "country": "Country",
    "continent": "Continent",
    "county": "County",
    "postal_code": "PostalCode",
    "zip_code": "PostalCode",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "address": "Address",
    "place": "Place",
}


def generate_all_tmdl(data, output_dir):
    """Generate all TMDL files from intermediate JSON data.

    Args:
        data: dict with keys from intermediate JSON (datasources, attributes,
              facts, metrics, derived_metrics, hierarchies, relationships,
              security_filters, freeform_sql)
        output_dir: Directory to write .tmdl files

    Returns:
        dict with generation statistics
    """
    os.makedirs(output_dir, exist_ok=True)
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    attributes = data.get("attributes", [])
    facts = data.get("facts", [])
    metrics = data.get("metrics", [])
    derived_metrics = data.get("derived_metrics", [])
    hierarchies = data.get("hierarchies", [])
    relationships = data.get("relationships", [])
    security_filters = data.get("security_filters", [])
    freeform_sql = data.get("freeform_sql", [])

    # Build lookup indexes
    attr_by_id = {a["id"]: a for a in attributes}
    attr_by_table = _group_attributes_by_table(attributes)
    fact_by_table = _group_facts_by_table(facts)
    hier_by_table = _group_hierarchies_by_table(hierarchies, attr_by_id)
    metrics_by_table = _assign_metrics_to_tables(metrics, facts, datasources)
    derived_by_table = _assign_metrics_to_tables(derived_metrics, facts, datasources)

    stats = {
        "tables": 0,
        "columns": 0,
        "measures": 0,
        "hierarchies": 0,
        "relationships": 0,
        "roles": 0,
        "warnings": [],
    }

    # Generate table TMDL files
    for ds in datasources:
        table_name = ds["name"]
        tmdl = generate_table_tmdl(
            ds, attr_by_table.get(table_name, []),
            fact_by_table.get(table_name, []),
            metrics_by_table.get(table_name, []),
            derived_by_table.get(table_name, []),
            hier_by_table.get(table_name, []),
            attr_by_id,
        )

        table_path = os.path.join(tables_dir, f"{table_name}.tmdl")
        with open(table_path, 'w', encoding='utf-8') as f:
            f.write(tmdl)
        stats["tables"] += 1
        logger.info("Generated table TMDL: %s", table_name)

    # Generate freeform SQL tables
    for ffs in freeform_sql:
        tmdl = _generate_freeform_table_tmdl(ffs)
        table_path = os.path.join(tables_dir, f"{ffs['name']}.tmdl")
        with open(table_path, 'w', encoding='utf-8') as f:
            f.write(tmdl)
        stats["tables"] += 1

    # Generate relationships
    if relationships:
        rel_tmdl = generate_relationships_tmdl(relationships)
        rel_path = os.path.join(output_dir, "relationships.tmdl")
        with open(rel_path, 'w', encoding='utf-8') as f:
            f.write(rel_tmdl)
        stats["relationships"] = len(relationships)

    # Generate RLS roles
    if security_filters:
        roles_tmdl = generate_roles_tmdl(security_filters, attr_by_id)
        roles_path = os.path.join(output_dir, "roles.tmdl")
        with open(roles_path, 'w', encoding='utf-8') as f:
            f.write(roles_tmdl)
        stats["roles"] = len(security_filters)

    # Count stats from generated content
    for ds in datasources:
        stats["columns"] += len(ds.get("columns", []))
    stats["measures"] = len(metrics) + len(derived_metrics)
    for h_list in hier_by_table.values():
        stats["hierarchies"] += len(h_list)

    return stats


def generate_table_tmdl(datasource, table_attrs, table_facts, table_metrics,
                        table_derived, table_hierarchies, attr_by_id):
    """Generate TMDL content for a single table.

    Args:
        datasource: Table dict from datasources.json
        table_attrs: List of attributes on this table
        table_facts: List of facts on this table
        table_metrics: List of metrics assigned to this table
        table_derived: List of derived metrics assigned to this table
        table_hierarchies: List of (hierarchy_name, levels) tuples for this table
        attr_by_id: Attribute lookup dict

    Returns:
        str: TMDL content
    """
    table_name = datasource["name"]
    table_id = datasource.get("id", "")
    columns = datasource.get("columns", [])
    connection = datasource.get("db_connection", {})

    lines = [f"table {table_name}"]
    if table_id:
        lines.append(f"\tlineageTag: {table_id}")

    # Determine which columns are fact table columns (hidden)
    fact_columns = set()
    for fact in table_facts:
        for expr in fact.get("expressions", []):
            if expr.get("table") == table_name:
                fact_columns.add(expr["column"])

    # Determine attribute key columns (hidden)
    key_columns = set()
    desc_columns = {}
    geo_columns = {}
    for attr in table_attrs:
        for form in attr.get("forms", []):
            if form.get("table") == table_name:
                if form.get("category") == "ID":
                    key_columns.add(form["column_name"])
                elif form.get("category") == "DESC":
                    desc_columns[form["column_name"]] = attr["name"]
        if attr.get("geographic_role") and attr.get("forms"):
            for form in attr["forms"]:
                if form.get("table") == table_name:
                    geo_columns[form["column_name"]] = attr["geographic_role"]

    # Is this a fact table? All non-key/non-FK columns should be hidden
    is_fact_table = any(f.get("expressions", [{}])[0].get("table") == table_name
                        for f in table_facts if f.get("expressions"))

    # TMDL allows only one isKey column per table, and it must be a physical column.
    # Pick the best single primary key from the key columns.
    primary_key = None
    if not is_fact_table and key_columns:
        table_id_col = f"{table_name}_ID" if not table_name.endswith("_ID") else table_name
        # Prefer column matching TABLE_ID pattern
        for col_name in key_columns:
            if col_name.upper() == table_id_col.upper():
                primary_key = col_name
                break
        if not primary_key:
            # Fall back to first _ID column alphabetically
            id_cols = sorted(c for c in key_columns if c.upper().endswith("_ID"))
            primary_key = id_cols[0] if id_cols else sorted(key_columns)[0]

    # Generate columns — also collect display names for hierarchy collision check
    col_display_names = set()
    lines.append("")
    for col in columns:
        col_name = col["name"]
        tmdl_type = _map_data_type(col.get("data_type", "string"))
        display_name = col_name

        # Use friendly name from attribute DESC form
        if col_name in desc_columns:
            display_name = desc_columns[col_name]

        col_display_names.add(display_name)

        # Quote names with spaces or special chars
        name_str = f"'{display_name}'" if _needs_quoting(display_name) else display_name

        lines.append(f"\tcolumn {name_str}")
        lines.append(f"\t\tdataType: {tmdl_type}")

        # Hidden: key columns and fact table columns
        if col_name in key_columns or is_fact_table:
            lines.append("\t\tisHidden")

        # Key column — only one physical column per table
        if col_name == primary_key:
            lines.append("\t\tisKey")

        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append(f"\t\tlineageTag: col-{_make_tag(table_name, col_name)}")

        # Geographic data category
        geo_role = geo_columns.get(col_name)
        if geo_role:
            category = _GEO_ROLE_MAP.get(geo_role.lower())
            if category:
                lines.append(f"\t\tdataCategory: {category}")

        lines.append("")

    # Generate measures (metrics assigned to this table)
    all_measures = table_metrics + table_derived
    for metric in all_measures:
        measure_lines = _generate_measure(metric, table_name)
        lines.extend(measure_lines)

    # Generate hierarchies
    for hier_name, levels in table_hierarchies:
        hier_lines = _generate_hierarchy(hier_name, levels, attr_by_id, table_name, columns, col_display_names)
        lines.extend(hier_lines)

    # Generate M partition
    partition_lines = _generate_partition(datasource)
    lines.extend(partition_lines)

    return '\n'.join(lines).rstrip() + '\n'


def generate_relationships_tmdl(relationships):
    """Generate relationships.tmdl content.

    Args:
        relationships: List of relationship dicts from relationships.json

    Returns:
        str: TMDL content
    """
    blocks = []
    for rel in relationships:
        from_table = rel["from_table"]
        from_col = rel["from_column"]
        to_table = rel["to_table"]
        to_col = rel["to_column"]
        name = f"rel_{from_table}_{to_table}"

        lines = [f"relationship {name}"]
        lines.append(f"\tfromColumn: {from_table}.{from_col}")
        lines.append(f"\ttoColumn: {to_table}.{to_col}")

        cross_filter = rel.get("cross_filter", "single")
        if cross_filter == "both":
            lines.append("\tcrossFilteringBehavior: bothDirections")
        else:
            lines.append("\tcrossFilteringBehavior: oneDirection")

        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks) + '\n'


def generate_roles_tmdl(security_filters, attr_by_id):
    """Generate roles.tmdl content from security filters.

    Args:
        security_filters: List from security_filters.json
        attr_by_id: Attribute lookup dict

    Returns:
        str: TMDL content
    """
    blocks = []
    for sf in security_filters:
        name = sf["name"]
        lines = [f"role '{name}'"]
        lines.append("")

        # Find the target table and column from target attributes
        for target in sf.get("target_attributes", []):
            attr = attr_by_id.get(target.get("id", ""))
            if attr:
                table_name = attr.get("lookup_table", "")
                # Find the column used in the filter expression
                col_name = _resolve_filter_column(attr, sf.get("expression", ""))
                if table_name and col_name:
                    filter_expr = _convert_security_expression(sf.get("expression", ""), col_name)
                    lines.append(f"\ttablePermission {table_name}")
                    lines.append(f"\t\tfilterExpression:= {filter_expr}")

        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks) + '\n'


# ── Private helpers ──────────────────────────────────────────────

def _map_data_type(mstr_type):
    """Map MicroStrategy data type to TMDL data type."""
    return _DATA_TYPE_MAP.get(mstr_type.lower().strip(), "string")


def _needs_quoting(name):
    """Check if a TMDL name needs quoting with single quotes."""
    return bool(re.search(r'[\s\-/\\().,;:!@#$%^&*+=\[\]{}|<>?\'"]', name))


def _make_tag(table_name, col_name):
    """Generate a deterministic lineage tag fragment."""
    combined = f"{table_name}-{col_name}".lower()
    # Simple hash-like tag
    h = 0
    for c in combined:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return f"{h:08x}"


def _group_attributes_by_table(attributes):
    """Group attributes by their lookup table."""
    by_table = {}
    for attr in attributes:
        table = attr.get("lookup_table", "")
        if table:
            by_table.setdefault(table, []).append(attr)
    return by_table


def _group_facts_by_table(facts):
    """Group facts by their expression tables."""
    by_table = {}
    for fact in facts:
        for expr in fact.get("expressions", []):
            table = expr.get("table", "")
            if table:
                by_table.setdefault(table, []).append(fact)
    return by_table


def _group_hierarchies_by_table(hierarchies, attr_by_id):
    """Group hierarchies by the table that owns most of their attributes.

    Returns dict of table_name → [(hier_name, levels)]
    """
    by_table = {}
    for hier in hierarchies:
        levels = hier.get("levels", [])
        if not levels:
            continue

        # Determine owning table from first level's attribute
        table_counts = {}
        for level in levels:
            attr = attr_by_id.get(level.get("attribute_id", ""))
            if attr:
                table = attr.get("lookup_table", "")
                if table:
                    table_counts[table] = table_counts.get(table, 0) + 1

        if table_counts:
            # Assign to the table with the most levels
            owner_table = max(table_counts, key=table_counts.get)
            by_table.setdefault(owner_table, []).append(
                (hier["name"], levels)
            )

    return by_table


def _assign_metrics_to_tables(metrics, facts, datasources):
    """Assign metrics to tables based on their column references.

    Simple metrics go to the fact table they reference.
    Compound/derived metrics go to the first fact table found.
    """
    by_table = {}
    # Find the primary fact table
    fact_tables = [ds["name"] for ds in datasources
                   if ds["name"].upper().startswith("FACT_")]
    default_table = fact_tables[0] if fact_tables else (
        datasources[0]["name"] if datasources else "")

    fact_table_map = {}
    for fact in facts:
        for expr in fact.get("expressions", []):
            fact_table_map[fact["name"].lower()] = expr.get("table", default_table)
            fact_table_map[fact["id"]] = expr.get("table", default_table)

    for metric in metrics:
        table = default_table
        col_ref = metric.get("column_ref")
        if col_ref:
            fact_name = col_ref.get("fact_name", "")
            fact_id = col_ref.get("fact_id", "")
            table = fact_table_map.get(fact_name.lower(),
                    fact_table_map.get(fact_id, default_table))

        by_table.setdefault(table, []).append(metric)

    return by_table


def _generate_measure(metric, table_name):
    """Generate TMDL measure lines for a metric."""
    name = metric["name"]
    name_str = f"'{name}'" if _needs_quoting(name) else name

    # Convert expression to DAX
    result = convert_metric_to_dax(metric)
    dax = result.get("dax", "")

    # For compound metrics that reference other metrics by name,
    # resolve to DAX measure references [Measure Name]
    if metric.get("metric_type") == "compound" and metric.get("dependencies"):
        dax = _resolve_compound_dax(metric, table_name)

    if not dax:
        dax = f"/* TODO: {metric.get('expression', '')} */"

    # TMDL requires multi-line expressions to be wrapped in triple-backtick blocks
    if '\n' in dax:
        lines = [f"\tmeasure {name_str} = ```"]
        for expr_line in dax.split('\n'):
            lines.append(f"\t\t\t{expr_line}")
        lines.append("\t\t\t```")
    else:
        lines = [f"\tmeasure {name_str} = {dax}"]

    fmt = metric.get("format_string", "")
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")

    # Display folder from folder path
    folder = _extract_display_folder(metric.get("folder_path", ""))
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")

    lines.append(f"\t\tlineageTag: {metric.get('id', _make_tag(table_name, name))}")
    lines.append("")

    return lines


def _resolve_compound_dax(metric, table_name):
    """Resolve compound metric expression to DAX using measure references."""
    expression = metric.get("expression", "")

    # Common compound patterns
    # Pattern: MetricA - MetricB → [MetricA] - [MetricB]
    # Pattern: (MetricA - MetricB) / MetricA → DIVIDE([MetricA] - [MetricB], [MetricA])

    result = convert_mstr_expression_to_dax(expression)
    dax = result.get("dax", expression)
    return dax


def _extract_display_folder(folder_path):
    """Extract display folder name from MSTR folder path."""
    if not folder_path:
        return ""
    # Take the last meaningful segment
    parts = [p for p in folder_path.replace("\\", "/").split("/") if p]
    # Skip common prefixes
    skip = {"Public Objects", "Metrics"}
    meaningful = [p for p in parts if p not in skip]
    return meaningful[-1] if meaningful else (parts[-1] if parts else "")


def _generate_hierarchy(hier_name, levels, attr_by_id, table_name, table_columns, col_display_names=None):
    """Generate TMDL hierarchy block."""
    # Disambiguate if hierarchy name collides with a column name
    if col_display_names and hier_name in col_display_names:
        hier_name = f"{hier_name} Hierarchy"
    name_str = f"'{hier_name}'" if _needs_quoting(hier_name) else hier_name

    lines = [f"\thierarchy {name_str}"]
    lines.append(f"\t\tlineageTag: hier-{_make_tag(table_name, hier_name)}")
    lines.append("")

    col_names = {c["name"] for c in table_columns}

    for level in sorted(levels, key=lambda l: l.get("order", 0)):
        level_name = level["name"]
        level_name_str = f"'{level_name}'" if _needs_quoting(level_name) else level_name

        # Resolve level to a column on this table
        attr = attr_by_id.get(level.get("attribute_id", ""))
        col_ref = _resolve_hierarchy_level_column(attr, table_name, col_names, level_name)

        lines.append(f"\t\tlevel {level_name_str}")
        lines.append(f"\t\t\tcolumn: {col_ref}")
        lines.append(f"\t\t\tlineageTag: hier-{_make_tag(table_name, hier_name + '-' + level_name)}")
        lines.append("")

    return lines


def _fuzzy_match_column(level_name, table_col_names):
    """Try to match a hierarchy level name to a table column by name patterns."""
    if not level_name or not table_col_names:
        return None
    name_lower = level_name.lower().replace(" ", "_")
    # Exact match (case-insensitive)
    for col in table_col_names:
        if col.lower() == name_lower:
            return col
    # Match with _ID suffix (e.g., "Quarter" → "QUARTER_ID")
    for col in table_col_names:
        if col.lower() == f"{name_lower}_id":
            return col
    # Match as substring (e.g., "Quarter" in "QUARTER_NAME")
    for col in table_col_names:
        if name_lower in col.lower():
            return col
    return None


def _resolve_hierarchy_level_column(attr, table_name, table_col_names, level_name=""):
    """Resolve an attribute to the best column reference for a hierarchy level."""
    if not attr:
        # Attribute not found — try to match level name to a table column
        return _fuzzy_match_column(level_name, table_col_names) or "UNKNOWN"

    # Look for ID form first, then DESC form
    id_col = None
    desc_col = None
    for form in attr.get("forms", []):
        if form.get("table") == table_name:
            if form.get("category") == "ID":
                id_col = form["column_name"]
            elif form.get("category") == "DESC":
                desc_col = form["column_name"]

    # Prefer DESC column for display, but use ID if no DESC
    chosen = desc_col or id_col
    if not chosen:
        # Fallback: use any form on this table
        for form in attr.get("forms", []):
            if form.get("table") == table_name:
                chosen = form["column_name"]
                break

    if not chosen:
        # Attribute is on a different table — use the ID form column name
        for form in attr.get("forms", []):
            if form.get("category") == "ID":
                chosen = form["column_name"]
                break

    if not chosen:
        return "UNKNOWN"

    # Check if this column name matches a friendly-named column
    # If the column has a DESC form mapped, use the attribute name
    if chosen in table_col_names:
        # Check if there's a DESC form with a friendly name
        for form in attr.get("forms", []):
            if form.get("column_name") == chosen and form.get("category") == "DESC":
                friendly = attr["name"]
                return f"'{friendly}'" if _needs_quoting(friendly) else friendly

    return chosen


def _generate_partition(datasource):
    """Generate TMDL M partition block."""
    table_name = datasource["name"]
    connection = datasource.get("db_connection", {})
    schema = connection.get("schema", "")
    sql = datasource.get("sql_statement", "")

    m_query = map_connection_to_m_query(
        connection,
        table_name=datasource.get("physical_table", table_name),
        schema=schema,
        sql_statement=sql if sql else None,
    )

    lines = [""]
    lines.append(f"\tpartition {table_name} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\texpression:= ```")
    # Indent M query
    for m_line in m_query.split('\n'):
        lines.append(f"\t\t\t{m_line}")
    lines.append("\t\t\t```")

    return lines


def _generate_freeform_table_tmdl(freeform):
    """Generate TMDL for a freeform SQL table."""
    table_name = freeform["name"]
    columns = freeform.get("columns", [])
    connection = freeform.get("db_connection", {})
    sql = freeform.get("sql_statement", "")

    lines = [f"table {table_name}"]
    lines.append(f"\tlineageTag: {freeform.get('id', _make_tag('ffs', table_name))}")
    lines.append("")

    for col in columns:
        col_name = col["name"]
        tmdl_type = _map_data_type(col.get("data_type", "string"))
        lines.append(f"\tcolumn {col_name}")
        lines.append(f"\t\tdataType: {tmdl_type}")
        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append(f"\t\tlineageTag: col-{_make_tag(table_name, col_name)}")
        lines.append("")

    # Partition with native query
    m_query = map_connection_to_m_query(
        connection, table_name=table_name, sql_statement=sql
    )
    lines.append(f"\tpartition {table_name} = m")
    lines.append("\t\tmode: import")
    lines.append("\t\texpression:= ```")
    for m_line in m_query.split('\n'):
        lines.append(f"\t\t\t{m_line}")
    lines.append("\t\t\t```")

    return '\n'.join(lines).rstrip() + '\n'


def _resolve_filter_column(attr, expression):
    """Resolve which attribute column is used in a security filter expression."""
    # Look for DESC form first (more meaningful for filters), then ID
    for form in attr.get("forms", []):
        if form.get("category") == "DESC":
            return form["column_name"]
    for form in attr.get("forms", []):
        if form.get("category") == "ID":
            return form["column_name"]
    return ""


def _convert_security_expression(expression, column_name):
    """Convert a MicroStrategy security filter expression to DAX filter."""
    # Pattern: "Attribute In (val1, val2)" → [COLUMN] IN {"val1", "val2"}
    in_match = re.match(r'.+?\s+In\s+\((.+)\)', expression, re.IGNORECASE)
    if in_match:
        values = [v.strip() for v in in_match.group(1).split(',')]
        val_str = ', '.join(f'"{v}"' for v in values)
        return f"[{column_name}] IN {{{val_str}}}"

    # Fallback: direct expression
    return f"/* {expression} */"


def generate_calendar_table_tmdl(date_columns, start_year=None, end_year=None):
    """Generate a Calendar auto-table TMDL using an M partition.

    Uses Power Query M (not DAX CALENDAR) to avoid 'invalid column ID'
    errors — calculated-table partitions cannot be referenced by hierarchies
    or relationships reliably in TMDL.

    Args:
        date_columns: List of (table_name, column_name) for date columns
        start_year: Optional start year (default: 2020)
        end_year: Optional end year (default: 2030)

    Returns:
        str: TMDL content for Calendar table
    """
    start_year = start_year or 2020
    end_year = end_year or 2030

    lines = ["table Calendar"]
    lines.append("\tlineageTag: calendar-auto-generated")
    lines.append("")

    cal_columns = [
        ("Date", "dateTime", True),
        ("Year", "int64", False),
        ("Quarter", "string", False),
        ("Month", "int64", False),
        ("MonthName", "string", False),
        ("Day", "int64", False),
        ("DayOfWeek", "int64", False),
        ("DayName", "string", False),
        ("WeekOfYear", "int64", False),
    ]

    for col_name, dtype, is_key in cal_columns:
        lines.append(f"\tcolumn {col_name}")
        lines.append(f"\t\tdataType: {dtype}")
        if is_key:
            lines.append("\t\tisKey")
        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append(f"\t\tlineageTag: cal-{col_name.lower()}")
        lines.append("")

    # Time hierarchy
    lines.append("\thierarchy 'Date Hierarchy'")
    lines.append("\t\tlineageTag: cal-hierarchy")
    lines.append("")
    for level_name, col_ref in [("Year", "Year"), ("Quarter", "Quarter"),
                                 ("Month", "MonthName"), ("Day", "Date")]:
        lines.append(f"\t\tlevel {level_name}")
        lines.append(f"\t\t\tcolumn: {col_ref}")
        lines.append(f"\t\t\tlineageTag: cal-level-{level_name.lower()}")
        lines.append("")

    # M partition — generates all columns server-side so TMDL can resolve them
    m_expr = (
        f'let\n'
        f'    StartDate = #date({start_year}, 1, 1),\n'
        f'    EndDate = #date({end_year}, 12, 31),\n'
        f'    DayCount = Duration.Days(EndDate - StartDate) + 1,\n'
        f'    DateList = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),\n'
        f'    #"Date Table" = Table.FromList(DateList, Splitter.SplitByNothing(), {{"Date"}}, null, ExtraValues.Error),\n'
        f'    #"Changed Type" = Table.TransformColumnTypes(#"Date Table", {{"Date", type date}}),\n'
        f'    #"Added Year" = Table.AddColumn(#"Changed Type", "Year", each Date.Year([Date]), Int64.Type),\n'
        f'    #"Added Quarter" = Table.AddColumn(#"Added Year", "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date]))),\n'
        f'    #"Added Month" = Table.AddColumn(#"Added Quarter", "Month", each Date.Month([Date]), Int64.Type),\n'
        f'    #"Added MonthName" = Table.AddColumn(#"Added Month", "MonthName", each Date.MonthName([Date])),\n'
        f'    #"Added Day" = Table.AddColumn(#"Added MonthName", "Day", each Date.Day([Date]), Int64.Type),\n'
        f'    #"Added DayOfWeek" = Table.AddColumn(#"Added Day", "DayOfWeek", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),\n'
        f'    #"Added DayName" = Table.AddColumn(#"Added DayOfWeek", "DayName", each Date.DayOfWeekName([Date])),\n'
        f'    #"Added WeekOfYear" = Table.AddColumn(#"Added DayName", "WeekOfYear", each Date.WeekOfYear([Date]), Int64.Type)\n'
        f'in\n'
        f'    #"Added WeekOfYear"'
    )

    lines.append("\tpartition Calendar = m")
    lines.append("\t\tmode: import")
    lines.append("\t\texpression:= ```")
    for m_line in m_expr.split('\n'):
        lines.append(f"\t\t\t{m_line}")
    lines.append("\t\t\t```")

    return '\n'.join(lines).rstrip() + '\n'
