"""
Change detector for MicroStrategy objects.

Polls the MicroStrategy REST API (or compares intermediate JSON files)
to detect objects that have been added, modified, or deleted since the
last migration run.  Produces a *change manifest* consumed by the
reconciler and drift report modules.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_MANIFEST_FILE = "change_manifest.json"

# Object types that are tracked for changes
_TRACKED_TYPES = [
    "reports",
    "dossiers",
    "cubes",
    "metrics",
    "derived_metrics",
    "attributes",
    "facts",
    "filters",
    "prompts",
    "hierarchies",
    "security_filters",
    "custom_groups",
    "consolidations",
]


def _hash_object(obj):
    """Stable SHA-256 hash of a JSON-serialisable object."""
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_json(path):
    """Load a JSON file, returning an empty list on failure."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load %s: %s", path, exc)
        return []


def _index_objects(objects):
    """Build {id: object} lookup, falling back to name if id missing."""
    index = {}
    for obj in objects:
        key = obj.get("id") or obj.get("name", "")
        if key:
            index[key] = obj
    return index


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def detect_changes(current_dir, previous_dir):
    """Compare two sets of intermediate JSON files and return a manifest.

    Args:
        current_dir:  Path to the *current* extraction output directory.
        previous_dir: Path to the *previous* extraction output directory.

    Returns:
        dict with keys ``added``, ``modified``, ``deleted``, ``unchanged``,
        each mapping to a list of ``{type, id, name}`` entries, plus a
        ``summary`` dict with counts.
    """
    added = []
    modified = []
    deleted = []
    unchanged = []

    for obj_type in _TRACKED_TYPES:
        filename = f"{obj_type}.json"
        current_objects = _load_json(os.path.join(current_dir, filename))
        previous_objects = _load_json(os.path.join(previous_dir, filename))

        cur_index = _index_objects(current_objects)
        prev_index = _index_objects(previous_objects)

        # Added or modified
        for key, obj in cur_index.items():
            entry = {
                "type": obj_type,
                "id": key,
                "name": obj.get("name", key),
            }
            if key not in prev_index:
                added.append(entry)
            elif _hash_object(obj) != _hash_object(prev_index[key]):
                modified.append(entry)
            else:
                unchanged.append(entry)

        # Deleted
        for key, obj in prev_index.items():
            if key not in cur_index:
                deleted.append({
                    "type": obj_type,
                    "id": key,
                    "name": obj.get("name", key),
                })

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_dir": current_dir,
        "previous_dir": previous_dir,
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "unchanged": unchanged,
        "summary": {
            "added": len(added),
            "modified": len(modified),
            "deleted": len(deleted),
            "unchanged": len(unchanged),
            "total_current": len(added) + len(modified) + len(unchanged),
            "total_previous": len(modified) + len(deleted) + len(unchanged),
        },
    }
    logger.info(
        "Change detection complete: +%d ~%d -%d =%d",
        len(added), len(modified), len(deleted), len(unchanged),
    )
    return manifest


def save_manifest(manifest, output_dir):
    """Write the change manifest to *output_dir*."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _MANIFEST_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info("Change manifest saved to %s", path)
    return path


def load_manifest(output_dir):
    """Load a previously saved change manifest."""
    path = os.path.join(output_dir, _MANIFEST_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_changes_from_api(client, project_id, since_timestamp, output_dir):
    """Detect changes by querying MicroStrategy REST API modification dates.

    Args:
        client:          ``MstrRestClient`` instance (authenticated).
        project_id:      MicroStrategy project ID.
        since_timestamp: ISO-8601 timestamp — only objects modified after
                         this point are considered changed.
        output_dir:      Directory to write the manifest.

    Returns:
        Change manifest dict.
    """
    modified_objects = []
    cutoff = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))

    # Query the search API for recently modified objects
    search_types = [3, 55, 21, 4]  # report, dossier, cube, metric
    type_names = {3: "reports", 55: "dossiers", 21: "cubes", 4: "metrics"}

    for obj_type_id in search_types:
        try:
            results = client.search_objects(
                project_id=project_id,
                object_type=obj_type_id,
                limit=1000,
            )
        except Exception as exc:
            logger.warning(
                "Could not query type %d: %s", obj_type_id, exc
            )
            continue

        for obj in results:
            mod_date_str = obj.get("modificationTime", obj.get("dateModified", ""))
            if not mod_date_str:
                continue
            try:
                mod_date = datetime.fromisoformat(
                    mod_date_str.replace("Z", "+00:00")
                )
            except ValueError:
                continue
            if mod_date > cutoff:
                modified_objects.append({
                    "type": type_names.get(obj_type_id, str(obj_type_id)),
                    "id": obj.get("id", ""),
                    "name": obj.get("name", ""),
                    "modified_at": mod_date_str,
                })

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "api",
        "project_id": project_id,
        "since": since_timestamp,
        "added": [],
        "modified": modified_objects,
        "deleted": [],
        "unchanged": [],
        "summary": {
            "added": 0,
            "modified": len(modified_objects),
            "deleted": 0,
            "unchanged": 0,
            "total_current": len(modified_objects),
            "total_previous": 0,
        },
    }
    if output_dir:
        save_manifest(manifest, output_dir)
    logger.info("API change detection: %d modified objects since %s",
                len(modified_objects), since_timestamp)
    return manifest
