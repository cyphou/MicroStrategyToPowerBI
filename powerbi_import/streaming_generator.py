"""
Streaming / real-time output generator.

Converts real-time classified MicroStrategy objects to:
  1. Power BI push dataset definitions (REST API schema)
  2. Fabric Eventstream definitions (KQL database → semantic model)
  3. Refresh schedule JSON for batch/near-real-time objects

Push datasets are used when data is delivered via REST API calls;
Eventstream is used when Fabric Real-Time Intelligence is available.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── MSTR → Push Dataset type mapping ────────────────────────────

_PUSH_TYPE_MAP = {
    "integer": "Int64",
    "int": "Int64",
    "bigint": "Int64",
    "smallint": "Int64",
    "tinyint": "Int64",
    "real": "Double",
    "double": "Double",
    "float": "Double",
    "decimal": "Decimal",
    "bigdecimal": "Decimal",
    "numeric": "Decimal",
    "money": "Decimal",
    "char": "String",
    "varchar": "String",
    "nvarchar": "String",
    "string": "String",
    "text": "String",
    "date": "DateTime",
    "datetime": "DateTime",
    "timestamp": "DateTime",
    "time": "DateTime",
    "boolean": "Bool",
    "bool": "Bool",
    "bit": "Bool",
}

# ── Default retention policy ─────────────────────────────────────

_DEFAULT_RETENTION = "basicFIFO"
_DEFAULT_RETENTION_HOURS = 24 * 30   # 30 days


# ── Public API ───────────────────────────────────────────────────


def generate_streaming_artifacts(data, realtime_result, output_dir, *,
                                  workspace_id=None):
    """Generate push-dataset and Eventstream definitions.

    Args:
        data: dict with intermediate JSON data.
        realtime_result: output of detect_realtime_sources().
        output_dir: Directory to write output files.
        workspace_id: Optional Fabric workspace ID for Eventstream.

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    objects = realtime_result.get("objects", [])
    streaming_objs = [o for o in objects if o["refresh_class"] == "streaming"]
    near_rt_objs = [o for o in objects if o["refresh_class"] == "near_realtime"]

    stats = {
        "push_datasets": 0,
        "eventstream_definitions": 0,
        "refresh_schedules": 0,
        "warnings": [],
    }

    # ── Push datasets for streaming objects ──────────────────────
    push_datasets = []
    for obj in streaming_objs:
        ds = _build_push_dataset(obj, data)
        if ds:
            push_datasets.append(ds)
            stats["push_datasets"] += 1

    if push_datasets:
        path = os.path.join(output_dir, "push_datasets.json")
        _write_json(path, push_datasets)
        logger.info("Generated %d push dataset definitions", len(push_datasets))

    # ── Eventstream definitions for streaming objects ─────────────
    eventstreams = []
    for obj in streaming_objs:
        es = _build_eventstream(obj, data, workspace_id=workspace_id)
        if es:
            eventstreams.append(es)
            stats["eventstream_definitions"] += 1

    if eventstreams:
        path = os.path.join(output_dir, "eventstreams.json")
        _write_json(path, eventstreams)
        logger.info("Generated %d Eventstream definitions", len(eventstreams))

    # ── Refresh schedules for near-realtime objects ──────────────
    schedules = []
    for obj in near_rt_objs:
        sched = _build_refresh_schedule(obj)
        if sched:
            schedules.append(sched)
            stats["refresh_schedules"] += 1

    if schedules:
        path = os.path.join(output_dir, "refresh_schedules.json")
        _write_json(path, schedules)
        logger.info("Generated %d refresh schedules", len(schedules))

    # Summary
    summary_path = os.path.join(output_dir, "streaming_summary.json")
    _write_json(summary_path, {
        "streaming_objects": len(streaming_objs),
        "near_realtime_objects": len(near_rt_objs),
        **stats,
    })

    return stats


# ── Push Dataset Builder ─────────────────────────────────────────


