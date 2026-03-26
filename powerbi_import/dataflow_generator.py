"""
Fabric Dataflow Gen2 generator.

Generates Dataflow Gen2 definitions that ingest data from MicroStrategy
source warehouses into Fabric Lakehouse Delta tables via Power Query M
mashups.  Output is JSON compatible with the Fabric REST API
``/items/{id}/definition`` payload.
"""

import json
import logging
import os

from powerbi_import.fabric_constants import SPARK_TYPE_MAP, map_spark_type
from powerbi_import.fabric_naming import (
    sanitize_dataflow_name,
    sanitize_table_name,
)

logger = logging.getLogger(__name__)

# ── M connector templates (source → Power Query M) ──────────────

_M_SOURCE_TEMPLATES = {
    "sql_server": (
        'let\n'
        '    Source = Sql.Database("{server}", "{database}"),\n'
        '    {schema}_{table} = Source{{[Schema="{schema}", Item="{table}"]}}[Data]\n'
        'in\n'
        '    {schema}_{table}'
    ),
    "postgresql": (
        'let\n'
        '    Source = PostgreSQL.Database("{server}", "{database}"),\n'
        '    {schema}_{table} = Source{{[Schema="{schema}", Item="{table}"]}}[Data]\n'
        'in\n'
        '    {schema}_{table}'
    ),
    "oracle": (
        'let\n'
        '    Source = Oracle.Database("{server}"),\n'
        '    {schema}_{table} = Source{{[Schema="{schema}", Item="{table}"]}}[Data]\n'
        'in\n'
        '    {schema}_{table}'
    ),
    "mysql": (
        'let\n'
        '    Source = MySQL.Database("{server}", "{database}"),\n'
        '    {table}_1 = Source{{[Schema="{schema}", Item="{table}"]}}[Data]\n'
        'in\n'
        '    {table}_1'
    ),
    "snowflake": (
        'let\n'
        '    Source = Snowflake.Databases("{server}", "{database}"),\n'
        '    {schema}_{table} = Source{{[Schema="{schema}", Item="{table}"]}}[Data]\n'
        'in\n'
        '    {schema}_{table}'
    ),
    "bigquery": (
        'let\n'
        '    Source = GoogleBigQuery.Database(),\n'
        '    {database}_{table} = Source{{[Name="{database}"]}}[Data]{{[Name="{schema}"]}}[Data]{{[Name="{table}"]}}[Data]\n'
        'in\n'
        '    {database}_{table}'
    ),
}

_DEFAULT_M_TEMPLATE = (
    'let\n'
    '    Source = OleDb.DataSource("{server}", [Query="SELECT * FROM {schema}.{table}"]),\n'
    '    Result = Source{{0}}[Data]\n'
    'in\n'
    '    Result'
)


# ── Public API ───────────────────────────────────────────────────


