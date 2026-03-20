"""
Merge report — HTML report showing merge impact, overlap heatmap,
conflict resolution details, and per-project contribution stats.
"""

import html
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_merge_report(assessment, output_path):
    """Generate an HTML merge impact report.

    Args:
        assessment: dict from merge_assessment.run_merge_assessment().
        output_path: Path for the output HTML file.

    Returns:
        Path to the generated HTML file.
    """
    projects = assessment.get("projects", [])
    overlap = assessment.get("overlap", {})
    viability = assessment.get("viability", {})

    report_html = _build_html(projects, overlap, viability)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)
    logger.info("Merge report written to %s", output_path)
    return output_path


def _build_html(projects, overlap, viability):
    """Build the complete HTML string for the merge report."""
    score = viability.get("score", 0)
    rating = viability.get("rating", "UNKNOWN")
    color_map = {"GREEN": "#28a745", "YELLOW": "#ffc107", "RED": "#dc3545"}
    rating_color = color_map.get(rating, "#6c757d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    shared_tables = overlap.get("shared_tables", {})
    shared_metrics = overlap.get("shared_metrics", {})
    shared_attrs = overlap.get("shared_attributes", {})
    conflicts = overlap.get("conflicts", [])
    unique = overlap.get("unique_per_project", {})

    sections = []

    # Header
    sections.append(f"""
    <div style="text-align:center;margin-bottom:30px">
        <h1>Merge Impact Report</h1>
        <p style="color:#666">{html.escape(timestamp)}</p>
        <div style="display:inline-block;background:{rating_color};color:#fff;
                    padding:15px 30px;border-radius:10px;font-size:1.5em">
            Score: {score}/100 — {html.escape(rating)}
        </div>
        <p style="margin-top:10px">{html.escape(viability.get('recommendation', ''))}</p>
    </div>
    """)

    # Projects overview
    sections.append(f"""
    <h2>Projects ({len(projects)})</h2>
    <ul>{''.join(f'<li>{html.escape(p)}</li>' for p in projects)}</ul>
    """)

    # Shared objects summary
    sections.append(f"""
    <h2>Overlap Summary</h2>
    <table>
        <tr><th>Category</th><th>Shared Count</th></tr>
        <tr><td>Tables</td><td>{len(shared_tables)}</td></tr>
        <tr><td>Metrics</td><td>{len(shared_metrics)}</td></tr>
        <tr><td>Attributes</td><td>{len(shared_attrs)}</td></tr>
    </table>
    """)

    # Shared tables detail
    if shared_tables:
        rows = "".join(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(', '.join(projs))}</td></tr>"
            for name, projs in sorted(shared_tables.items())
        )
        sections.append(f"""
        <h3>Shared Tables</h3>
        <table><tr><th>Table</th><th>Projects</th></tr>{rows}</table>
        """)

    # Conflicts
    if conflicts:
        rows = "".join(
            f"<tr><td>{html.escape(c['type'])}</td>"
            f"<td>{html.escape(c['name'])}</td>"
            f"<td>{html.escape(', '.join(c['projects']))}</td></tr>"
            for c in conflicts
        )
        sections.append(f"""
        <h3 style="color:#dc3545">Conflicts ({len(conflicts)})</h3>
        <table><tr><th>Type</th><th>Name</th><th>Projects</th></tr>{rows}</table>
        """)
    else:
        sections.append("<h3>Conflicts</h3><p style='color:green'>None detected.</p>")

    # Unique per project
    if unique:
        for proj, items in unique.items():
            metrics = items.get("metrics", [])
            sections.append(f"""
            <h3>Unique to {html.escape(proj)}</h3>
            <p>{len(metrics)} unique metrics</p>
            """)

    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Merge Impact Report</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px; background: #fafafa; }}
  h1 {{ color: #1a1a2e; }}
  h2 {{ color: #16213e; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
  h3 {{ color: #0f3460; }}
  table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
