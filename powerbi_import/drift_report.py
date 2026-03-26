"""
Drift report generator.

Compares the current Power BI ``.pbip`` output against the previous
migration output to detect *manual edits* that would be overwritten by
a re-migration.  Produces a JSON conflict list and an HTML report.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from html import escape as esc

logger = logging.getLogger(__name__)

_DRIFT_JSON = "drift_report.json"
_DRIFT_HTML = "drift_report.html"

# File extensions we compare inside .pbip output trees
_TRACKED_EXTENSIONS = {".json", ".tmdl", ".m", ".pq"}


def _hash_file(path):
    """SHA-256 of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_files(root):
    """Walk *root* and return {relative_path: sha256} for tracked files."""
    file_map = {}
    if not os.path.isdir(root):
        return file_map
    for dirpath, _dirs, filenames in os.walk(root):
        for fname in filenames:
            _, ext = os.path.splitext(fname)
            if ext.lower() not in _TRACKED_EXTENSIONS:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace("\\", "/")
            file_map[rel] = _hash_file(full)
    return file_map


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def detect_drift(current_output_dir, previous_output_dir):
    """Compare two .pbip output directories and return a drift report.

    Args:
        current_output_dir:  Directory with the *live* PBI output (may
                             contain manual edits by the user).
        previous_output_dir: Directory with the *last migration* output
                             (the baseline).

    Returns:
        dict with ``drifted``, ``added_locally``, ``deleted_locally``,
        ``unchanged`` lists and a ``summary``.
    """
    cur = _collect_files(current_output_dir)
    prev = _collect_files(previous_output_dir)

    drifted = []
    added_locally = []
    deleted_locally = []
    unchanged = []

    # Files present in both
    for rel, cur_hash in cur.items():
        if rel in prev:
            if cur_hash != prev[rel]:
                drifted.append({"file": rel, "status": "modified"})
            else:
                unchanged.append({"file": rel})
        else:
            added_locally.append({"file": rel, "status": "added"})

    # Files present only in previous (deleted by user)
    for rel in prev:
        if rel not in cur:
            deleted_locally.append({"file": rel, "status": "deleted"})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_dir": current_output_dir,
        "previous_dir": previous_output_dir,
        "drifted": drifted,
        "added_locally": added_locally,
        "deleted_locally": deleted_locally,
        "unchanged": unchanged,
        "summary": {
            "drifted": len(drifted),
            "added_locally": len(added_locally),
            "deleted_locally": len(deleted_locally),
            "unchanged": len(unchanged),
        },
    }
    logger.info(
        "Drift detection: %d drifted, %d added, %d deleted, %d unchanged",
        len(drifted), len(added_locally), len(deleted_locally), len(unchanged),
    )
    return report


def save_drift_report(report, output_dir):
    """Write JSON + HTML drift reports to *output_dir*."""
    os.makedirs(output_dir, exist_ok=True)

    # JSON
    json_path = os.path.join(output_dir, _DRIFT_JSON)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # HTML
    html_path = os.path.join(output_dir, _DRIFT_HTML)
    html = _render_html(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Drift report saved to %s and %s", json_path, html_path)
    return json_path, html_path


# ------------------------------------------------------------------
# HTML rendering
# ------------------------------------------------------------------

_STATUS_COLOR = {
    "modified": "#ff8c00",
    "added": "#107c10",
    "deleted": "#a80000",
}


def _render_html(report):
    """Produce a standalone HTML drift report."""
    summary = report.get("summary", {})
    total_changes = (
        summary.get("drifted", 0)
        + summary.get("added_locally", 0)
        + summary.get("deleted_locally", 0)
    )
    status_label = "CLEAN" if total_changes == 0 else f"{total_changes} CONFLICT(S)"
    status_color = "#107c10" if total_changes == 0 else "#a80000"

    rows = []
    for item in report.get("drifted", []):
        rows.append(_html_row(item["file"], "modified"))
    for item in report.get("added_locally", []):
        rows.append(_html_row(item["file"], "added"))
    for item in report.get("deleted_locally", []):
        rows.append(_html_row(item["file"], "deleted"))

    table_body = "\n".join(rows) if rows else (
        '<tr><td colspan="2" style="text-align:center;color:#888;">'
        "No drift detected — output matches last migration.</td></tr>"
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Drift Report</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 2rem; background: #fafafa; }}
h1 {{ color: #333; }}
.badge {{ display: inline-block; padding: 4px 12px; border-radius: 4px; color: #fff;
          font-weight: 600; background: {status_color}; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #ddd; }}
th {{ background: #f0f0f0; }}
.status {{ font-weight: 600; }}
</style>
</head>
<body>
<h1>Drift Report <span class="badge">{esc(status_label)}</span></h1>
<p>Generated: {esc(report.get("generated_at", ""))}</p>
<table>
<tr><th>File</th><th>Status</th></tr>
{table_body}
</table>
<h2>Summary</h2>
<ul>
<li><strong>Modified:</strong> {summary.get("drifted", 0)}</li>
<li><strong>Added locally:</strong> {summary.get("added_locally", 0)}</li>
<li><strong>Deleted locally:</strong> {summary.get("deleted_locally", 0)}</li>
<li><strong>Unchanged:</strong> {summary.get("unchanged", 0)}</li>
</ul>
</body>
</html>"""


def _html_row(filepath, status):
    color = _STATUS_COLOR.get(status, "#333")
    return (
        f'<tr><td>{esc(filepath)}</td>'
        f'<td class="status" style="color:{color};">{esc(status)}</td></tr>'
    )