def generate_dataflows(data, output_dir, *, lakehouse_name=None):
    """Generate Fabric Dataflow Gen2 definitions.

    Creates one dataflow per datasource.  Each dataflow contains a
    Power Query M mashup that reads from the source and writes to a
    Lakehouse Delta table.

    Args:
        data: dict with intermediate JSON data (datasources, freeform_sql).
        output_dir: Directory to write dataflow JSON files.
        lakehouse_name: Target Lakehouse name (for destination binding).

    Returns:
        dict with ``dataflows_generated``, ``dataflow_dir``.
    """
    df_dir = os.path.join(output_dir, "dataflows")
    os.makedirs(df_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    freeform_sql = data.get("freeform_sql", [])
    dataflows = []

    for ds in datasources:
        df_def = _build_dataflow(ds, lakehouse_name=lakehouse_name)
        dataflows.append(df_def)

    for ffs in freeform_sql:
        df_def = _build_freeform_dataflow(ffs, lakehouse_name=lakehouse_name)
        dataflows.append(df_def)

    # Write individual dataflow files
    for df_def in dataflows:
        name = df_def["properties"]["displayName"]
        path = os.path.join(df_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(df_def, f, indent=2, ensure_ascii=False)

    # Write manifest
    manifest = {
        "dataflow_count": len(dataflows),
        "lakehouse_name": lakehouse_name,
        "dataflows": [d["properties"]["displayName"] for d in dataflows],
    }
    manifest_path = os.path.join(df_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("Generated %d Dataflow Gen2 definitions", len(dataflows))
    return {
        "dataflows_generated": len(dataflows),
        "dataflow_dir": df_dir,
    }


# ── Dataflow builder ─────────────────────────────────────────────


def _build_dataflow(ds, *, lakehouse_name=None):
    """Build a Fabric Dataflow Gen2 definition dict for a datasource."""
    table_name = ds.get("physical_table") or ds["name"]
    connection = ds.get("db_connection", {})
    db_type = (connection.get("db_type") or "").lower()
    server = connection.get("server", "")
    database = connection.get("database", "")
    schema = connection.get("schema", "dbo")
    columns = ds.get("columns", [])

    display_name = sanitize_dataflow_name(table_name)
    dest_table = sanitize_table_name(table_name)

    # Build M query
    m_query = _build_m_query(db_type, server=server, database=database,
                             schema=schema, table=table_name)

    # Build column mappings for destination
    col_mappings = _build_column_mappings(columns)

    return {
        "type": "dataflow",
        "properties": {
            "displayName": display_name,
            "description": f"Ingest {table_name} from {db_type or 'source'} to Lakehouse",
        },
        "definition": {
            "parts": [
                {
                    "path": "mashup",
                    "payload": m_query,
                    "payloadType": "InlineBase64",
                },
            ],
        },
        "destination": {
            "type": "lakehouse",
            "lakehouse": {
                "name": lakehouse_name or "default",
                "table": dest_table,
                "updateMethod": "replace",
            },
            "columnMappings": col_mappings,
        },
    }


def _build_freeform_dataflow(ffs, *, lakehouse_name=None):
    """Build a dataflow for a freeform SQL source."""
    table_name = ffs["name"]
    sql = ffs.get("sql", "")
    connection = ffs.get("db_connection", {})
    db_type = (connection.get("db_type") or "").lower()
    server = connection.get("server", "")
    database = connection.get("database", "")
    columns = ffs.get("columns", [])

    display_name = sanitize_dataflow_name(table_name)
    dest_table = sanitize_table_name(table_name)

    # For freeform SQL, use native query M
    m_query = (
        f'let\n'
        f'    Source = Value.NativeQuery(Sql.Database("{server}", "{database}"), '
        f'"{sql}", null, [EnableFolding=false])\n'
        f'in\n'
        f'    Source'
    )

    col_mappings = _build_column_mappings(columns)

    return {
        "type": "dataflow",
        "properties": {
            "displayName": display_name,
            "description": f"Ingest {table_name} (freeform SQL) to Lakehouse",
        },
        "definition": {
            "parts": [
                {
                    "path": "mashup",
                    "payload": m_query,
                    "payloadType": "InlineBase64",
                },
            ],
        },
        "destination": {
            "type": "lakehouse",
            "lakehouse": {
                "name": lakehouse_name or "default",
                "table": dest_table,
                "updateMethod": "replace",
            },
            "columnMappings": col_mappings,
        },
    }


# ── M query builder ──────────────────────────────────────────────


def _build_m_query(db_type, *, server, database, schema, table):
    """Build a Power Query M expression for the source connection."""
    template = _M_SOURCE_TEMPLATES.get(db_type, _DEFAULT_M_TEMPLATE)
    return template.format(
        server=server,
        database=database,
        schema=schema,
        table=table,
    )


# ── Column mappings ──────────────────────────────────────────────


def _build_column_mappings(columns):
    """Build Dataflow column mapping list."""
    mappings = []
    for col in columns:
        name = col.get("name", "")
        data_type = col.get("data_type", "string")
        spark_type = map_spark_type(data_type)
        mappings.append({
            "source": name,
            "destination": name,
            "dataType": spark_type,
        })
    return mappings
