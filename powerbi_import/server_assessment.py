"""
Server-wide assessment for MicroStrategy project portfolios.

Scans multiple projects, classifies readiness (GREEN/YELLOW/RED),
groups into migration waves, and generates HTML + JSON reports.
"""

import json
import logging
import os
from html import escape as esc

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────

class WorkbookReadiness:
    """Assessment result for a single MSTR project."""

    __slots__ = ("name", "status", "pass_count", "warn_count", "fail_count",
                 "info_count", "complexity", "effort_hours", "connectors",
                 "counts")

    def __init__(self, name, assessment_report):
        self.name = name
        r = assessment_report
        # Support both flat (v2) and nested (v3) report structures
        summary = r.get("summary", r)
        checks = r.get("checks", [])
        self.pass_count = sum(1 for c in checks if c.get("severity") == "pass")
        self.warn_count = sum(1 for c in checks if c.get("severity") == "warning")
        self.fail_count = sum(1 for c in checks if c.get("severity") == "fail")
        self.info_count = sum(1 for c in checks if c.get("severity") == "info")
        self.complexity = summary.get("complexity_score", 0)
        self.effort_hours = summary.get("effort_hours", 0)
        self.connectors = summary.get("connectors", [])
        self.counts = summary.get("object_counts", {})

        if self.fail_count == 0 and self.warn_count <= 2:
            self.status = "GREEN"
        elif self.fail_count <= 2:
            self.status = "YELLOW"
        else:
            self.status = "RED"

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class MigrationWave:
    """A migration wave grouping projects by readiness."""

    def __init__(self, number, label, workbooks):
        self.number = number
        self.label = label
        self.workbooks = workbooks
        self.total_effort = sum(w.effort_hours for w in workbooks)


class ServerAssessment:
    """Portfolio-level assessment result."""

    def __init__(self, results, waves):
        self.workbook_results = results
        self.waves = waves
        self.total = len(results)
        self.green = sum(1 for r in results if r.status == "GREEN")
        self.yellow = sum(1 for r in results if r.status == "YELLOW")
        self.red = sum(1 for r in results if r.status == "RED")
        self.readiness_pct = round(self.green / max(self.total, 1) * 100, 1)
        self.total_effort = sum(r.effort_hours for r in results)
        self.connector_census = _build_connector_census(results)


# ── Public API ───────────────────────────────────────────────────

def run_server_assessment(project_assessments):
    """Run server-wide assessment from a list of assessment reports.

    Args:
        project_assessments: list of assessment_report dicts, or list of
            (project_name, assessment_report_dict) tuples.

    Returns:
        dict with workbooks, waves, and aggregate stats.
    """
    results = []
    for item in project_assessments:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            name, report = item
        elif isinstance(item, dict):
            name = item.get("project_name", f"Project_{len(results)+1}")
            report = item
        else:
            continue
        results.append(WorkbookReadiness(name, report))

    wave1 = [r for r in results if r.status == "GREEN" and r.complexity <= 20]
    wave2 = [r for r in results if r not in wave1 and r.status != "RED"]
    wave3 = [r for r in results if r.status == "RED" or r.complexity > 50]
    # Ensure no duplicates
    wave2 = [r for r in wave2 if r not in wave3]

    waves = [
        MigrationWave(1, "Easy (GREEN, low complexity)", wave1),
        MigrationWave(2, "Medium (YELLOW, moderate)", wave2),
        MigrationWave(3, "Complex (RED, high complexity)", wave3),
    ]

    return _server_assessment_to_dict(ServerAssessment(results, waves))


def _server_assessment_to_dict(assessment):
    """Convert ServerAssessment to a plain dict."""
    return {
        "total_workbooks": assessment.total,
        "readiness_pct": assessment.readiness_pct,
        "green": assessment.green,
        "yellow": assessment.yellow,
        "red": assessment.red,
        "total_effort_hours": assessment.total_effort,
        "connector_census": assessment.connector_census,
        "workbooks": [r.to_dict() for r in assessment.workbook_results],
        "waves": [
            {"wave": w.number, "label": w.label,
             "members": [wb.name for wb in w.workbooks],
             "effort_hours": w.total_effort}
            for w in assessment.waves
        ],
    }


