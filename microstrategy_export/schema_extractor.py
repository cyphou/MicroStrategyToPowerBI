"""
Schema extractor for MicroStrategy objects.

Extracts tables, attributes (with forms), facts (with expressions),
hierarchies, custom groups, consolidations, and freeform SQL.
"""

import logging

logger = logging.getLogger(__name__)


def extract_tables(client):
    """Extract all warehouse/logical tables from the project schema.

    Returns list of table dicts compatible with downstream datasources.json format.
    """
    raw_tables = client.get_tables()
    tables = []
    for t in raw_tables:
        table = {
            "id": t.get("id", ""),
            "name": t.get("name", ""),
            "physical_table": t.get("physicalTable", {}).get("tableName", t.get("name", "")),
            "db_connection": _extract_connection_info(t),
            "columns": _extract_table_columns(t),
            "is_freeform_sql": t.get("isFreeformSql", False),
            "sql_statement": t.get("sqlStatement", ""),
            "type": "table",
        }
        tables.append(table)
    return tables


def extract_attributes(client):
    """Extract all attributes with their forms.

    Returns list of attribute dicts with forms → columns mapping.
    """
    raw_attrs = client.get_attributes()
    attributes = []
    for a in raw_attrs:
        # Get detailed definition including forms
        try:
            detail = client.get_attribute(a['id'])
        except Exception:
            detail = a

        attr = {
            "id": detail.get("id", ""),
            "name": detail.get("name", ""),
            "description": detail.get("description", ""),
            "forms": _extract_attribute_forms(detail),
            "data_type": _resolve_attribute_type(detail),
            "geographic_role": _detect_geographic_role(detail),
            "sort_order": detail.get("sortOrder", ""),
            "display_format": detail.get("displayFormat", ""),
            "parent_attributes": _extract_parent_attributes(detail),
            "child_attributes": _extract_child_attributes(detail),
            "lookup_table": _extract_lookup_table(detail),
        }
        attributes.append(attr)
    return attributes


def extract_facts(client):
    """Extract all facts (measure columns).

    Returns list of fact dicts with expressions and aggregation info.
    """
    raw_facts = client.get_facts()
    facts = []
    for f in raw_facts:
        try:
            detail = client.get_fact(f['id'])
        except Exception:
            detail = f

        fact = {
            "id": detail.get("id", ""),
            "name": detail.get("name", ""),
            "description": detail.get("description", ""),
            "expressions": _extract_fact_expressions(detail),
            "data_type": _resolve_fact_type(detail),
            "default_aggregation": _extract_default_aggregation(detail),
            "format_string": detail.get("formatString", ""),
        }
        facts.append(fact)
    return facts


def extract_hierarchies(client):
    """Extract user hierarchies and system hierarchies.

    Returns list of hierarchy dicts with ordered levels.
    """
    raw = client.get_user_hierarchies()
    hierarchies = []
    for h in raw:
        hierarchy = {
            "id": h.get("id", ""),
            "name": h.get("name", ""),
            "type": h.get("subType", "user"),
            "levels": _extract_hierarchy_levels(h),
        }
        hierarchies.append(hierarchy)
    return hierarchies


def extract_custom_groups(client):
    """Extract custom groups (user-defined groupings).

    Returns list of custom group dicts.
    """
    # Custom groups are searched as a specific subtype
    results = client.search_objects(object_type=1, pattern="")
    custom_groups = []
    for obj in results:
        if obj.get("subtype") == 9984:  # Custom group subtype
            custom_groups.append({
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "elements": [],  # Populated from full definition
                "type": "custom_group",
            })
    return custom_groups


def extract_freeform_sql(client):
    """Extract freeform SQL tables.

    Returns list of freeform SQL dicts with SQL statements.
    """
    tables = client.get_tables()
    freeform = []
    for t in tables:
        if t.get("isFreeformSql", False):
            freeform.append({
                "id": t.get("id", ""),
                "name": t.get("name", ""),
                "sql_statement": t.get("sqlStatement", ""),
                "db_connection": _extract_connection_info(t),
                "columns": _extract_table_columns(t),
            })
    return freeform


def infer_relationships(attributes, facts, tables):
    """Infer relationships between tables from attribute/fact definitions.

    MicroStrategy relationships come from:
    1. Attribute lookup tables → fact tables (many-to-one)
    2. Attribute parent-child links
    3. Shared columns between tables
    """
    relationships = []
    seen = set()

    # 1. From attribute forms → lookup table → fact table columns
    for attr in attributes:
        lookup = attr.get("lookup_table", "")
        if not lookup:
            continue

        for form in attr.get("forms", []):
            col_name = form.get("column_name", "")
            if not col_name:
                continue

            # Find fact tables that reference this column
            for fact in facts:
                for expr in fact.get("expressions", []):
                    fact_table = expr.get("table", "")
                    fact_col = expr.get("column", "")

                    if fact_table and fact_table != lookup:
                        key = (lookup, col_name, fact_table, fact_col or col_name)
                        if key not in seen:
                            seen.add(key)
                            relationships.append({
                                "from_table": lookup,
                                "from_column": col_name,
                                "to_table": fact_table,
                                "to_column": fact_col or col_name,
                                "cardinality": "manyToOne",
                                "cross_filter": "single",
                                "inferred_from": "attribute_fact",
                            })

    # 2. Attribute parent-child relationships
    for attr in attributes:
        for parent in attr.get("parent_attributes", []):
            parent_name = parent.get("name", "")
            parent_table = parent.get("lookup_table", "")
            child_table = attr.get("lookup_table", "")

            if parent_table and child_table and parent_table != child_table:
                key = (child_table, attr["name"], parent_table, parent_name)
                if key not in seen:
                    seen.add(key)
                    relationships.append({
                        "from_table": child_table,
                        "from_column": attr["name"],
                        "to_table": parent_table,
                        "to_column": parent_name,
                        "cardinality": "manyToOne",
                        "cross_filter": "single",
                        "inferred_from": "attribute_hierarchy",
                    })

    return relationships


