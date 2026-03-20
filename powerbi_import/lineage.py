"""
Data lineage graph for MicroStrategy → Power BI migration.

Builds an in-memory directed acyclic graph (DAG) tracking how objects
flow from warehouse tables through the MSTR semantic layer into Power BI
tables, measures, and visuals.  Supports impact analysis ("what breaks
if column X changes?") and export to JSON-LD / OpenLineage format.
"""

import json
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Node types (layers) ─────────────────────────────────────────

LAYER_SOURCE = "source"          # Warehouse table / column
LAYER_MSTR_ATTRIBUTE = "mstr_attribute"
LAYER_MSTR_FACT = "mstr_fact"
LAYER_MSTR_METRIC = "mstr_metric"
LAYER_MSTR_REPORT = "mstr_report"
LAYER_MSTR_DOSSIER = "mstr_dossier"
LAYER_PBI_TABLE = "pbi_table"
LAYER_PBI_COLUMN = "pbi_column"
LAYER_PBI_MEASURE = "pbi_measure"
LAYER_PBI_VISUAL = "pbi_visual"
LAYER_PBI_PAGE = "pbi_page"

_ALL_LAYERS = [
    LAYER_SOURCE, LAYER_MSTR_ATTRIBUTE, LAYER_MSTR_FACT,
    LAYER_MSTR_METRIC, LAYER_MSTR_REPORT, LAYER_MSTR_DOSSIER,
    LAYER_PBI_TABLE, LAYER_PBI_COLUMN, LAYER_PBI_MEASURE,
    LAYER_PBI_VISUAL, LAYER_PBI_PAGE,
]


# ── Core data structures ────────────────────────────────────────

class LineageNode:
    """A node in the lineage DAG."""
    __slots__ = ("id", "name", "layer", "metadata")

    def __init__(self, node_id, name, layer, metadata=None):
        self.id = node_id
        self.name = name
        self.layer = layer
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "layer": self.layer,
            "metadata": self.metadata,
        }


class LineageEdge:
    """A directed edge from *source* to *target*."""
    __slots__ = ("source_id", "target_id", "relationship")

    def __init__(self, source_id, target_id, relationship="derives"):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship = relationship

    def to_dict(self):
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relationship": self.relationship,
        }


