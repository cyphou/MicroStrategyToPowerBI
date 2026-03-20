"""
Merge assessment — analyze N intermediate-JSON project directories
for overlap, deduplicate candidates, and score merge viability.
"""

import json
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

_JSON_FILES = [
    "datasources.json", "attributes.json", "facts.json", "metrics.json",
    "derived_metrics.json", "reports.json", "dossiers.json", "cubes.json",
    "filters.json", "prompts.json", "custom_groups.json",
    "consolidations.json", "hierarchies.json", "relationships.json",
    "security_filters.json", "freeform_sql.json", "thresholds.json",
    "subtotals.json",
]


def load_project_data(project_dir):
    """Load all intermediate JSON files from a project directory.

    Returns:
        dict mapping filename (without extension) → parsed list/dict.
    """
    data = {}
    for fname in _JSON_FILES:
        path = os.path.join(project_dir, fname)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data[fname.replace(".json", "")] = json.load(f)
    return data


def analyze_overlap(projects):
    """Analyze overlap across N project data dicts.

    Args:
        projects: list of (project_name, data_dict) tuples.

    Returns:
        dict with overlap analysis:
          - shared_tables: tables appearing in 2+ projects
          - shared_metrics: metrics appearing in 2+ projects
          - shared_attributes: attributes appearing in 2+ projects
          - conflicts: items with same name but different definitions
          - unique_per_project: items unique to each project
    """
    table_sources = defaultdict(set)
    metric_sources = defaultdict(set)
    attr_sources = defaultdict(set)
    metric_defs = defaultdict(list)
    attr_defs = defaultdict(list)

    for proj_name, data in projects:
        # Datasources → table names
        for ds in data.get("datasources", []):
            for t in ds.get("tables", []):
                tname = t.get("name", t.get("table_name", ""))
                if tname:
                    table_sources[tname].add(proj_name)

        # Attributes
        for attr in data.get("attributes", []):
            name = attr.get("name", "")
            if name:
                attr_sources[name].add(proj_name)
                attr_defs[name].append((proj_name, attr))

        # Metrics
        for m in data.get("metrics", []):
            name = m.get("name", "")
            if name:
                metric_sources[name].add(proj_name)
                metric_defs[name].append((proj_name, m))
        for m in data.get("derived_metrics", []):
            name = m.get("name", "")
            if name:
                metric_sources[name].add(proj_name)
                metric_defs[name].append((proj_name, m))

    # Classify overlaps
    shared_tables = {t: sorted(ps) for t, ps in table_sources.items() if len(ps) > 1}
    shared_metrics = {m: sorted(ps) for m, ps in metric_sources.items() if len(ps) > 1}
    shared_attrs = {a: sorted(ps) for a, ps in attr_sources.items() if len(ps) > 1}

    # Detect conflicts (same name, different definition)
    conflicts = []
    for name, defs in metric_defs.items():
        if len(defs) > 1:
            exprs = set()
            for pn, d in defs:
                exprs.add(d.get("expression", "") or d.get("aggregation", ""))
            if len(exprs) > 1:
                conflicts.append({
                    "type": "metric",
                    "name": name,
                    "projects": [d[0] for d in defs],
                    "definitions": [d[1].get("expression", "") for d in defs],
                })

    for name, defs in attr_defs.items():
        if len(defs) > 1:
            forms = set()
            for pn, d in defs:
                forms.add(json.dumps(d.get("forms", []), sort_keys=True))
            if len(forms) > 1:
                conflicts.append({
                    "type": "attribute",
                    "name": name,
                    "projects": [d[0] for d in defs],
                })

    # Unique per project
    unique_per_project = {}
    for proj_name, data in projects:
        proj_metrics = set()
        for m in data.get("metrics", []) + data.get("derived_metrics", []):
            name = m.get("name", "")
            if name and len(metric_sources.get(name, set())) == 1:
                proj_metrics.add(name)
        unique_per_project[proj_name] = {"metrics": sorted(proj_metrics)}

    return {
        "shared_tables": shared_tables,
        "shared_metrics": shared_metrics,
        "shared_attributes": shared_attrs,
        "conflicts": conflicts,
        "unique_per_project": unique_per_project,
    }


def score_merge_viability(overlap):
    """Score how viable a merge is (0-100) based on overlap analysis.

    Higher score  → easier merge (more shared, fewer conflicts).
    """
    n_shared_tables = len(overlap.get("shared_tables", {}))
    n_shared_metrics = len(overlap.get("shared_metrics", {}))
    n_conflicts = len(overlap.get("conflicts", []))

    # Base score from shared objects
    shared_score = min(50, (n_shared_tables + n_shared_metrics) * 5)
    # Penalty for conflicts
    conflict_penalty = min(40, n_conflicts * 10)
    score = max(0, 50 + shared_score - conflict_penalty)
    score = min(100, score)

    if n_conflicts == 0:
        rating = "GREEN"
    elif n_conflicts <= 3:
        rating = "YELLOW"
    else:
        rating = "RED"

    return {
        "score": score,
        "rating": rating,
        "shared_tables": n_shared_tables,
        "shared_metrics": n_shared_metrics,
        "conflicts": n_conflicts,
        "recommendation": (
            "Safe to auto-merge" if rating == "GREEN"
            else "Review conflicts before merging" if rating == "YELLOW"
            else "Significant conflicts — manual resolution required"
        ),
    }


def run_merge_assessment(project_dirs):
    """Run full merge assessment on a list of project directories.

    Args:
        project_dirs: list of paths to intermediate-JSON directories.

    Returns:
        dict with overlap analysis and viability score.
    """
    projects = []
    for d in project_dirs:
        name = os.path.basename(d.rstrip("/\\"))
        data = load_project_data(d)
        projects.append((name, data))
        logger.info("Loaded project '%s': %d files", name, len(data))

    overlap = analyze_overlap(projects)
    viability = score_merge_viability(overlap)

    logger.info(
        "Merge assessment: score=%d rating=%s conflicts=%d",
        viability["score"], viability["rating"], viability["conflicts"],
    )
    return {
        "projects": [p[0] for p in projects],
        "overlap": overlap,
        "viability": viability,
    }