# ── Internal helpers ─────────────────────────────────────────────

def _extract_connection_info(table_obj):
    """Extract database connection info from a table definition."""
    conn = table_obj.get("dbConnection", {}) or table_obj.get("physicalTable", {}).get("dbConnection", {}) or {}
    return {
        "name": conn.get("name", ""),
        "id": conn.get("id", ""),
        "db_type": conn.get("dbType", ""),
        "server": conn.get("server", ""),
        "database": conn.get("database", ""),
        "schema": conn.get("schema", ""),
    }


def _extract_table_columns(table_obj):
    """Extract column definitions from a table."""
    columns = []
    for col in table_obj.get("columns", []) or table_obj.get("physicalTable", {}).get("columns", []) or []:
        columns.append({
            "name": col.get("name", ""),
            "data_type": col.get("dataType", ""),
            "precision": col.get("precision", 0),
            "scale": col.get("scale", 0),
        })
    return columns


def _extract_attribute_forms(attr_detail):
    """Extract attribute forms (ID, DESC, etc.)."""
    forms = []
    for form in attr_detail.get("forms", []) or attr_detail.get("attributeForms", []) or []:
        forms.append({
            "name": form.get("name", ""),
            "category": form.get("category", ""),  # ID, DESC, etc.
            "column_name": _get_form_column(form),
            "table_name": _get_form_table(form),
            "data_type": (form.get("dataType", "string") if isinstance(form.get("dataType"), str) else form.get("dataType", {}).get("type", "string")),
            "is_key": form.get("category", "") == "ID",
        })
    return forms


def _get_form_column(form):
    """Get column name from an attribute form."""
    expressions = form.get("expressions", []) or []
    if expressions:
        tables = expressions[0].get("tables", []) or []
        return expressions[0].get("columnName", "") or (
            tables[0].get("columnName", "") if tables else ""
        )
    return form.get("columnName", "")


def _get_form_table(form):
    """Get table name from an attribute form."""
    expressions = form.get("expressions", []) or []
    if expressions:
        tables = expressions[0].get("tables", []) or []
        if tables:
            return tables[0].get("name", "")
    return ""


def _resolve_attribute_type(detail):
    """Resolve the primary data type of an attribute."""
    forms = detail.get("forms", []) or detail.get("attributeForms", []) or []
    for form in forms:
        if form.get("category", "") == "ID":
            dt = form.get("dataType", {})
            return dt.get("type", "string") if isinstance(dt, dict) else str(dt)
    return "string"


def _detect_geographic_role(detail):
    """Detect if an attribute has a geographic role."""
    name_lower = detail.get("name", "").lower()
    geo_keywords = {
        "country": "country",
        "state": "stateOrProvince",
        "province": "stateOrProvince",
        "city": "city",
        "zip": "postalCode",
        "postal": "postalCode",
        "latitude": "latitude",
        "longitude": "longitude",
        "region": "continent",
        "county": "county",
    }
    for keyword, role in geo_keywords.items():
        if keyword in name_lower:
            return role
    return ""


def _extract_parent_attributes(detail):
    """Extract parent attributes from hierarchy relationships."""
    parents = []
    for p in detail.get("parents", []) or detail.get("parentAttributes", []) or []:
        parents.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
        })
    return parents


def _extract_child_attributes(detail):
    """Extract child attributes from hierarchy relationships."""
    children = []
    for c in detail.get("children", []) or detail.get("childAttributes", []) or []:
        children.append({
            "id": c.get("id", ""),
            "name": c.get("name", ""),
        })
    return children


def _extract_lookup_table(detail):
    """Extract the lookup table for an attribute."""
    lut = detail.get("attributeLookupTable", {}) or detail.get("lookupTable", {}) or {}
    return lut.get("name", "")


def _extract_fact_expressions(detail):
    """Extract fact column expressions (table + column mappings)."""
    expressions = []
    for expr in detail.get("expressions", []) or detail.get("factExpressions", []) or []:
        tables = expr.get("tables", []) or []
        for tbl in tables:
            expressions.append({
                "table": tbl.get("name", ""),
                "column": expr.get("columnName", ""),
                "expression_text": expr.get("expressionText", ""),
            })
        if not tables and expr.get("columnName"):
            expressions.append({
                "table": "",
                "column": expr.get("columnName", ""),
                "expression_text": expr.get("expressionText", ""),
            })
    return expressions


def _resolve_fact_type(detail):
    """Resolve the data type of a fact."""
    exprs = detail.get("expressions", []) or []
    if exprs:
        dt = exprs[0].get("dataType", {})
        if isinstance(dt, dict):
            return dt.get("type", "double")
        return str(dt) if dt else "double"
    return "double"


def _extract_default_aggregation(detail):
    """Extract the default aggregation function for a fact."""
    return detail.get("defaultAggregation", "sum").lower()


def _extract_hierarchy_levels(hierarchy):
    """Extract hierarchy levels with ordering."""
    levels = []
    for attr in hierarchy.get("attributes", []) or hierarchy.get("levels", []) or []:
        levels.append({
            "name": attr.get("name", ""),
            "id": attr.get("id", ""),
            "ordinal": attr.get("ordinal", len(levels)),
        })
    levels.sort(key=lambda x: x.get("ordinal", 0))
    return levels