class LineageGraph:
    """In-memory directed graph for data lineage."""

    def __init__(self):
        self.nodes = {}          # id → LineageNode
        self.edges = []          # list of LineageEdge
        self._children = defaultdict(set)   # parent → {children}
        self._parents = defaultdict(set)    # child → {parents}

    # ── Mutation ─────────────────────────────────────────────────

    def add_node(self, node_id, name, layer, metadata=None):
        """Add a node (idempotent)."""
        if node_id not in self.nodes:
            self.nodes[node_id] = LineageNode(node_id, name, layer, metadata)
        return self.nodes[node_id]

    def add_edge(self, source_id, target_id, relationship="derives"):
        """Add a directed edge (idempotent)."""
        key = (source_id, target_id)
        if target_id not in self._children.get(source_id, set()):
            self.edges.append(LineageEdge(source_id, target_id, relationship))
            self._children[source_id].add(target_id)
            self._parents[target_id].add(source_id)

    # ── Queries ──────────────────────────────────────────────────

    def get_node(self, node_id):
        return self.nodes.get(node_id)

    def get_children(self, node_id):
        """Direct downstream dependents."""
        return [self.nodes[c] for c in self._children.get(node_id, set())
                if c in self.nodes]

    def get_parents(self, node_id):
        """Direct upstream sources."""
        return [self.nodes[p] for p in self._parents.get(node_id, set())
                if p in self.nodes]

    def get_downstream(self, node_id):
        """All transitive downstream nodes (BFS)."""
        visited = set()
        queue = list(self._children.get(node_id, set()))
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            queue.extend(self._children.get(nid, set()))
        return [self.nodes[n] for n in visited if n in self.nodes]

    def get_upstream(self, node_id):
        """All transitive upstream nodes (BFS)."""
        visited = set()
        queue = list(self._parents.get(node_id, set()))
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            queue.extend(self._parents.get(nid, set()))
        return [self.nodes[n] for n in visited if n in self.nodes]

    def detect_cycles(self):
        """Return list of node IDs involved in cycles (should be empty for a DAG)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self.nodes}
        cycle_nodes = []

        def _dfs(nid):
            color[nid] = GRAY
            for child_id in self._children.get(nid, set()):
                if child_id not in color:
                    continue
                if color[child_id] == GRAY:
                    cycle_nodes.append(child_id)
                elif color[child_id] == WHITE:
                    _dfs(child_id)
            color[nid] = BLACK

        for nid in list(self.nodes):
            if color.get(nid) == WHITE:
                _dfs(nid)
        return cycle_nodes

    def nodes_by_layer(self, layer):
        """Return all nodes of a given layer."""
        return [n for n in self.nodes.values() if n.layer == layer]

    @property
    def node_count(self):
        return len(self.nodes)

    @property
    def edge_count(self):
        return len(self.edges)

    # ── Impact analysis ──────────────────────────────────────────

    def impact_analysis(self, node_id):
        """Analyse impact of changing/removing *node_id*.

        Returns dict with affected objects grouped by layer.
        """
        downstream = self.get_downstream(node_id)
        result = defaultdict(list)
        for node in downstream:
            result[node.layer].append({
                "id": node.id,
                "name": node.name,
            })
        return dict(result)

    # ── Serialisation ────────────────────────────────────────────

    def to_dict(self):
        """Serialise entire graph to a plain dict."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent)

    def to_openlineage(self):
        """Export graph in OpenLineage-compatible JSON-LD format.

        Simplified mapping:
        - Source nodes → datasets
        - MSTR objects → transformations (jobs)
        - PBI objects → output datasets
        """
        datasets = []
        jobs = []
        runs = []

        for node in self.nodes.values():
            if node.layer == LAYER_SOURCE:
                datasets.append({
                    "@type": "Dataset",
                    "name": node.name,
                    "namespace": "microstrategy",
                    "facets": {"sourceType": {"type": "warehouse_table"}},
                })
            elif node.layer.startswith("mstr_"):
                jobs.append({
                    "@type": "Job",
                    "name": node.name,
                    "namespace": "microstrategy",
                    "facets": {"objectType": {"type": node.layer}},
                })
            elif node.layer.startswith("pbi_"):
                datasets.append({
                    "@type": "Dataset",
                    "name": node.name,
                    "namespace": "powerbi",
                    "facets": {"objectType": {"type": node.layer}},
                })

        return {
            "@context": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
            "datasets": datasets,
            "jobs": jobs,
            "runs": runs,
        }

    def save(self, path):
        """Write lineage graph to JSON file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Lineage graph saved to %s (%d nodes, %d edges)",
                     path, self.node_count, self.edge_count)


# ── Graph builder ────────────────────────────────────────────────

def build_lineage_graph(data):
    """Build a full lineage graph from intermediate JSON data.

    Args:
        data: dict with keys matching the 18 intermediate JSON files
              (datasources, attributes, facts, metrics, derived_metrics,
              reports, dossiers, hierarchies, relationships, etc.)

    Returns:
        LineageGraph instance
    """
    g = LineageGraph()

    datasources = data.get("datasources", [])
    attributes = data.get("attributes", [])
    facts = data.get("facts", [])
    metrics = data.get("metrics", [])
    derived_metrics = data.get("derived_metrics", [])
    reports = data.get("reports", [])
    dossiers = data.get("dossiers", [])

    # ── Layer 1: Source tables & columns ─────────────────────────
    _add_source_nodes(g, datasources)

    # ── Layer 2: MSTR Attributes ─────────────────────────────────
    _add_attribute_nodes(g, attributes, datasources)

    # ── Layer 3: MSTR Facts ──────────────────────────────────────
    _add_fact_nodes(g, facts, datasources)

    # ── Layer 4: MSTR Metrics ────────────────────────────────────
    _add_metric_nodes(g, metrics, facts, attributes)
    _add_metric_nodes(g, derived_metrics, facts, attributes, prefix="derived_")

    # ── Layer 5: MSTR Reports ────────────────────────────────────
    _add_report_nodes(g, reports, attributes, metrics, derived_metrics)

    # ── Layer 6: MSTR Dossiers ───────────────────────────────────
    _add_dossier_nodes(g, dossiers, attributes, metrics, derived_metrics)

    # ── Layer 7: PBI Tables & Columns ────────────────────────────
    _add_pbi_table_nodes(g, datasources, attributes, facts)

    # ── Layer 8: PBI Measures ────────────────────────────────────
    _add_pbi_measure_nodes(g, metrics, derived_metrics, datasources, facts)

    # ── Layer 9: PBI Visuals & Pages ─────────────────────────────
    _add_pbi_visual_nodes(g, reports, dossiers)

    cycles = g.detect_cycles()
    if cycles:
        logger.warning("Lineage graph contains %d cycle(s): %s", len(cycles), cycles)

    logger.info("Lineage graph built: %d nodes, %d edges", g.node_count, g.edge_count)
    return g


# ── Private builders ─────────────────────────────────────────────

def _add_source_nodes(g, datasources):
    """Add warehouse tables and their columns as source-layer nodes."""
    for ds in datasources:
        table_id = f"src:{ds['name']}"
        g.add_node(table_id, ds["name"], LAYER_SOURCE,
                   {"physical_table": ds.get("physical_table", ds["name"])})
        for col in ds.get("columns", []):
            col_id = f"src:{ds['name']}.{col['name']}"
            g.add_node(col_id, col["name"], LAYER_SOURCE,
                       {"table": ds["name"], "data_type": col.get("data_type", "")})
            g.add_edge(table_id, col_id, "contains")


def _add_attribute_nodes(g, attributes, datasources):
    """Add MSTR attributes and link to source columns."""
    table_names = {ds["name"] for ds in datasources}
    for attr in attributes:
        attr_id = f"mstr_attr:{attr['id']}"
        g.add_node(attr_id, attr["name"], LAYER_MSTR_ATTRIBUTE,
                   {"mstr_id": attr["id"]})
        for form in attr.get("forms", []):
            table = form.get("table_name") or form.get("table", "")
            col = form.get("column_name", "")
            if table and col:
                src_col_id = f"src:{table}.{col}"
                g.add_edge(src_col_id, attr_id, "maps_to")
            elif col:
                # Try to find column in any table
                for ds in datasources:
                    for c in ds.get("columns", []):
                        if c["name"] == col:
                            g.add_edge(f"src:{ds['name']}.{col}", attr_id, "maps_to")


def _add_fact_nodes(g, facts, datasources):
    """Add MSTR facts and link to source columns."""
    for fact in facts:
        fact_id = f"mstr_fact:{fact['id']}"
        g.add_node(fact_id, fact["name"], LAYER_MSTR_FACT,
                   {"mstr_id": fact["id"]})
        for expr in fact.get("expressions", []):
            table = expr.get("table", "")
            col = expr.get("column", "")
            if table and col:
                g.add_edge(f"src:{table}.{col}", fact_id, "maps_to")


def _add_metric_nodes(g, metrics, facts, attributes, prefix=""):
    """Add MSTR metrics and link to referenced facts/attributes."""
    fact_by_name = {f["name"].lower(): f for f in facts}
    attr_by_name = {a["name"].lower(): a for a in attributes}

    for metric in metrics:
        metric_id = f"mstr_metric:{prefix}{metric['id']}"
        g.add_node(metric_id, metric["name"], LAYER_MSTR_METRIC,
                   {"mstr_id": metric["id"], "type": metric.get("metric_type", "")})

        # Link to referenced facts via column_ref or dependencies
        col_ref = metric.get("column_ref", "")
        if col_ref:
            fact = fact_by_name.get(col_ref.lower())
            if fact:
                g.add_edge(f"mstr_fact:{fact['id']}", metric_id, "computes")

        # Link via explicit dependencies
        for dep in metric.get("dependencies", []):
            dep_name = dep.get("name", "").lower()
            dep_id = dep.get("id", "")
            if dep_id:
                # Could be another metric or attribute
                g.add_edge(f"mstr_metric:{dep_id}", metric_id, "computes")
                g.add_edge(f"mstr_metric:{prefix}{dep_id}", metric_id, "computes")
            elif dep_name:
                fact = fact_by_name.get(dep_name)
                if fact:
                    g.add_edge(f"mstr_fact:{fact['id']}", metric_id, "computes")
                attr = attr_by_name.get(dep_name)
                if attr:
                    g.add_edge(f"mstr_attr:{attr['id']}", metric_id, "references")


def _add_report_nodes(g, reports, attributes, metrics, derived_metrics):
    """Add MSTR reports and link to their attributes/metrics."""
    attr_by_name = {a["name"].lower(): a for a in attributes}
    all_metrics = {m["name"].lower(): m for m in metrics + derived_metrics}

    for report in reports:
        if report.get("error"):
            continue
        report_id = f"mstr_report:{report['id']}"
        g.add_node(report_id, report["name"], LAYER_MSTR_REPORT,
                   {"mstr_id": report["id"], "type": report.get("report_type", "")})

        # Grid rows/columns reference attributes
        grid = report.get("grid", {})
        for elem in grid.get("rows", []) + grid.get("columns", []):
            name = elem.get("name", "").lower()
            attr = attr_by_name.get(name)
            if attr:
                g.add_edge(f"mstr_attr:{attr['id']}", report_id, "used_in")

        # Metrics referenced
        for m in report.get("metrics", []):
            m_name = m.get("name", "").lower()
            met = all_metrics.get(m_name)
            if met:
                prefix = "derived_" if met.get("metric_type") == "derived" else ""
                g.add_edge(f"mstr_metric:{prefix}{met['id']}", report_id, "used_in")

        # Filters reference attributes
        for f in report.get("filters", []):
            attr_name = f.get("attribute", "").lower()
            attr = attr_by_name.get(attr_name)
            if attr:
                g.add_edge(f"mstr_attr:{attr['id']}", report_id, "filters")


def _add_dossier_nodes(g, dossiers, attributes, metrics, derived_metrics):
    """Add MSTR dossiers with their chapters/pages/visualizations."""
    attr_by_name = {a["name"].lower(): a for a in attributes}
    all_metrics = {m["name"].lower(): m for m in metrics + derived_metrics}

    for dossier in dossiers:
        if dossier.get("error"):
            continue
        doss_id = f"mstr_dossier:{dossier['id']}"
        g.add_node(doss_id, dossier["name"], LAYER_MSTR_DOSSIER,
                   {"mstr_id": dossier["id"]})

        for chapter in dossier.get("chapters", []):
            for page in chapter.get("pages", []):
                for viz in page.get("visualizations", []):
                    viz_data = viz.get("data", {})
                    # Attributes used in viz
                    for a in viz_data.get("attributes", []):
                        attr = attr_by_name.get(a.get("name", "").lower())
                        if attr:
                            g.add_edge(f"mstr_attr:{attr['id']}", doss_id, "used_in")
                    # Metrics used in viz
                    for m in viz_data.get("metrics", []):
                        met = all_metrics.get(m.get("name", "").lower())
                        if met:
                            prefix = "derived_" if met.get("metric_type") == "derived" else ""
                            g.add_edge(f"mstr_metric:{prefix}{met['id']}", doss_id, "used_in")


def _add_pbi_table_nodes(g, datasources, attributes, facts):
    """Add PBI table/column nodes and link from MSTR attributes/facts."""
    for ds in datasources:
        pbi_table_id = f"pbi_table:{ds['name']}"
        g.add_node(pbi_table_id, ds["name"], LAYER_PBI_TABLE)
        # Source table → PBI table
        g.add_edge(f"src:{ds['name']}", pbi_table_id, "migrated_to")

        for col in ds.get("columns", []):
            pbi_col_id = f"pbi_col:{ds['name']}.{col['name']}"
            g.add_node(pbi_col_id, col["name"], LAYER_PBI_COLUMN,
                       {"table": ds["name"]})
            g.add_edge(pbi_table_id, pbi_col_id, "contains")
            g.add_edge(f"src:{ds['name']}.{col['name']}", pbi_col_id, "migrated_to")

    # Link MSTR attributes → PBI columns
    for attr in attributes:
        for form in attr.get("forms", []):
            table = form.get("table_name") or form.get("table", "")
            col = form.get("column_name", "")
            if table and col:
                g.add_edge(f"mstr_attr:{attr['id']}",
                           f"pbi_col:{table}.{col}", "migrated_to")

    # Link MSTR facts → PBI columns
    for fact in facts:
        for expr in fact.get("expressions", []):
            table = expr.get("table", "")
            col = expr.get("column", "")
            if table and col:
                g.add_edge(f"mstr_fact:{fact['id']}",
                           f"pbi_col:{table}.{col}", "migrated_to")


def _add_pbi_measure_nodes(g, metrics, derived_metrics, datasources, facts):
    """Add PBI measure nodes and link from MSTR metrics."""
    # Simple heuristic: assign metric to first table with a matching fact
    fact_table = {}
    for f in facts:
        for expr in f.get("expressions", []):
            if expr.get("table"):
                fact_table[f["name"].lower()] = expr["table"]
                break

    default_table = datasources[0]["name"] if datasources else "Measures"

    for metric in metrics + derived_metrics:
        prefix = "derived_" if metric.get("metric_type") == "derived" else ""
        pbi_m_id = f"pbi_measure:{metric['name']}"
        table = fact_table.get(metric.get("column_ref", "").lower(), default_table)
        g.add_node(pbi_m_id, metric["name"], LAYER_PBI_MEASURE,
                   {"table": table})
        g.add_edge(f"mstr_metric:{prefix}{metric['id']}", pbi_m_id, "migrated_to")


def _add_pbi_visual_nodes(g, reports, dossiers):
    """Add PBI visual/page nodes and link from PBI tables/measures."""
    # Reports → one page each with visuals referencing measures/columns
    for report in reports:
        if report.get("error"):
            continue
        page_id = f"pbi_page:{report['id']}"
        g.add_node(page_id, report["name"], LAYER_PBI_PAGE)
        g.add_edge(f"mstr_report:{report['id']}", page_id, "migrated_to")

        # Link metrics used
        for m in report.get("metrics", []):
            g.add_edge(f"pbi_measure:{m.get('name', '')}", page_id, "displayed_on")

        # Grid elements → columns
        grid = report.get("grid", {})
        for elem in grid.get("rows", []) + grid.get("columns", []):
            if elem.get("type") == "attribute":
                # We don't know exact table here; link via name
                g.add_edge(f"pbi_measure:{elem.get('name', '')}", page_id, "displayed_on")

    # Dossiers → pages → visuals
    for dossier in dossiers:
        if dossier.get("error"):
            continue
        for chapter in dossier.get("chapters", []):
            for page in chapter.get("pages", []):
                page_id = f"pbi_page:{page.get('key', page.get('name', ''))}"
                page_name = page.get("name", "Page")
                g.add_node(page_id, page_name, LAYER_PBI_PAGE)
                g.add_edge(f"mstr_dossier:{dossier['id']}", page_id, "migrated_to")

                for viz in page.get("visualizations", []):
                    viz_id = f"pbi_visual:{viz.get('key', viz.get('name', ''))}"
                    g.add_node(viz_id, viz.get("name", ""), LAYER_PBI_VISUAL,
                               {"type": viz.get("pbi_visual_type", "")})
                    g.add_edge(page_id, viz_id, "contains")

                    viz_data = viz.get("data", {})
                    for m in viz_data.get("metrics", []):
                        g.add_edge(f"pbi_measure:{m.get('name', '')}",
                                   viz_id, "displayed_on")
                    for a in viz_data.get("attributes", []):
                        # Attribute name → PBI column (best effort)
                        name = a.get("name", "")
                        if name:
                            g.add_edge(f"pbi_measure:{name}", viz_id, "displayed_on")
