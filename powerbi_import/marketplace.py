"""
Pattern marketplace — versioned registry for DAX recipes, visual mappings,
M templates, and model templates.

Supports loading from a local catalogue directory of ``.json`` files and
programmatic registration.  Semver versioning per pattern.
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset({
    "dax_recipe",
    "visual_mapping",
    "m_template",
    "naming_convention",
    "model_template",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class PatternMetadata:
    """Metadata for a registered pattern."""

    __slots__ = (
        "name", "version", "author", "description",
        "tags", "category", "created", "updated",
    )

    def __init__(self, *, name="", version="1.0.0", author="",
                 description="", tags=None, category="dax_recipe",
                 created="", updated="", **_kwargs):
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.tags = list(tags) if tags else []
        self.category = category if category in VALID_CATEGORIES else "dax_recipe"
        self.created = created
        self.updated = updated

    def matches(self, tags=None, category=None, name_pattern=None):
        """Return True if this pattern matches the given filters."""
        if category and self.category != category:
            return False
        if tags and not set(tags) & set(self.tags):
            return False
        if name_pattern and not re.search(name_pattern, self.name, re.IGNORECASE):
            return False
        return True

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
        }


class Pattern:
    """A versioned pattern with metadata and payload."""

    def __init__(self, metadata, payload, source_path=""):
        if isinstance(metadata, dict):
            metadata = PatternMetadata(**metadata)
        self.metadata = metadata
        self.payload = payload or {}
        self.source_path = source_path

    @property
    def name(self):
        return self.metadata.name

    @property
    def version(self):
        return self.metadata.version

    @property
    def category(self):
        return self.metadata.category

    def to_dict(self):
        return {
            "metadata": self.metadata.to_dict(),
            "payload": self.payload,
        }


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def _parse_version(ver_str):
    """Parse a semver string into a comparable tuple."""
    try:
        parts = ver_str.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PatternRegistry:
    """Versioned pattern registry with search and apply capabilities.

    Usage::

        registry = PatternRegistry()
        registry.load("examples/marketplace/")
        recipes = registry.search(tags=["revenue"], category="dax_recipe")
        registry.apply_dax_recipes(measures, tags=["revenue"])
    """

    def __init__(self):
        # {name: {version: Pattern}}
        self._patterns = {}

    # ---- Loading ----------------------------------------------------------

    def load(self, catalogue_dir):
        """Load all ``.json`` files from a directory.

        Returns:
            Number of patterns loaded.
        """
        if not catalogue_dir or not os.path.isdir(catalogue_dir):
            logger.warning("Catalogue directory not found: %s", catalogue_dir)
            return 0

        count = 0
        for fname in sorted(os.listdir(catalogue_dir)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(catalogue_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._register_from_dict(data, source_path=path)
                count += 1
            except (json.JSONDecodeError, OSError, KeyError) as e:
                logger.warning("Skipping %s: %s", fname, e)
        logger.info("Loaded %d patterns from %s", count, catalogue_dir)
        return count

    def register(self, pattern_dict):
        """Register a pattern from a dict (programmatic API)."""
        self._register_from_dict(pattern_dict)

    def _register_from_dict(self, data, source_path=""):
        meta = data.get("metadata", {})
        payload = data.get("payload", {})
        pattern = Pattern(meta, payload, source_path=source_path)
        name = pattern.name
        version = pattern.version
        if name not in self._patterns:
            self._patterns[name] = {}
        self._patterns[name][version] = pattern

    # ---- Queries ----------------------------------------------------------

    @property
    def count(self):
        """Number of unique pattern names."""
        return len(self._patterns)

    def get(self, name, version=None):
        """Get a pattern by name.  Without version, returns the latest."""
        versions = self._patterns.get(name)
        if not versions:
            return None
        if version:
            return versions.get(version)
        latest_ver = max(versions.keys(), key=_parse_version)
        return versions[latest_ver]

    def search(self, tags=None, category=None, name_pattern=None):
        """Search patterns (returns latest version per name)."""
        results = []
        for name, versions in self._patterns.items():
            latest_ver = max(versions.keys(), key=_parse_version)
            pattern = versions[latest_ver]
            if pattern.metadata.matches(tags=tags, category=category,
                                        name_pattern=name_pattern):
                results.append(pattern)
        return results

    def list_all(self):
        """Return all patterns (latest version per name)."""
        return self.search()

    # ---- Apply ------------------------------------------------------------

    def apply_dax_recipes(self, measures, tags=None, category="dax_recipe"):
        """Apply matching DAX recipe patterns to a measures dict.

        Supports two payload modes:
          - ``inject``: add a new measure (``name`` + ``dax``)
          - ``replace``: regex replacement (``match`` + ``replacement``)

        Returns:
            dict with keys: injected, replaced, skipped.
        """
        changes = {"injected": [], "replaced": [], "skipped": []}
        patterns = self.search(tags=tags, category=category)

        for pat in patterns:
            inject = pat.payload.get("inject")
            replace = pat.payload.get("replace")

            if inject:
                rname = inject.get("name", "")
                rdax = inject.get("dax", "")
                if rname and rdax:
                    if rname not in measures:
                        measures[rname] = rdax
                        changes["injected"].append(rname)
                    else:
                        changes["skipped"].append(rname)

            if replace:
                regex = re.compile(replace.get("match", ""))
                repl = replace.get("replacement", "")
                for name, dax in list(measures.items()):
                    new_dax = regex.sub(repl, dax)
                    if new_dax != dax:
                        measures[name] = new_dax
                        changes["replaced"].append(name)

        return changes

    def apply_visual_overrides(self, visual_type_map):
        """Apply visual mapping overrides in-place.

        Returns:
            Number of overrides applied.
        """
        count = 0
        patterns = self.search(category="visual_mapping")
        for pat in patterns:
            mappings = pat.payload.get("mappings", {})
            for src, dest in mappings.items():
                visual_type_map[src] = dest
                count += 1
        return count

    # ---- Export -----------------------------------------------------------

    def export(self, output_path):
        """Export all patterns (latest versions) to a JSON catalogue file."""
        patterns = [p.to_dict() for p in self.list_all()]
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d patterns to %s", len(patterns), output_path)

    def to_dict(self):
        """Summary dict for reporting."""
        return {
            "total_patterns": self.count,
            "categories": list({p.category for p in self.list_all()}),
            "patterns": [p.to_dict() for p in self.list_all()],
        }
