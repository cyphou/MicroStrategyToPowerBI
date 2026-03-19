"""
Global (server-wide) assessment module.

Runs ``assess_project`` on every workbook in a directory of intermediate-JSON
folders, then builds a portfolio-level assessment with pairwise merge
clustering.
"""

import json
import logging
import os
from collections import defaultdict

from powerbi_import.assessment import assess_project

logger = logging.getLogger(__name__)


# ── Data model ───────────────────────────────────────────────────


class ProjectProfile:
    """Lightweight summary for one workbook/project."""

    __slots__ = ("name", "path", "assessment", "object_count", "complexity",
                 "fidelity", "effort_hours", "overall_score", "connectors")

    def __init__(self, name, path, assessment):
        self.name = name
        self.path = path
        self.assessment = assessment
        s = assessment.get("summary", assessment)
        self.object_count = s.get("total_objects", 0)
        self.complexity = s.get("complexity_score", 0)
        self.fidelity = s.get("estimated_fidelity", 0)
        self.effort_hours = s.get("effort_hours", 0)
        self.overall_score = assessment.get("overall_score", "GREEN")
        self.connectors = set(s.get("connectors", []))

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__
                if s != "assessment" and s != "connectors"} | {
            "connectors": sorted(self.connectors)
        }


# ── Pairwise similarity ─────────────────────────────────────────


def _pairwise_score(a, b):
    """Return 0‑1 similarity between two ProjectProfiles.

    Heuristic based on shared connectors, similar complexity, and compatible
    data overlap (same datasource tables).
    """
    if not a.connectors and not b.connectors:
        connector_sim = 0.5
    elif not a.connectors or not b.connectors:
        connector_sim = 0.0
    else:
        shared = len(a.connectors & b.connectors)
        total = len(a.connectors | b.connectors)
        connector_sim = shared / total if total else 0

    complexity_diff = abs(a.complexity - b.complexity)
    complexity_sim = max(0, 1.0 - complexity_diff / 100)

    return round(0.6 * connector_sim + 0.4 * complexity_sim, 3)


# ── Merge clustering (BFS) ──────────────────────────────────────


def _cluster_projects(profiles, threshold=0.5):
    """Group projects into merge clusters using BFS on similarity graph."""
    n = len(profiles)
    if n == 0:
        return []

    adj = defaultdict(set)
    for i in range(n):
        for j in range(i + 1, n):
            if _pairwise_score(profiles[i], profiles[j]) >= threshold:
                adj[i].add(j)
                adj[j].add(i)

    visited = set()
    clusters = []
    for start in range(n):
        if start in visited:
            continue
        queue = [start]
        cluster = []
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster.append(profiles[node])
            for nb in adj[node]:
                if nb not in visited:
                    queue.append(nb)
        clusters.append(cluster)
    return clusters


# ── Public API ───────────────────────────────────────────────────


def run_global_assessment(base_dir, output_dir=None, threshold=0.5):
    """Assess all projects in *base_dir* and produce a portfolio report.

    *base_dir* should contain one sub-folder per workbook, each with the
    18 intermediate JSON files.

    Returns:
        dict with portfolio-level assessment.
    """
    profiles = []

    # Detect sub-dirs that contain datasources.json (indicator of extracted project)
    for entry in sorted(os.listdir(base_dir)):
        sub = os.path.join(base_dir, entry)
        if not os.path.isdir(sub):
            continue
        ds_path = os.path.join(sub, "datasources.json")
        if not os.path.exists(ds_path):
            continue

        data = _load_project(sub)
        result = assess_project(data)
        profiles.append(ProjectProfile(entry, sub, result))
        logger.info("Assessed %s: score=%s, complexity=%d",
                     entry, result.get("overall_score", "?"),
                     result.get("summary", result).get("complexity_score", 0))

    clusters = _cluster_projects(profiles, threshold)

    report = {
        "total_projects": len(profiles),
        "total_effort_hours": round(sum(p.effort_hours for p in profiles), 1),
        "score_distribution": {
            "GREEN": sum(1 for p in profiles if p.overall_score == "GREEN"),
            "YELLOW": sum(1 for p in profiles if p.overall_score == "YELLOW"),
            "RED": sum(1 for p in profiles if p.overall_score == "RED"),
        },
        "projects": [p.to_dict() for p in profiles],
        "merge_clusters": [
            {"cluster_id": i + 1,
             "members": [p.name for p in cl],
             "total_effort": round(sum(p.effort_hours for p in cl), 1)}
            for i, cl in enumerate(clusters)
        ],
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "global_assessment.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        html_path = os.path.join(output_dir, "global_assessment.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_render_global_html(report))

        logger.info("Global assessment written to %s", output_dir)

    return report


