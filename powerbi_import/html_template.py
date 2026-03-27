"""
Shared HTML template for all report generators.

Provides a unified CSS framework, JavaScript interactivity, and HTML
component builders (stat cards, tables, charts, badges, sections) used
by migration_report, comparison_report, governance_report,
telemetry_dashboard, lineage_report, and other HTML generators.
"""

import html as _html

# ---------------------------------------------------------------------------
# Design token constants
# ---------------------------------------------------------------------------

PBI_BLUE = "#217346"
PBI_DARK_BLUE = "#1B5E3A"
PBI_LIGHT_BLUE = "#E8F5E9"
PBI_DARK = "#1E1E1E"
PBI_GRAY = "#605E5C"
PBI_LIGHT_GRAY = "#F3F2F1"
PBI_BG = "#FAFAFA"
PBI_SURFACE = "#FFFFFF"

SUCCESS = "#107C10"
SUCCESS_BG = "#DFF6DD"
WARN = "#FFB900"
WARN_BG = "#FFF4CE"
FAIL = "#D13438"
FAIL_BG = "#FDE7E9"

PURPLE = "#8764B8"
TEAL = "#008272"
ORANGE = "#CA5010"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esc(text):
    """HTML-escape text, converting to string first."""
    return _html.escape(str(text)) if text is not None else ""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def get_report_css():
    """Return a complete ``<style>`` block with the report CSS framework."""
    return """<style>
:root {
  --pbi-blue: #217346;
  --pbi-dark: #1E1E1E;
  --pbi-gray: #605E5C;
  --pbi-bg: #FAFAFA;
  --pbi-surface: #FFFFFF;
  --success: #107C10;
  --success-bg: #DFF6DD;
  --warn: #FFB900;
  --warn-bg: #FFF4CE;
  --fail: #D13438;
  --fail-bg: #FDE7E9;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', -apple-system, sans-serif; background: var(--pbi-bg); color: var(--pbi-dark); line-height: 1.6; }
.header { background: linear-gradient(135deg, var(--pbi-blue), #1B5E3A); color: #fff; padding: 2rem; text-align: center; }
.header h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
.header .subtitle { opacity: 0.85; font-size: 0.95rem; }
.container { max-width: 1440px; margin: 0 auto; padding: 1.5rem; }

/* Stat cards */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }
.stat-card { background: var(--pbi-surface); border-radius: 8px; padding: 1.25rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-top: 3px solid var(--pbi-blue); transition: transform 0.15s; }
.stat-card:hover { transform: translateY(-2px); }
.stat-card .value { font-size: 2rem; font-weight: 700; }
.stat-card .label { font-size: 0.85rem; color: var(--pbi-gray); margin-top: 0.25rem; }
.stat-card.accent-success { border-top-color: var(--success); }
.stat-card.accent-warn { border-top-color: var(--warn); }
.stat-card.accent-fail { border-top-color: var(--fail); }
.stat-card.accent-purple { border-top-color: #8764B8; }
.stat-card.accent-teal { border-top-color: #008272; }

/* Collapsible sections */
.section { margin: 1.5rem 0; }
.section-header { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; padding: 0.75rem 1rem; background: var(--pbi-surface); border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.section-header h2 { font-size: 1.15rem; flex: 1; }
.section-header .toggle { font-size: 1.2rem; transition: transform 0.2s; }
.section-content { padding: 1rem; display: block; }
.section-content.collapsed { display: none; }

/* Tables */
table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.9rem; }
th { position: sticky; top: 0; background: var(--pbi-blue); color: #fff; padding: 0.6rem 0.75rem; text-align: left; cursor: pointer; }
td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #E1DFDD; }
tr:hover { background: var(--pbi-bg); }
.search-box { padding: 0.5rem; border: 1px solid #E1DFDD; border-radius: 4px; width: 250px; margin-bottom: 0.5rem; }

/* Badges */
.badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-green, .badge-success { background: var(--success-bg); color: var(--success); }
.badge-yellow, .badge-warn { background: var(--warn-bg); color: #986F0B; }
.badge-red, .badge-fail { background: var(--fail-bg); color: var(--fail); }
.badge-blue { background: #E8F5E9; color: var(--pbi-blue); }
.badge-gray { background: #F3F2F1; color: var(--pbi-gray); }
.badge-purple { background: #F3E8FF; color: #8764B8; }
.badge-teal { background: #E0F7FA; color: #008272; }

/* Fidelity bar */
.fidelity-bar { height: 12px; background: #E1DFDD; border-radius: 6px; overflow: hidden; }
.fidelity-bar .fill { height: 100%; border-radius: 6px; transition: width 0.3s; }
.fidelity-bar .fill.high { background: var(--success); }
.fidelity-bar .fill.med { background: var(--warn); }
.fidelity-bar .fill.low { background: var(--fail); }

/* Cards */
.card { background: var(--pbi-surface); border-radius: 8px; padding: 1rem; margin: 0.75rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card h3 { font-size: 1rem; margin-bottom: 0.5rem; }

/* Bar chart */
.bar-chart .bar-row { display: flex; align-items: center; margin: 0.3rem 0; }
.bar-chart .bar-label { width: 140px; font-size: 0.85rem; text-align: right; padding-right: 0.75rem; }
.bar-chart .bar-track { flex: 1; height: 18px; background: #E1DFDD; border-radius: 4px; overflow: hidden; }
.bar-chart .bar-fill { height: 100%; background: var(--pbi-blue); border-radius: 4px; }
.bar-chart .bar-value { width: 50px; padding-left: 0.5rem; font-size: 0.85rem; }

/* Tabs */
.tab-bar { display: flex; gap: 0; border-bottom: 2px solid #E1DFDD; margin: 1rem 0 0; }
.tab-bar button { background: none; border: none; padding: 0.5rem 1rem; cursor: pointer; font-size: 0.9rem; color: var(--pbi-gray); border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-bar button.active { color: var(--pbi-blue); border-bottom-color: var(--pbi-blue); font-weight: 600; }
.tab-content { display: none; padding: 1rem 0; }
.tab-content.active { display: block; }

/* Command box */
.cmd-box { background: #1E1E1E; color: #D4D4D4; padding: 0.75rem 1rem; border-radius: 6px; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 0.85rem; overflow-x: auto; }

/* Flow diagram */
.flow { display: flex; align-items: center; gap: 0; margin: 1rem 0; flex-wrap: wrap; }
.flow-step { background: var(--pbi-surface); border: 1px solid #E1DFDD; border-radius: 8px; padding: 0.5rem 1rem; text-align: center; font-size: 0.85rem; }
.flow-arrow { font-size: 1.2rem; color: var(--pbi-gray); padding: 0 0.5rem; }

/* Footer */
.footer { text-align: center; padding: 1.5rem; color: var(--pbi-gray); font-size: 0.8rem; border-top: 1px solid #E1DFDD; margin-top: 2rem; }

/* Print */
@media print { .section-content.collapsed { display: block !important; } .stat-card:hover { transform: none; } }
/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root { --pbi-bg: #1E1E1E; --pbi-surface: #252526; --pbi-dark: #D4D4D4; --pbi-gray: #A0A0A0; }
  th { background: #2D2D2D; }
  td { border-bottom-color: #3E3E3E; }
  tr:hover { background: #2A2A2A; }
}
/* Responsive */
@media (max-width: 768px) { .stat-grid { grid-template-columns: 1fr 1fr; } .bar-chart .bar-label { width: 100px; } }
</style>"""


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

