"""
Shared semantic model generator.

Generates a single project-level semantic model that contains all tables,
columns, measures, relationships, hierarchies, and RLS roles from the
entire MicroStrategy project.  Thin reports can then reference this shared
model via live connection.

The ``generate_merged_model`` function (v4.0) extends this to accept N
project directories and produce a unified merged semantic model.
"""

import json
import logging
import os

from powerbi_import.tmdl_generator import generate_all_tmdl

logger = logging.getLogger(__name__)


def generate_shared_model(data, output_dir, *, model_name="SharedModel"):
    """Generate a standalone shared semantic model (.pbip with no report pages).

    The output is a fully valid .pbip project where the Report contains
    only an empty placeholder page and a ``definition.pbir`` pointing to
    the co-located semantic model.

    Args:
        data: dict of intermediate JSON data.
        output_dir: Root output directory.
        model_name: Display name for the shared model.

    Returns:
        dict with generation stats.
    """
    project_dir = os.path.join(output_dir, f"{model_name}_SharedModel")
    os.makedirs(project_dir, exist_ok=True)

    # ── .pbip entry point ────────────────────────────────────────
    pbip = {
        "version": "1.0",
        "artifacts": [{
            "report": {"path": f"{model_name}.Report"},
            "semanticModel": {"path": f"{model_name}.SemanticModel"},
        }],
    }
    _write_json(os.path.join(project_dir, f"{model_name}.pbip"), pbip)

    # ── Semantic Model (full TMDL) ───────────────────────────────
    sm_dir = os.path.join(project_dir, f"{model_name}.SemanticModel")
    os.makedirs(sm_dir, exist_ok=True)
    _write_json(os.path.join(sm_dir, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel"},
        "config": {"logicalId": _slugify(model_name)},
    })
    _write_json(os.path.join(sm_dir, "definition.pbism"), {
        "version": "4.0",
        "datasetReference": {
            "byPath": None,
            "byConnection": None,
        },
    })

    definition_dir = os.path.join(sm_dir, "definition")
    os.makedirs(definition_dir, exist_ok=True)
    stats = generate_all_tmdl(data, definition_dir)

    # Write model.tmdl header (generate_all_tmdl doesn't create this)
    model_path = os.path.join(definition_dir, "model.tmdl")
    with open(model_path, "w", encoding="utf-8") as f:
        f.write(f"model {model_name}\n\tculture: en-US\n")

    # ── Report (empty shell) ─────────────────────────────────────
    rpt_dir = os.path.join(project_dir, f"{model_name}.Report")
    os.makedirs(rpt_dir, exist_ok=True)
    _write_json(os.path.join(rpt_dir, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report"},
        "config": {"logicalId": _slugify(model_name + "_report")},
    })

    rpt_def = os.path.join(rpt_dir, "definition")
    os.makedirs(rpt_def, exist_ok=True)
    _write_json(os.path.join(rpt_def, "report.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
        "version": "4.0",
    })

    # Single empty page
    pages_dir = os.path.join(rpt_def, "pages", "overview")
    os.makedirs(pages_dir, exist_ok=True)
    _write_json(os.path.join(pages_dir, "page.json"), {
        "name": "overview",
        "displayName": "Overview",
        "displayOption": "FitToPage",
        "width": 1280,
        "height": 720,
        "visuals": [],
    })

    # ── .gitignore ───────────────────────────────────────────────
    with open(os.path.join(project_dir, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(".pbi/\n*.pbicache\n")

    logger.info("Shared model generated at %s", project_dir)
    return stats


# ── Helpers ──────────────────────────────────────────────────────


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _slugify(name):
    import re
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name).lower()


def generate_merged_model(project_dirs, output_dir, *, model_name="MergedModel",
                          merge_config_path=None):
    """Merge N intermediate-JSON project directories into one shared model.

    1. Runs merge assessment for overlap/conflicts.
    2. Applies merge config (renames, conflict resolution).
    3. Generates a unified shared semantic model.

    Args:
        project_dirs: list of paths to intermediate-JSON directories.
        output_dir: Root output directory.
        model_name: Display name for the merged model.
        merge_config_path: Optional path to merge-config.json.

    Returns:
        dict with merge_assessment and generation stats.
    """
    from powerbi_import.merge_assessment import run_merge_assessment, load_project_data
    from powerbi_import.merge_config import load_merge_config, merge_project_data
    from powerbi_import.merge_report_html import generate_merge_report

    # Step 1: Assessment
    assessment = run_merge_assessment(project_dirs)

    # Step 2: Report
    report_path = os.path.join(output_dir, "merge_report.html")
    generate_merge_report(assessment, report_path)

    # Step 3: Merge data
    config = load_merge_config(merge_config_path)
    projects = []
    for d in project_dirs:
        name = os.path.basename(d.rstrip("/\\"))
        data = load_project_data(d)
        projects.append((name, data))

    merged_data = merge_project_data(projects, config)

    # Step 4: Generate unified model
    gen_stats = generate_shared_model(merged_data, output_dir, model_name=model_name)

    logger.info("Merged model generated from %d projects", len(project_dirs))
    return {
        "assessment": assessment,
        "generation": gen_stats,
        "report_path": report_path,
    }
