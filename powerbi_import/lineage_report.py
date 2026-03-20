"""
Interactive HTML lineage report.

Generates a self-contained HTML page with a D3.js force-directed graph
showing data flow from warehouse tables through MSTR objects to Power BI
artefacts.  Filterable by layer.
"""

import html
import json
import logging
import os

logger = logging.getLogger(__name__)

# Colour palette per layer
_LAYER_COLORS = {
    "source": "#6c757d",
    "mstr_attribute": "#0d6efd",
    "mstr_fact": "#198754",
    "mstr_metric": "#ffc107",
    "mstr_report": "#dc3545",
    "mstr_dossier": "#e83e8c",
    "pbi_table": "#0dcaf0",
    "pbi_column": "#20c997",
    "pbi_measure": "#fd7e14",
    "pbi_visual": "#6610f2",
    "pbi_page": "#d63384",
}

_LAYER_LABELS = {
    "source": "Warehouse Table / Column",
    "mstr_attribute": "MSTR Attribute",
    "mstr_fact": "MSTR Fact",
    "mstr_metric": "MSTR Metric",
    "mstr_report": "MSTR Report",
    "mstr_dossier": "MSTR Dossier",
    "pbi_table": "PBI Table",
    "pbi_column": "PBI Column",
    "pbi_measure": "PBI Measure",
    "pbi_visual": "PBI Visual",
    "pbi_page": "PBI Page",
}


def generate_lineage_html(graph, output_path, *, title="Data Lineage"):
    """Generate an interactive HTML lineage visualisation.

    Args:
        graph: LineageGraph instance
        output_path: Path for the output .html file
        title: Page title

    Returns:
        str: absolute path of the written file
    """
    nodes_json = json.dumps([n.to_dict() for n in graph.nodes.values()])
    edges_json = json.dumps([e.to_dict() for e in graph.edges])
    colors_json = json.dumps(_LAYER_COLORS)
    labels_json = json.dumps(_LAYER_LABELS)
    safe_title = html.escape(title)

    page = _HTML_TEMPLATE.replace("{{TITLE}}", safe_title)
    page = page.replace("{{NODES_JSON}}", nodes_json)
    page = page.replace("{{EDGES_JSON}}", edges_json)
    page = page.replace("{{COLORS_JSON}}", colors_json)
    page = page.replace("{{LABELS_JSON}}", labels_json)
    page = page.replace("{{NODE_COUNT}}", str(graph.node_count))
    page = page.replace("{{EDGE_COUNT}}", str(graph.edge_count))

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)

    logger.info("Lineage HTML report written to %s", output_path)
    return os.path.abspath(output_path)


def generate_impact_html(graph, node_id, output_path):
    """Generate an impact-analysis HTML for a single node.

    Shows only the subgraph of upstream + downstream nodes.
    """
    upstream = graph.get_upstream(node_id)
    downstream = graph.get_downstream(node_id)
    center_node = graph.get_node(node_id)

    if not center_node:
        logger.warning("Node %s not found in graph", node_id)
        return None

    related_ids = {n.id for n in upstream + downstream}
    related_ids.add(node_id)

    sub_nodes = [n.to_dict() for n in graph.nodes.values() if n.id in related_ids]
    sub_edges = [e.to_dict() for e in graph.edges
                 if e.source_id in related_ids and e.target_id in related_ids]

    # Mark center node
    for n in sub_nodes:
        n["is_center"] = (n["id"] == node_id)

    title = f"Impact Analysis — {center_node.name}"
    nodes_json = json.dumps(sub_nodes)
    edges_json = json.dumps(sub_edges)
    colors_json = json.dumps(_LAYER_COLORS)
    labels_json = json.dumps(_LAYER_LABELS)

    page = _HTML_TEMPLATE.replace("{{TITLE}}", html.escape(title))
    page = page.replace("{{NODES_JSON}}", nodes_json)
    page = page.replace("{{EDGES_JSON}}", edges_json)
    page = page.replace("{{COLORS_JSON}}", colors_json)
    page = page.replace("{{LABELS_JSON}}", labels_json)
    page = page.replace("{{NODE_COUNT}}", str(len(sub_nodes)))
    page = page.replace("{{EDGE_COUNT}}", str(len(sub_edges)))

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(page)

    logger.info("Impact HTML report written to %s", output_path)
    return os.path.abspath(output_path)


