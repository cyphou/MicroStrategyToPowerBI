"""
Fabric Data Factory pipeline generator.

Generates Data Factory pipeline JSON definitions for orchestrating:
  source warehouse → Lakehouse copy activity → semantic model refresh → notification.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────


def generate_pipeline(data, output_dir, *,
                      lakehouse_name=None,
                      semantic_model_name=None,
                      workspace_id=None):
    """Generate a Fabric Data Factory pipeline definition.

    Args:
        data: dict with intermediate JSON data.
        output_dir: Directory to write pipeline JSON.
        lakehouse_name: Target Lakehouse name.
        semantic_model_name: Semantic model to refresh after load.
        workspace_id: Target workspace ID.

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    freeform_sql = data.get("freeform_sql", [])

    # Group by connection for copy activities
    conn_groups = {}
    for ds in datasources:
        conn = ds.get("db_connection", {})
        key = _conn_key(conn)
        conn_groups.setdefault(key, {"connection": conn, "tables": []})
        conn_groups[key]["tables"].append(ds)

    activities = []

    # Copy activities per connection group
    for key, group in conn_groups.items():
        conn = group["connection"]
        for ds in group["tables"]:
            table_name = ds.get("physical_table") or ds["name"]
            delta_name = ds["name"]
            activity = _build_copy_activity(
                table_name, delta_name, conn,
                lakehouse_name=lakehouse_name,
            )
            activities.append(activity)

    # Freeform SQL copy activities
    for ffs in freeform_sql:
        conn = ffs.get("db_connection", {})
        activity = _build_copy_activity(
            ffs["name"], ffs["name"], conn,
            sql_statement=ffs.get("sql_statement"),
            lakehouse_name=lakehouse_name,
        )
        activities.append(activity)

    # Semantic model refresh activity
    if semantic_model_name:
        activities.append(_build_refresh_activity(
            semantic_model_name,
            workspace_id=workspace_id,
            depends_on=[a["name"] for a in activities],
        ))

    # Notification activity (always last)
    activities.append(_build_notification_activity(
        depends_on=[activities[-1]["name"]] if activities else [],
    ))

    pipeline = {
        "name": f"pipeline_mstr_migration_{lakehouse_name or 'default'}",
        "properties": {
            "description": "Auto-generated ETL pipeline from MicroStrategy migration",
            "activities": activities,
            "annotations": [
                "auto-generated",
                "microstrategy-migration",
            ],
        },
    }

    pipeline_path = os.path.join(output_dir, "pipeline.json")
    with open(pipeline_path, "w", encoding="utf-8") as f:
        json.dump(pipeline, f, indent=2, ensure_ascii=False)

    logger.info("Generated pipeline with %d activities", len(activities))
    return {
        "activities_count": len(activities),
        "pipeline_path": pipeline_path,
    }


# ── Activity builders ────────────────────────────────────────────


def _build_copy_activity(source_table, target_table, connection, *,
                         sql_statement=None, lakehouse_name=None):
    """Build a Copy Data activity JSON."""
    db_type = (connection.get("db_type") or "").lower()
    server = connection.get("server", "")
    database = connection.get("database", "")
    schema = connection.get("schema", "")

    source_config = _build_source_config(db_type, server, database, schema,
                                         source_table, sql_statement)

    return {
        "name": f"Copy_{target_table}",
        "type": "Copy",
        "dependsOn": [],
        "policy": {
            "timeout": "0.12:00:00",
            "retry": 2,
            "retryIntervalInSeconds": 30,
        },
        "typeProperties": {
            "source": source_config,
            "sink": {
                "type": "LakehouseTableSink",
                "tableActionOption": "Overwrite",
                "partitionOption": "None",
            },
            "datasetSettings": {
                "source": {
                    "type": _source_dataset_type(db_type),
                    "connection": {
                        "server": server,
                        "database": database,
                    },
                },
                "sink": {
                    "type": "LakehouseTable",
                    "table": target_table,
                    "lakehouse": lakehouse_name or "<LAKEHOUSE_NAME>",
                },
            },
        },
    }


def _build_refresh_activity(semantic_model_name, *, workspace_id=None, depends_on=None):
    """Build a Semantic Model Refresh activity."""
    return {
        "name": f"Refresh_{semantic_model_name}",
        "type": "SemanticModelRefresh",
        "dependsOn": [
            {"activity": dep, "dependencyConditions": ["Succeeded"]}
            for dep in (depends_on or [])
        ],
        "typeProperties": {
            "semanticModelName": semantic_model_name,
            "workspaceId": workspace_id or "<WORKSPACE_ID>",
            "refreshType": "Full",
        },
    }


def _build_notification_activity(*, depends_on=None):
    """Build a notification activity (placeholder)."""
    return {
        "name": "Notify_Migration_Complete",
        "type": "WebActivity",
        "dependsOn": [
            {"activity": dep, "dependencyConditions": ["Succeeded"]}
            for dep in (depends_on or [])
        ],
        "typeProperties": {
            "method": "POST",
            "url": "<WEBHOOK_URL>",
            "body": {
                "message": "MicroStrategy → Fabric migration pipeline completed successfully.",
                "status": "Success",
            },
        },
    }


def _build_source_config(db_type, server, database, schema,
                         table_name, sql_statement=None):
    """Build the source configuration for a copy activity."""
    if sql_statement:
        return {
            "type": _source_type(db_type),
            "sqlReaderQuery": sql_statement,
        }
    return {
        "type": _source_type(db_type),
        "schema": schema or "dbo",
        "table": table_name,
    }


def _source_type(db_type):
    """Map db_type to Data Factory source type."""
    mapping = {
        "sql_server": "SqlServerSource",
        "oracle": "OracleSource",
        "postgresql": "PostgreSqlSource",
        "mysql": "MySqlSource",
        "snowflake": "SnowflakeSource",
        "databricks": "DatabricksSource",
        "bigquery": "GoogleBigQuerySource",
        "teradata": "TeradataSource",
        "db2": "Db2Source",
    }
    return mapping.get(db_type, "SqlServerSource")


def _source_dataset_type(db_type):
    """Map db_type to Data Factory dataset type."""
    mapping = {
        "sql_server": "SqlServerTable",
        "oracle": "OracleTable",
        "postgresql": "PostgreSqlTable",
        "mysql": "MySqlTable",
        "snowflake": "SnowflakeTable",
        "databricks": "DatabricksTable",
        "bigquery": "GoogleBigQueryTable",
        "teradata": "TeradataTable",
        "db2": "Db2Table",
    }
    return mapping.get(db_type, "SqlServerTable")


def _conn_key(connection):
    return (
        (connection.get("db_type") or "").lower(),
        connection.get("server", ""),
        connection.get("database", ""),
    )