def get_report_js():
    """Return interactive JavaScript for sections, tabs, search, sort."""
    return """<script>
function toggleSection(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.classList.toggle('collapsed');
  var header = el.previousElementSibling;
  if (header) { var t = header.querySelector('.toggle'); if (t) t.textContent = el.classList.contains('collapsed') ? '▶' : '▼'; }
}
function switchTab(groupId, tabName) {
  document.querySelectorAll('[data-tab-group="'+groupId+'"]').forEach(function(el) { el.classList.remove('active'); });
  document.querySelectorAll('[data-tab-content="'+groupId+'"]').forEach(function(el) { el.classList.remove('active'); });
  var btn = document.querySelector('[data-tab-group="'+groupId+'"][data-tab="'+tabName+'"]');
  var content = document.querySelector('[data-tab-content="'+groupId+'"][data-tab="'+tabName+'"]');
  if (btn) btn.classList.add('active');
  if (content) content.classList.add('active');
}
function filterTable(inputId, tableId) {
  var val = document.getElementById(inputId).value.toLowerCase();
  var rows = document.getElementById(tableId).querySelectorAll('tbody tr');
  rows.forEach(function(row) { row.style.display = row.textContent.toLowerCase().includes(val) ? '' : 'none'; });
}
function sortTable(tableId, colIndex) {
  var table = document.getElementById(tableId);
  if (!table) return;
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var asc = table.getAttribute('data-sort-dir') !== 'asc';
  table.setAttribute('data-sort-dir', asc ? 'asc' : 'desc');
  rows.sort(function(a, b) {
    var va = a.cells[colIndex].textContent.trim(), vb = b.cells[colIndex].textContent.trim();
    var na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  rows.forEach(function(row) { tbody.appendChild(row); });
}
</script>"""


