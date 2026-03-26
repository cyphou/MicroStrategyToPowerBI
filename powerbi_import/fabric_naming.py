"""
Fabric naming — name sanitization and collision detection for Fabric items.

Enforces naming rules for Lakehouse tables (64-char, no spaces),
Dataflow names, Pipeline names, and Semantic Model names.  Provides
collision detection with automatic suffix generation.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Naming limits ────────────────────────────────────────────────

_MAX_TABLE_NAME = 64
_MAX_ITEM_NAME = 256
_SAFE_TABLE_RE = re.compile(r"[^a-zA-Z0-9_]")
_SAFE_ITEM_RE = re.compile(r"[^\w\s\-.()\[\]]", re.UNICODE)


# ── Public API ───────────────────────────────────────────────────


def sanitize_table_name(name):
    """Sanitize a name for use as a Lakehouse Delta table name.

    Rules:
    - Replace non-alphanumeric chars (except ``_``) with ``_``.
    - Collapse consecutive underscores.
    - Truncate to 64 characters.
    - Must start with a letter or ``_``.
    """
    cleaned = _SAFE_TABLE_RE.sub("_", name or "")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "table"
    # Must start with letter or _
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned[:_MAX_TABLE_NAME]


def sanitize_item_name(name):
    """Sanitize a name for use as a Fabric item (Dataflow, Pipeline, etc.).

    More lenient than table names — allows spaces, dashes, dots, parens.
    Truncates to 256 characters.
    """
    cleaned = _SAFE_ITEM_RE.sub("", name or "").strip()
    if not cleaned:
        cleaned = "Item"
    return cleaned[:_MAX_ITEM_NAME]


def sanitize_dataflow_name(name):
    """Sanitize specifically for Dataflow Gen2 names."""
    return sanitize_item_name(f"DF_{name}" if name else "DF_Default")


def sanitize_pipeline_name(name):
    """Sanitize specifically for Data Factory pipeline names."""
    return sanitize_item_name(f"PL_{name}" if name else "PL_Default")


def sanitize_semantic_model_name(name):
    """Sanitize for Semantic Model display name."""
    return sanitize_item_name(name or "SemanticModel")


def resolve_collisions(names):
    """Detect and resolve naming collisions by appending numeric suffixes.

    Args:
        names: list of name strings.

    Returns:
        list of unique names (same order), with ``_2``, ``_3``, etc. appended
        to colliding entries.
    """
    seen = {}
    result = []
    for name in names:
        lower = name.lower()
        if lower in seen:
            seen[lower] += 1
            resolved = f"{name}_{seen[lower]}"
            result.append(resolved)
        else:
            seen[lower] = 1
            result.append(name)
    return result


def validate_table_names(names):
    """Validate a list of table names and return a report.

    Returns:
        dict with ``valid`` (list), ``sanitized`` (list of (original, fixed) tuples),
        and ``collisions`` (list of resolved names if any).
    """
    valid = []
    sanitized = []
    cleaned = []
    for name in names:
        clean = sanitize_table_name(name)
        cleaned.append(clean)
        if clean == name:
            valid.append(name)
        else:
            sanitized.append((name, clean))

    resolved = resolve_collisions(cleaned)
    collisions = [(orig, res) for orig, res in zip(cleaned, resolved) if orig != res]

    return {
        "valid": valid,
        "sanitized": sanitized,
        "collisions": collisions,
        "final_names": resolved,
    }
