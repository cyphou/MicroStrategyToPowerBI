"""
Telemetry dashboard.

Generates an HTML dashboard from historical telemetry runs showing
trends in object counts, durations, error rates, and feature usage.
"""

import json
import logging
import os
from html import escape as esc

from powerbi_import.telemetry import load_runs

logger = logging.getLogger(__name__)


def generate_telemetry_dashboard(output_dir):
    """Generate an HTML dashboard from telemetry log.

    Args:
        output_dir: directory containing telemetry_log.json.

    Returns:
        str — path to the generated HTML file, or None if no data.
    """
    runs = load_runs(output_dir)
    if not runs:
        logger.info("No telemetry data found in %s", output_dir)
        return None

    html_path = os.path.join(output_dir, "telemetry_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_render_dashboard(runs))

    logger.info("Telemetry dashboard written to %s", html_path)
    return html_path


def _render_dashboard(runs):
    total = len(runs)
    successes = sum(1 for r in runs if r.get("status") == "success")
    failures = sum(1 for r in runs if r.get("status") == "error")
    avg_duration = sum(r.get("duration_seconds", 0) for r in runs) / total if total else 0

    run_rows = []
    for r in reversed(runs[-50:]):  # last 50 runs, most recent first
        st = r.get("status", "?")
        color = "#107c10" if st == "success" else "#a80000" if st == "error" else "#ff8c00"
        oc = r.get("object_counts", {})
        total_obj = sum(oc.values()) if isinstance(oc, dict) else 0
        errs = len(r.get("errors", []))
        run_rows.append(
            f"<tr><td>{esc(r.get('run_id', ''))}</td>"
            f"<td>{esc(r.get('project_name', ''))}</td>"
            f"<td style='color:{color}'>{st}</td>"
            f"<td>{r.get('duration_seconds', 0):.1f}s</td>"
            f"<td>{total_obj}</td>"
            f"<td>{errs}</td>"
            f"<td>{esc(r.get('started_at', ''))}</td></tr>"
        )
    run_table = "\n".join(run_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Migration Telemetry Dashboard</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 2rem; color: #333; }}
h1 {{ color: #0078d4; }}
.card {{ display: inline-block; background: #f3f3f3; border-radius: 8px;
         padding: 1rem 1.5rem; margin: 0.5rem; text-align: center; }}
.card .num {{ font-size: 2rem; font-weight: bold; }}
.card .label {{ font-size: 0.85rem; color: #666; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #0078d4; color: #fff; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
</style>
</head>
<body>
<h1>Migration Telemetry Dashboard</h1>

<div>
  <div class="card"><div class="num">{total}</div><div class="label">Total Runs</div></div>
  <div class="card"><div class="num" style="color:#107c10">{successes}</div><div class="label">Successes</div></div>
  <div class="card"><div class="num" style="color:#a80000">{failures}</div><div class="label">Failures</div></div>
  <div class="card"><div class="num">{avg_duration:.1f}s</div><div class="label">Avg Duration</div></div>
</div>

<h2>Recent Runs</h2>
<table>
<thead><tr><th>Run ID</th><th>Project</th><th>Status</th><th>Duration</th><th>Objects</th><th>Errors</th><th>Started</th></tr></thead>
<tbody>{run_table}</tbody>
</table>

</body>
</html>"""
