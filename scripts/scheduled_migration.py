"""
Scheduled migration runner.

Provides a cron-compatible entry-point that polls for changes, runs
incremental migration, validates, and optionally deploys.  Designed
to be invoked periodically (e.g. via cron, Windows Task Scheduler, or
Azure pipelines).

Configuration is read from ``migration_schedule.json``.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Ensure the project root is on the path so we can import siblings
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from microstrategy_export.change_detector import (  # noqa: E402
    detect_changes,
    save_manifest,
)
from powerbi_import.drift_report import detect_drift, save_drift_report  # noqa: E402
from powerbi_import.reconciler import reconcile, save_reconcile_report  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = "migration_schedule.json"


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

def load_schedule_config(path=None):
    """Load the schedule configuration file.

    Returns a dict with sensible defaults merged with overrides from the
    JSON file.
    """
    defaults = {
        "current_extract_dir": "microstrategy_export",
        "previous_extract_dir": "microstrategy_export_prev",
        "output_dir": "output",
        "previous_output_dir": "output_prev",
        "baseline_dir": "output_baseline",
        "report_dir": "migration_ops",
        "validate": True,
        "deploy": False,
        "reconcile": True,
        "dry_run": False,
        "notify": None,
    }
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                overrides = json.load(f)
            defaults.update(overrides)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load config %s: %s", path, exc)
    return defaults


# ------------------------------------------------------------------
# Pipeline steps
# ------------------------------------------------------------------

def run_scheduled_migration(config_path=None):
    """Execute the full scheduled migration pipeline.

    Steps:
      1. Load configuration
      2. Detect changes (current vs previous intermediate JSONs)
      3. Detect drift (live output vs baseline)
      4. Reconcile (three-way merge if enabled)
      5. Save reports
      6. Return summary

    Returns:
        dict with pipeline results and summary.
    """
    config = load_schedule_config(config_path)
    report_dir = config["report_dir"]
    os.makedirs(report_dir, exist_ok=True)

    results = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "steps": {},
    }

    # Step 1: Change detection
    logger.info("Step 1: Detecting changes…")
    try:
        manifest = detect_changes(
            config["current_extract_dir"],
            config["previous_extract_dir"],
        )
        save_manifest(manifest, report_dir)
        results["steps"]["change_detection"] = {
            "status": "success",
            "summary": manifest["summary"],
        }
    except Exception as exc:
        logger.error("Change detection failed: %s", exc)
        results["steps"]["change_detection"] = {
            "status": "error",
            "error": str(exc),
        }
        manifest = None

    # Step 2: Drift detection
    logger.info("Step 2: Detecting drift…")
    try:
        drift = detect_drift(
            config["output_dir"],
            config["previous_output_dir"],
        )
        save_drift_report(drift, report_dir)
        results["steps"]["drift_detection"] = {
            "status": "success",
            "summary": drift["summary"],
        }
    except Exception as exc:
        logger.error("Drift detection failed: %s", exc)
        results["steps"]["drift_detection"] = {
            "status": "error",
            "error": str(exc),
        }
        drift = None

    # Step 3: Reconciliation
    if config.get("reconcile") and manifest:
        has_changes = (
            manifest["summary"].get("added", 0)
            + manifest["summary"].get("modified", 0)
            + manifest["summary"].get("deleted", 0)
        ) > 0
        if has_changes:
            logger.info("Step 3: Reconciling…")
            try:
                rec = reconcile(
                    config["output_dir"],
                    config["output_dir"],
                    config["baseline_dir"],
                    dry_run=config.get("dry_run", False),
                )
                save_reconcile_report(rec, report_dir)
                results["steps"]["reconciliation"] = {
                    "status": "success",
                    "summary": rec["summary"],
                }
            except Exception as exc:
                logger.error("Reconciliation failed: %s", exc)
                results["steps"]["reconciliation"] = {
                    "status": "error",
                    "error": str(exc),
                }
        else:
            results["steps"]["reconciliation"] = {
                "status": "skipped",
                "reason": "No changes detected.",
            }
    else:
        results["steps"]["reconciliation"] = {
            "status": "skipped",
            "reason": "Reconciliation disabled or no manifest.",
        }

    results["finished_at"] = datetime.now(timezone.utc).isoformat()
    results["status"] = (
        "success"
        if all(
            s.get("status") in ("success", "skipped")
            for s in results["steps"].values()
        )
        else "partial_failure"
    )

    # Persist run summary
    summary_path = os.path.join(report_dir, "scheduled_run.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Scheduled migration complete: %s", results["status"])

    return results


# ------------------------------------------------------------------
# CLI entry-point when run as a script
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    config_file = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_CONFIG
    result = run_scheduled_migration(config_file)
    print(json.dumps(result.get("steps", {}), indent=2))
