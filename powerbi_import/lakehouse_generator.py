"""
Lakehouse schema and shortcut generator.

Generates Fabric Lakehouse Delta table definitions from MicroStrategy
schema (attributes, facts, datasources) and optional OneLake shortcuts.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── MSTR data type → Spark SQL type mapping ──────────────────────

_SPARK_TYPE_MAP = {
    "integer": "INT",
    "int": "INT",
    "biginteger": "BIGINT",
    "long": "BIGINT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT",
    "real": "DOUBLE",
    "float": "FLOAT",
    "double": "DOUBLE",
    "numeric": "DECIMAL(38,10)",
    "decimal": "DECIMAL(38,10)",
    "bigdecimal": "DECIMAL(38,10)",
    "money": "DECIMAL(19,4)",
    "nvarchar": "STRING",
    "varchar": "STRING",
    "char": "STRING",
    "nchar": "STRING",
    "text": "STRING",
    "longvarchar": "STRING",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "time": "STRING",
    "boolean": "BOOLEAN",
    "bit": "BOOLEAN",
    "binary": "BINARY",
    "varbinary": "BINARY",
    "blob": "BINARY",
}


def _map_spark_type(mstr_type):
    """Map a MicroStrategy data type to a Spark SQL type."""
    return _SPARK_TYPE_MAP.get((mstr_type or "string").lower().strip(), "STRING")


# ── Public API ───────────────────────────────────────────────────


def generate_lakehouse_schema(data, output_dir, *, lakehouse_name=None):
    """Generate Spark SQL DDL scripts for Fabric Lakehouse tables.

    Args:
        data: dict with intermediate JSON data (datasources, freeform_sql).
        output_dir: Directory to write SQL files into.
        lakehouse_name: Optional lakehouse name for USE statement.

    Returns:
        dict with generation stats: tables_generated, script_path.
    """
    os.makedirs(output_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    freeform_sql = data.get("freeform_sql", [])

    ddl_statements = []

    if lakehouse_name:
        ddl_statements.append(f"-- Lakehouse: {lakehouse_name}")
        ddl_statements.append("")

    # Generate CREATE TABLE for each datasource
    for ds in datasources:
        table_name = ds.get("physical_table") or ds["name"]
        columns = ds.get("columns", [])
        ddl = _generate_create_table(table_name, columns)
        ddl_statements.append(ddl)

    # Generate CREATE TABLE for freeform SQL source views
    for ffs in freeform_sql:
        table_name = ffs["name"]
        columns = ffs.get("columns", [])
        ddl = _generate_create_table(table_name, columns)
        ddl_statements.append(ddl)

    # Write combined DDL script
    script_path = os.path.join(output_dir, "lakehouse_schema.sql")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(ddl_statements) + "\n")

    # Also write individual table DDL files
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    table_count = 0
    for ds in datasources:
        table_name = ds.get("physical_table") or ds["name"]
        columns = ds.get("columns", [])
        ddl = _generate_create_table(table_name, columns)
        with open(os.path.join(tables_dir, f"{table_name}.sql"), "w", encoding="utf-8") as f:
            f.write(ddl + "\n")
        table_count += 1

    for ffs in freeform_sql:
        table_name = ffs["name"]
        columns = ffs.get("columns", [])
        ddl = _generate_create_table(table_name, columns)
        with open(os.path.join(tables_dir, f"{table_name}.sql"), "w", encoding="utf-8") as f:
            f.write(ddl + "\n")
        table_count += 1

    logger.info("Generated Lakehouse DDL for %d tables", table_count)
    return {
        "tables_generated": table_count,
        "script_path": script_path,
    }


def generate_shortcuts(data, output_dir, *, adls_account=None, container=None):
    """Generate Lakehouse shortcut definitions for OneLake / ADLS sources.

    Shortcuts enable zero-copy access to existing data in ADLS, OneLake,
    S3, or GCS without ETL.

    Args:
        data: dict with intermediate JSON data (datasources).
        output_dir: Directory to write shortcut JSON files.
        adls_account: ADLS storage account name.
        container: ADLS container name.

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    shortcuts = []

    for ds in datasources:
        table_name = ds.get("physical_table") or ds["name"]
        connection = ds.get("db_connection", {})
        db_type = (connection.get("db_type") or "").lower()

        shortcut = _build_shortcut(table_name, db_type, connection,
                                   adls_account=adls_account,
                                   container=container)
        if shortcut:
            shortcuts.append(shortcut)

    # Write shortcut definitions
    shortcuts_path = os.path.join(output_dir, "shortcuts.json")
    with open(shortcuts_path, "w", encoding="utf-8") as f:
        json.dump(shortcuts, f, indent=2, ensure_ascii=False)

    logger.info("Generated %d Lakehouse shortcut definitions", len(shortcuts))
    return {
        "shortcuts_generated": len(shortcuts),
        "shortcuts_path": shortcuts_path,
    }


# ── DDL generation ───────────────────────────────────────────────


def _generate_create_table(table_name, columns):
    """Generate a Spark SQL CREATE TABLE statement for a Delta table."""
    if not columns:
        return f"-- Skipped {table_name}: no columns defined"

    col_defs = []
    for col in columns:
        col_name = col["name"]
        spark_type = _map_spark_type(col.get("data_type", "string"))
        col_defs.append(f"    {col_name} {spark_type}")

    col_str = ",\n".join(col_defs)
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        f"{col_str}\n"
        f") USING DELTA;"
    )


# ── Shortcut generation ─────────────────────────────────────────


def _build_shortcut(table_name, db_type, connection, *,
                    adls_account=None, container=None):
    """Build a shortcut definition dict."""
    shortcut = {
        "name": table_name,
        "target": {},
    }

    # ADLS shortcut
    if adls_account and container:
        shortcut["target"] = {
            "type": "adlsGen2",
            "adlsGen2": {
                "accountName": adls_account,
                "containerName": container,
                "path": f"/tables/{table_name}",
            },
        }
        return shortcut

    # Databricks / Snowflake warehouse shortcuts map to external table references
    if db_type in ("databricks", "snowflake"):
        server = connection.get("server", "")
        database = connection.get("database", "")
        schema = connection.get("schema", "")
        shortcut["target"] = {
            "type": "externalTable",
            "externalTable": {
                "source": db_type,
                "server": server,
                "database": database,
                "schema": schema,
                "table": table_name,
            },
        }
        return shortcut

    # No shortcut for traditional databases — need ETL
    return None
