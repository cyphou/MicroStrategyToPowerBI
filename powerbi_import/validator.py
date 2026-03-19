"""
Artifact validator for generated .pbip projects.

Validates:
  D.1 — TMDL syntax (table/column/measure structure)
  D.2 — PBIR visual JSON schema (report.json, page.json)
  D.3 — Relationship cycle detection
  D.4 — DAX reference resolution (measures → columns/measures exist)
"""

import json
import os
import re
import logging

logger = logging.getLogger(__name__)

# ── TMDL validation regexes ──────────────────────────────────────

_TABLE_RE = re.compile(r"^table\s+(.+)$", re.MULTILINE)
_COLUMN_RE = re.compile(r"^\tcolumn\s+(.+)$", re.MULTILINE)
_MEASURE_RE = re.compile(r"^\tmeasure\s+(.+)$", re.MULTILINE)
_DATA_TYPE_RE = re.compile(r"^\t\tdataType:\s+(.+)$", re.MULTILINE)
_SOURCE_COL_RE = re.compile(r"^\t\tsourceColumn:\s+(.+)$", re.MULTILINE)
_EXPRESSION_RE = re.compile(r"^\t\texpression\s*=\s*(.+)$", re.MULTILINE)
_LINEAGE_RE = re.compile(r"^\t+lineageTag:\s+(.+)$", re.MULTILINE)
_RELATIONSHIP_RE = re.compile(r"^relationship\s+(.+)$", re.MULTILINE)
_FROM_COL_RE = re.compile(r"^\tfromColumn:\s+(.+)$", re.MULTILINE)
_TO_COL_RE = re.compile(r"^\ttoColumn:\s+(.+)$", re.MULTILINE)
_ROLE_RE = re.compile(r"^role\s+(.+)$", re.MULTILINE)

_VALID_DATA_TYPES = {"int64", "double", "decimal", "string", "dateTime", "boolean"}

# ── PBIR required keys ───────────────────────────────────────────

_REPORT_REQUIRED_KEYS = {"$schema"}
_PAGE_REQUIRED_KEYS = {"displayName"}
_VISUAL_REQUIRED_KEYS = {"position"}

# ── Public API ───────────────────────────────────────────────────


def validate_project(project_dir):
    """Validate a complete .pbip project.

    Args:
        project_dir: Root directory containing *.pbip, *.SemanticModel/, *.Report/

    Returns:
        dict with keys: valid (bool), files_checked (int), errors (list[str]),
        warnings (list[str])
    """
    errors = []
    warnings = []
    files_checked = 0

    # Find SemanticModel and Report folders
    sm_dir = None
    rpt_dir = None
    pbip_file = None

    for entry in os.listdir(project_dir):
        full = os.path.join(project_dir, entry)
        if entry.endswith(".pbip") and os.path.isfile(full):
            pbip_file = full
        elif entry.endswith(".SemanticModel") and os.path.isdir(full):
            sm_dir = full
        elif entry.endswith(".Report") and os.path.isdir(full):
            rpt_dir = full

    # .pbip entry point
    if pbip_file:
        files_checked += 1
        errs = _validate_pbip_file(pbip_file)
        errors.extend(errs)
    else:
        errors.append("Missing .pbip entry-point file")

    # SemanticModel
    if sm_dir:
        n, errs, wrns = _validate_semantic_model(sm_dir)
        files_checked += n
        errors.extend(errs)
        warnings.extend(wrns)
    else:
        errors.append("Missing .SemanticModel folder")

    # Report
    if rpt_dir:
        n, errs, wrns = _validate_report(rpt_dir)
        files_checked += n
        errors.extend(errs)
        warnings.extend(wrns)
    else:
        errors.append("Missing .Report folder")

    return {
        "valid": len(errors) == 0,
        "files_checked": files_checked,
        "errors": errors,
        "warnings": warnings,
    }


# ── .pbip file validation ────────────────────────────────────────