# ---------------------------------------------------------------------------
# HTML component builders
# ---------------------------------------------------------------------------

def html_open(title="Migration Report", subtitle="", timestamp="", version=""):
    """Open HTML document through container start."""
    meta = f'<div class="subtitle">{esc(subtitle)}</div>' if subtitle else ""
    ts = f' | {esc(timestamp)}' if timestamp else ""
    ver = f' | v{esc(version)}' if version else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
{get_report_css()}
</head>
<body>
<div class="header"><h1>{esc(title)}</h1>{meta}<div class="subtitle" style="margin-top:0.5rem;font-size:0.8rem;">Generated{ts}{ver}</div></div>
<div class="container">
"""


def html_close(version="", timestamp=""):
    """Close HTML document with footer."""
    ver = f' v{esc(version)}' if version else ""
    ts = f' | {esc(timestamp)}' if timestamp else ""
    return f"""</div>
<div class="footer">MicroStrategy → Power BI Migration Tool{ver}{ts}</div>
{get_report_js()}
</body>
</html>"""


def stat_card(value, label, color="", accent=""):
    """Single metric card."""
    accent_cls = f" accent-{accent}" if accent else ""
    style = f' style="color:{color}"' if color else ""
    return f'<div class="stat-card{accent_cls}"><div class="value"{style}>{esc(value)}</div><div class="label">{esc(label)}</div></div>'


def stat_grid(cards):
    """Grid wrapper for stat cards."""
    return f'<div class="stat-grid">{"".join(cards)}</div>'


def section_open(section_id, title="", icon="", collapsed=False):
    """Collapsible section start."""
    toggle = "▶" if collapsed else "▼"
    cls = " collapsed" if collapsed else ""
    icon_span = f'<span>{icon}</span> ' if icon else ""
    return f"""<div class="section">
