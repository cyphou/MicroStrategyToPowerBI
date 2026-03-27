"""Tableau → Universal BI schema adapter.

Converts the Tableau intermediate JSON files (as produced by the
TableauToPowerBI extraction layer) into the universal schema format.
"""

import logging
from typing import Any, Dict, List

from universal_bi.schema import empty_schema, _next_id

logger = logging.getLogger(__name__)

# Tableau mark type → universal viz type
_MARK_TYPE_MAP = {
    "Bar": "bar",
    "Line": "line",
    "Area": "area",
    "Circle": "scatter",
    "Square": "heatmap",
    "Pie": "pie",
    "Gantt Bar": "gantt",
    "Polygon": "map",
    "Text": "table",
    "Shape": "shape",
    "Map": "map",
    "Automatic": "auto",
}


def convert(tableau_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Tableau intermediate data dict into a universal schema.

    *tableau_data* is the dict loaded from the Tableau intermediate JSON
    files (keyed by: datasources, worksheets, dashboards, calculations,
    parameters, filters, hierarchies, user_filters, custom_sql, etc.).
    """
    schema = empty_schema(["tableau"])

    schema["datasources"] = _convert_datasources(tableau_data)
    schema["dimensions"] = _convert_dimensions(tableau_data)
    schema["measures"] = _convert_measures(tableau_data)
    schema["relationships"] = _convert_relationships(tableau_data)
    schema["hierarchies"] = _convert_hierarchies(tableau_data)
    schema["security_rules"] = _convert_security(tableau_data)
    schema["pages"] = _convert_pages(tableau_data)
    schema["parameters"] = _convert_parameters(tableau_data)
    schema["filters"] = list(tableau_data.get("filters", []))
    schema["custom_groups"] = _convert_custom_groups(tableau_data)
    schema["custom_sql"] = _convert_custom_sql(tableau_data)

    logger.info("Tableau adapter: %d datasources, %d dimensions, %d measures, "
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
        conn = ds.get("connection", {})
        details = conn.get("details", {})
        for tbl in ds.get("tables", []):
            columns = []
            for col in tbl.get("columns", []):
                columns.append({
                    "name": col.get("name", ""),
                    "data_type": col.get("datatype", "string"),
                    "role": col.get("role", "dimension"),
                })
            result.append({
                "id": _next_id("DS"),
                "name": tbl.get("name", ""),
                "physical_table": tbl.get("name", ""),
                "db_connection": {
                    "db_type": conn.get("type", ""),
                    "server": details.get("server", ""),
                    "database": details.get("database", ""),
                    "schema": details.get("schema", ""),
                },
                "columns": columns,
                "is_custom_sql": False,
                "sql_statement": "",
                "source_platform": "tableau",
                "source_id": f"{ds.get('name', '')}::{tbl.get('name', '')}",
            })
    return result


def _convert_dimensions(data: Dict) -> List[Dict]:
    """Extract dimension columns from Tableau datasources + calculations."""
    dims = []
    seen: set = set()

    # From datasource columns with role "dimension"
    for ds in data.get("datasources", []):
        for tbl in ds.get("tables", []):
            for col in tbl.get("columns", []):
                if col.get("role") == "dimension":
                    key = f"{tbl.get('name', '')}::{col.get('name', '')}"
                    if key not in seen:
                        seen.add(key)
                        dims.append({
                            "id": _next_id("DI"),
                            "name": col.get("name", ""),
                            "description": "",
                            "data_type": col.get("datatype", "string"),
                            "column_name": col.get("name", ""),
                            "table": tbl.get("name", ""),
                            "geographic_role": None,
                            "sort_order": "ascending",
                            "display_format": col.get("default_format", ""),
                            "forms": [],
                            "source_platform": "tableau",
                            "source_id": key,
                        })

    # From calculations with role "dimension"
    for calc in data.get("calculations", []):
        if calc.get("role") == "dimension":
            name = calc.get("caption", calc.get("name", "")).strip("[]")
            key = f"calc::{name}"
            if key not in seen:
                seen.add(key)
                dims.append({
                    "id": _next_id("DI"),
                    "name": name,
                    "description": calc.get("description", ""),
                    "data_type": calc.get("datatype", "string"),
                    "column_name": name,
                    "table": calc.get("datasource_name", ""),
                    "geographic_role": None,
                    "sort_order": "ascending",
                    "display_format": "",
                    "forms": [],
                    "source_platform": "tableau",
                    "source_id": key,
                })

    return dims


def _convert_measures(data: Dict) -> List[Dict]:
    measures = []

    # From calculations with role "measure"
    for calc in data.get("calculations", []):
        if calc.get("role") == "measure":
            name = calc.get("caption", calc.get("name", "")).strip("[]")
            measures.append({
                "id": _next_id("ME"),
                "name": name,
                "description": calc.get("description", ""),
                "measure_type": "calculated",
                "expression": calc.get("formula", ""),
                "dax_expression": calc.get("dax_expression", ""),
                "aggregation": "",
                "format_string": "",
                "dependencies": [],
                "column_ref": None,
                "source_platform": "tableau",
                "source_id": calc.get("name", ""),
            })

    # From datasource columns with role "measure"
    for ds in data.get("datasources", []):
        for tbl in ds.get("tables", []):
            for col in tbl.get("columns", []):
                if col.get("role") == "measure":
                    measures.append({
                        "id": _next_id("ME"),
                        "name": col.get("name", ""),
                        "description": "",
                        "measure_type": "fact",
                        "expression": "",
                        "dax_expression": "",
                        "aggregation": "sum",
                        "format_string": col.get("default_format", ""),
                        "data_type": col.get("datatype", "real"),
                        "expressions": [{"table": tbl.get("name", ""),
                                         "column": col.get("name", "")}],
                        "dependencies": [],
                        "column_ref": None,
                        "source_platform": "tableau",
                        "source_id": f"{tbl.get('name', '')}::{col.get('name', '')}",
                    })

    return measures


def _convert_relationships(data: Dict) -> List[Dict]:
    rels = []
    for ds in data.get("datasources", []):
        for rel in ds.get("relationships", []):
            left = rel.get("left", {})
            right = rel.get("right", {})
            join_type = rel.get("type", "inner")
            cardinality = "many_to_one"
            if join_type in ("full", "cross"):
                cardinality = "many_to_many"
            rels.append({
                "from_table": left.get("table", ""),
                "from_column": left.get("column", ""),
                "to_table": right.get("table", ""),
                "to_column": right.get("column", ""),
                "type": cardinality,
                "active": True,
                "cross_filter": "single",
                "source_platform": "tableau",
            })
    return rels


def _convert_hierarchies(data: Dict) -> List[Dict]:
    return [
        {
            "id": _next_id("HI"),
            "name": h.get("name", ""),
            "type": "user",
            "levels": [
                {"name": lv.get("name", lv.get("field", "")),
                 "column_name": lv.get("field", lv.get("name", "")),
                 "order": i + 1}
                for i, lv in enumerate(h.get("levels", []))
            ],
            "source_platform": "tableau",
        }
        for h in data.get("hierarchies", [])
    ]


def _convert_security(data: Dict) -> List[Dict]:
    return [
        {
            "id": _next_id("SF"),
            "name": uf.get("name", f"UserFilter_{i}"),
            "expression": uf.get("expression", uf.get("formula", "")),
            "target_columns": [{"column": uf.get("field", "")}],
            "groups": [],
            "users": uf.get("users", []),
            "description": "",
            "source_platform": "tableau",
        }
        for i, uf in enumerate(data.get("user_filters", []))
    ]


def _convert_pages(data: Dict) -> List[Dict]:
    """Convert Tableau worksheets + dashboards into universal pages."""
    pages: List[Dict] = []

    # Worksheets → one page each
    for ws in data.get("worksheets", []):
        fields: List[Dict] = []
        for f in ws.get("fields", []):
            shelf = f.get("shelf", "")
            role = _shelf_to_role(shelf)
            fields.append({
                "name": f.get("name", ""),
                "role": role,
                "shelf": shelf,
            })

        mark = ws.get("original_mark_class", "Automatic")
        viz_type = _MARK_TYPE_MAP.get(mark, ws.get("chart_type", "auto"))

        pages.append({
            "id": _next_id("PG"),
            "name": ws.get("name", ""),
            "parent_name": ws.get("name", ""),
            "parent_type": "worksheet",
            "visuals": [{
                "id": _next_id("VZ"),
                "name": ws.get("name", ""),
                "viz_type": viz_type,
                "fields": fields,
                "position": {"x": 0, "y": 0, "width": 1280, "height": 720},
                "filters": ws.get("filters", []),
                "formatting": ws.get("formatting", {}),
                "thresholds": [],
                "source_platform": "tableau",
            }],
            "source_platform": "tableau",
        })

    # Dashboards → one page each (referencing worksheet visuals)
    ws_lookup = {ws.get("name", ""): ws for ws in data.get("worksheets", [])}
    for db in data.get("dashboards", []):
        vizs: List[Dict] = []
        for obj in db.get("objects", []):
            if obj.get("type") != "worksheetReference":
                continue
            ws_name = obj.get("worksheetName", obj.get("name", ""))
            ws = ws_lookup.get(ws_name, {})
            fields = []
            for f in ws.get("fields", []):
                fields.append({
                    "name": f.get("name", ""),
                    "role": _shelf_to_role(f.get("shelf", "")),
                })
            pos = obj.get("position", {})
            mark = ws.get("original_mark_class", "Automatic")
            viz_type = _MARK_TYPE_MAP.get(mark, ws.get("chart_type", "auto"))
            vizs.append({
                "id": _next_id("VZ"),
                "name": ws_name,
                "viz_type": viz_type,
                "fields": fields,
                "position": {
                    "x": pos.get("x", 0),
                    "y": pos.get("y", 0),
                    "width": pos.get("w", 600),
                    "height": pos.get("h", 350),
                },
                "filters": [],
                "formatting": {},
                "thresholds": [],
                "source_platform": "tableau",
            })
        if vizs:
            pages.append({
                "id": _next_id("PG"),
                "name": db.get("name", ""),
                "parent_name": db.get("name", ""),
                "parent_type": "dashboard",
                "visuals": vizs,
                "source_platform": "tableau",
            })

    return pages


def _convert_parameters(data: Dict) -> List[Dict]:
    return [
        {
            "id": _next_id("PR"),
            "name": p.get("caption", p.get("name", "")).strip("[]").split(".")[-1],
            "param_type": "value",
            "data_type": p.get("datatype", "string"),
            "required": False,
            "allow_multi": False,
            "default_value": p.get("value", ""),
            "options": p.get("allowable_values", []),
            "pbi_type": "parameter",
            "attribute_name": "",
            "min_value": None,
            "max_value": None,
            "source_platform": "tableau",
        }
        for p in data.get("parameters", [])
    ]


def _convert_custom_groups(data: Dict) -> List[Dict]:
    groups = []
    for g in data.get("groups", []):
        groups.append({
            "id": _next_id("CG"),
            "name": g.get("name", ""),
            "type": "group",
            "elements": g.get("members", g.get("elements", [])),
            "source_platform": "tableau",
        })
    for s in data.get("sets", []):
        groups.append({
            "id": _next_id("CG"),
            "name": s.get("name", ""),
            "type": "set",
            "elements": s.get("members", []),
            "source_platform": "tableau",
        })
    return groups


def _convert_custom_sql(data: Dict) -> List[Dict]:
    return [
        {
            "id": _next_id("FF"),
            "name": cs.get("name", ""),
            "sql_statement": cs.get("sql", cs.get("query", "")),
            "db_connection": cs.get("connection", {}),
            "columns": cs.get("columns", []),
            "source_platform": "tableau",
        }
        for cs in data.get("custom_sql", [])
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shelf_to_role(shelf: str) -> str:
    """Map Tableau shelf name to universal field role."""
    mapping = {
        "columns": "axis",
        "rows": "axis",
        "color": "legend",
        "size": "value",
        "label": "value",
        "detail": "detail",
        "tooltip": "tooltip",
        "measure_value": "value",
        "pages": "filter",
    }
    return mapping.get(shelf, "value")
