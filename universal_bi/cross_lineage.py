"""Cross-platform lineage and deduplication.

When merging extraction output from multiple BI platforms, this module
detects shared data sources, overlapping dimensions, and equivalent
measures so the generation layer can produce a *merged* semantic model
without duplicates.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_shared_sources(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Identify datasource tables that appear in more than one platform.

    Returns a list of dicts ``{name, platforms, columns}`` for each
    shared table.
    """
    by_name: Dict[str, Dict[str, Any]] = {}
    for ds in schema.get("datasources", []):
        key = ds.get("name", "").lower()
        if not key:
            continue
        entry = by_name.setdefault(key, {"name": ds.get("name", ""),
                                          "platforms": set(),
                                          "columns": set()})
        entry["platforms"].add(ds.get("source_platform", "unknown"))
        for col in ds.get("columns", []):
            entry["columns"].add(col.get("name", "").lower())

    shared = []
    for entry in by_name.values():
        if len(entry["platforms"]) > 1:
            shared.append({
                "name": entry["name"],
                "platforms": sorted(entry["platforms"]),
                "columns": sorted(entry["columns"]),
            })

    logger.info("Shared sources detected: %d", len(shared))
    return shared


def detect_equivalent_dimensions(schema: Dict[str, Any],
                                  threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Find dimension pairs across platforms that likely represent the same concept.

    Uses table + column name matching with a Jaccard-like score.
    *threshold* (0-1) controls the minimum similarity.
    """
    by_platform: Dict[str, List[Dict]] = {}
    for dim in schema.get("dimensions", []):
        plat = dim.get("source_platform", "unknown")
        by_platform.setdefault(plat, []).append(dim)

    platforms = sorted(by_platform.keys())
    equivalences: List[Dict[str, Any]] = []

    for i in range(len(platforms)):
        for j in range(i + 1, len(platforms)):
            p1, p2 = platforms[i], platforms[j]
            for d1 in by_platform[p1]:
                for d2 in by_platform[p2]:
                    score = _dim_similarity(d1, d2)
                    if score >= threshold:
                        equivalences.append({
                            "dimension_a": {"name": d1.get("name"),
                                            "platform": p1,
                                            "table": d1.get("table"),
                                            "column": d1.get("column_name")},
                            "dimension_b": {"name": d2.get("name"),
                                            "platform": p2,
                                            "table": d2.get("table"),
                                            "column": d2.get("column_name")},
                            "score": round(score, 3),
                        })

    logger.info("Equivalent dimension pairs: %d", len(equivalences))
    return equivalences


def detect_equivalent_measures(schema: Dict[str, Any],
                                threshold: float = 0.8) -> List[Dict[str, Any]]:
    """Find measure pairs across platforms that likely represent the same metric."""
    by_platform: Dict[str, List[Dict]] = {}
    for m in schema.get("measures", []):
        plat = m.get("source_platform", "unknown")
        by_platform.setdefault(plat, []).append(m)

    platforms = sorted(by_platform.keys())
    equivalences: List[Dict[str, Any]] = []

    for i in range(len(platforms)):
        for j in range(i + 1, len(platforms)):
            p1, p2 = platforms[i], platforms[j]
            for m1 in by_platform[p1]:
                for m2 in by_platform[p2]:
                    score = _measure_similarity(m1, m2)
                    if score >= threshold:
                        equivalences.append({
                            "measure_a": {"name": m1.get("name"),
                                          "platform": p1,
                                          "aggregation": m1.get("aggregation")},
                            "measure_b": {"name": m2.get("name"),
                                          "platform": p2,
                                          "aggregation": m2.get("aggregation")},
                            "score": round(score, 3),
                        })

    logger.info("Equivalent measure pairs: %d", len(equivalences))
    return equivalences


def deduplicate(schema: Dict[str, Any],
                dim_threshold: float = 0.9,
                measure_threshold: float = 0.9) -> Dict[str, Any]:
    """Remove duplicate dimensions and measures across platforms.

    When equivalences are found above *threshold*, the first occurrence
    is kept and later duplicates are removed.  A ``dedup_log`` key is
    added to the schema with details of what was removed.
    """
    log: List[str] = []

    # Deduplicate dimensions
    dim_equivs = detect_equivalent_dimensions(schema, dim_threshold)
    remove_dims: Set[Tuple[str, str]] = set()  # (platform, name)
    for eq in dim_equivs:
        b = eq["dimension_b"]
        key = (b["platform"], b["name"])
        if key not in remove_dims:
            remove_dims.add(key)
            log.append(f"Removed duplicate dimension '{b['name']}' from {b['platform']} "
                       f"(equivalent to '{eq['dimension_a']['name']}' from {eq['dimension_a']['platform']}, "
                       f"score={eq['score']})")

    schema["dimensions"] = [
        d for d in schema.get("dimensions", [])
        if (d.get("source_platform", ""), d.get("name", "")) not in remove_dims
    ]

    # Deduplicate measures
    meas_equivs = detect_equivalent_measures(schema, measure_threshold)
    remove_meas: Set[Tuple[str, str]] = set()
    for eq in meas_equivs:
        b = eq["measure_b"]
        key = (b["platform"], b["name"])
        if key not in remove_meas:
            remove_meas.add(key)
            log.append(f"Removed duplicate measure '{b['name']}' from {b['platform']} "
                       f"(equivalent to '{eq['measure_a']['name']}' from {eq['measure_a']['platform']}, "
                       f"score={eq['score']})")

    schema["measures"] = [
        m for m in schema.get("measures", [])
        if (m.get("source_platform", ""), m.get("name", "")) not in remove_meas
    ]

    schema["dedup_log"] = log
    logger.info("Deduplication: removed %d dimensions, %d measures",
                len(remove_dims), len(remove_meas))
    return schema


def build_lineage(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Build a cross-platform lineage graph from the universal schema.

    Returns a dict with ``nodes`` (list) and ``edges`` (list).
    Node types: ``source``, ``dimension``, ``measure``, ``page``, ``visual``.
    """
    nodes: List[Dict] = []
    edges: List[Dict] = []
    node_ids: set = set()

    def _add_node(nid: str, name: str, ntype: str, platform: str = ""):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({"id": nid, "name": name, "type": ntype,
                          "platform": platform})

    # Datasources
    for ds in schema.get("datasources", []):
        nid = f"src::{ds.get('name', '')}"
        _add_node(nid, ds.get("name", ""), "source",
                  ds.get("source_platform", ""))

    # Dimensions
    for dim in schema.get("dimensions", []):
        nid = f"dim::{dim.get('name', '')}"
        _add_node(nid, dim.get("name", ""), "dimension",
                  dim.get("source_platform", ""))
        # Edge: source table → dimension
        src_nid = f"src::{dim.get('table', '')}"
        if src_nid in node_ids:
            edges.append({"from": src_nid, "to": nid, "type": "contains"})

    # Measures
    for m in schema.get("measures", []):
        nid = f"mea::{m.get('name', '')}"
        _add_node(nid, m.get("name", ""), "measure",
                  m.get("source_platform", ""))

    # Pages + visuals
    for pg in schema.get("pages", []):
        pg_nid = f"page::{pg.get('name', '')}"
        _add_node(pg_nid, pg.get("name", ""), "page",
                  pg.get("source_platform", ""))
        for vis in pg.get("visuals", []):
            v_nid = f"vis::{pg.get('name', '')}::{vis.get('name', '')}"
            _add_node(v_nid, vis.get("name", ""), "visual",
                      vis.get("source_platform", ""))
            edges.append({"from": pg_nid, "to": v_nid, "type": "contains"})
            # Visual → dimensions/measures it uses
            for f in vis.get("fields", []):
                fname = f.get("name", "")
                dim_nid = f"dim::{fname}"
                mea_nid = f"mea::{fname}"
                if dim_nid in node_ids:
                    edges.append({"from": dim_nid, "to": v_nid, "type": "feeds"})
                elif mea_nid in node_ids:
                    edges.append({"from": mea_nid, "to": v_nid, "type": "feeds"})

    return {"nodes": nodes, "edges": edges}


def lineage_summary(lineage: Dict[str, Any]) -> Dict[str, Any]:
    """Summarise a lineage graph into counts by type and platform."""
    nodes = lineage.get("nodes", [])
    by_type: Dict[str, int] = {}
    by_platform: Dict[str, int] = {}
    for n in nodes:
        by_type[n.get("type", "")] = by_type.get(n.get("type", ""), 0) + 1
        plat = n.get("platform", "")
        if plat:
            by_platform[plat] = by_platform.get(plat, 0) + 1
    return {
        "total_nodes": len(nodes),
        "total_edges": len(lineage.get("edges", [])),
        "by_type": by_type,
        "by_platform": by_platform,
    }


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _normalise(name: str) -> str:
    """Lower-case, strip underscores/spaces for comparison."""
    return name.lower().replace("_", "").replace(" ", "").replace("-", "")


def _dim_similarity(d1: Dict, d2: Dict) -> float:
    """Score 0-1 how similar two dimensions are."""
    score = 0.0
    # Name similarity (exact = 0.5, normalised match = 0.4)
    if d1.get("name", "") == d2.get("name", ""):
        score += 0.5
    elif _normalise(d1.get("name", "")) == _normalise(d2.get("name", "")):
        score += 0.4
    else:
        return 0.0  # Name must match at least loosely

    # Same table
    if d1.get("table") and _normalise(d1.get("table", "")) == _normalise(d2.get("table", "")):
        score += 0.3

    # Same column
    if d1.get("column_name") and _normalise(d1.get("column_name", "")) == _normalise(d2.get("column_name", "")):
        score += 0.2

    return min(score, 1.0)


def _measure_similarity(m1: Dict, m2: Dict) -> float:
    """Score 0-1 how similar two measures are."""
    score = 0.0
    if m1.get("name", "") == m2.get("name", ""):
        score += 0.5
    elif _normalise(m1.get("name", "")) == _normalise(m2.get("name", "")):
        score += 0.4
    else:
        return 0.0

    # Same aggregation
    if m1.get("aggregation") and m1.get("aggregation") == m2.get("aggregation"):
        score += 0.3

    # Same data type
    if m1.get("data_type") and m1.get("data_type") == m2.get("data_type"):
        score += 0.2

    return min(score, 1.0)
