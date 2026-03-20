"""
Fabric environment configuration generator.

Generates Fabric environment definitions: Spark pool configuration,
library requirements, and connection settings for migration workloads.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────


def generate_environment(data, output_dir, *, env_name=None):
    """Generate a Fabric environment configuration.

    Args:
        data: dict with intermediate JSON data.
        output_dir: Directory to write environment config files.
        env_name: Environment name.

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    datasources = data.get("datasources", [])

    # Detect required JDBC drivers from connection types
    db_types = set()
    for ds in datasources:
        dt = (ds.get("db_connection", {}).get("db_type") or "").lower()
        if dt:
            db_types.add(dt)

    for ffs in data.get("freeform_sql", []):
        dt = (ffs.get("db_connection", {}).get("db_type") or "").lower()
        if dt:
            db_types.add(dt)

    # Build environment config
    env_config = _build_environment_config(
        db_types, datasources, env_name=env_name,
    )

    config_path = os.path.join(output_dir, "environment.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(env_config, f, indent=2, ensure_ascii=False)

    # Generate requirements.txt for Python libraries
    requirements = _build_requirements(db_types)
    req_path = os.path.join(output_dir, "requirements.txt")
    with open(req_path, "w", encoding="utf-8") as f:
        f.write("\n".join(requirements) + "\n")

    logger.info("Generated Fabric environment config with %d connectors", len(db_types))
    return {
        "connectors": sorted(db_types),
        "config_path": config_path,
        "requirements_path": req_path,
    }


def estimate_capacity(data):
    """Estimate Fabric CU consumption for the migration workload.

    Args:
        data: dict with intermediate JSON data.

    Returns:
        dict with capacity estimates.
    """
    datasources = data.get("datasources", [])
    total_columns = sum(len(ds.get("columns", [])) for ds in datasources)
    table_count = len(datasources)
    metric_count = len(data.get("metrics", [])) + len(data.get("derived_metrics", []))
    report_count = len(data.get("reports", []))
    dossier_count = len(data.get("dossiers", []))

    # Rough heuristic-based estimation
    # Base CU for small model
    cu_estimate = 2  # F2 minimum

    if table_count > 10:
        cu_estimate = max(cu_estimate, 4)
    if table_count > 20:
        cu_estimate = max(cu_estimate, 8)
    if total_columns > 200:
        cu_estimate = max(cu_estimate, 8)
    if metric_count > 50:
        cu_estimate = max(cu_estimate, 4)

    # Check for large/complex indicators
    has_freeform = bool(data.get("freeform_sql"))
    has_rls = bool(data.get("security_filters"))

    warnings = []
    if cu_estimate >= 8:
        warnings.append("Large model — consider F8 or higher capacity")
    if has_freeform:
        warnings.append("Freeform SQL present — may require higher memory for native queries")
    if has_rls:
        warnings.append("RLS present — per-user cache increases memory usage")

    return {
        "recommended_sku": f"F{cu_estimate}",
        "cu_estimate": cu_estimate,
        "table_count": table_count,
        "column_count": total_columns,
        "metric_count": metric_count,
        "report_count": report_count,
        "dossier_count": dossier_count,
        "warnings": warnings,
    }


# ── Builders ─────────────────────────────────────────────────────


_JDBC_LIBRARIES = {
    "sql_server": {"maven": "com.microsoft.sqlserver:mssql-jdbc:12.4.2.jre11"},
    "oracle": {"maven": "com.oracle.database.jdbc:ojdbc11:23.3.0.23.09"},
    "postgresql": {"maven": "org.postgresql:postgresql:42.7.3"},
    "mysql": {"maven": "com.mysql:mysql-connector-j:8.3.0"},
    "teradata": {"maven": "com.teradata.jdbc:terajdbc:20.0.0.12"},
    "db2": {"maven": "com.ibm.db2:jcc:11.5.9.0"},
}

_PYTHON_PACKAGES = {
    "snowflake": "snowflake-connector-python>=3.6.0",
    "bigquery": "google-cloud-bigquery>=3.17.0",
    "databricks": "databricks-sql-connector>=3.1.0",
}


def _build_environment_config(db_types, datasources, *, env_name=None):
    """Build a Fabric environment configuration dict."""
    libraries = []

    for dt in sorted(db_types):
        lib = _JDBC_LIBRARIES.get(dt)
        if lib:
            libraries.append({
                "type": "maven",
                "id": lib["maven"],
            })

    spark_config = {
        "spark.sql.parquet.int96RebaseModeInWrite": "CORRECTED",
        "spark.sql.parquet.datetimeRebaseModeInWrite": "CORRECTED",
        "spark.sql.ansi.enabled": "false",
    }

    return {
        "name": env_name or "mstr_migration_env",
        "description": "Fabric environment for MicroStrategy → Power BI migration ETL",
        "runtimeVersion": "1.2",
        "sparkProperties": spark_config,
        "libraries": libraries,
        "pools": {
            "defaultPool": {
                "type": "Workspace",
                "starterPool": {
                    "maxNodeCount": 3,
                    "maxExecutors": 2,
                },
            },
        },
    }


def _build_requirements(db_types):
    """Build a requirements.txt for Python dependencies."""
    packages = [
        "# Auto-generated by MicroStrategy → Power BI Migration Tool",
        "# Install in Fabric environment for ETL notebooks",
        "",
    ]
    for dt in sorted(db_types):
        pkg = _PYTHON_PACKAGES.get(dt)
        if pkg:
            packages.append(pkg)

    # Always include useful ETL utilities
    packages.extend([
        "",
        "# Common ETL utilities",
        "delta-spark>=3.0.0",
    ])

    return packages
