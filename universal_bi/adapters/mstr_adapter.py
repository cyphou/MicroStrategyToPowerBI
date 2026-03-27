"""MicroStrategy → Universal BI schema adapter.

Converts the 18 MSTR intermediate JSON files into a single universal
schema document that the federated generation layer can consume.
"""

import logging
from typing import Any, Dict, List

from universal_bi.schema import empty_schema, _next_id

logger = logging.getLogger(__name__)


def convert(mstr_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an MSTR intermediate data dict into a universal schema.

    *mstr_data* is the dict returned by ``extract_mstr_data`` or loaded
    from the 18 JSON files (keyed by: datasources, attributes, facts,
    metrics, derived_metrics, reports, dossiers, etc.).
    """
    schema = empty_schema(["microstrategy"])

    schema["datasources"] = _convert_datasources(mstr_data)
    schema["dimensions"] = _convert_dimensions(mstr_data)
    schema["measures"] = _convert_measures(mstr_data)
    schema["relationships"] = _convert_relationships(mstr_data)
    schema["hierarchies"] = _convert_hierarchies(mstr_data)
    schema["security_rules"] = _convert_security(mstr_data)
    schema["pages"] = _convert_pages(mstr_data)
    schema["parameters"] = _convert_parameters(mstr_data)
    schema["filters"] = list(mstr_data.get("filters", []))
    schema["custom_groups"] = _convert_custom_groups(mstr_data)
    schema["custom_sql"] = _convert_custom_sql(mstr_data)

    logger.info("MSTR adapter: %d datasources, %d dimensions, %d measures, "
                "%d pages",
                len(schema["datasources"]), len(schema["dimensions"]),
                len(schema["measures"]), len(schema["pages"]))
    return schema


# ---------------------------------------------------------------------------
# Internal converters
# ---------------------------------------------------------------------------

def _convert_datasources(data: Dict) -> List[Dict]:
    result = []
    for ds in data.get("datasources", []):
        result.append({
            "id": ds.get("id", _next_id("DS")),
            "name": ds.get("name", ""),
            "physical_table": ds.get("physical_table", ds.get("name", "")),
            "db_connection": ds.get("db_connection", {}),
            "columns": ds.get("columns", []),
            "is_custom_sql": ds.get("is_freeform_sql", False),
            "sql_statement": ds.get("sql_statement", ""),
            "source_platform": "microstrategy",
            "source_id": ds.get("id", ""),
        })
    return result


def _convert_dimensions(data: Dict) -> List[Dict]:
    dims = []
    for attr in data.get("attributes", []):
        forms = attr.get("forms", [])
        primary = forms[0] if forms else {}
        dims.append({
            "id": attr.get("id", _next_id("DM")),
            "name": attr.get("name", ""),
            "description": attr.get("description", ""),
            "data_type": attr.get("data_type", primary.get("data_type", "string")),
            "column_name": primary.get("column_name", ""),
            "table": primary.get("table", attr.get("lookup_table", "")),
            "geographic_role": attr.get("geographic_role"),
            "sort_order": attr.get("sort_order", "ascending"),
            "display_format": attr.get("display_format", ""),
            "forms": forms,
            "source_platform": "microstrategy",
            "source_id": attr.get("id", ""),
        })
    return dims


def _convert_measures(data: Dict) -> List[Dict]:
    measures = []

    # Facts → measure_type "fact"
    for fact in data.get("facts", []):
        measures.append({
            "id": fact.get("id", _next_id("FA")),
            "name": fact.get("name", ""),
            "description": fact.get("description", ""),
            "measure_type": "fact",
            "expression": "",
            "dax_expression": "",
            "aggregation": fact.get("default_aggregation", "sum"),
            "format_string": fact.get("format_string", ""),
            "data_type": fact.get("data_type", "real"),
            "expressions": fact.get("expressions", []),
            "dependencies": [],
            "column_ref": None,
            "source_platform": "microstrategy",
            "source_id": fact.get("id", ""),
        })

    # Simple metrics
    for m in data.get("metrics", []):
        measures.append({
            "id": m.get("id", _next_id("ME")),
            "name": m.get("name", ""),
            "description": m.get("description", ""),
            "measure_type": "simple",
            "expression": m.get("expression", ""),
            "dax_expression": m.get("dax_expression", ""),
            "aggregation": m.get("aggregation", "sum"),
            "format_string": m.get("format_string", ""),
            "subtotal_type": m.get("subtotal_type", "sum"),
            "folder_path": m.get("folder_path", ""),
            "dependencies": m.get("dependencies", []),
            "column_ref": m.get("column_ref"),
            "source_platform": "microstrategy",
            "source_id": m.get("id", ""),
        })

    # Derived metrics
    for m in data.get("derived_metrics", []):
        measures.append({
            "id": m.get("id", _next_id("DM")),
            "name": m.get("name", ""),
            "description": m.get("description", ""),
            "measure_type": "derived",
            "expression": m.get("expression", ""),
            "dax_expression": m.get("dax_expression", ""),
            "aggregation": m.get("aggregation", ""),
            "format_string": m.get("format_string", ""),
            "subtotal_type": m.get("subtotal_type", "none"),
            "folder_path": m.get("folder_path", ""),
            "is_smart_metric": m.get("is_smart_metric", False),
            "dependencies": m.get("dependencies", []),
            "column_ref": m.get("column_ref"),
            "source_platform": "microstrategy",
            "source_id": m.get("id", ""),
        })

    return measures


def _convert_relationships(data: Dict) -> List[Dict]:
    return [
        {
            "from_table": r.get("from_table", ""),
            "from_column": r.get("from_column", ""),
            "to_table": r.get("to_table", ""),
            "to_column": r.get("to_column", ""),
            "type": r.get("type", "many_to_one"),
            "active": r.get("active", True),
            "cross_filter": r.get("cross_filter", "single"),
            "source_platform": "microstrategy",
        }
        for r in data.get("relationships", [])
    ]


def _convert_hierarchies(data: Dict) -> List[Dict]:
    return [
        {
            "id": h.get("id", _next_id("HI")),
            "name": h.get("name", ""),
            "type": h.get("type", "user"),
            "levels": h.get("levels", []),
            "source_platform": "microstrategy",
        }
        for h in data.get("hierarchies", [])
    ]


def _convert_security(data: Dict) -> List[Dict]:
    return [
        {
            "id": s.get("id", _next_id("SF")),
            "name": s.get("name", ""),
            "expression": s.get("expression", ""),
            "target_columns": s.get("target_attributes", []),
            "groups": s.get("groups", []),
            "users": s.get("users", []),
            "description": s.get("description", ""),
            "source_platform": "microstrategy",
        }
        for s in data.get("security_filters", [])
    ]


def _convert_pages(data: Dict) -> List[Dict]:
    """Convert MSTR reports + dossiers into universal pages."""
    pages: List[Dict] = []

    # Reports → one page each
    for rpt in data.get("reports", []):
        fields: List[Dict] = []
        for row in rpt.get("grid", {}).get("rows", []):
            fields.append({"name": row.get("name", ""), "role": "row",
                           "id": row.get("id", "")})
        for col in rpt.get("grid", {}).get("columns", []):
            fields.append({"name": col.get("name", ""), "role": "column",
                           "id": col.get("id", "")})
        for met in rpt.get("metrics", []):
            fields.append({"name": met.get("name", ""), "role": "value",
                           "id": met.get("id", "")})

        viz_type = rpt.get("report_type", "table")
        if rpt.get("graph"):
            viz_type = rpt["graph"].get("type", viz_type)

        pages.append({
            "id": rpt.get("id", _next_id("PG")),
            "name": rpt.get("name", ""),
            "parent_name": rpt.get("name", ""),
            "parent_type": "report",
            "visuals": [{
                "id": rpt.get("id", _next_id("VZ")),
                "name": rpt.get("name", ""),
                "viz_type": viz_type,
                "fields": fields,
                "position": {"x": 0, "y": 0, "width": 1280, "height": 720},
                "filters": rpt.get("filters", []),
                "formatting": {},
                "thresholds": rpt.get("thresholds", []),
                "source_platform": "microstrategy",
            }],
            "source_platform": "microstrategy",
        })

    # Dossiers → one page per dossier page
    for doss in data.get("dossiers", []):
        for ch in doss.get("chapters", []):
            for pg in ch.get("pages", []):
                vizs = []
                for v in pg.get("visualizations", []):
                    vfields: List[Dict] = []
                    for a in v.get("data", {}).get("attributes", []):
                        vfields.append({"name": a.get("name", ""), "role": "axis",
                                        "id": a.get("id", "")})
                    for m in v.get("data", {}).get("metrics", []):
                        vfields.append({"name": m.get("name", ""), "role": "value",
                                        "id": m.get("id", "")})
                    vizs.append({
                        "id": v.get("key", _next_id("VZ")),
                        "name": v.get("name", ""),
                        "viz_type": v.get("viz_type", "table"),
                        "fields": vfields,
                        "position": v.get("position", {"x": 0, "y": 0,
                                                        "width": 600, "height": 350}),
                        "filters": v.get("filters", []),
                        "formatting": v.get("formatting", {}),
                        "thresholds": v.get("thresholds", []),
                        "source_platform": "microstrategy",
                    })
                pages.append({
                    "id": pg.get("key", _next_id("PG")),
                    "name": pg.get("name", ""),
                    "parent_name": doss.get("name", ""),
                    "parent_type": "dossier",
                    "visuals": vizs,
                    "source_platform": "microstrategy",
                })

    return pages


def _convert_parameters(data: Dict) -> List[Dict]:
    return [
        {
            "id": p.get("id", _next_id("PR")),
            "name": p.get("name", ""),
            "param_type": p.get("type", "element"),
            "data_type": "string",
            "required": p.get("required", False),
            "allow_multi": p.get("allow_multi_select", False),
            "default_value": p.get("default_value", ""),
            "options": p.get("options", []),
            "pbi_type": p.get("pbi_type", "slicer"),
            "attribute_name": p.get("attribute_name", ""),
            "min_value": p.get("min_value"),
            "max_value": p.get("max_value"),
            "source_platform": "microstrategy",
        }
        for p in data.get("prompts", [])
    ]


def _convert_custom_groups(data: Dict) -> List[Dict]:
    return [
        {
            "id": cg.get("id", _next_id("CG")),
            "name": cg.get("name", ""),
            "type": cg.get("type", "custom_group"),
            "elements": cg.get("elements", []),
            "source_platform": "microstrategy",
        }
        for cg in data.get("custom_groups", [])
    ]


def _convert_custom_sql(data: Dict) -> List[Dict]:
    return [
        {
            "id": cs.get("id", _next_id("FF")),
            "name": cs.get("name", ""),
            "sql_statement": cs.get("sql_statement", ""),
            "db_connection": cs.get("db_connection", {}),
            "columns": cs.get("columns", []),
            "source_platform": "microstrategy",
        }
        for cs in data.get("freeform_sql", [])
    ]
