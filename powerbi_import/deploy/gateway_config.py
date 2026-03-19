"""
On-premises data gateway configuration helper.

Generates gateway connection configuration for the migrated semantic model
so that Power BI Service can reach the original MicroStrategy warehouse.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── Gateway data-source type mapping ─────────────────────────────

_GATEWAY_DS_TYPES = {
    "oracle": "Oracle",
    "sql_server": "Sql",
    "postgresql": "PostgreSql",
    "mysql": "MySql",
    "db2": "DB2",
    "teradata": "Teradata",
    "redshift": "AmazonRedshift",
    "snowflake": "Snowflake",
    "bigquery": "GoogleBigQuery",
    "sap_hana": "SapHana",
    "netezza": "Netezza",
    "vertica": "Vertica",
    "sybase": "Sybase",
    "informix": "Informix",
    "odbc": "Odbc",
}


# ── Public API ───────────────────────────────────────────────────


def generate_gateway_config(datasources, output_path=None):
    """Generate gateway connection configurations from extracted datasources.

    Args:
        datasources: List of datasource dicts from extraction.
        output_path: If provided, write config JSON to this path.

    Returns:
        dict with ``connections`` list and ``instructions``.
    """
    connections = []
    for ds in datasources:
        conn = _map_datasource(ds)
        if conn:
            connections.append(conn)

    config = {
        "connections": connections,
        "instructions": _build_instructions(connections),
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Gateway config written to %s", output_path)

    return config


# ── Mapping logic ────────────────────────────────────────────────


def _map_datasource(ds):
    """Map a single extracted datasource to gateway connection info."""
    ds_type = (ds.get("db_type") or ds.get("type") or "").lower()
    gateway_type = _GATEWAY_DS_TYPES.get(ds_type)

    if not gateway_type:
        logger.warning("Unknown datasource type '%s' — skipping gateway config", ds_type)
        return None

    server = ds.get("server") or ds.get("host") or ""
    database = ds.get("database") or ds.get("db_name") or ""
    port = ds.get("port")

    connection = {
        "name": ds.get("name") or f"{gateway_type}_{database}",
        "gatewayDataSourceType": gateway_type,
        "server": server,
        "database": database,
        "authentication": _infer_auth(ds),
    }

    if port:
        connection["port"] = port

    # Additional connection properties for specific types
    extras = _get_type_extras(ds_type, ds)
    if extras:
        connection["connectionProperties"] = extras

    return connection


def _infer_auth(ds):
    """Infer authentication configuration."""
    auth_type = (ds.get("auth_type") or ds.get("authentication") or "").lower()

    if auth_type in ("windows", "integrated", "kerberos"):
        return {"type": "Windows", "note": "Configure Windows credentials in gateway admin"}
    if auth_type in ("oauth", "oauth2", "entra"):
        return {"type": "OAuth2", "note": "Configure OAuth2 in gateway admin"}

    return {"type": "Basic", "note": "Configure username/password in gateway admin"}


def _get_type_extras(ds_type, ds):
    """Get type-specific connection properties."""
    extras = {}

    if ds_type == "oracle":
        if ds.get("service_name"):
            extras["serviceName"] = ds["service_name"]
        if ds.get("tns_name"):
            extras["tnsName"] = ds["tns_name"]
    elif ds_type == "snowflake":
        if ds.get("warehouse"):
            extras["warehouse"] = ds["warehouse"]
        if ds.get("role"):
            extras["role"] = ds["role"]
    elif ds_type == "bigquery":
        if ds.get("project_id"):
            extras["projectId"] = ds["project_id"]
    elif ds_type == "redshift":
        if ds.get("cluster_id"):
            extras["clusterId"] = ds["cluster_id"]

    return extras


# ── Instructions ─────────────────────────────────────────────────


def _build_instructions(connections):
    """Build human-readable setup instructions."""
    if not connections:
        return ["No datasource connections to configure."]

    instructions = [
        "Gateway setup steps:",
        "1. Install the on-premises data gateway on a machine with network access to the database.",
        "2. Register the gateway in the Power BI Service admin portal.",
        "3. Add the following data source connections to the gateway:",
    ]

    for i, conn in enumerate(connections, 1):
        instructions.append(
            f"   {i}. {conn['name']}: {conn['gatewayDataSourceType']} → "
            f"{conn['server']}/{conn['database']} ({conn['authentication']['type']})"
        )

    instructions.extend([
        "4. In the Power BI dataset settings, bind each connection to the gateway data source.",
        "5. Configure scheduled refresh if needed.",
    ])

    return instructions
