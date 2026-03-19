"""
Incremental migration support.

Tracks which MicroStrategy objects have been migrated, their versions,
and enables delta-only re-runs. State is persisted in a JSON file
alongside the output artifacts.
"""

import hashlib
import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_STATE_FILE = "migration_state.json"


class MigrationState:
    """Tracks migration state for incremental runs.

    State structure:
    {
        "version": 1,
        "created": "ISO timestamp",
        "updated": "ISO timestamp",
        "objects": {
            "<object_type>:<object_id>": {
                "name": "...",
                "type": "report|dossier|cube|metric|...",
                "hash": "sha256 of source definition",
                "migrated_at": "ISO timestamp",
                "fidelity": "full|approximated|manual_review",
                "output_path": "relative path to generated .pbip"
            }
        }
    }
    """

    def __init__(self, state_dir):
        self._path = os.path.join(state_dir, _STATE_FILE)
        self._data = self._load()

    def _load(self):
        """Load existing state or create empty."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Corrupted state file, starting fresh: %s", e)
        return {
            "version": 1,
            "created": _now_iso(),
            "updated": _now_iso(),
            "objects": {},
        }

    def save(self):
        """Persist state to disk."""
        self._data["updated"] = _now_iso()
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        logger.debug("State saved: %d objects tracked", len(self._data["objects"]))

    def object_key(self, obj_type, obj_id):
        """Build a canonical key for an object."""
        return f"{obj_type}:{obj_id}"

    def is_changed(self, obj_type, obj_id, definition):
        """Check if an object has changed since last migration.

        Args:
            obj_type: "report", "dossier", "cube", etc.
            obj_id: MicroStrategy object ID
            definition: dict — the full object definition from extraction

        Returns:
            True if the object is new or has changed.
        """
        key = self.object_key(obj_type, obj_id)
        new_hash = _hash_definition(definition)

        existing = self._data["objects"].get(key)
        if existing is None:
            return True
        return existing.get("hash") != new_hash

    def mark_migrated(self, obj_type, obj_id, name, definition,
                      fidelity="full", output_path=""):
        """Record that an object has been successfully migrated."""
        key = self.object_key(obj_type, obj_id)
        self._data["objects"][key] = {
            "name": name,
            "type": obj_type,
            "hash": _hash_definition(definition),
            "migrated_at": _now_iso(),
            "fidelity": fidelity,
            "output_path": output_path,
        }

    def mark_removed(self, obj_type, obj_id):
        """Remove an object from tracking (e.g. deleted in source)."""
        key = self.object_key(obj_type, obj_id)
        self._data["objects"].pop(key, None)

    def get_changed_objects(self, objects, obj_type):
        """Filter a list of objects to only those that have changed.

        Args:
            objects: list of dicts with at least "id" key
            obj_type: "report", "dossier", etc.

        Returns:
            list of objects that are new or changed
        """
        changed = []
        for obj in objects:
            obj_id = obj.get("id", "")
            if self.is_changed(obj_type, obj_id, obj):
                changed.append(obj)
        return changed

    def get_stale_objects(self, current_ids, obj_type):
        """Find objects in state that no longer exist in the source.

        Args:
            current_ids: set of object IDs currently in the project
            obj_type: "report", "dossier", etc.

        Returns:
            list of (key, entry) tuples for stale objects
        """
        stale = []
        prefix = f"{obj_type}:"
        for key, entry in self._data["objects"].items():
            if key.startswith(prefix):
                obj_id = key[len(prefix):]
                if obj_id not in current_ids:
                    stale.append((key, entry))
        return stale

    @property
    def total_tracked(self):
        return len(self._data["objects"])

    @property
    def summary(self):
        """Return a summary dict of tracked objects by type."""
        by_type = {}
        for entry in self._data["objects"].values():
            t = entry.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        return by_type

    def to_dict(self):
        return dict(self._data)


def _hash_definition(definition):
    """Compute a stable hash of an object definition."""
    raw = json.dumps(definition, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()
