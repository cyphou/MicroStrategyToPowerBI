"""
Post-migration certification — run validators, compare source vs output,
and produce a PASS/FAIL certification verdict.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

_CERTIFICATION_THRESHOLD = 80  # Minimum fidelity score to pass


def certify_migration(data, output_dir, *, threshold=None):
    """Run post-migration certification on a generated project.

    Runs all available validators and computes an overall certification
    score. If the fidelity meets the threshold → CERTIFIED, else → FAILED.

    Args:
        data: dict of intermediate JSON data.
        output_dir: Path to the generated .pbip project.
        threshold: Minimum fidelity % to certify (default 80).

    Returns:
        dict with certification results.
    """
    threshold = threshold or _CERTIFICATION_THRESHOLD
    checks = []
    warnings = []

    # Check 1: TMDL files exist
    checks.append(_check_tmdl_files(output_dir))

    # Check 2: PBIR pages exist
    checks.append(_check_pbir_pages(output_dir))

    # Check 3: Measure count matches
    checks.append(_check_measure_count(data, output_dir))

    # Check 4: Relationship coverage
    checks.append(_check_relationships(data, output_dir))

    # Check 5: Visual coverage
    checks.append(_check_visual_coverage(data, output_dir))

    # Check 6: Expression fidelity
    checks.append(_check_expression_fidelity(data))

    # Check 7: No manual_review items over 20% of total
    checks.append(_check_manual_review_ratio(data))

    # Calculate overall score
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    score = round(passed / total * 100) if total else 0

    certified = score >= threshold
    verdict = "CERTIFIED" if certified else "FAILED"

    result = {
        "verdict": verdict,
        "score": score,
        "threshold": threshold,
        "checks": checks,
        "warnings": warnings,
        "timestamp": datetime.now().isoformat(),
        "passed_checks": passed,
        "total_checks": total,
    }

    # Write certification report
    cert_path = os.path.join(output_dir, "certification.json")
    os.makedirs(os.path.dirname(cert_path) or ".", exist_ok=True)
    with open(cert_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info("Certification: %s (score=%d%%, threshold=%d%%)", verdict, score, threshold)
    return result


def _check_tmdl_files(output_dir):
    """Check that TMDL definition files exist."""
    # Look for tables directory in any SemanticModel subfolder
    for root, dirs, files in os.walk(output_dir):
        if "tables" in dirs:
            tables_dir = os.path.join(root, "tables")
            tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
            if tmdl_files:
                return {
                    "name": "TMDL Files Exist",
                    "passed": True,
                    "detail": f"{len(tmdl_files)} table TMDL files found",
                }
    return {
        "name": "TMDL Files Exist",
        "passed": False,
        "detail": "No TMDL table files found in output",
    }


def _check_pbir_pages(output_dir):
    """Check that PBIR page directories exist."""
    for root, dirs, files in os.walk(output_dir):
        if "pages" in dirs:
            pages_dir = os.path.join(root, "pages")
            page_dirs = [d for d in os.listdir(pages_dir)
                         if os.path.isdir(os.path.join(pages_dir, d))]
            if page_dirs:
                return {
                    "name": "PBIR Pages Exist",
                    "passed": True,
                    "detail": f"{len(page_dirs)} report pages found",
                }
    return {
        "name": "PBIR Pages Exist",
        "passed": False,
        "detail": "No PBIR pages found in output",
    }


def _check_measure_count(data, output_dir):
    """Check that generated measures roughly match source metric count."""
    source_count = len(data.get("metrics", [])) + len(data.get("derived_metrics", []))
    if source_count == 0:
        return {"name": "Measure Count", "passed": True, "detail": "No source metrics"}

    # Count measures in TMDL files
    generated = 0
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            if f.endswith(".tmdl"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                generated += content.count("\tmeasure ")

    ratio = generated / source_count if source_count else 1.0
    passed = ratio >= 0.7  # At least 70% coverage
    return {
        "name": "Measure Count",
        "passed": passed,
        "detail": f"{generated}/{source_count} measures generated ({ratio:.0%})",
    }


def _check_relationships(data, output_dir):
    """Check that relationships file exists if source has relationships."""
    source_rels = len(data.get("relationships", []))
    if source_rels == 0:
        return {"name": "Relationships", "passed": True, "detail": "No source relationships"}

    for root, dirs, files in os.walk(output_dir):
        if "relationships.tmdl" in files:
            return {
                "name": "Relationships",
                "passed": True,
                "detail": f"relationships.tmdl found ({source_rels} source relationships)",
            }
    return {
        "name": "Relationships",
        "passed": False,
        "detail": f"{source_rels} source relationships but no relationships.tmdl",
    }


def _check_visual_coverage(data, output_dir):
    """Check that visuals were generated for dossiers/reports."""
    source_visuals = 0
    for d in data.get("dossiers", []):
        for ch in d.get("chapters", []):
            for p in ch.get("pages", []):
                source_visuals += len(p.get("visualizations", []))
    source_visuals += len(data.get("reports", []))

    if source_visuals == 0:
        return {"name": "Visual Coverage", "passed": True, "detail": "No source visuals"}

    # Count visual.json files
    gen_visuals = 0
    for root, dirs, files in os.walk(output_dir):
        if "visual.json" in files:
            gen_visuals += 1

    ratio = gen_visuals / source_visuals if source_visuals else 1.0
    passed = ratio >= 0.5  # At least 50% of visuals generated
    return {
        "name": "Visual Coverage",
        "passed": passed,
        "detail": f"{gen_visuals}/{source_visuals} visuals generated ({ratio:.0%})",
    }


def _check_expression_fidelity(data):
    """Check overall expression conversion fidelity."""
    total = 0
    full = 0
    for m in data.get("metrics", []) + data.get("derived_metrics", []):
        fidelity = m.get("dax_fidelity", m.get("fidelity", ""))
        if fidelity:
            total += 1
            if fidelity == "full":
                full += 1

    if total == 0:
        return {"name": "Expression Fidelity", "passed": True, "detail": "No fidelity data"}

    ratio = full / total
    passed = ratio >= 0.5
    return {
        "name": "Expression Fidelity",
        "passed": passed,
        "detail": f"{full}/{total} expressions with full fidelity ({ratio:.0%})",
    }


def _check_manual_review_ratio(data):
    """Check that manual_review items don't exceed 20% of total."""
    total = 0
    manual = 0
    for m in data.get("metrics", []) + data.get("derived_metrics", []):
        fidelity = m.get("dax_fidelity", m.get("fidelity", ""))
        if fidelity:
            total += 1
            if fidelity == "manual_review":
                manual += 1

    if total == 0:
        return {"name": "Manual Review Ratio", "passed": True, "detail": "No fidelity data"}

    ratio = manual / total
    passed = ratio <= 0.2
    return {
        "name": "Manual Review Ratio",
        "passed": passed,
        "detail": f"{manual}/{total} require manual review ({ratio:.0%})",
    }
