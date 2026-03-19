"""
Thin report generator.

Generates lightweight Power BI reports that reference a shared semantic
model via live connection, rather than embedding their own model.
Each thin report has pages/visuals but no tables/measures of its own.
"""

import json
import logging
import os

from powerbi_import.visual_generator import generate_all_visuals

logger = logging.getLogger(__name__)


def generate_thin_report(data, output_dir, *, report_name, shared_model_name,
                         shared_model_id=None):
    """Generate a thin .pbip report referencing a shared semantic model.

    Args:
        data: dict with intermediate JSON data.
        output_dir: root output directory.
        report_name: display name for the report.
        shared_model_name: name of the shared semantic model to reference.
        shared_model_id: optional remote dataset ID (for published models).

    Returns:
        dict with generation stats.
    """
    project_dir = os.path.join(output_dir, _safe(report_name))
    os.makedirs(project_dir, exist_ok=True)

    # ── .pbip ────────────────────────────────────────────────────
    pbip = {
        "version": "1.0",
        "artifacts": [{
            "report": {"path": f"{_safe(report_name)}.Report"},
        }],
    }
    _write_json(os.path.join(project_dir, f"{_safe(report_name)}.pbip"), pbip)

    # ── Report directory ─────────────────────────────────────────
    rpt_dir = os.path.join(project_dir, f"{_safe(report_name)}.Report")
    os.makedirs(rpt_dir, exist_ok=True)

    _write_json(os.path.join(rpt_dir, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report"},
        "config": {"logicalId": _slugify(report_name)},
    })

    rpt_def = os.path.join(rpt_dir, "definition")
    os.makedirs(rpt_def, exist_ok=True)

    # ── definition.pbir (points to shared model) ─────────────────
    if shared_model_id:
        pbir = {
            "version": "4.0",
            "datasetReference": {
                "byPath": None,
                "byConnection": {
                    "connectionString": None,
                    "pbiServiceModelId": None,
                    "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                    "pbiModelDatabaseName": shared_model_id,
                    "name": "EntityDataSource",
                    "connectionType": "pbiServiceXmlaStyleLive",
                },
            },
        }
    else:
        pbir = {
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": f"../{_safe(shared_model_name)}_SharedModel/{_safe(shared_model_name)}.SemanticModel",
                },
                "byConnection": None,
            },
        }
    _write_json(os.path.join(rpt_def, "definition.pbir"), pbir)

    # ── report.json ──────────────────────────────────────────────
    _write_json(os.path.join(rpt_def, "report.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
        "version": "4.0",
    })

    # ── Pages & visuals ──────────────────────────────────────────
    pages_dir = os.path.join(rpt_def, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    stats = generate_all_visuals(data, pages_dir)

    # ── .gitignore ───────────────────────────────────────────────
    gi_path = os.path.join(project_dir, ".gitignore")
    with open(gi_path, "w", encoding="utf-8") as f:
        f.write(".pbi/\n*.pbicache\n")

    logger.info("Thin report generated at %s", project_dir)
    return stats


# ── Helpers ──────────────────────────────────────────────────────


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _safe(name):
    import re
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


def _slugify(name):
    import re
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()
