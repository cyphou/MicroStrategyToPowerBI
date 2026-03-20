"""
Merge configuration — user-configurable rules for resolving name
conflicts, aliasing objects, and controlling merge behaviour.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = {
    "conflict_resolution": "keep_first",
    "renames": {},
    "aliases": {},
    "excluded_objects": [],
    "preferred_project": None,
    "merge_rls": True,
    "merge_hierarchies": True,
}


def load_merge_config(path):
    """Load merge configuration from a JSON file.

    Args:
        path: Path to a merge-config.json file.

    Returns:
        Validated config dict with defaults applied.
    """
    config = dict(_DEFAULT_CONFIG)
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
        logger.info("Loaded merge config from %s", path)
    else:
        logger.info("Using default merge configuration")
    return config


def apply_renames(data, renames):
    """Apply rename rules to project data.

    Args:
        data: project data dict (attributes, metrics, etc.)
        renames: dict mapping old_name → new_name

    Returns:
        Modified data dict with renames applied.
    """
    if not renames:
        return data

    for category in ("attributes", "metrics", "derived_metrics", "facts"):
        items = data.get(category, [])
        for item in items:
            name = item.get("name", "")
            if name in renames:
                item["original_name"] = name
                item["name"] = renames[name]
                logger.debug("Renamed %s '%s' → '%s'", category, name, renames[name])

    return data


def resolve_conflicts(objects_by_project, config):
    """Resolve naming conflicts across projects using config rules.

    Args:
        objects_by_project: dict mapping object_name → [(project, definition), ...]
        config: merge configuration dict

    Returns:
        list of resolved objects (deduplicated).
    """
    strategy = config.get("conflict_resolution", "keep_first")
    preferred = config.get("preferred_project")
    resolved = []

    for name, entries in objects_by_project.items():
        if len(entries) == 1:
            resolved.append(entries[0][1])
            continue

        if preferred:
            pref_entries = [e for e in entries if e[0] == preferred]
            if pref_entries:
                resolved.append(pref_entries[0][1])
                continue

        if strategy == "keep_first":
            resolved.append(entries[0][1])
        elif strategy == "keep_last":
            resolved.append(entries[-1][1])
        elif strategy == "keep_all":
            for proj, defn in entries:
                suffixed = dict(defn)
                suffixed["name"] = f"{defn.get('name', '')}_{proj}"
                resolved.append(suffixed)
        else:
            resolved.append(entries[0][1])

    return resolved


def merge_project_data(projects, config):
    """Merge N project data dicts into a single unified data dict.

    Args:
        projects: list of (project_name, data_dict) tuples.
        config: merge configuration dict.

    Returns:
        Merged data dict suitable for generation.
    """
    excluded = set(config.get("excluded_objects", []))
    renames = config.get("renames", {})
    merged = {}

    # Categories that can be simply concatenated after dedup
    list_categories = [
        "attributes", "facts", "metrics", "derived_metrics", "reports",
        "dossiers", "cubes", "filters", "prompts", "custom_groups",
        "consolidations", "hierarchies", "relationships", "security_filters",
        "freeform_sql", "thresholds", "subtotals",
    ]

    for cat in list_categories:
        objects_by_name = {}
        for proj_name, data in projects:
            renamed_data = apply_renames(dict(data), renames)
            for item in renamed_data.get(cat, []):
                name = item.get("name", item.get("id", ""))
                if name in excluded:
                    continue
                if name not in objects_by_name:
                    objects_by_name[name] = []
                objects_by_name[name].append((proj_name, item))

        merged[cat] = resolve_conflicts(objects_by_name, config)

    # Datasources — merge by connection string dedup
    ds_by_conn = {}
    for proj_name, data in projects:
        for ds in data.get("datasources", []):
            key = ds.get("connection_string", ds.get("name", proj_name))
            if key not in ds_by_conn:
                ds_by_conn[key] = ds
            else:
                # Merge tables from additional datasources
                existing_tables = {t.get("name") for t in ds_by_conn[key].get("tables", [])}
                for t in ds.get("tables", []):
                    if t.get("name") not in existing_tables:
                        ds_by_conn[key].setdefault("tables", []).append(t)
    merged["datasources"] = list(ds_by_conn.values())

    logger.info(
        "Merged %d projects: %d metrics, %d attributes, %d reports",
        len(projects),
        len(merged.get("metrics", [])) + len(merged.get("derived_metrics", [])),
        len(merged.get("attributes", [])),
        len(merged.get("reports", [])),
    )
    return merged


def generate_default_config(output_path):
    """Generate a template merge-config.json file.

    Args:
        output_path: Where to write the config template.
    """
    template = {
        "conflict_resolution": "keep_first",
        "renames": {
            "# OldMetricName": "NewMetricName"
        },
        "aliases": {},
        "excluded_objects": [],
        "preferred_project": None,
        "merge_rls": True,
        "merge_hierarchies": True,
    }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    logger.info("Default merge config written to %s", output_path)
