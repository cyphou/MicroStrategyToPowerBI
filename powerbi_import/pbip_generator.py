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
import uuid

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

def generate_pbip(data, output_dir, report_name="MicroStrategy Report", no_calendar=False,
                  direct_lake=False, lakehouse_name=None, cultures=None):
    """Assemble a complete .pbip project from intermediate JSON data.

    Args:
        data: dict with all 18 intermediate JSON keys
        output_dir: root directory to write project into
        report_name: name used for project folders and manifest IDs
        no_calendar: if True, never generate auto Calendar table
        direct_lake: if True, generate DirectLake partitions instead of Import/M
        lakehouse_name: Fabric lakehouse name for DirectLake entity references
        cultures: list of culture codes (e.g. ["en-US", "fr-FR"]). Default: ["en-US"].

    Returns:
        dict with combined generation statistics
    """
    os.makedirs(output_dir, exist_ok=True)
    # Generate deterministic GUIDs for logicalId (Power BI requires System.Guid)
    _ns = uuid.UUID("a3b2c1d0-1234-5678-9abc-def012345678")
    sm_logical_id = str(uuid.uuid5(_ns, report_name + "-sm"))
    rpt_logical_id = str(uuid.uuid5(_ns, report_name + "-rpt"))

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

    tmdl_stats = generate_all_tmdl(data, sm_def, direct_lake=direct_lake,
                                    lakehouse_name=lakehouse_name,
                                    cultures=cultures)
    _merge_stats(stats, tmdl_stats)

    # Calendar table — only if not suppressed and no dedicated date dimension table exists
    date_cols = _detect_date_columns(data)
    if date_cols and not no_calendar and not _has_date_dimension_table(data):
        cal_tmdl = generate_calendar_table_tmdl(date_cols)
        cal_path = os.path.join(sm_def, "tables", "Calendar.tmdl")
        os.makedirs(os.path.dirname(cal_path), exist_ok=True)
        with open(cal_path, "w", encoding="utf-8") as f:
            f.write(cal_tmdl)
        stats["tables"] += 1

    # model.tmdl header
    _write_model_tmdl(sm_def, report_name, data=data, no_calendar=no_calendar,
                      cultures=cultures)

    # Manifests
    _write_platform(sm_root, "SemanticModel", sm_logical_id, display_name=report_name)
    _write_pbism(sm_root)

    # database.tmdl (compatibility level)
    _write_database_tmdl(sm_def)

    # ── 2. Report ────────────────────────────────────────────────
    rpt_root = os.path.join(output_dir, f"{report_name}.Report")
    rpt_def = os.path.join(rpt_root, "definition")

    visual_stats = generate_all_visuals(data, rpt_def, cultures=cultures)
    stats["pages"] = visual_stats.get("pages", 0)
    stats["visuals"] = visual_stats.get("visuals", 0)
    stats["slicers"] = visual_stats.get("slicers", 0)
    stats["unsupported_visuals"] = visual_stats.get("unsupported", 0)

    _write_platform(rpt_root, "Report", rpt_logical_id, display_name=report_name)

    # definition.pbir (links report → semantic model)
    _write_pbir(rpt_root, report_name)

    # version.json
    _write_version_json(rpt_def)

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

def _write_platform(folder, item_type, logical_id, display_name=""):
    """Write .platform JSON."""
    os.makedirs(folder, exist_ok=True)
    platform = {
        "$schema": _PLATFORM_SCHEMA,
        "metadata": {
            "type": item_type,
            "displayName": display_name or logical_id,
        },
        "config": {
            "version": "2.0",
            "logicalId": logical_id,
        },
    }
    path = os.path.join(folder, ".platform")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(platform, f, indent=2)