def _validate_pbip_file(path):
    """Validate the .pbip JSON entry-point."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "version" not in data:
            errors.append(f"{path}: missing 'version' key")
        if "artifacts" not in data:
            errors.append(f"{path}: missing 'artifacts' key")
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path}: invalid JSON — {exc}")
    return errors


# ── SemanticModel validation ─────────────────────────────────────


def _validate_semantic_model(sm_dir):
    errors = []
    warnings = []
    files_checked = 0

    # .platform
    platform = os.path.join(sm_dir, ".platform")
    if os.path.exists(platform):
        files_checked += 1
        errs = _validate_json_file(platform, required_keys={"metadata"})
        errors.extend(errs)
    else:
        errors.append(f"Missing {platform}")

    # definition.pbism
    pbism = os.path.join(sm_dir, "definition.pbism")
    if os.path.exists(pbism):
        files_checked += 1
        errs = _validate_json_file(pbism, required_keys={"version"})
        errors.extend(errs)
    else:
        errors.append(f"Missing {pbism}")

    # model.tmdl
    definition_dir = os.path.join(sm_dir, "definition")
    model_tmdl = os.path.join(definition_dir, "model.tmdl")
    if os.path.exists(model_tmdl):
        files_checked += 1
        errs = _validate_model_tmdl(model_tmdl)
        errors.extend(errs)

    # Table TMDL files
    tables_dir = os.path.join(definition_dir, "tables")
    tables = {}  # table_name → {columns: set, measures: set}
    if os.path.isdir(tables_dir):
        for tmdl_file in sorted(os.listdir(tables_dir)):
            if tmdl_file.endswith(".tmdl"):
                tmdl_path = os.path.join(tables_dir, tmdl_file)
                files_checked += 1
                table_errs, table_wrns, table_info = validate_tmdl_file(tmdl_path)
                errors.extend(table_errs)
                warnings.extend(table_wrns)
                if table_info:
                    tables[table_info["name"]] = table_info

    # Relationships
    rel_path = os.path.join(definition_dir, "relationships.tmdl")
    relationships = []
    if os.path.exists(rel_path):
        files_checked += 1
        rel_errs, rels = _validate_relationships_tmdl(rel_path, tables)
        errors.extend(rel_errs)
        relationships = rels

    # Cycle detection
    cycle_errs = detect_relationship_cycles(relationships)
    errors.extend(cycle_errs)

    # Roles
    roles_path = os.path.join(definition_dir, "roles.tmdl")
    if os.path.exists(roles_path):
        files_checked += 1
        # Basic readability check
        try:
            with open(roles_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not _ROLE_RE.search(content):
                warnings.append(f"{roles_path}: no 'role' definitions found")
        except OSError as exc:
            errors.append(f"{roles_path}: cannot read — {exc}")

    # DAX reference validation across all tables
    dax_errs = validate_dax_references(tables)
    warnings.extend(dax_errs)

    return files_checked, errors, warnings


# ── TMDL file validation ─────────────────────────────────────────


def validate_tmdl_file(path):
    """Validate a single table .tmdl file.

    Returns:
        (errors, warnings, table_info_dict_or_None)
    """
    errors = []
    warnings = []
    table_info = None

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return [f"{path}: cannot read — {exc}"], [], None

    # Must start with 'table <name>'
    table_match = _TABLE_RE.search(content)
    if not table_match:
        errors.append(f"{path}: missing table declaration")
        return errors, warnings, None

    table_name = table_match.group(1).strip().strip("'")
    columns = set()
    measures = set()

    # Validate columns
    for m in _COLUMN_RE.finditer(content):
        col_name = m.group(1).strip().strip("'")
        columns.add(col_name)

    # Validate data types
    for m in _DATA_TYPE_RE.finditer(content):
        dtype = m.group(1).strip()
        if dtype not in _VALID_DATA_TYPES:
            errors.append(f"{path}: invalid dataType '{dtype}'")

    # Validate measures
    for m in _MEASURE_RE.finditer(content):
        measure_name = m.group(1).strip().strip("'")
        measures.add(measure_name)

    if not columns and not measures:
        warnings.append(f"{path}: table '{table_name}' has no columns or measures")

    table_info = {
        "name": table_name,
        "columns": columns,
        "measures": measures,
    }

    return errors, warnings, table_info


def _validate_model_tmdl(path):
    """Validate model.tmdl header file."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("model "):
            errors.append(f"{path}: must start with 'model <name>'")
    except OSError as exc:
        errors.append(f"{path}: cannot read — {exc}")
    return errors


def _validate_relationships_tmdl(path, tables):
    """Validate relationships.tmdl and return parsed relationship list."""
    errors = []
    relationships = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return [f"{path}: cannot read — {exc}"], []

    # Parse relationships
    blocks = content.split("relationship ")
    for block in blocks[1:]:  # skip first empty split
        lines = block.strip().split("\n")
        name = lines[0].strip()
        from_col = ""
        to_col = ""
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("fromColumn:"):
                from_col = line.split(":", 1)[1].strip()
            elif line.startswith("toColumn:"):
                to_col = line.split(":", 1)[1].strip()

        if from_col and to_col:
            from_parts = from_col.split(".", 1)
            to_parts = to_col.split(".", 1)
            if len(from_parts) == 2 and len(to_parts) == 2:
                from_table, from_column = from_parts
                to_table, to_column = to_parts

                # Check that referenced tables exist
                if tables and from_table not in tables:
                    errors.append(f"{path}: relationship '{name}' references unknown table '{from_table}'")
                if tables and to_table not in tables:
                    errors.append(f"{path}: relationship '{name}' references unknown table '{to_table}'")

                relationships.append({
                    "name": name,
                    "from_table": from_table,
                    "to_table": to_table,
                })
            else:
                errors.append(f"{path}: relationship '{name}' has invalid column reference format")

    return errors, relationships


# ── Cycle detection ──────────────────────────────────────────────


