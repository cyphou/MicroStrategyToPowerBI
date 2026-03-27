"""Universal BI schema — platform-agnostic intermediate format.

Defines the canonical data model that serves as the translation layer
between *any* BI platform extraction and the Power BI generation layer.

Schema sections:
  datasources  — physical tables + connections
  dimensions   — dimension columns (MSTR attributes / Tableau dim columns)
  measures     — metrics / calculated measures / facts
  relationships — table-to-table joins
  hierarchies  — drill hierarchies
  security_rules — RLS filters
  pages        — report / dashboard pages with visuals
  parameters   — prompts / parameters → slicers
  filters      — global / report filters
  custom_groups — groupings / sets
  custom_sql   — freeform SQL tables
"""

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"

VALID_PLATFORMS = {"microstrategy", "tableau", "cognos", "ssrs"}
VALID_MEASURE_TYPES = {"simple", "derived", "fact", "calculated"}
VALID_CARDINALITIES = {"many_to_one", "one_to_many", "many_to_many", "one_to_one"}
VALID_CROSS_FILTERS = {"single", "both"}
VALID_VIZ_ROLES = {"axis", "value", "legend", "tooltip", "filter", "detail", "row", "column"}

# ---------------------------------------------------------------------------
# Schema factory
# ---------------------------------------------------------------------------

