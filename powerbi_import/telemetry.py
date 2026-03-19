"""
Telemetry module.

Collects migration run data — timing, object counts, error counts,
feature usage — for historical analysis and dashboard generation.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MigrationRun:
    """Data collected for a single migration run."""

    def __init__(self, project_name=""):
        self.run_id = f"run_{int(time.time())}"
        self.project_name = project_name
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at = None
        self.duration_seconds = 0
        self.status = "in_progress"
        self.object_counts = {}
        self.generation_stats = {}
        self.errors = []
        self.warnings = []
        self.features_used = []

    def finish(self, status="success"):
        self.finished_at = datetime.now(timezone.utc).isoformat()
        started = datetime.fromisoformat(self.started_at)
        finished = datetime.fromisoformat(self.finished_at)
        self.duration_seconds = round((finished - started).total_seconds(), 2)
        self.status = status

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "project_name": self.project_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "object_counts": self.object_counts,
            "generation_stats": self.generation_stats,
            "errors": self.errors,
            "warnings": self.warnings,
            "features_used": self.features_used,
        }


def save_run(run, output_dir):
    """Append a run to the telemetry log."""
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "telemetry_log.json")

    runs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                runs = json.load(f)
        except (json.JSONDecodeError, OSError):
            runs = []

    runs.append(run.to_dict())

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2, ensure_ascii=False)

    logger.info("Telemetry saved: %s", run.run_id)


def load_runs(output_dir):
    """Load all runs from telemetry log."""
    log_path = os.path.join(output_dir, "telemetry_log.json")
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