def save_server_assessment_json(assessment, output_dir):
    """Save server assessment as JSON."""
    os.makedirs(output_dir, exist_ok=True)
    data = {
        "total_projects": assessment.total,
        "readiness_pct": assessment.readiness_pct,
        "green": assessment.green,
        "yellow": assessment.yellow,
        "red": assessment.red,
        "total_effort_hours": assessment.total_effort,
        "connector_census": assessment.connector_census,
        "waves": [
            {"wave": w.number, "label": w.label,
             "projects": [wb.name for wb in w.workbooks],
             "effort_hours": w.total_effort}
            for w in assessment.waves
        ],
        "projects": [r.to_dict() for r in assessment.workbook_results],
    }
    path = os.path.join(output_dir, "server_assessment.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def generate_server_html_report(assessment, output_dir):
    """Generate server assessment HTML dashboard."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "server_assessment.html")

    status_color = {"GREEN": "#107c10", "YELLOW": "#ff8c00", "RED": "#a80000"}
    project_rows = "\n".join(
        f"<tr><td>{esc(r.name)}</td>"
        f"<td style='color:{status_color[r.status]};font-weight:bold'>{r.status}</td>"
        f"<td>{r.complexity}</td><td>{r.effort_hours:.1f}h</td>"
        f"<td>{', '.join(r.connectors) or '—'}</td></tr>"
        for r in assessment.workbook_results
    )
    wave_rows = "\n".join(
        f"<tr><td>Wave {w.number}</td><td>{esc(w.label)}</td>"
        f"<td>{len(w.workbooks)}</td><td>{w.total_effort:.1f}h</td></tr>"
        for w in assessment.waves
    )
    connector_rows = "\n".join(
        f"<tr><td>{esc(c)}</td><td>{n}</td></tr>"
        for c, n in sorted(assessment.connector_census.items(), key=lambda x: -x[1])
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Server Assessment</title>
<style>
body {{ font-family:'Segoe UI',system-ui,sans-serif; margin:2rem; color:#333; }}
h1 {{ color:#0078d4; }} h2 {{ color:#333; margin-top:1.5rem; }}
.card {{ display:inline-block; background:#f3f3f3; border-radius:8px;
         padding:1rem 1.5rem; margin:0.5rem; text-align:center; }}
.card .num {{ font-size:2rem; font-weight:bold; }}
.card .label {{ font-size:0.85rem; color:#666; }}
table {{ border-collapse:collapse; width:100%; margin-top:1rem; }}
th,td {{ border:1px solid #ddd; padding:0.5rem 0.75rem; text-align:left; }}
th {{ background:#0078d4; color:#fff; }}
tr:nth-child(even) {{ background:#f9f9f9; }}
</style></head><body>
<h1>Server-Wide Migration Assessment</h1>
<div>
  <div class="card"><div class="num">{assessment.total}</div><div class="label">Projects</div></div>
  <div class="card"><div class="num" style="color:#107c10">{assessment.green}</div><div class="label">GREEN</div></div>
  <div class="card"><div class="num" style="color:#ff8c00">{assessment.yellow}</div><div class="label">YELLOW</div></div>
  <div class="card"><div class="num" style="color:#a80000">{assessment.red}</div><div class="label">RED</div></div>
  <div class="card"><div class="num">{assessment.readiness_pct}%</div><div class="label">Readiness</div></div>
  <div class="card"><div class="num">{assessment.total_effort:.0f}h</div><div class="label">Total Effort</div></div>
</div>
<h2>Migration Waves</h2>
<table><thead><tr><th>Wave</th><th>Description</th><th>Projects</th><th>Effort</th></tr></thead>
<tbody>{wave_rows}</tbody></table>
<h2>Connector Census</h2>
<table><thead><tr><th>Connector</th><th>Count</th></tr></thead>
<tbody>{connector_rows}</tbody></table>
<h2>Project Details</h2>
<table><thead><tr><th>Project</th><th>Status</th><th>Complexity</th><th>Effort</th><th>Connectors</th></tr></thead>
<tbody>{project_rows}</tbody></table>
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ── Helpers ──────────────────────────────────────────────────────

def _build_connector_census(results):
    census = {}
    for r in results:
        for c in r.connectors:
            census[c] = census.get(c, 0) + 1
    return census
