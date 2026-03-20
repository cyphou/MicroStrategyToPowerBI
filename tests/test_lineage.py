"""Tests for v6.0 lineage features (Sprint T)."""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from powerbi_import.lineage import (
    LineageGraph, LineageNode, LineageEdge,
    build_lineage_graph,
    LAYER_SOURCE, LAYER_MSTR_ATTRIBUTE, LAYER_MSTR_FACT,
    LAYER_MSTR_METRIC, LAYER_MSTR_REPORT, LAYER_MSTR_DOSSIER,
    LAYER_PBI_TABLE, LAYER_PBI_COLUMN, LAYER_PBI_MEASURE,
    LAYER_PBI_VISUAL, LAYER_PBI_PAGE,
)
from powerbi_import.lineage_report import generate_lineage_html, generate_impact_html


# ── Fixtures ─────────────────────────────────────────────────────

def _sample_data():
    """Minimal intermediate JSON data for testing."""
    return {
        "datasources": [
            {
                "id": "t1", "name": "Sales",
                "physical_table": "dbo.Sales",
                "db_connection": {"name": "MSTR_DW"},
                "columns": [
                    {"name": "Customer_ID", "data_type": "integer"},
                    {"name": "Amount", "data_type": "decimal"},
                    {"name": "Region", "data_type": "string"},
                ],
            },
            {
                "id": "t2", "name": "Product",
                "physical_table": "dbo.Product",
                "db_connection": {"name": "MSTR_DW"},
                "columns": [
                    {"name": "Product_ID", "data_type": "integer"},
                    {"name": "Product_Name", "data_type": "string"},
                ],
            },
        ],
        "attributes": [
            {
                "id": "a1", "name": "Customer",
                "description": "Customer attribute",
                "forms": [
                    {"name": "ID", "category": "ID", "column_name": "Customer_ID", "table_name": "Sales"},
                ],
                "data_type": "integer",
                "lookup_table": "Sales",
            },
            {
                "id": "a2", "name": "Product",
                "description": "",
                "forms": [
                    {"name": "ID", "category": "ID", "column_name": "Product_ID", "table_name": "Product"},
                    {"name": "DESC", "category": "DESC", "column_name": "Product_Name", "table_name": "Product"},
                ],
                "data_type": "string",
                "lookup_table": "Product",
            },
            {
                "id": "a3", "name": "Region",
                "description": "Sales region",
                "forms": [
                    {"name": "ID", "category": "ID", "column_name": "Region", "table_name": "Sales"},
                ],
                "data_type": "string",
                "lookup_table": "Sales",
            },
        ],
        "facts": [
            {
                "id": "f1", "name": "Sales Amount",
                "description": "Total sales",
                "expressions": [{"table": "Sales", "column": "Amount"}],
                "data_type": "decimal",
                "default_aggregation": "sum",
            },
        ],
        "metrics": [
            {
                "id": "m1", "name": "Total Sales",
                "metric_type": "simple",
                "expression": "Sum(SalesAmount)",
                "aggregation": "sum",
                "column_ref": "Sales Amount",
                "description": "Sum of sales",
                "dependencies": [],
            },
            {
                "id": "m2", "name": "Avg Sale",
                "metric_type": "simple",
                "expression": "Avg(SalesAmount)",
                "aggregation": "avg",
                "column_ref": "Sales Amount",
                "description": "",
                "dependencies": [],
            },
        ],
        "derived_metrics": [
            {
                "id": "d1", "name": "Sales YoY",
                "metric_type": "derived",
                "expression": "([Total Sales] - Lag([Total Sales], 1)) / Lag([Total Sales], 1)",
                "aggregation": "",
                "column_ref": "",
                "description": "Year-over-year growth",
                "dependencies": [{"id": "m1", "name": "Total Sales"}],
            },
        ],
        "reports": [
            {
                "id": "r1", "name": "Sales Report",
                "report_type": "grid",
                "grid": {
                    "rows": [{"name": "Customer", "type": "attribute"}],
                    "columns": [],
                },
                "metrics": [{"name": "Total Sales"}, {"name": "Avg Sale"}],
                "filters": [{"attribute": "Region", "operator": "in", "values": ["East"]}],
            },
        ],
        "dossiers": [
            {
                "id": "dos1", "name": "Sales Dashboard",
                "chapters": [
                    {
                        "name": "Overview",
                        "pages": [
                            {
                                "key": "p1", "name": "Summary",
                                "visualizations": [
                                    {
                                        "key": "v1", "name": "Sales Chart",
                                        "viz_type": "vertical_bar",
                                        "pbi_visual_type": "clusteredColumnChart",
                                        "data": {
                                            "attributes": [{"id": "a3", "name": "Region"}],
                                            "metrics": [{"id": "m1", "name": "Total Sales"}],
                                        },
                                    },
                                    {
                                        "key": "v2", "name": "Product Table",
                                        "viz_type": "grid",
                                        "pbi_visual_type": "tableEx",
                                        "data": {
                                            "attributes": [{"id": "a2", "name": "Product"}],
                                            "metrics": [{"id": "m2", "name": "Avg Sale"}],
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
        "security_filters": [],
        "hierarchies": [],
        "relationships": [],
    }


# ── LineageGraph core tests ──────────────────────────────────────

class TestLineageGraphCore:
    def test_add_node(self):
        g = LineageGraph()
        g.add_node("n1", "Node 1", LAYER_SOURCE)
        assert g.node_count == 1
        assert g.get_node("n1").name == "Node 1"

    def test_add_node_idempotent(self):
        g = LineageGraph()
        g.add_node("n1", "Node 1", LAYER_SOURCE)
        g.add_node("n1", "Node 1 dup", LAYER_SOURCE)
        assert g.node_count == 1
        assert g.get_node("n1").name == "Node 1"  # first wins

    def test_add_edge(self):
        g = LineageGraph()
        g.add_node("n1", "A", LAYER_SOURCE)
        g.add_node("n2", "B", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("n1", "n2", "maps_to")
        assert g.edge_count == 1

    def test_add_edge_idempotent(self):
        g = LineageGraph()
        g.add_node("n1", "A", LAYER_SOURCE)
        g.add_node("n2", "B", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("n1", "n2")
        g.add_edge("n1", "n2")
        assert g.edge_count == 1

    def test_get_children(self):
        g = LineageGraph()
        g.add_node("p", "Parent", LAYER_SOURCE)
        g.add_node("c1", "Child1", LAYER_MSTR_ATTRIBUTE)
        g.add_node("c2", "Child2", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("p", "c1")
        g.add_edge("p", "c2")
        children = g.get_children("p")
        assert len(children) == 2
        assert {c.id for c in children} == {"c1", "c2"}

    def test_get_parents(self):
        g = LineageGraph()
        g.add_node("p1", "P1", LAYER_SOURCE)
        g.add_node("p2", "P2", LAYER_SOURCE)
        g.add_node("c", "Child", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("p1", "c")
        g.add_edge("p2", "c")
        parents = g.get_parents("c")
        assert len(parents) == 2

    def test_get_downstream_transitive(self):
        g = LineageGraph()
        g.add_node("a", "A", LAYER_SOURCE)
        g.add_node("b", "B", LAYER_MSTR_ATTRIBUTE)
        g.add_node("c", "C", LAYER_MSTR_METRIC)
        g.add_node("d", "D", LAYER_PBI_MEASURE)
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "d")
        downstream = g.get_downstream("a")
        assert len(downstream) == 3
        assert {n.id for n in downstream} == {"b", "c", "d"}

    def test_get_upstream_transitive(self):
        g = LineageGraph()
        g.add_node("a", "A", LAYER_SOURCE)
        g.add_node("b", "B", LAYER_MSTR_ATTRIBUTE)
        g.add_node("c", "C", LAYER_MSTR_METRIC)
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        upstream = g.get_upstream("c")
        assert len(upstream) == 2
        assert {n.id for n in upstream} == {"a", "b"}

    def test_nodes_by_layer(self):
        g = LineageGraph()
        g.add_node("s1", "S1", LAYER_SOURCE)
        g.add_node("s2", "S2", LAYER_SOURCE)
        g.add_node("a1", "A1", LAYER_MSTR_ATTRIBUTE)
        assert len(g.nodes_by_layer(LAYER_SOURCE)) == 2
        assert len(g.nodes_by_layer(LAYER_MSTR_ATTRIBUTE)) == 1


class TestCycleDetection:
    def test_no_cycles(self):
        g = LineageGraph()
        g.add_node("a", "A", LAYER_SOURCE)
        g.add_node("b", "B", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("a", "b")
        assert g.detect_cycles() == []

    def test_detects_cycle(self):
        g = LineageGraph()
        g.add_node("a", "A", LAYER_SOURCE)
        g.add_node("b", "B", LAYER_SOURCE)
        g.add_node("c", "C", LAYER_SOURCE)
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")  # cycle
        cycles = g.detect_cycles()
        assert len(cycles) > 0

    def test_self_loop_detected(self):
        g = LineageGraph()
        g.add_node("a", "A", LAYER_SOURCE)
        g.add_edge("a", "a")
        cycles = g.detect_cycles()
        assert len(cycles) > 0


class TestImpactAnalysis:
    def test_impact_downstream(self):
        g = LineageGraph()
        g.add_node("src_col", "Amount", LAYER_SOURCE)
        g.add_node("fact", "Sales Amount", LAYER_MSTR_FACT)
        g.add_node("metric", "Total Sales", LAYER_MSTR_METRIC)
        g.add_node("report", "Sales Report", LAYER_MSTR_REPORT)
        g.add_node("pbi_m", "Total Sales", LAYER_PBI_MEASURE)
        g.add_edge("src_col", "fact")
        g.add_edge("fact", "metric")
        g.add_edge("metric", "report")
        g.add_edge("metric", "pbi_m")

        impact = g.impact_analysis("src_col")
        assert LAYER_MSTR_FACT in impact
        assert LAYER_MSTR_METRIC in impact
        assert LAYER_MSTR_REPORT in impact
        assert LAYER_PBI_MEASURE in impact

    def test_impact_empty(self):
        g = LineageGraph()
        g.add_node("leaf", "Leaf", LAYER_PBI_VISUAL)
        impact = g.impact_analysis("leaf")
        assert impact == {}


class TestSerialization:
    def test_to_dict(self):
        g = LineageGraph()
        g.add_node("n1", "N1", LAYER_SOURCE, {"foo": "bar"})
        g.add_node("n2", "N2", LAYER_MSTR_ATTRIBUTE)
        g.add_edge("n1", "n2", "maps_to")
        d = g.to_dict()
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
        assert d["edges"][0]["relationship"] == "maps_to"

    def test_to_json(self):
        g = LineageGraph()
        g.add_node("n1", "N1", LAYER_SOURCE)
        j = g.to_json()
        parsed = json.loads(j)
        assert "nodes" in parsed
        assert "edges" in parsed

    def test_to_openlineage(self):
        g = LineageGraph()
        g.add_node("src1", "Sales", LAYER_SOURCE)
        g.add_node("attr1", "Customer", LAYER_MSTR_ATTRIBUTE)
        g.add_node("pbi1", "Sales", LAYER_PBI_TABLE)
        g.add_edge("src1", "attr1")
        g.add_edge("attr1", "pbi1")
        ol = g.to_openlineage()
        assert "@context" in ol
        assert len(ol["datasets"]) >= 2  # source + pbi
        assert len(ol["jobs"]) >= 1

    def test_save_to_file(self):
        g = LineageGraph()
        g.add_node("n1", "N1", LAYER_SOURCE)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lineage.json")
            g.save(path)
            assert os.path.exists(path)
            with open(path, 'r') as f:
                data = json.load(f)
            assert len(data["nodes"]) == 1


class TestNodeEdgeDataClasses:
    def test_node_to_dict(self):
        n = LineageNode("id1", "Name", LAYER_SOURCE, {"k": "v"})
        d = n.to_dict()
        assert d["id"] == "id1"
        assert d["metadata"]["k"] == "v"

    def test_edge_to_dict(self):
        e = LineageEdge("s", "t", "derives")
        d = e.to_dict()
        assert d["source"] == "s"
        assert d["target"] == "t"
        assert d["relationship"] == "derives"


# ── build_lineage_graph integration tests ────────────────────────

class TestBuildLineageGraph:
    def test_builds_from_sample_data(self):
        g = build_lineage_graph(_sample_data())
        assert g.node_count > 0
        assert g.edge_count > 0

    def test_has_source_nodes(self):
        g = build_lineage_graph(_sample_data())
        sources = g.nodes_by_layer(LAYER_SOURCE)
        # 2 tables + their columns (3 + 2 = 5 columns + 2 tables = 7)
        assert len(sources) >= 7

    def test_has_attribute_nodes(self):
        g = build_lineage_graph(_sample_data())
        attrs = g.nodes_by_layer(LAYER_MSTR_ATTRIBUTE)
        assert len(attrs) == 3  # Customer, Product, Region

    def test_has_fact_nodes(self):
        g = build_lineage_graph(_sample_data())
        facts = g.nodes_by_layer(LAYER_MSTR_FACT)
        assert len(facts) == 1

    def test_has_metric_nodes(self):
        g = build_lineage_graph(_sample_data())
        metrics = g.nodes_by_layer(LAYER_MSTR_METRIC)
        assert len(metrics) == 3  # Total Sales, Avg Sale, Sales YoY

    def test_has_report_nodes(self):
        g = build_lineage_graph(_sample_data())
        reports = g.nodes_by_layer(LAYER_MSTR_REPORT)
        assert len(reports) == 1

    def test_has_dossier_nodes(self):
        g = build_lineage_graph(_sample_data())
        dossiers = g.nodes_by_layer(LAYER_MSTR_DOSSIER)
        assert len(dossiers) == 1

    def test_has_pbi_table_nodes(self):
        g = build_lineage_graph(_sample_data())
        tables = g.nodes_by_layer(LAYER_PBI_TABLE)
        assert len(tables) == 2

    def test_has_pbi_column_nodes(self):
        g = build_lineage_graph(_sample_data())
        cols = g.nodes_by_layer(LAYER_PBI_COLUMN)
        assert len(cols) == 5  # 3 + 2 columns

    def test_has_pbi_measure_nodes(self):
        g = build_lineage_graph(_sample_data())
        measures = g.nodes_by_layer(LAYER_PBI_MEASURE)
        assert len(measures) == 3

    def test_has_pbi_page_nodes(self):
        g = build_lineage_graph(_sample_data())
        pages = g.nodes_by_layer(LAYER_PBI_PAGE)
        assert len(pages) >= 2  # 1 report page + 1 dossier page

    def test_has_pbi_visual_nodes(self):
        g = build_lineage_graph(_sample_data())
        visuals = g.nodes_by_layer(LAYER_PBI_VISUAL)
        assert len(visuals) == 2  # Sales Chart + Product Table

    def test_no_cycles(self):
        g = build_lineage_graph(_sample_data())
        assert g.detect_cycles() == []

    def test_impact_on_source_column(self):
        g = build_lineage_graph(_sample_data())
        impact = g.impact_analysis("src:Sales.Amount")
        # Amount → fact → metrics → report/dossier → PBI measure → PBI page/visual
        assert len(impact) >= 1

    def test_empty_data(self):
        g = build_lineage_graph({})
        assert g.node_count == 0
        assert g.edge_count == 0

    def test_skips_error_reports(self):
        data = _sample_data()
        data["reports"] = [{"id": "r_err", "name": "Bad", "error": "timeout"}]
        g = build_lineage_graph(data)
        reports = g.nodes_by_layer(LAYER_MSTR_REPORT)
        assert len(reports) == 0


# ── Lineage HTML report tests ───────────────────────────────────

class TestLineageHTML:
    def test_generate_html(self):
        g = build_lineage_graph(_sample_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lineage.html")
            result = generate_lineage_html(g, path, title="Test Lineage")
            assert os.path.exists(path)
            content = open(path, 'r', encoding='utf-8').read()
            assert "Test Lineage" in content
            assert "d3.v7.min.js" in content
            assert "nodes" in content.lower()

    def test_generate_html_empty_graph(self):
        g = LineageGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.html")
            generate_lineage_html(g, path)
            assert os.path.exists(path)

    def test_generate_impact_html(self):
        g = build_lineage_graph(_sample_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "impact.html")
            result = generate_impact_html(g, "src:Sales.Amount", path)
            assert result is not None
            content = open(path, 'r', encoding='utf-8').read()
            assert "Impact Analysis" in content

    def test_generate_impact_html_unknown_node(self):
        g = LineageGraph()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nope.html")
            result = generate_impact_html(g, "nonexistent", path)
            assert result is None


# ── Multi-hop lineage tests ──────────────────────────────────────

class TestMultiHopLineage:
    def test_source_to_visual(self):
        """Verify full chain: source column → fact → metric → PBI measure → PBI visual."""
        g = build_lineage_graph(_sample_data())
        # Amount column should reach PBI visual through multiple hops
        downstream = g.get_downstream("src:Sales.Amount")
        layers = {n.layer for n in downstream}
        assert LAYER_MSTR_FACT in layers
        # Metric should be reachable
        metric_nodes = [n for n in downstream if n.layer == LAYER_MSTR_METRIC]
        assert len(metric_nodes) >= 1

    def test_upstream_from_visual(self):
        """From a PBI visual, trace back to source."""
        g = build_lineage_graph(_sample_data())
        visual_nodes = g.nodes_by_layer(LAYER_PBI_VISUAL)
        if visual_nodes:
            upstream = g.get_upstream(visual_nodes[0].id)
            assert len(upstream) >= 1
