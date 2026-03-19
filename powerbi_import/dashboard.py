"""
Web dashboard for migration progress and fidelity visualization.

Generates a self-contained, interactive HTML dashboard from migration
report data. Features:
  - Overall progress / fidelity score gauge
  - Fidelity heatmap by object type
  - Object dependency graph (Mermaid)
  - Detailed object table with search/filter
  - Timeline of migration runs (incremental mode)
"""

import json
import os
import logging
from html import escape as html_escape

logger = logging.getLogger(__name__)


def generate_dashboard(report_data, output_dir, state_data=None):
    """Generate an interactive HTML dashboard.

    Args:
        report_data: dict from migration_report.generate_migration_report()
        output_dir: directory to write dashboard.html
        state_data: optional dict from MigrationState.to_dict() for incremental timeline

    Returns:
        str — path to the generated dashboard file
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "dashboard.html")

    summary = report_data.get("summary", {})
    objects = report_data.get("objects", [])

    html = _build_html(summary, objects, state_data)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written to %s", path)
    return path


def _build_html(summary, objects, state_data):
    """Assemble the full HTML dashboard."""
    fidelity_score = summary.get("fidelity_score", 0)
    total_objects = summary.get("total_objects", 0)
    fc = summary.get("fidelity_counts", {})
    tc = summary.get("type_counts", {})
    gen = summary.get("generation", {})

    # Heatmap data: type → fidelity distribution
    heatmap = _build_heatmap(objects)
    heatmap_json = json.dumps(heatmap, ensure_ascii=False)

    # Object rows
    obj_rows = _build_object_rows(objects)

    # Dependency graph (Mermaid)
    mermaid = _build_dependency_mermaid(objects)

    # Timeline
    timeline_html = _build_timeline(state_data) if state_data else ""

    score_pct = round(fidelity_score * 100)
    score_color = "#22c55e" if score_pct >= 80 else "#f59e0b" if score_pct >= 50 else "#ef4444"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Migration Dashboard — {html_escape(summary.get('report_name', 'Migration'))}</title>
<style>
:root {{ --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 24px; }}
h1 {{ font-size: 1.5rem; margin-bottom: 8px; }}
h2 {{ font-size: 1.15rem; margin-bottom: 12px; color: var(--accent); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: var(--card); border-radius: 12px; padding: 20px; }}
.gauge {{ text-align: center; }}
.gauge-circle {{ width: 120px; height: 120px; border-radius: 50%;
  background: conic-gradient({score_color} {score_pct}%, #334155 0%);
  display: flex; align-items: center; justify-content: center; margin: 0 auto 12px; }}
.gauge-inner {{ width: 90px; height: 90px; border-radius: 50%; background: var(--card);
  display: flex; align-items: center; justify-content: center; font-size: 1.8rem; font-weight: 700; }}
.stat {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #334155; }}
.stat:last-child {{ border: none; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
.badge-full {{ background: #166534; color: #bbf7d0; }}
.badge-approx {{ background: #854d0e; color: #fef08a; }}
.badge-manual {{ background: #9a3412; color: #fed7aa; }}
.badge-unsup {{ background: #7f1d1d; color: #fecaca; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; }}
th {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
input[type="text"] {{ width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155;
  border-radius: 6px; color: var(--text); margin-bottom: 12px; font-size: 0.9rem; }}
.heatmap {{ display: grid; grid-template-columns: 120px repeat(4, 1fr); gap: 2px; font-size: 0.8rem; }}
.heatmap-cell {{ padding: 6px; text-align: center; border-radius: 4px; }}
.heatmap-header {{ color: var(--muted); font-weight: 600; }}
.mermaid {{ background: #1e293b; padding: 16px; border-radius: 8px; overflow-x: auto; }}
.timeline {{ border-left: 2px solid var(--accent); padding-left: 16px; margin-top: 12px; }}
.timeline-item {{ margin-bottom: 12px; position: relative; }}
.timeline-item::before {{ content: ''; width: 10px; height: 10px; background: var(--accent);
  border-radius: 50%; position: absolute; left: -21px; top: 4px; }}
.timeline-date {{ font-size: 0.75rem; color: var(--muted); }}
</style>
</head>
<body>
<h1>MicroStrategy → Power BI Migration Dashboard</h1>
<p style="color:var(--muted);margin-bottom:24px">{html_escape(summary.get('report_name', ''))}</p>

<div class="grid">
  <!-- Fidelity Gauge -->
  <div class="card gauge">
    <h2>Fidelity Score</h2>
    <div class="gauge-circle"><div class="gauge-inner">{score_pct}%</div></div>
    <div class="stat"><span>Fully migrated</span><span>{fc.get('fully_migrated', 0)}</span></div>
    <div class="stat"><span>Approximated</span><span>{fc.get('approximated', 0)}</span></div>
    <div class="stat"><span>Manual review</span><span>{fc.get('manual_review', 0)}</span></div>
    <div class="stat"><span>Unsupported</span><span>{fc.get('unsupported', 0)}</span></div>
  </div>

  <!-- Generation Stats -->
  <div class="card">
    <h2>Generation Summary</h2>
    <div class="stat"><span>Total objects</span><span>{total_objects}</span></div>
    <div class="stat"><span>TMDL tables</span><span>{gen.get('tables', 0)}</span></div>
    <div class="stat"><span>Columns</span><span>{gen.get('columns', 0)}</span></div>
    <div class="stat"><span>DAX measures</span><span>{gen.get('measures', 0)}</span></div>
    <div class="stat"><span>Relationships</span><span>{gen.get('relationships', 0)}</span></div>
    <div class="stat"><span>Pages</span><span>{gen.get('pages', 0)}</span></div>
    <div class="stat"><span>Visuals</span><span>{gen.get('visuals', 0)}</span></div>
  </div>

  <!-- Type Breakdown -->
  <div class="card">
    <h2>Objects by Type</h2>
    {''.join(f'<div class="stat"><span>{html_escape(t)}</span><span>{c}</span></div>' for t, c in sorted(tc.items()))}
  </div>
</div>

<!-- Heatmap -->
<div class="card" style="margin-bottom:24px">
  <h2>Fidelity Heatmap</h2>
  <div class="heatmap">
    <div class="heatmap-cell heatmap-header">Type</div>
    <div class="heatmap-cell heatmap-header">Full</div>
    <div class="heatmap-cell heatmap-header">Approx</div>
    <div class="heatmap-cell heatmap-header">Manual</div>
    <div class="heatmap-cell heatmap-header">Unsupported</div>
    {_render_heatmap_rows(heatmap)}
  </div>
</div>

<!-- Object Table -->
<div class="card" style="margin-bottom:24px">
  <h2>All Objects</h2>
  <input type="text" id="search" placeholder="Filter objects..." onkeyup="filterTable()">
  <table id="objTable">
    <thead><tr><th>Type</th><th>Name</th><th>Fidelity</th><th>Note</th></tr></thead>
    <tbody>{obj_rows}</tbody>
  </table>
</div>

{timeline_html}

<script>
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  const rows = document.querySelectorAll('#objTable tbody tr');
  rows.forEach(r => {{
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


def _build_heatmap(objects):
    """Build heatmap data: {type: {fidelity: count}}."""
    heatmap = {}
    for obj in objects:
        t = obj.get("type", "unknown")
        f = obj.get("fidelity", "unsupported")
        if t not in heatmap:
            heatmap[t] = {"fully_migrated": 0, "approximated": 0, "manual_review": 0, "unsupported": 0}
        heatmap[t][f] = heatmap[t].get(f, 0) + 1
    return heatmap


def _render_heatmap_rows(heatmap):
    """Render heatmap grid rows."""
    rows = []
    for obj_type in sorted(heatmap.keys()):
        counts = heatmap[obj_type]
        total = sum(counts.values()) or 1
        rows.append(f'<div class="heatmap-cell">{html_escape(obj_type)}</div>')
        for level in ["fully_migrated", "approximated", "manual_review", "unsupported"]:
            count = counts.get(level, 0)
            pct = count / total
            opacity = max(0.15, pct)
            color = {"fully_migrated": "34,197,94", "approximated": "245,158,11",
                     "manual_review": "239,68,68", "unsupported": "127,29,29"}[level]
            rows.append(
                f'<div class="heatmap-cell" style="background:rgba({color},{opacity:.2f})">'
                f'{count}</div>'
            )
    return "\n    ".join(rows)


def _build_object_rows(objects):
    """Build HTML table rows for all objects."""
    rows = []
    for obj in objects:
        badge = _badge(obj.get("fidelity", "unsupported"))
        note = html_escape(obj.get("note", ""))
        rows.append(
            f'<tr><td>{html_escape(obj.get("type", ""))}</td>'
            f'<td>{html_escape(obj.get("name", ""))}</td>'
            f'<td>{badge}</td><td>{note}</td></tr>'
        )
    return "\n".join(rows)


def _badge(fidelity):
    """Return an HTML badge span for a fidelity level."""
    cls = {
        "fully_migrated": "badge-full",
        "approximated": "badge-approx",
        "manual_review": "badge-manual",
        "unsupported": "badge-unsup",
    }.get(fidelity, "badge-unsup")
    label = fidelity.replace("_", " ").title()
    return f'<span class="badge {cls}">{label}</span>'


def _build_dependency_mermaid(objects):
    """Build a Mermaid flowchart of object dependencies."""
    # Simple: reports/dossiers depend on metrics, metrics depend on attributes/facts
    lines = ["graph LR"]
    metrics = [o for o in objects if o["type"] in ("metric", "derived_metric")]
    reports = [o for o in objects if o["type"] == "report"]
    dossiers = [o for o in objects if o["type"] == "dossier"]

    for r in reports[:10]:  # cap at 10 for readability
        name = r["name"][:20]
        lines.append(f'    R_{_safe_id(r["name"])}["{html_escape(name)}"]')
    for m in metrics[:10]:
        name = m["name"][:20]
        lines.append(f'    M_{_safe_id(m["name"])}["{html_escape(name)}"]')

    for r in reports[:10]:
        for m in metrics[:5]:
            lines.append(f'    M_{_safe_id(m["name"])} --> R_{_safe_id(r["name"])}')

    return "\n".join(lines)


def _build_timeline(state_data):
    """Render a timeline of migration runs from state data."""
    objects = state_data.get("objects", {})
    if not objects:
        return ""

    # Group by date
    by_date = {}
    for key, entry in objects.items():
        date = entry.get("migrated_at", "")[:10]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(entry)

    items = []
    for date in sorted(by_date.keys(), reverse=True)[:10]:
        entries = by_date[date]
        items.append(
            f'<div class="timeline-item">'
            f'<div class="timeline-date">{html_escape(date)}</div>'
            f'<div>{len(entries)} objects migrated</div>'
            f'</div>'
        )

    return f"""
<div class="card" style="margin-bottom:24px">
  <h2>Migration Timeline</h2>
  <div class="timeline">
    {''.join(items)}
  </div>
</div>"""


def _safe_id(name):
    """Make a string safe for use as a Mermaid node ID."""
    import re
    return re.sub(r'[^a-zA-Z0-9]', '_', name)[:20]