<div class="section-header" onclick="toggleSection('{section_id}')">
{icon_span}<h2>{esc(title)}</h2><span class="toggle">{toggle}</span>
</div>
<div id="{section_id}" class="section-content{cls}">
"""


def section_close():
    """Section end."""
    return "</div></div>"


def card(content, title=""):
    """Card wrapper."""
    title_html = f"<h3>{esc(title)}</h3>" if title else ""
    return f'<div class="card">{title_html}{content}</div>'


def badge(score, level=""):
    """Colored badge.  Auto-maps level names to CSS classes."""
    level_map = {
        "GREEN": "green", "YELLOW": "yellow", "RED": "red",
        "PASS": "green", "WARN": "yellow", "FAIL": "red",
        "HIGH": "green", "MEDIUM": "yellow", "LOW": "red",
        "success": "green", "warn": "yellow", "fail": "red",
    }
    css = level_map.get(level, level or "gray")
    return f'<span class="badge badge-{css}">{esc(score)}</span>'


def fidelity_bar(pct):
    """Progress bar with color thresholds."""
    pct = max(0, min(100, float(pct)))
    cls = "high" if pct >= 95 else "med" if pct >= 80 else "low"
    return f'<div class="fidelity-bar"><div class="fill {cls}" style="width:{pct:.1f}%"></div></div>'


def donut_chart(segments, center_text=""):
    """SVG donut chart.

    Args:
        segments: list of (label, value, color) tuples.
        center_text: text to display in center.
    """
    total = sum(v for _, v, _ in segments) or 1
    r, cx, cy = 40, 50, 50
    circumference = 2 * 3.14159 * r
    offset = 0
    arcs = []
    legend = []
    for label, value, color in segments:
        pct = value / total
        dash = circumference * pct
        gap = circumference - dash
        arcs.append(
            f'<circle r="{r}" cx="{cx}" cy="{cy}" fill="none" stroke="{color}" '
            f'stroke-width="15" stroke-dasharray="{dash:.1f} {gap:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" />'
        )
        offset += dash
        legend.append(f'<span style="color:{color};margin-right:1rem;">● {esc(label)}: {value}</span>')

    center = f'<text x="{cx}" y="{cy}" text-anchor="middle" dy="0.35em" font-size="12" fill="#605E5C">{esc(center_text)}</text>' if center_text else ""
    svg = f'<svg viewBox="0 0 100 100" width="120" height="120" style="transform:rotate(-90deg)">{"".join(arcs)}{center}</svg>'
    return f'<div style="display:flex;align-items:center;gap:1rem;">{svg}<div>{"".join(legend)}</div></div>'


def bar_chart(items, max_value=None):
    """Horizontal bar chart.

    Args:
        items: list of (label, value) tuples.
        max_value: override max for scaling (default: max from items).
    """
    if not items:
        return ""
    mv = max_value or max(v for _, v in items) or 1
    rows = []
    for label, value in items:
        pct = (value / mv) * 100
        rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<div class="bar-value">{value}</div>'
            f'</div>'
        )
    return f'<div class="bar-chart">{"".join(rows)}</div>'


def data_table(headers, rows, table_id="", sortable=False, searchable=False):
    """Full data table with optional search and sort.

    Args:
        headers: list of column header strings.
        rows: list of row lists (each row is list of cell values).
        table_id: HTML id for the table.
        sortable: enable click-to-sort.
        searchable: add search input above table.
    """
    tid = table_id or f"tbl_{id(rows)}"
    parts = []

    if searchable:
        input_id = f"search_{tid}"
        parts.append(
            f'<input class="search-box" id="{input_id}" type="text" '
            f'placeholder="Search..." oninput="filterTable(\'{input_id}\', \'{tid}\')">'
        )

    onclick = ' onclick="sortTable(\'{tid}\', {i})"' if sortable else ""
    ths = []
    for i, h in enumerate(headers):
        click = f' onclick="sortTable(\'{tid}\', {i})"' if sortable else ""
        ths.append(f"<th{click}>{esc(h)}</th>")

    trs = []
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        trs.append(f"<tr>{cells}</tr>")

    parts.append(
        f'<table id="{tid}"><thead><tr>{"".join(ths)}</tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>'
    )
    return "".join(parts)


def tab_bar(group_id, tabs):
    """Tab bar UI.

    Args:
        tabs: list of (tab_id, label) tuples. First tab is active.
    """
    buttons = []
    for i, (tab_id, label) in enumerate(tabs):
        active = " active" if i == 0 else ""
        buttons.append(
            f'<button class="{active}" data-tab-group="{group_id}" data-tab="{tab_id}" '
            f'onclick="switchTab(\'{group_id}\', \'{tab_id}\')">{esc(label)}</button>'
        )
    return f'<div class="tab-bar">{"".join(buttons)}</div>'


def tab_content(group_id, tab_id, content, active=False):
    """Tab content panel."""
    cls = " active" if active else ""
    return f'<div class="tab-content{cls}" data-tab-content="{group_id}" data-tab="{tab_id}">{content}</div>'


def flow_diagram(steps):
    """Horizontal flow diagram (step → step → ...).

    Args:
        steps: list of step label strings.
    """
    parts = []
    for i, step in enumerate(steps):
        if i > 0:
            parts.append('<span class="flow-arrow">→</span>')
        parts.append(f'<div class="flow-step">{esc(step)}</div>')
    return f'<div class="flow">{"".join(parts)}</div>'


def cmd_box(command):
    """Terminal-styled code block."""
    return f'<div class="cmd-box">{esc(command)}</div>'
