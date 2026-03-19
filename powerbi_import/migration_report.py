"""
Migration report generator.

Produces a per-object fidelity report in both JSON and HTML formats,
summarising which MicroStrategy objects were fully migrated, approximated,
flagged for manual review, or unsupported.
"""

import json
import os
import logging
from html import escape as html_escape

logger = logging.getLogger(__name__)

# ── Fidelity levels ──────────────────────────────────────────────

FULLY_MIGRATED = "fully_migrated"
APPROXIMATED = "approximated"
MANUAL_REVIEW = "manual_review"
UNSUPPORTED = "unsupported"

_FIDELITY_ORDER = [FULLY_MIGRATED, APPROXIMATED, MANUAL_REVIEW, UNSUPPORTED]


# ── Public API ───────────────────────────────────────────────────

def generate_migration_report(data, stats, output_dir, report_name="MicroStrategy Report"):
    """Generate JSON and HTML migration reports.

    Args:
        data: dict with all intermediate JSON keys
        stats: dict with generation statistics from generate_pbip
        output_dir: directory to write reports into
        report_name: project name for the report title

    Returns:
        dict — the full report structure (same as the JSON output)
    """
    os.makedirs(output_dir, exist_ok=True)

    objects = _assess_objects(data)
    summary = _build_summary(objects, stats, report_name)
    report = {"summary": summary, "objects": objects}

    # JSON report
    json_path = os.path.join(output_dir, "migration_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # HTML report
    html_path = os.path.join(output_dir, "migration_report.html")
    html = _render_html(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Migration report written to %s and %s", json_path, html_path)
    return report


# ── Object assessment ────────────────────────────────────────────

def _assess_objects(data):
    """Walk all intermediate data and classify every object."""
    objects = []

    # Metrics
    for m in data.get("metrics", []):
        fidelity = _assess_metric(m)
        objects.append(_obj_entry("metric", m, fidelity))

    for m in data.get("derived_metrics", []):
        fidelity = _assess_derived_metric(m)
        objects.append(_obj_entry("derived_metric", m, fidelity))

    # Attributes
    for a in data.get("attributes", []):
        objects.append(_obj_entry("attribute", a, FULLY_MIGRATED))

    # Facts
    for f in data.get("facts", []):
        objects.append(_obj_entry("fact", f, FULLY_MIGRATED))

    # Reports
    for r in data.get("reports", []):
        fidelity = _assess_report(r)
        objects.append(_obj_entry("report", r, fidelity))

    # Dossiers
    for d in data.get("dossiers", []):
        fidelity = _assess_dossier(d)
        objects.append(_obj_entry("dossier", d, fidelity))

    # Security filters → RLS
    for sf in data.get("security_filters", []):
        objects.append(_obj_entry("security_filter", sf, APPROXIMATED,
                                  note="Mapped to RLS role"))

    # Prompts
    for p in data.get("prompts", []):
        fidelity = _assess_prompt(p)
        objects.append(_obj_entry("prompt", p, fidelity))

    # Custom groups
    for cg in data.get("custom_groups", []):
        objects.append(_obj_entry("custom_group", cg, MANUAL_REVIEW,
                                  note="Custom groups require manual DAX grouping"))

    # Cubes
    for c in data.get("cubes", []):
        objects.append(_obj_entry("cube", c, APPROXIMATED,
                                  note="Cube mapped to Import-mode table"))

    return objects


def _obj_entry(obj_type, obj, fidelity, note=""):
    """Create a standardised object entry."""
    return {
        "type": obj_type,
        "id": obj.get("id", ""),
        "name": obj.get("name", ""),
        "fidelity": fidelity,
        "note": note,
    }


def _assess_metric(m):
    """Classify a simple/compound metric."""
    expr = m.get("expression", "")
    if not expr:
        return MANUAL_REVIEW
    mt = m.get("metric_type", "simple")
    if mt == "compound":
        return APPROXIMATED
    return FULLY_MIGRATED


def _assess_derived_metric(m):
    """Classify a derived (OLAP) metric."""
    expr = m.get("expression", "")
    if not expr:
        return UNSUPPORTED
    return APPROXIMATED


def _assess_report(r):
    """Classify a report."""
    has_grid = bool(r.get("grid"))
    has_graph = bool(r.get("graph"))
    if has_grid or has_graph:
        return FULLY_MIGRATED
    return MANUAL_REVIEW


def _assess_dossier(d):
    """Classify a dossier."""
    chapters = d.get("chapters", [])
    if not chapters:
        return MANUAL_REVIEW
    return FULLY_MIGRATED


def _assess_prompt(p):
    """Classify a prompt."""
    ptype = p.get("prompt_type", "")
    if ptype in ("attribute_element", "value", "date"):
        return FULLY_MIGRATED
    return APPROXIMATED


# ── Summary builder ──────────────────────────────────────────────

def _build_summary(objects, stats, report_name):
    """Aggregate fidelity counts and generation stats."""
    counts = {level: 0 for level in _FIDELITY_ORDER}
    type_counts = {}
    for obj in objects:
        counts[obj["fidelity"]] += 1
        type_counts[obj["type"]] = type_counts.get(obj["type"], 0) + 1

    total = len(objects)
    score = 0
    if total:
        weights = {FULLY_MIGRATED: 1.0, APPROXIMATED: 0.7,
                   MANUAL_REVIEW: 0.3, UNSUPPORTED: 0.0}
        score = sum(weights[o["fidelity"]] for o in objects) / total

    return {
        "report_name": report_name,
        "total_objects": total,
        "fidelity_score": round(score, 3),
        "fidelity_counts": counts,
        "type_counts": type_counts,
        "generation": {
            "tables": stats.get("tables", 0),
            "columns": stats.get("columns", 0),
            "measures": stats.get("measures", 0),
            "relationships": stats.get("relationships", 0),
            "pages": stats.get("pages", 0),
            "visuals": stats.get("visuals", 0),
        },
    }


# ── HTML renderer ────────────────────────────────────────────────

def _render_html(report):
    """Render the migration report as a standalone HTML page."""
    s = report["summary"]
    objects = report["objects"]

    fc = s["fidelity_counts"]
    gen = s["generation"]

    rows = []
    for obj in objects:
        badge = _fidelity_badge(obj["fidelity"])
        note = html_escape(obj.get("note", ""))
        rows.append(
            f"<tr><td>{html_escape(obj['type'])}</td>"
            f"<td>{html_escape(obj['name'])}</td>"
            f"<td>{badge}</td>"
            f"<td>{note}</td></tr>"
        )

    table_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Migration Report — {html_escape(s['report_name'])}</title>
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
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; color: #fff; }}
.fully_migrated {{ background: #107c10; }}
.approximated {{ background: #ff8c00; }}
.manual_review {{ background: #d83b01; }}
.unsupported {{ background: #a80000; }}
</style>
</head>
<body>
<h1>Migration Report — {html_escape(s['report_name'])}</h1>

<h2>Fidelity Score: {s['fidelity_score']:.0%}</h2>

<div>
  <div class="card"><div class="num">{fc.get('fully_migrated', 0)}</div><div class="label">Fully Migrated</div></div>
  <div class="card"><div class="num">{fc.get('approximated', 0)}</div><div class="label">Approximated</div></div>
  <div class="card"><div class="num">{fc.get('manual_review', 0)}</div><div class="label">Manual Review</div></div>
  <div class="card"><div class="num">{fc.get('unsupported', 0)}</div><div class="label">Unsupported</div></div>
</div>

<h2>Generation Summary</h2>
<div>
  <div class="card"><div class="num">{gen.get('tables', 0)}</div><div class="label">Tables</div></div>
  <div class="card"><div class="num">{gen.get('measures', 0)}</div><div class="label">Measures</div></div>
  <div class="card"><div class="num">{gen.get('pages', 0)}</div><div class="label">Pages</div></div>
  <div class="card"><div class="num">{gen.get('visuals', 0)}</div><div class="label">Visuals</div></div>
  <div class="card"><div class="num">{gen.get('relationships', 0)}</div><div class="label">Relationships</div></div>
</div>

<h2>Object Details ({s['total_objects']} objects)</h2>
<table>
<thead><tr><th>Type</th><th>Name</th><th>Fidelity</th><th>Notes</th></tr></thead>
<tbody>
{table_rows}
</tbody>
</table>
</body>
</html>"""


def _fidelity_badge(level):
    """Return an HTML badge span for a fidelity level."""
    label = level.replace("_", " ").title()
    return f'<span class="badge {level}">{html_escape(label)}</span>'