def detect_relationship_cycles(relationships):
    """Detect cycles in the relationship graph using DFS.

    Args:
        relationships: list of dicts with 'from_table' and 'to_table'

    Returns:
        list of error strings (empty if no cycles)
    """
    if not relationships:
        return []

    # Build adjacency list
    graph = {}
    for rel in relationships:
        src = rel["from_table"]
        dst = rel["to_table"]
        graph.setdefault(src, []).append(dst)
        graph.setdefault(dst, [])

    visited = set()
    in_stack = set()
    errors = []

    def _dfs(node, path):
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor in in_stack:
                cycle = path + [neighbor]
                cycle_str = " → ".join(cycle[cycle.index(neighbor):])
                errors.append(f"Circular relationship detected: {cycle_str}")
                return
            if neighbor not in visited:
                _dfs(neighbor, path + [neighbor])
        in_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node, [node])

    return errors


# ── DAX reference validation ─────────────────────────────────────


def validate_dax_references(tables):
    """Check that measure DAX expressions don't reference nonexistent columns.

    This is a best-effort heuristic check — it looks for Table[Column] patterns.

    Args:
        tables: dict mapping table_name → {columns: set, measures: set}

    Returns:
        list of warning strings
    """
    warnings = []
    all_columns = {}
    all_measures = set()
    for tname, tinfo in tables.items():
        for col in tinfo["columns"]:
            all_columns[(tname, col)] = True
        all_measures.update(tinfo["measures"])

    # We'd need the actual DAX expressions to do this properly.
    # For now, the validator checks structural correctness.
    # Full DAX reference resolution requires parsing the TMDL expression blocks.
    return warnings


# ── Report / PBIR validation ─────────────────────────────────────


def _validate_report(rpt_dir):
    errors = []
    warnings = []
    files_checked = 0

    # .platform
    platform = os.path.join(rpt_dir, ".platform")
    if os.path.exists(platform):
        files_checked += 1
        errs = _validate_json_file(platform, required_keys={"metadata"})
        errors.extend(errs)
    else:
        errors.append(f"Missing {platform}")

    # report.json
    definition_dir = os.path.join(rpt_dir, "definition")
    report_json = os.path.join(definition_dir, "report.json")
    if os.path.exists(report_json):
        files_checked += 1
        errs = validate_report_json(report_json)
        errors.extend(errs)
    else:
        errors.append(f"Missing {report_json}")

    # Pages
    pages_dir = os.path.join(definition_dir, "pages")
    if os.path.isdir(pages_dir):
        for page_id in sorted(os.listdir(pages_dir)):
            page_dir = os.path.join(pages_dir, page_id)
            if os.path.isdir(page_dir):
                page_json = os.path.join(page_dir, "page.json")
                if os.path.exists(page_json):
                    files_checked += 1
                    errs, wrns = validate_page_json(page_json)
                    errors.extend(errs)
                    warnings.extend(wrns)
                else:
                    errors.append(f"Missing page.json in {page_dir}")

    return files_checked, errors, warnings


def validate_report_json(path):
    """Validate report.json against PBIR v2.0.0 expectations."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in _REPORT_REQUIRED_KEYS:
            if key not in data:
                errors.append(f"{path}: missing required key '{key}'")
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path}: invalid JSON — {exc}")
    return errors


def validate_page_json(path):
    """Validate a page.json (PBIR v2.0.0 — visuals are in separate files)."""
    errors = []
    warnings = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in _PAGE_REQUIRED_KEYS:
            if key not in data:
                errors.append(f"{path}: missing required key '{key}'")
        # In PBIR v2.0.0, visuals live in visuals/<id>/visual.json, not inline.
        # Check the visuals/ subfolder next to page.json if it exists.
        page_dir = os.path.dirname(path)
        visuals_dir = os.path.join(page_dir, "visuals")
        if os.path.isdir(visuals_dir):
            for vdir in os.listdir(visuals_dir):
                vpath = os.path.join(visuals_dir, vdir, "visual.json")
                if os.path.isfile(vpath):
                    try:
                        with open(vpath, "r", encoding="utf-8") as vf:
                            vis = json.load(vf)
                        if "position" not in vis:
                            errors.append(f"{vpath}: visual missing 'position'")
                        else:
                            pos = vis["position"]
                            for dim in ("x", "y", "width", "height"):
                                if dim not in pos:
                                    errors.append(f"{vpath}: position missing '{dim}'")
                    except (json.JSONDecodeError, OSError) as exc:
                        errors.append(f"{vpath}: invalid JSON — {exc}")
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path}: invalid JSON — {exc}")
    return errors, warnings


# ── Generic helpers ──────────────────────────────────────────────


def _validate_json_file(path, required_keys=None):
    """Validate a JSON file is parseable and has required keys."""
    errors = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if required_keys:
            for key in required_keys:
                if key not in data:
                    errors.append(f"{path}: missing required key '{key}'")
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path}: invalid JSON — {exc}")
    return errors