# ── HTML template ────────────────────────────────────────────────

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#1e1e1e;color:#d4d4d4}
#header{background:#252526;padding:12px 24px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #333}
#header h1{font-size:18px;font-weight:600;color:#fff}
.stat{font-size:13px;color:#888}
#controls{background:#252526;padding:8px 24px;border-bottom:1px solid #333;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.layer-btn{padding:4px 10px;border:1px solid #555;border-radius:4px;cursor:pointer;font-size:12px;background:#333;color:#ccc;transition:all 0.2s}
.layer-btn.active{border-color:currentColor;background:currentColor;color:#fff}
.layer-btn:hover{opacity:0.85}
#graph{width:100%;height:calc(100vh - 100px)}
svg{width:100%;height:100%}
.link{stroke:#555;stroke-opacity:0.6;fill:none}
.link:hover{stroke-opacity:1;stroke-width:2px}
.node circle{stroke:#fff;stroke-width:1.5px;cursor:pointer}
.node text{font-size:10px;fill:#ccc;pointer-events:none}
.node:hover circle{stroke-width:3px}
#tooltip{position:absolute;background:#333;border:1px solid #555;padding:8px 12px;border-radius:6px;font-size:12px;pointer-events:none;display:none;z-index:100;max-width:300px}
#tooltip .tt-name{font-weight:600;color:#fff;margin-bottom:4px}
#tooltip .tt-layer{color:#888;font-size:11px}
</style>
</head>
<body>
<div id="header">
  <h1>{{TITLE}}</h1>
  <span class="stat">{{NODE_COUNT}} nodes &middot; {{EDGE_COUNT}} edges</span>
</div>
<div id="controls"></div>
<div id="graph"></div>
<div id="tooltip"><div class="tt-name"></div><div class="tt-layer"></div></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
(function(){
  const nodes = {{NODES_JSON}};
  const edges = {{EDGES_JSON}};
  const COLORS = {{COLORS_JSON}};
  const LABELS = {{LABELS_JSON}};

  // Layer filter state
  const activeLayers = new Set(Object.keys(COLORS));

  // Build controls
  const controls = document.getElementById('controls');
  Object.keys(LABELS).forEach(layer => {
    const btn = document.createElement('span');
    btn.className = 'layer-btn active';
    btn.style.color = COLORS[layer] || '#888';
    btn.textContent = LABELS[layer] || layer;
    btn.dataset.layer = layer;
    btn.addEventListener('click', () => {
      if (activeLayers.has(layer)) { activeLayers.delete(layer); btn.classList.remove('active'); }
      else { activeLayers.add(layer); btn.classList.add('active'); }
      updateVisibility();
    });
    controls.appendChild(btn);
  });

  // D3 force simulation
  const container = document.getElementById('graph');
  const width = container.clientWidth;
  const height = container.clientHeight;

  const svg = d3.select('#graph').append('svg')
    .attr('viewBox', [0, 0, width, height]);

  const g = svg.append('g');

  // Zoom
  svg.call(d3.zoom().scaleExtent([0.1, 8]).on('zoom', (e) => g.attr('transform', e.transform)));

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(80).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide(20));

  // Draw edges
  const link = g.append('g').selectAll('line')
    .data(edges).join('line').attr('class', 'link')
    .attr('marker-end', 'url(#arrow)');

  // Arrow marker
  svg.append('defs').append('marker').attr('id','arrow')
    .attr('viewBox','0 -5 10 10').attr('refX',18).attr('refY',0)
    .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
    .append('path').attr('d','M0,-5L10,0L0,5').attr('fill','#555');

  // Draw nodes
  const node = g.append('g').selectAll('g')
    .data(nodes).join('g').attr('class','node')
    .call(d3.drag()
      .on('start', (e,d) => { if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on('drag', (e,d) => { d.fx=e.x; d.fy=e.y; })
      .on('end', (e,d) => { if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; })
    );

  node.append('circle').attr('r', d => d.is_center ? 12 : 7)
    .attr('fill', d => COLORS[d.layer] || '#888');

  node.append('text').attr('dx', 12).attr('dy', 4).text(d => d.name);

  // Tooltip
  const tooltip = document.getElementById('tooltip');
  node.on('mouseover', (e, d) => {
    tooltip.style.display = 'block';
    tooltip.querySelector('.tt-name').textContent = d.name;
    tooltip.querySelector('.tt-layer').textContent = (LABELS[d.layer] || d.layer) + (d.metadata && d.metadata.table ? ' — ' + d.metadata.table : '');
  }).on('mousemove', (e) => {
    tooltip.style.left = (e.pageX + 12) + 'px';
    tooltip.style.top = (e.pageY - 20) + 'px';
  }).on('mouseout', () => { tooltip.style.display = 'none'; });

  simulation.on('tick', () => {
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function updateVisibility(){
    node.style('display', d => activeLayers.has(d.layer) ? null : 'none');
    link.style('display', d => {
      const sLayer = typeof d.source === 'object' ? d.source.layer : nodes.find(n=>n.id===d.source)?.layer;
      const tLayer = typeof d.target === 'object' ? d.target.layer : nodes.find(n=>n.id===d.target)?.layer;
      return activeLayers.has(sLayer) && activeLayers.has(tLayer) ? null : 'none';
    });
  }
})();
</script>
</body>
</html>"""
