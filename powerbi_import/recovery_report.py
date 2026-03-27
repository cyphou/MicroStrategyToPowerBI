"""
Recovery report — tracks self-healing repairs made during generation.

When the generator encounters a fixable issue (e.g. invalid column name,
unsupported visual type, broken relationship), it records the repair here
so users can review what was automatically corrected.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_TMDL = "TMDL"
CATEGORY_VISUAL = "VISUAL"
CATEGORY_M_QUERY = "M_QUERY"
CATEGORY_RELATIONSHIP = "RELATIONSHIP"
CATEGORY_DAX = "DAX"
CATEGORY_SCHEMA = "SCHEMA"

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Recovery report
# ---------------------------------------------------------------------------

class RecoveryReport:
    """Collects and reports automatic repairs made during migration.

    Usage::

        recovery = RecoveryReport()
        recovery.record("TMDL", "sanitised_column_name",
                        description="Replaced spaces in column name",
                        original_value="Sales Amount",
                        repaired_value="Sales_Amount",
                        severity="INFO")
        recovery.save("artifacts/")
    """

    def __init__(self):
        self._repairs = []

    # ---- Recording --------------------------------------------------------

    def record(self, category, repair_type, *, description="",
               action="", severity=SEVERITY_INFO, follow_up="",
               item_name="", original_value=None, repaired_value=None):
        """Record one repair action.

        Args:
            category: One of CATEGORY_* constants.
            repair_type: Short identifier (e.g. ``sanitised_column_name``).
            description: Human-readable description.
            action: What was done to fix the issue.
            severity: INFO / WARNING / ERROR.
            follow_up: Recommended manual follow-up (if any).
            item_name: Name of the affected object.
            original_value: The value before repair.
            repaired_value: The value after repair.
        """
        entry = {
            "category": category,
            "repair_type": repair_type,
            "description": description,
            "action": action,
            "severity": severity,
            "item_name": item_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if follow_up:
            entry["follow_up"] = follow_up
        if original_value is not None:
            entry["original_value"] = str(original_value)
        if repaired_value is not None:
            entry["repaired_value"] = str(repaired_value)
        self._repairs.append(entry)

    # ---- Queries ----------------------------------------------------------

    @property
    def has_repairs(self):
        return len(self._repairs) > 0

    @property
    def count(self):
        return len(self._repairs)

    def get_summary(self):
        """Return a summary grouped by category and severity."""
        by_cat = {}
        by_sev = {}
        for r in self._repairs:
            cat = r["category"]
            sev = r["severity"]
            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_sev[sev] = by_sev.get(sev, 0) + 1
        return {
            "total_repairs": len(self._repairs),
            "by_category": by_cat,
            "by_severity": by_sev,
        }

    def get_repairs(self, category=None, severity=None):
        """Return repairs, optionally filtered."""
        results = self._repairs
        if category:
            results = [r for r in results if r["category"] == category]
        if severity:
            results = [r for r in results if r["severity"] == severity]
        return results

    # ---- Serialisation ----------------------------------------------------

    def to_dict(self):
        return {
            "summary": self.get_summary(),
            "repairs": list(self._repairs),
        }

    def save(self, output_dir):
        """Save recovery report as JSON.

        Returns:
            Path to the written file.
        """
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "recovery_report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Recovery report saved: %d repairs → %s",
                     len(self._repairs), path)
        return path

    # ---- Integration ------------------------------------------------------

    def merge_into(self, migration_summary):
        """Merge recovery data into the migration summary dict.

        Adds ``recovery`` key with summary and repair list.
        """
        if not self.has_repairs:
            return
        migration_summary["recovery"] = self.to_dict()

    # ---- Display ----------------------------------------------------------

    def print_summary(self):
        """Print a human-readable summary to stdout."""
        if not self.has_repairs:
            print("  No automatic repairs were needed.")
            return
        summary = self.get_summary()
        print(f"  Recovery Report: {summary['total_repairs']} automatic repairs")
        for cat, count in sorted(summary["by_category"].items()):
            print(f"    {cat}: {count}")
        errors = summary["by_severity"].get(SEVERITY_ERROR, 0)
        warnings = summary["by_severity"].get(SEVERITY_WARNING, 0)
        if errors:
            print(f"    ⚠ {errors} ERROR-level repairs — review recommended")
        if warnings:
            print(f"    ⚠ {warnings} WARNING-level repairs")
