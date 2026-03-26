"""
Cross-platform equivalence tester.

Compares MSTR report data (via REST API report instances) against Power BI
measure results (via REST API) to validate migration fidelity.  Also
supports optional visual screenshot comparison using SSIM.

FF.1 — Value equivalence: row-level comparison with configurable tolerance.
FF.2 — Screenshot comparison: SSIM-based page similarity scoring.
"""

import json
import logging
import math
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_EQUIVALENCE_REPORT = "equivalence_report.json"

# Default tolerance for numeric comparison
DEFAULT_TOLERANCE = 0.01

# SSIM threshold below which a page is flagged
DEFAULT_SSIM_THRESHOLD = 0.85


# ── Value comparison ─────────────────────────────────────────────

def compare_values(mstr_rows, pbi_rows, *, tolerance=DEFAULT_TOLERANCE,
                   key_columns=None):
    """Compare row-level values between MSTR and PBI datasets.

    Args:
        mstr_rows: list of dicts — one per row from MicroStrategy.
        pbi_rows:  list of dicts — one per row from Power BI.
        tolerance: maximum allowed absolute difference for numeric values.
        key_columns: list of column names to join rows on.  If None,
                     rows are compared positionally.

    Returns:
        dict with ``matches``, ``mismatches``, ``missing_mstr``,
        ``missing_pbi``, ``summary``.
    """
    matches = []
    mismatches = []
    missing_mstr = []
    missing_pbi = []

    if key_columns:
        mstr_idx = _index_rows(mstr_rows, key_columns)
        pbi_idx = _index_rows(pbi_rows, key_columns)

        all_keys = set(mstr_idx) | set(pbi_idx)
        for key in sorted(all_keys, key=str):
            if key not in mstr_idx:
                missing_mstr.append({"key": key, "pbi_row": pbi_idx[key]})
            elif key not in pbi_idx:
                missing_pbi.append({"key": key, "mstr_row": mstr_idx[key]})
            else:
                diffs = _compare_row(mstr_idx[key], pbi_idx[key], tolerance)
                entry = {"key": key}
                if diffs:
                    entry["diffs"] = diffs
                    mismatches.append(entry)
                else:
                    matches.append(entry)
    else:
        max_rows = max(len(mstr_rows), len(pbi_rows))
        for i in range(max_rows):
            if i >= len(mstr_rows):
                missing_mstr.append({"index": i, "pbi_row": pbi_rows[i]})
            elif i >= len(pbi_rows):
                missing_pbi.append({"index": i, "mstr_row": mstr_rows[i]})
            else:
                diffs = _compare_row(mstr_rows[i], pbi_rows[i], tolerance)
                if diffs:
                    mismatches.append({"index": i, "diffs": diffs})
                else:
                    matches.append({"index": i})

    total = len(matches) + len(mismatches) + len(missing_mstr) + len(missing_pbi)
    match_rate = len(matches) / total if total > 0 else 1.0

    return {
        "matches": matches,
        "mismatches": mismatches,
        "missing_mstr": missing_mstr,
        "missing_pbi": missing_pbi,
        "summary": {
            "total_rows": total,
            "matches": len(matches),
            "mismatches": len(mismatches),
            "missing_mstr": len(missing_mstr),
            "missing_pbi": len(missing_pbi),
            "match_rate": round(match_rate, 4),
        },
    }


def _index_rows(rows, key_columns):
    """Build {composite_key: row} lookup."""
    idx = {}
    for row in rows:
        key = tuple(row.get(c) for c in key_columns)
        idx[key] = row
    return idx


def _compare_row(mstr_row, pbi_row, tolerance):
    """Compare two rows field-by-field, return list of diffs."""
    diffs = []
    all_cols = set(mstr_row) | set(pbi_row)
    for col in sorted(all_cols):
        mv = mstr_row.get(col)
        pv = pbi_row.get(col)
        if not _values_equal(mv, pv, tolerance):
            diffs.append({
                "column": col,
                "mstr_value": mv,
                "pbi_value": pv,
            })
    return diffs


def _values_equal(a, b, tolerance):
    """Compare two values with numeric tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) <= tolerance
    return str(a) == str(b)


# ── Screenshot / SSIM comparison ─────────────────────────────────

def compare_screenshots(mstr_images, pbi_images, *,
                        threshold=DEFAULT_SSIM_THRESHOLD):
    """Compare screenshots from MSTR and PBI pages.

    Args:
        mstr_images: list of dicts with ``page`` and ``pixels``
                     (2D list of (R,G,B) tuples or flat grayscale values).
        pbi_images:  same format as mstr_images.
        threshold:   SSIM below this flags the page.

    Returns:
        dict with per-page ``ssim`` scores and ``flagged`` pages.
    """
    results = []
    flagged = []

    for i in range(min(len(mstr_images), len(pbi_images))):
        page = mstr_images[i].get("page", f"Page {i+1}")
        mstr_px = mstr_images[i].get("pixels", [])
        pbi_px = pbi_images[i].get("pixels", [])
        ssim = _compute_ssim(mstr_px, pbi_px)
        entry = {"page": page, "ssim": round(ssim, 4)}
        results.append(entry)
        if ssim < threshold:
            flagged.append(entry)

    return {
        "pages": results,
        "flagged": flagged,
        "summary": {
            "total_pages": len(results),
            "flagged_pages": len(flagged),
            "avg_ssim": round(
                sum(r["ssim"] for r in results) / len(results), 4
            ) if results else 0,
        },
    }


def _compute_ssim(pixels_a, pixels_b):
    """Simplified SSIM approximation for two flat pixel arrays.

    Uses the structural similarity index: a mean-based luminance *
    contrast * structure comparison.  For a full implementation, use
    ``skimage.metrics.structural_similarity`` — this is a lightweight
    fallback for environments without SciPy.
    """
    a = _flatten(pixels_a)
    b = _flatten(pixels_b)
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0

    a = a[:n]
    b = b[:n]

    mean_a = sum(a) / n
    mean_b = sum(b) / n
    var_a = sum((x - mean_a) ** 2 for x in a) / n
    var_b = sum((x - mean_b) ** 2 for x in b) / n
    cov_ab = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / n

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    numerator = (2 * mean_a * mean_b + c1) * (2 * cov_ab + c2)
    denominator = (mean_a ** 2 + mean_b ** 2 + c1) * (var_a + var_b + c2)

    return numerator / denominator if denominator != 0 else 0.0


def _flatten(pixels):
    """Flatten a potentially nested pixel list to a flat list of numbers."""
    flat = []
    for item in pixels:
        if isinstance(item, (list, tuple)):
            # RGB tuple → grayscale
            if len(item) >= 3:
                flat.append(0.299 * item[0] + 0.587 * item[1] + 0.114 * item[2])
            else:
                flat.extend(item)
        else:
            flat.append(float(item))
    return flat


# ── Report persistence ───────────────────────────────────────────

def save_equivalence_report(report, output_dir):
    """Write equivalence report to JSON."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, _EQUIVALENCE_REPORT)
    report_with_meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **report,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report_with_meta, f, indent=2, ensure_ascii=False,
                  default=str)
    logger.info("Equivalence report saved to %s", path)
    return path