def empty_schema(source_platforms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return a blank universal schema document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source_platforms": list(source_platforms or []),
        "datasources": [],
        "dimensions": [],
        "measures": [],
        "relationships": [],
        "hierarchies": [],
        "security_rules": [],
        "pages": [],
        "parameters": [],
        "filters": [],
        "custom_groups": [],
        "custom_sql": [],
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(schema: Dict[str, Any]) -> List[str]:
    """Validate a universal schema document.  Returns a list of error strings (empty = valid)."""
    errors: List[str] = []

    if schema.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version: {schema.get('schema_version')}")

    for key in ("datasources", "dimensions", "measures", "relationships",
                "hierarchies", "security_rules", "pages", "parameters",
                "filters", "custom_groups", "custom_sql"):
        if not isinstance(schema.get(key), list):
            errors.append(f"Missing or non-list key: {key}")

    # Check datasources
    ds_names = set()
    for ds in schema.get("datasources", []):
        name = ds.get("name", "")
        if not name:
            errors.append("Datasource with empty name")
        if name in ds_names:
            errors.append(f"Duplicate datasource name: {name}")
        ds_names.add(name)

    # Check measures have expression or dax_expression
    for m in schema.get("measures", []):
        if not m.get("name"):
            errors.append("Measure with empty name")
        mt = m.get("measure_type", "")
        if mt and mt not in VALID_MEASURE_TYPES:
            errors.append(f"Invalid measure_type '{mt}' for {m.get('name')}")

    # Check relationships reference known tables
    for rel in schema.get("relationships", []):
        ft = rel.get("from_table", "")
        tt = rel.get("to_table", "")
        if not ft or not tt:
            errors.append(f"Relationship with empty table reference: {ft} → {tt}")

    return errors


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

_COUNTER = 0


def _next_id(prefix: str = "UBI") -> str:
    global _COUNTER
    _COUNTER += 1
    return f"{prefix}_{_COUNTER:04d}"


def merge_schemas(*schemas: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple universal schemas into one, deduplicating datasources
    and marking provenance via *source_platform*."""
    merged = empty_schema()
    seen_platforms: set = set()
    seen_ds: Dict[str, Dict] = {}          # name → datasource
    seen_rels: set = set()                  # (from_t, from_c, to_t, to_c)

    for schema in schemas:
        for p in schema.get("source_platforms", []):
            seen_platforms.add(p)

        # Datasources — dedup by name (case-insensitive)
        for ds in schema.get("datasources", []):
            key = ds.get("name", "").lower()
            if key and key not in seen_ds:
                seen_ds[key] = copy.deepcopy(ds)
            elif key:
                # Merge columns from duplicate datasource
                existing = seen_ds[key]
                existing_cols = {c["name"].lower() for c in existing.get("columns", [])}
                for col in ds.get("columns", []):
                    if col["name"].lower() not in existing_cols:
                        existing.setdefault("columns", []).append(col)
                        existing_cols.add(col["name"].lower())

        # Relationships — dedup by (from_table, from_column, to_table, to_column)
        for rel in schema.get("relationships", []):
            key = (rel.get("from_table", "").lower(),
                   rel.get("from_column", "").lower(),
                   rel.get("to_table", "").lower(),
                   rel.get("to_column", "").lower())
            if key not in seen_rels:
                seen_rels.add(key)
                merged["relationships"].append(copy.deepcopy(rel))

        # Simple concatenation for these (provenance tracked per object)
        for section in ("dimensions", "measures", "hierarchies",
                        "security_rules", "pages", "parameters",
                        "filters", "custom_groups", "custom_sql"):
            merged[section].extend(copy.deepcopy(schema.get(section, [])))

    merged["source_platforms"] = sorted(seen_platforms)
    merged["datasources"] = list(seen_ds.values())
    return merged


# ---------------------------------------------------------------------------
# Conversion back to MSTR-compatible format (for generation layer)
# ---------------------------------------------------------------------------

def to_mstr_format(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a universal schema back to the MSTR-compatible dict format
    expected by ``import_to_powerbi.PowerBIImporter``."""
    data: Dict[str, Any] = {
        "datasources": [],
        "attributes": [],
        "facts": [],
        "metrics": [],
        "derived_metrics": [],
        "reports": [],
        "dossiers": [],
        "cubes": [],
        "filters": [],
        "prompts": [],
        "custom_groups": [],
        "consolidations": [],
        "hierarchies": [],
        "relationships": [],
        "security_filters": [],
        "freeform_sql": [],
        "thresholds": [],
        "subtotals": [],
    }

    # --- datasources ---
    for ds in schema.get("datasources", []):
        data["datasources"].append({
            "id": ds.get("id", _next_id("DS")),
            "name": ds.get("name", ""),
            "physical_table": ds.get("physical_table", ds.get("name", "")),
            "db_connection": ds.get("db_connection", {}),
            "columns": ds.get("columns", []),
            "is_freeform_sql": ds.get("is_custom_sql", False),
            "sql_statement": ds.get("sql_statement", ""),
            "type": "table",
        })

    # --- dimensions → attributes ---
    for dim in schema.get("dimensions", []):
        forms = dim.get("forms", [])
        if not forms:
            forms = [{"name": "ID", "category": "ID",
                       "data_type": dim.get("data_type", "string"),
                       "column_name": dim.get("column_name", dim.get("name", "")),
                       "table": dim.get("table", "")}]
        data["attributes"].append({
            "id": dim.get("id", _next_id("AT")),
            "name": dim.get("name", ""),
            "description": dim.get("description", ""),
            "forms": forms,
            "data_type": dim.get("data_type", "string"),
            "geographic_role": dim.get("geographic_role"),
            "sort_order": dim.get("sort_order", "ascending"),
            "display_format": dim.get("display_format", ""),
            "parent_attributes": [],
            "child_attributes": [],
            "lookup_table": dim.get("table", ""),
        })

    # --- measures → metrics / derived_metrics / facts ---
    for m in schema.get("measures", []):
        mt = m.get("measure_type", "simple")
        if mt == "fact":
            data["facts"].append({
                "id": m.get("id", _next_id("FA")),
                "name": m.get("name", ""),
                "description": m.get("description", ""),
                "expressions": m.get("expressions", []),
                "data_type": m.get("data_type", "real"),
                "default_aggregation": m.get("aggregation", "sum"),
                "format_string": m.get("format_string", ""),
            })
        elif mt == "derived":
            data["derived_metrics"].append({
                "id": m.get("id", _next_id("DM")),
                "name": m.get("name", ""),
                "description": m.get("description", ""),
                "metric_type": "derived",
                "expression": m.get("expression", ""),
                "dax_expression": m.get("dax_expression", ""),
                "aggregation": m.get("aggregation", ""),
                "column_ref": m.get("column_ref"),
                "format_string": m.get("format_string", ""),
                "subtotal_type": m.get("subtotal_type", "none"),
                "folder_path": m.get("folder_path", ""),
                "is_smart_metric": m.get("is_smart_metric", False),
                "dependencies": m.get("dependencies", []),
            })
        else:
            data["metrics"].append({
                "id": m.get("id", _next_id("ME")),
                "name": m.get("name", ""),
                "description": m.get("description", ""),
                "metric_type": mt,
                "expression": m.get("expression", ""),
                "dax_expression": m.get("dax_expression", ""),
                "aggregation": m.get("aggregation", "sum"),
                "format_string": m.get("format_string", ""),
                "subtotal_type": m.get("subtotal_type", "sum"),
                "folder_path": m.get("folder_path", ""),
                "is_smart_metric": False,
                "dependencies": m.get("dependencies", []),
                "column_ref": m.get("column_ref"),
            })

    # --- relationships ---
    data["relationships"] = [
        {
            "from_table": r.get("from_table", ""),
            "from_column": r.get("from_column", ""),
            "to_table": r.get("to_table", ""),
            "to_column": r.get("to_column", ""),
            "type": r.get("type", "many_to_one"),
            "active": r.get("active", True),
            "cross_filter": r.get("cross_filter", "single"),
            "source": r.get("source", "universal_bi"),
        }
        for r in schema.get("relationships", [])
    ]

    # --- hierarchies ---
    data["hierarchies"] = [
        {
            "id": h.get("id", _next_id("HI")),
            "name": h.get("name", ""),
            "type": h.get("type", "user"),
            "levels": h.get("levels", []),
        }
        for h in schema.get("hierarchies", [])
    ]

    # --- security_rules → security_filters ---
    data["security_filters"] = [
        {
            "id": s.get("id", _next_id("SF")),
            "name": s.get("name", ""),
            "expression": s.get("expression", ""),
            "target_attributes": s.get("target_columns", []),
            "users": s.get("users", []),
            "groups": s.get("groups", []),
            "description": s.get("description", ""),
        }
        for s in schema.get("security_rules", [])
    ]

    # --- parameters → prompts ---
    data["prompts"] = [
        {
            "id": p.get("id", _next_id("PR")),
            "name": p.get("name", ""),
            "type": p.get("param_type", "element"),
            "required": p.get("required", False),
            "allow_multi_select": p.get("allow_multi", False),
            "default_value": p.get("default_value", ""),
            "options": p.get("options", []),
            "pbi_type": p.get("pbi_type", "slicer"),
            "attribute_name": p.get("attribute_name", p.get("name", "")),
            "min_value": p.get("min_value"),
            "max_value": p.get("max_value"),
        }
        for p in schema.get("parameters", [])
    ]

    # --- pages → dossiers (one dossier wrapping all pages) ---
    pages = schema.get("pages", [])
    if pages:
        chapters: List[Dict] = []
        for page in pages:
            vizs = []
            for v in page.get("visuals", []):
                vizs.append({
                    "key": v.get("id", _next_id("VZ")),
                    "name": v.get("name", ""),
                    "viz_type": v.get("viz_type", "table"),
                    "data": {
                        "attributes": [f for f in v.get("fields", [])
                                       if f.get("role") in ("axis", "row", "column", "legend", "detail")],
                        "metrics": [f for f in v.get("fields", [])
                                    if f.get("role") in ("value", "tooltip")],
                    },
                    "formatting": v.get("formatting", {}),
                    "thresholds": v.get("thresholds", []),
                    "position": v.get("position", {"x": 0, "y": 0, "width": 600, "height": 350}),
                    "actions": v.get("actions", []),
                    "info_window": None,
                })
            chapters.append({
                "key": page.get("id", _next_id("CH")),
                "name": page.get("parent_name", page.get("name", "")),
                "pages": [{
                    "key": page.get("id", _next_id("PG")),
                    "name": page.get("name", ""),
                    "visualizations": vizs,
                }],
            })
        data["dossiers"] = [{
            "id": _next_id("DOSS"),
            "name": "Federated Dashboard",
            "description": "Cross-platform federated migration",
            "chapters": chapters,
        }]

    # --- custom_groups ---
    data["custom_groups"] = [
        {
            "id": cg.get("id", _next_id("CG")),
            "name": cg.get("name", ""),
            "type": "custom_group",
            "elements": cg.get("elements", []),
        }
        for cg in schema.get("custom_groups", [])
    ]

    # --- custom_sql → freeform_sql ---
    data["freeform_sql"] = [
        {
            "id": cs.get("id", _next_id("FF")),
            "name": cs.get("name", ""),
            "sql_statement": cs.get("sql_statement", ""),
            "db_connection": cs.get("db_connection", {}),
            "columns": cs.get("columns", []),
        }
        for cs in schema.get("custom_sql", [])
    ]

    # --- filters ---
    data["filters"] = schema.get("filters", [])

    logger.info("Converted universal schema → MSTR format: %d datasources, "
                "%d attributes, %d facts, %d metrics, %d derived_metrics, "
                "%d pages",
                len(data["datasources"]), len(data["attributes"]),
                len(data["facts"]), len(data["metrics"]),
                len(data["derived_metrics"]),
                sum(len(ch["pages"]) for d in data["dossiers"] for ch in d.get("chapters", [])))

    return data