def _write_pbism(sm_root):
    """Write definition.pbism manifest."""
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {
            "qnaEnabled": True,
        },
    }
    path = os.path.join(sm_root, "definition.pbism")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _write_model_tmdl(definition_dir, report_name, data=None, no_calendar=False,
                      cultures=None):
    """Write model.tmdl header file with ref declarations."""
    from powerbi_import.i18n import get_primary_culture, generate_culture_tmdl, generate_translations_tmdl

    primary = get_primary_culture(cultures)
    lines = [
        "model Model",
        f"\tculture: {primary}",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        f"\tsourceQueryCulture: {primary}",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
    ]

    if data:
        # Collect table names
        table_names = [ds["name"] for ds in data.get("datasources", [])]
        # Add Calendar if date columns exist, not suppressed, and no date dimension table
        date_cols = _detect_date_columns(data)
        if date_cols and not no_calendar and not _has_date_dimension_table(data):
            table_names.append("Calendar")

        if table_names:
            order_str = ",".join(f'"{t}"' for t in table_names)
            lines.append(f"annotation PBI_QueryOrder = [{order_str}]")
            lines.append("")
            for t in table_names:
                ref = f"ref table '{t}'" if " " in t else f"ref table {t}"
                lines.append(ref)
            lines.append("")

        # ref relationship (match names from tmdl_generator)
        for rel in data.get("relationships", []):
            rel_id = rel.get("id", "")
            if rel_id:
                ref_name = rel_id
            else:
                ref_name = f"rel_{rel['from_table']}_{rel['to_table']}"
            lines.append(f"ref relationship {ref_name}")
        if data.get("relationships"):
            lines.append("")

        # ref role (from security filters)
        for sf in data.get("security_filters", []):
            role_name = sf.get("name", "")
            if role_name:
                ref = f"ref role '{role_name}'" if " " in role_name else f"ref role {role_name}"
                lines.append(ref)
        if data.get("security_filters"):
            lines.append("")

    content = "\n".join(lines) + "\n"
    path = os.path.join(definition_dir, "model.tmdl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # Write culture/translation TMDL files for additional cultures
    if cultures and len(cultures) > 1:
        culture_tmdl = generate_culture_tmdl(cultures)
        if culture_tmdl:
            culture_path = os.path.join(definition_dir, "cultures.tmdl")
            with open(culture_path, "w", encoding="utf-8") as f:
                f.write(culture_tmdl)

        translations_tmdl = generate_translations_tmdl(
            cultures,
            data.get("datasources", []) if data else [],
            data.get("metrics", []) + data.get("derived_metrics", []) if data else [],
        )
        if translations_tmdl:
            translations_path = os.path.join(definition_dir, "translations.tmdl")
            with open(translations_path, "w", encoding="utf-8") as f:
                f.write(translations_tmdl)


def _write_pbip_file(output_dir, report_name):
    """Write the <name>.pbip entry-point JSON file."""
    pbip = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [
            {
                "report": {"path": f"{report_name}.Report"},
            }
        ],
        "settings": {
            "enableAutoRecovery": True,
        },
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


_DATE_DIM_PATTERNS = {"date", "calendar", "time", "period"}


def _has_date_dimension_table(data):
    """Check if a dedicated date dimension/lookup table already exists.

    Detects tables with names like LU_DATE, DIM_DATE, DIM_CALENDAR, etc.
    These tables already provide date hierarchy columns, making an
    auto-generated Calendar table redundant.
    """
    for ds in data.get("datasources", []):
        name = ds.get("name", "").upper()
        # Strip common prefixes to get the core name
        for prefix in ("LU_", "DIM_", "D_", "LOOKUP_", "DIM"):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        if name.lower() in _DATE_DIM_PATTERNS:
            return True
    return False


def _write_pbir(rpt_root, report_name):
    """Write definition.pbir — links report to semantic model by path."""
    pbir = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{report_name}.SemanticModel",
            }
        },
    }
    path = os.path.join(rpt_root, "definition.pbir")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pbir, f, indent=2)


def _write_database_tmdl(definition_dir):
    """Write database.tmdl with compatibility level."""
    content = "database\n\tcompatibilityLevel: 1600\n"
    path = os.path.join(definition_dir, "database.tmdl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _write_version_json(rpt_def):
    """Write version.json for report definition."""
    version = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    }
    path = os.path.join(rpt_def, "version.json")
    os.makedirs(rpt_def, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(version, f, indent=2)


def _merge_stats(dst, src):
    """Merge TMDL stats into the combined stats dict."""
    for key in ("tables", "columns", "measures", "relationships",
                "hierarchies", "roles"):
        dst[key] = src.get(key, 0)
    dst["warnings"].extend(src.get("warnings", []))
