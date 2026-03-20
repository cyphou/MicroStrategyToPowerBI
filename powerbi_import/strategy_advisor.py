"""
Strategy advisor module.

Analyzes project characteristics and recommends the optimal Power BI
connectivity mode (Import, DirectQuery, Composite, or DirectLake).
"""

import logging

logger = logging.getLogger(__name__)

# ── Connectivity modes ───────────────────────────────────────────

IMPORT = "Import"
DIRECT_QUERY = "DirectQuery"
COMPOSITE = "Composite"
DIRECT_LAKE = "DirectLake"


# ── Thresholds ───────────────────────────────────────────────────

_LARGE_TABLE_ROWS_THRESHOLD = 10_000_000
_MANY_TABLES_THRESHOLD = 15
_REAL_TIME_KEYWORDS = {"real-time", "realtime", "streaming", "live", "real_time"}


# ── Public API ───────────────────────────────────────────────────


def recommend_strategy(data, *, fabric_available=False):
    """Return a strategy recommendation dict.

    Args:
        data: dict with intermediate JSON data.
        fabric_available: if True, DirectLake is an option.

    Returns:
        dict with 'recommended', 'rationale', and 'alternatives'.
    """
    signals = _gather_signals(data)
    recommendation = _decide(signals, fabric_available)
    return recommendation


# ── Signal gathering ─────────────────────────────────────────────


def _gather_signals(data):
    signals = {
        "table_count": len(data.get("datasources", [])),
        "has_large_tables": False,
        "has_freeform_sql": bool(data.get("freeform_sql")),
        "has_security_filters": bool(data.get("security_filters")),
        "connector_count": 0,
        "connectors": set(),
        "total_columns": 0,
        "has_cubes": bool(data.get("cubes")),
        "cube_count": len(data.get("cubes", [])),
        "metric_count": len(data.get("metrics", [])) + len(data.get("derived_metrics", [])),
        "relationship_count": len(data.get("relationships", [])),
    }

    for ds in data.get("datasources", []):
        cols = ds.get("columns", [])
        signals["total_columns"] += len(cols)

        db = ds.get("db_connection", {})
        ct = db.get("db_type", "")
        if ct:
            signals["connectors"].add(ct)

        row_count = ds.get("row_count", 0)
        if row_count and row_count > _LARGE_TABLE_ROWS_THRESHOLD:
            signals["has_large_tables"] = True

    signals["connector_count"] = len(signals["connectors"])
    return signals


# ── Decision logic ───────────────────────────────────────────────


def _decide(signals, fabric_available):
    reasons = []
    alternatives = []

    # DirectLake preferred on Fabric — cubes map naturally to Lakehouse Delta
    # tables, and even standard Import models benefit from DirectLake when a
    # Lakehouse is available.
    if fabric_available:
        if signals["has_cubes"]:
            reasons.append("Fabric available with cubes — DirectLake gives best performance")
        elif signals["has_large_tables"]:
            reasons.append("Fabric available with large tables — DirectLake avoids Import size limits")
        else:
            reasons.append("Fabric available — DirectLake recommended for Lakehouse-backed models")
        return {
            "recommended": DIRECT_LAKE,
            "rationale": " | ".join(reasons),
            "alternatives": [COMPOSITE, IMPORT],
            "signals": _serialize_signals(signals),
        }

    # Large tables → DirectQuery or Composite
    if signals["has_large_tables"]:
        reasons.append("Large tables detected — DirectQuery avoids Import size limits")
        if signals["connector_count"] > 1:
            reasons.append("Multiple connectors — Composite mode needed")
            return {
                "recommended": COMPOSITE,
                "rationale": " | ".join(reasons),
                "alternatives": [DIRECT_QUERY],
                "signals": _serialize_signals(signals),
            }
        return {
            "recommended": DIRECT_QUERY,
            "rationale": " | ".join(reasons),
            "alternatives": [COMPOSITE, IMPORT],
            "signals": _serialize_signals(signals),
        }

    # Multi-connector → Composite
    if signals["connector_count"] > 1:
        reasons.append("Multiple datasource connectors — Composite mode recommended")
        return {
            "recommended": COMPOSITE,
            "rationale": " | ".join(reasons),
            "alternatives": [IMPORT],
            "signals": _serialize_signals(signals),
        }

    # Default: Import
    reasons.append("Standard workload — Import mode provides best user experience")
    if signals["has_security_filters"]:
        reasons.append("RLS filters present — ensure refresh-based security")

    return {
        "recommended": IMPORT,
        "rationale": " | ".join(reasons),
        "alternatives": [COMPOSITE] if signals["table_count"] > _MANY_TABLES_THRESHOLD else [],
        "signals": _serialize_signals(signals),
    }


def _serialize_signals(signals):
    s = dict(signals)
    s["connectors"] = sorted(s.get("connectors", set()))
    return s