def _build_push_dataset(obj, data):
    """Build a Power BI push dataset definition.

    Maps the object's underlying tables/metrics to a push dataset schema.
    """
    name = obj.get("name", "UnnamedDataset")
    obj_type = obj.get("object_type", "")

    tables = _resolve_tables(obj, data)
    if not tables:
        return None

    dataset_tables = []
    for tbl in tables:
        columns = _resolve_push_columns(tbl, data)
        dataset_tables.append({
            "name": tbl.get("name", "Table"),
            "columns": columns,
        })

    return {
        "name": f"PushDataset_{_safe_name(name)}",
        "source_object": {"id": obj.get("id", ""), "name": name, "type": obj_type},
        "defaultMode": "Push",
        "defaultRetentionPolicy": _DEFAULT_RETENTION,
        "tables": dataset_tables,
    }


def _resolve_tables(obj, data):
    """Identify which intermediate-JSON tables underlie the object."""
    datasources = data.get("datasources", [])
    if not datasources:
        return []

    # If the object references specific tables (dossier/report bindings),
    # return those; otherwise fall back to all datasources.
    obj_tables = obj.get("details", {}).get("tables", [])
    if obj_tables:
        table_names = {t if isinstance(t, str) else t.get("name", "") for t in obj_tables}
        return [ds for ds in datasources if ds.get("name") in table_names]

    return datasources


def _resolve_push_columns(table, data):
    """Build column list for a push dataset table."""
    columns = []
    for col in table.get("columns", []):
        col_name = col.get("name", "")
        raw_type = (col.get("data_type") or col.get("sql_type") or "string").lower()
        push_type = _PUSH_TYPE_MAP.get(raw_type, "String")
        columns.append({"name": col_name, "dataType": push_type})

    # Always include a timestamp column if none exists
    col_names = {c["name"].lower() for c in columns}
    if not col_names & {"timestamp", "eventtime", "event_time", "loadedatetime"}:
        columns.append({"name": "_PushTimestamp", "dataType": "DateTime"})

    return columns


# ── Eventstream Builder ──────────────────────────────────────────


def _build_eventstream(obj, data, *, workspace_id=None):
    """Build a Fabric Eventstream definition.

    Maps an MSTR real-time source → Eventstream → KQL Database → Semantic Model.
    """
    name = obj.get("name", "Unnamed")

    datasources = data.get("datasources", [])
    connections = []
    for ds in datasources:
        conn = ds.get("db_connection", {})
        if conn:
            connections.append({
                "db_type": conn.get("db_type", "unknown"),
                "server": conn.get("server", conn.get("host", "")),
                "database": conn.get("database", ""),
            })

    return {
        "name": f"Eventstream_{_safe_name(name)}",
        "source_object": {"id": obj.get("id", ""), "name": name},
        "workspaceId": workspace_id or "<WORKSPACE_ID>",
        "source": {
            "type": "CustomEndpoint",
            "description": f"Streaming source for {name} (migrated from MicroStrategy)",
        },
        "destinations": [
            {
                "type": "KQLDatabase",
                "name": f"KQL_{_safe_name(name)}",
                "table": _safe_name(name),
                "retentionHours": _DEFAULT_RETENTION_HOURS,
            },
            {
                "type": "Lakehouse",
                "name": f"LH_{_safe_name(name)}",
                "table": _safe_name(name),
            },
        ],
        "sourceConnections": connections,
    }


# ── Refresh Schedule Builder ─────────────────────────────────────


def _build_refresh_schedule(obj):
    """Build a PBI refresh schedule for a near-realtime object."""
    interval = obj.get("refresh_interval_seconds")
    if interval is None:
        interval = 1800   # default 30 min

    # Power BI supports refresh intervals of 15 min (Premium) up to daily
    minutes = max(15, interval // 60)

    return {
        "name": obj.get("name", ""),
        "object_type": obj.get("object_type", ""),
        "schedule": {
            "enabled": True,
            "refreshType": "Full",
            "frequencyMinutes": minutes,
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"],
            "localTimeZoneId": "UTC",
        },
        "source_interval_seconds": interval,
    }


# ── Helpers ──────────────────────────────────────────────────────


def _safe_name(name):
    """Sanitize a name for use in identifiers."""
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '_', name).strip('_')[:64]


def _write_json(path, obj):
    """Write an object to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