# ── Helpers ──────────────────────────────────────────────────────


_JSON_FILES = [
    "datasources.json", "attributes.json", "facts.json", "metrics.json",
    "derived_metrics.json", "reports.json", "dossiers.json", "cubes.json",
    "filters.json", "prompts.json", "custom_groups.json", "consolidations.json",
    "hierarchies.json", "relationships.json", "security_filters.json",
    "freeform_sql.json", "thresholds.json", "subtotals.json",
]


def _load_project(folder):
    data = {}
    for fname in _JSON_FILES:
        key = fname.replace(".json", "")
        fpath = os.path.join(folder, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data[key] = json.load(f)
            except (json.JSONDecodeError, OSError):
                data[key] = []
        else:
            data[key] = []
    return data


def _render_global_html(report):
    from html import escape as esc

    proj_rows = []
    for p in report["projects"]:
        sc = p.get("overall_score", "GREEN")
        color = {"GREEN": "#107c10", "YELLOW": "#ff8c00", "RED": "#a80000"}.get(sc, "#333")
        proj_rows.append(
            f"<tr><td>{esc(p['name'])}</td>"
            f"<td style='color:{color};font-weight:bold'>{sc}</td>"
            f"<td>{p['complexity']}</td>"
            f"<td>{p['object_count']}</td>"
            f"<td>{p['effort_hours']:.1f}h</td>"
            f"<td>{p['fidelity']:.0%}</td></tr>"
        )
    proj_table = "\n".join(proj_rows)

    cluster_rows = []
    for cl in report["merge_clusters"]:
        cluster_rows.append(
            f"<tr><td>Cluster {cl['cluster_id']}</td>"
            f"<td>{', '.join(esc(m) for m in cl['members'])}</td>"
            f"<td>{cl['total_effort']:.1f}h</td></tr>"
        )
    cluster_table = "\n".join(cluster_rows)

    dist = report["score_distribution"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Global Assessment</title>
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
<h1>Portfolio Global Assessment</h1>

<div>
  <div class="card"><div class="num">{report['total_projects']}</div><div class="label">Projects</div></div>
  <div class="card"><div class="num">{report['total_effort_hours']:.1f}h</div><div class="label">Total Effort</div></div>
  <div class="card"><div class="num" style="color:#107c10">{dist['GREEN']}</div><div class="label">GREEN</div></div>
  <div class="card"><div class="num" style="color:#ff8c00">{dist['YELLOW']}</div><div class="label">YELLOW</div></div>
  <div class="card"><div class="num" style="color:#a80000">{dist['RED']}</div><div class="label">RED</div></div>
</div>

<h2>Projects</h2>
<table>
<thead><tr><th>Project</th><th>Score</th><th>Complexity</th><th>Objects</th><th>Effort</th><th>Fidelity</th></tr></thead>
<tbody>{proj_table}</tbody>
</table>

<h2>Merge Clusters</h2>
<table>
<thead><tr><th>Cluster</th><th>Members</th><th>Total Effort</th></tr></thead>
<tbody>{cluster_table}</tbody>
</table>

</body>
</html>"""
