"""
Snapshot regression suite.

Generates golden snapshots from migration output and compares subsequent
runs against the baseline to detect unintended regressions.

FF.3 — Snapshot generation and comparison.
FF.4 — Scope: TMDL files, visual JSON, M queries, migration report,
        model.tmdl header.
"""

import hashlib
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)

_SNAPSHOT_DIR = "snapshots"
_MANIFEST_FILE = "snapshot_manifest.json"

# File patterns to snapshot
_SNAPSHOT_PATTERNS = {
    ".tmdl": "tmdl",
    ".json": "json",
    ".m": "m_query",
    ".pq": "m_query",
}


# ── Public API ───────────────────────────────────────────────────

def generate_snapshots(project_dir, snapshot_dir=None):
    """Generate golden snapshots from a .pbip project directory.

    Args:
        project_dir:  Root of the generated .pbip output.
        snapshot_dir: Where to store snapshots.  Defaults to
                      ``project_dir/_snapshots/``.

    Returns:
        dict manifest: ``{files: [{path, hash, category}], generated_at}``.
    """
    if snapshot_dir is None:
        snapshot_dir = os.path.join(project_dir, _SNAPSHOT_DIR)

    os.makedirs(snapshot_dir, exist_ok=True)
    entries = []

    for dirpath, _dirs, filenames in os.walk(project_dir):
        # Don't snapshot our own snapshot directory
        if os.path.abspath(dirpath).startswith(os.path.abspath(snapshot_dir)):
            continue
        for fname in sorted(filenames):
            _, ext = os.path.splitext(fname)
            category = _SNAPSHOT_PATTERNS.get(ext.lower())
            if category is None:
                continue

            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, project_dir).replace("\\", "/")
            content_hash = _hash_file(full)

            # Copy to snapshot dir (preserving relative path)
            dest = os.path.join(snapshot_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(full, dest)

            entries.append({
                "path": rel,
                "hash": content_hash,
                "category": category,
            })

    manifest = {
        "generated_at": _now_iso(),
        "project_dir": project_dir,
        "file_count": len(entries),
        "files": entries,
    }
    manifest_path = os.path.join(snapshot_dir, _MANIFEST_FILE)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("Generated %d snapshots in %s", len(entries), snapshot_dir)
    return manifest


def compare_snapshots(project_dir, snapshot_dir):
    """Compare current project output against stored snapshots.

    Args:
        project_dir:  Current .pbip output directory.
        snapshot_dir: Directory containing golden snapshots.

    Returns:
        dict with ``drifted``, ``added``, ``removed``, ``unchanged``,
        ``summary``.
    """
    manifest_path = os.path.join(snapshot_dir, _MANIFEST_FILE)
    if not os.path.exists(manifest_path):
        return {
            "error": "No snapshot manifest found",
            "drifted": [],
            "added": [],
            "removed": [],
            "unchanged": [],
            "summary": {"drifted": 0, "added": 0, "removed": 0, "unchanged": 0},
        }

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    baseline = {e["path"]: e["hash"] for e in manifest.get("files", [])}
    current = _collect_current(project_dir, snapshot_dir)

    drifted = []
    added = []
    removed = []
    unchanged = []

    for path, cur_hash in current.items():
        if path not in baseline:
            added.append({"path": path, "category": _categorise(path)})
        elif cur_hash != baseline[path]:
            drifted.append({"path": path, "category": _categorise(path)})
        else:
            unchanged.append({"path": path})

    for path in baseline:
        if path not in current:
            removed.append({"path": path, "category": _categorise(path)})

    return {
        "compared_at": _now_iso(),
        "drifted": drifted,
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "summary": {
            "drifted": len(drifted),
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
        },
    }


def update_snapshots(project_dir, snapshot_dir):
    """Re-baseline snapshots from current project output.

    This replaces the existing snapshots with the current output.

    Returns:
        New manifest dict.
    """
    if os.path.isdir(snapshot_dir):
        shutil.rmtree(snapshot_dir)
    return generate_snapshots(project_dir, snapshot_dir)


# ── Helpers ──────────────────────────────────────────────────────

def _hash_file(path):
    """SHA-256 of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_current(project_dir, snapshot_dir):
    """Collect {rel_path: hash} for tracked files under *project_dir*."""
    result = {}
    abs_snap = os.path.abspath(snapshot_dir)
    for dirpath, _dirs, filenames in os.walk(project_dir):
        if os.path.abspath(dirpath).startswith(abs_snap):
            continue
        for fname in sorted(filenames):
            _, ext = os.path.splitext(fname)
            if ext.lower() not in _SNAPSHOT_PATTERNS:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, project_dir).replace("\\", "/")
            result[rel] = _hash_file(full)
    return result


def _categorise(path):
    """Determine category from file extension."""
    _, ext = os.path.splitext(path)
    return _SNAPSHOT_PATTERNS.get(ext.lower(), "other")


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
