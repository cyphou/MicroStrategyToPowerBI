"""
.pbip project assembler.

Creates the full .pbip folder structure:
    <ReportName>.pbip
    <ReportName>.SemanticModel/
        .platform
        definition.pbism
        definition/
            model.tmdl            (auto-generated header)
            tables/<Table>.tmdl
            relationships.tmdl
            roles.tmdl
    <ReportName>.Report/
        .platform
        definition/
            report.json           (PBIR v4.0 manifest)
            pages/<pageId>/
                page.json         (visual JSON per page)
"""

import json
import os
import logging

from powerbi_import.tmdl_generator import (
    generate_all_tmdl,
    generate_calendar_table_tmdl,
)
from powerbi_import.visual_generator import generate_all_visuals

logger = logging.getLogger(__name__)

# ── Schema URIs ──────────────────────────────────────────────────

_PLATFORM_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/"
    "gitIntegration/platformProperties/2.0.0/schema.json"
)
_PBISM_VERSION = "4.0"
_PBIP_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/"
    "item/report/definition/report/1.0.0/schema.json"
)


# ── Public API ───────────────────────────────────────────────────

def generate_pbip(data, output_dir, report_name="MicroStrategy Report"):
    """Assemble a complete .pbip project from intermediate JSON data.

    Args:
        data: dict with all 18 intermediate JSON keys
        output_dir: root directory to write project into
        report_name: name used for project folders and manifest IDs

    Returns:
        dict with combined generation statistics
    """
    os.makedirs(output_dir, exist_ok=True)
    logical_id = _slugify(report_name)

    stats = {
        "tables": 0,
        "columns": 0,
        "measures": 0,
        "relationships": 0,
        "hierarchies": 0,
        "roles": 0,
        "pages": 0,
        "visuals": 0,
        "slicers": 0,
        "unsupported_visuals": 0,
        "warnings": [],
    }

    # ── 1. Semantic Model ────────────────────────────────────────
    sm_root = os.path.join(output_dir, f"{report_name}.SemanticModel")
    sm_def = os.path.join(sm_root, "definition")

    tmdl_stats = generate_all_tmdl(data, sm_def)
    _merge_stats(stats, tmdl_stats)

    # Calendar table
    date_cols = _detect_date_columns(data)
    if date_cols:
        cal_tmdl = generate_calendar_table_tmdl(date_cols)
        cal_path = os.path.join(sm_def, "tables", "Calendar.tmdl")
        os.makedirs(os.path.dirname(cal_path), exist_ok=True)
        with open(cal_path, "w", encoding="utf-8") as f:
            f.write(cal_tmdl)
        stats["tables"] += 1

    # model.tmdl header
    _write_model_tmdl(sm_def, report_name)

    # Manifests
    _write_platform(sm_root, "SemanticModel", logical_id + "-sm")
    _write_pbism(sm_root)

    # ── 2. Report ────────────────────────────────────────────────
    rpt_root = os.path.join(output_dir, f"{report_name}.Report")
    rpt_def = os.path.join(rpt_root, "definition")

    visual_stats = generate_all_visuals(data, rpt_def)
    stats["pages"] = visual_stats.get("pages", 0)
    stats["visuals"] = visual_stats.get("visuals", 0)
    stats["slicers"] = visual_stats.get("slicers", 0)
    stats["unsupported_visuals"] = visual_stats.get("unsupported", 0)

    _write_platform(rpt_root, "Report", logical_id + "-rpt")

    # ── 3. .pbip entry-point file ────────────────────────────────
    _write_pbip_file(output_dir, report_name)

    # ── 4. .gitignore ────────────────────────────────────────────
    _write_gitignore(output_dir)

    logger.info(
        "PBIP project generated: %d tables, %d measures, %d pages, %d visuals",
        stats["tables"], stats["measures"], stats["pages"], stats["visuals"],
    )
    return stats


# ── Scaffold writers ─────────────────────────────────────────────

def _write_platform(folder, item_type, logical_id):
    """Write .platform JSON."""
    os.makedirs(folder, exist_ok=True)
    platform = {
        "$schema": _PLATFORM_SCHEMA,
        "metadata": {"type": item_type},
        "config": {"logicalId": logical_id},
    }
    path = os.path.join(folder, ".platform")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(platform, f, indent=2)


def _write_pbism(sm_root):
    """Write definition.pbism manifest."""
    manifest = {"version": _PBISM_VERSION, "settings": {}}
    path = os.path.join(sm_root, "definition.pbism")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _write_model_tmdl(definition_dir, report_name):
    """Write model.tmdl header file."""
    content = (
        f"model Model\n"
        f"\tculture: en-US\n"
        f"\tdescription: Migrated from MicroStrategy — {report_name}\n"
    )
    path = os.path.join(definition_dir, "model.tmdl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_pbip_file(output_dir, report_name):
    """Write the <name>.pbip entry-point JSON file."""
    pbip = {
        "version": "1.0",
        "artifacts": [
            {
                "report": {"path": f"{report_name}.Report"},
                "semanticModel": {"path": f"{report_name}.SemanticModel"},
            }
        ],
    }
    path = os.path.join(output_dir, f"{report_name}.pbip")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pbip, f, indent=2)


def _write_gitignore(output_dir):
    """Write a .gitignore suitable for .pbip projects."""
    content = (
        "# Power BI project ignores\n"
        ".pbi/\n"
        "*.pbix\n"
        "*.bak\n"
    )
    path = os.path.join(output_dir, ".gitignore")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Helpers ──────────────────────────────────────────────────────

def _slugify(name):
    """Convert a display name to a safe logical ID."""
    return name.lower().replace(" ", "-").replace("_", "-")


def _detect_date_columns(data):
    """Find (table_name, column_name) pairs with date types."""
    date_cols = []
    for ds in data.get("datasources", []):
        for col in ds.get("columns", []):
            if col.get("data_type", "").lower() in ("date", "datetime", "timestamp"):
                date_cols.append((ds["name"], col["name"]))
    return date_cols


def _merge_stats(dst, src):
    """Merge TMDL stats into the combined stats dict."""
    for key in ("tables", "columns", "measures", "relationships",
                "hierarchies", "roles"):
        dst[key] = src.get(key, 0)
    dst["warnings"].extend(src.get("warnings", []))
