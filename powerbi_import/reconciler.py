"""
Three-way reconciler for migration output.

Performs a three-way merge:
  MSTR source (new migration) × PBI target (current live) × PBI target (previous migration)

This preserves manual PBI customisations while applying upstream MSTR
changes.  Files that were *not* edited by the user are simply replaced;
files the user modified are flagged as conflicts.
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_RECONCILE_REPORT = "reconcile_report.json"

# File extensions we track
_TRACKED_EXTENSIONS = {".json", ".tmdl", ".m", ".pq"}


def _hash_file(path):
    """SHA-256 of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_files(root):
    """Walk *root* and return {relative_path: sha256}."""
    fmap = {}
    if not os.path.isdir(root):
        return fmap
    for dirpath, _dirs, filenames in os.walk(root):
        for fname in filenames:
            _, ext = os.path.splitext(fname)
            if ext.lower() not in _TRACKED_EXTENSIONS:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace("\\", "/")
            fmap[rel] = _hash_file(full)
    return fmap


# ------------------------------------------------------------------
# Resolution strategies
# ------------------------------------------------------------------

STRATEGY_ACCEPT_SOURCE = "accept_source"
STRATEGY_KEEP_TARGET = "keep_target"
STRATEGY_CONFLICT = "conflict"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def reconcile(source_dir, target_dir, baseline_dir, *, dry_run=False):
    """Three-way reconcile *source_dir* into *target_dir*.

    Args:
        source_dir:   New migration output (from latest extraction).
        target_dir:   Current live PBI output (may contain user edits).
        baseline_dir: Previous migration output (snapshot at last migration).
        dry_run:      If True, report conflicts without copying files.

    Returns:
        Reconciliation report dict with ``auto_applied``, ``conflicts``,
        ``new_files``, ``removed_files``.
    """
    src_files = _collect_files(source_dir)
    tgt_files = _collect_files(target_dir)
    base_files = _collect_files(baseline_dir)

    auto_applied = []
    conflicts = []
    new_files = []
    removed_files = []

    all_paths = set(src_files) | set(tgt_files) | set(base_files)

    for rel in sorted(all_paths):
        in_src = rel in src_files
        in_tgt = rel in tgt_files
        in_base = rel in base_files

        if in_src and not in_base and not in_tgt:
            # Brand-new file from source — add it
            new_files.append({"file": rel, "action": "add"})
            if not dry_run:
                _copy_file(source_dir, target_dir, rel)

        elif in_src and in_base and not in_tgt:
            # User deleted it; source changed. Keep deleted (user wins).
            removed_files.append({
                "file": rel,
                "action": "keep_deleted",
                "reason": "User deleted; source also changed.",
            })

        elif not in_src and in_base and in_tgt:
            # Source removed it; target still has it.
            if tgt_files[rel] == base_files[rel]:
                # User didn't touch it — safe to remove
                removed_files.append({"file": rel, "action": "remove"})
                if not dry_run:
                    _remove_file(target_dir, rel)
            else:
                # User modified a file that's been removed upstream
                conflicts.append({
                    "file": rel,
                    "reason": "Source removed; user modified.",
                    "strategy": STRATEGY_CONFLICT,
                })

        elif in_src and in_base and in_tgt:
            src_h = src_files[rel]
            tgt_h = tgt_files[rel]
            base_h = base_files[rel]

            if src_h == base_h:
                # Source unchanged — keep user edits
                auto_applied.append({
                    "file": rel,
                    "action": "keep_target",
                    "reason": "Source unchanged; keeping user version.",
                })
            elif tgt_h == base_h:
                # User didn't touch it — safe to replace
                auto_applied.append({
                    "file": rel,
                    "action": "accept_source",
                    "reason": "User unchanged; applying source update.",
                })
                if not dry_run:
                    _copy_file(source_dir, target_dir, rel)
            elif src_h == tgt_h:
                # Both changed identically — no action needed
                auto_applied.append({
                    "file": rel,
                    "action": "identical",
                    "reason": "Source and user made same change.",
                })
            else:
                # Both changed differently — conflict
                conflicts.append({
                    "file": rel,
                    "reason": "Both source and user modified.",
                    "strategy": STRATEGY_CONFLICT,
                })

        elif in_src and not in_base and in_tgt:
            # New in both source and target — compare
            if src_files[rel] == tgt_files[rel]:
                auto_applied.append({
                    "file": rel,
                    "action": "identical",
                    "reason": "Both added with identical content.",
                })
            else:
                conflicts.append({
                    "file": rel,
                    "reason": "Both source and user added with different content.",
                    "strategy": STRATEGY_CONFLICT,
                })

        elif not in_src and not in_base and in_tgt:
            # User-only file — leave it alone
            auto_applied.append({
                "file": rel,
                "action": "keep_target",
                "reason": "User-added file; not in source.",
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "source_dir": source_dir,
        "target_dir": target_dir,
        "baseline_dir": baseline_dir,
        "auto_applied": auto_applied,
        "conflicts": conflicts,
        "new_files": new_files,
        "removed_files": removed_files,
        "summary": {
            "auto_applied": len(auto_applied),
            "conflicts": len(conflicts),
            "new_files": len(new_files),
            "removed_files": len(removed_files),
        },
    }

    logger.info(
        "Reconciliation%s: %d auto, %d conflicts, %d new, %d removed",
        " (dry-run)" if dry_run else "",
        len(auto_applied), len(conflicts), len(new_files), len(removed_files),
    )
    return report


def save_reconcile_report(report, output_dir):
    """Persist reconciliation report as JSON."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _RECONCILE_REPORT)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Reconcile report saved to %s", path)
    return path


# ------------------------------------------------------------------
# File operations
# ------------------------------------------------------------------

def _copy_file(src_root, dst_root, rel_path):
    """Copy a file from *src_root/rel_path* to *dst_root/rel_path*."""
    src = os.path.join(src_root, rel_path)
    dst = os.path.join(dst_root, rel_path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def _remove_file(root, rel_path):
    """Remove *root/rel_path* if it exists."""
    path = os.path.join(root, rel_path)
    if os.path.exists(path):
        os.remove(path)
