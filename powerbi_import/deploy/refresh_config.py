"""
Refresh configuration generator for Power BI datasets.

Maps MicroStrategy cache policies, subscription schedules, and
cube refresh intervals to Power BI dataset refresh configuration
payloads (REST API format).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── Default schedule constants ───────────────────────────────────

_DAYS_ALL = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

_DEFAULT_TIMEZONE = "UTC"


# ── Public API ───────────────────────────────────────────────────


def generate_refresh_config(realtime_result, output_dir):
    """Generate Power BI refresh schedule configurations.

    Creates:
      - refresh_config.json: array of per-dataset refresh schedule payloads
        ready for POST /datasets/{id}/refreshSchedule

    Args:
        realtime_result: output of detect_realtime_sources()
        output_dir: directory to write output

    Returns:
        dict with generation stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    objects = realtime_result.get("objects", [])
    configs = []
    stats = {"total": 0, "batch": 0, "near_realtime": 0, "streaming": 0}

    for obj in objects:
        config = _build_config(obj)
        configs.append(config)
        stats["total"] += 1
        stats[obj.get("refresh_class", "batch")] += 1

    path = os.path.join(output_dir, "refresh_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)

    logger.info(
        "Generated refresh configs: %d total (%d batch, %d near-RT, %d streaming)",
        stats["total"], stats["batch"], stats["near_realtime"], stats["streaming"],
    )
    return stats


# ── Config builders per class ────────────────────────────────────


def _build_config(obj):
    """Build a refresh schedule config dict for an object."""
    cls = obj.get("refresh_class", "batch")
    name = obj.get("name", "")
    interval = obj.get("refresh_interval_seconds")

    if cls == "streaming":
        return _streaming_config(name, obj)
    elif cls == "near_realtime":
        return _near_realtime_config(name, interval, obj)
    else:
        return _batch_config(name, interval, obj)


def _streaming_config(name, obj):
    """Config for streaming objects → push dataset (no scheduled refresh)."""
    return {
        "name": name,
        "object_type": obj.get("object_type", ""),
        "refresh_class": "streaming",
        "recommendation": "push_dataset",
        "schedule": None,
        "notes": (
            "This object uses real-time / event-driven refresh. "
            "Use a Power BI push dataset or Fabric Eventstream instead of "
            "scheduled refresh. No refresh schedule is generated."
        ),
    }


def _near_realtime_config(name, interval, obj):
    """Config for near-realtime objects → frequent scheduled refresh."""
    if interval is None:
        minutes = 30
    else:
        minutes = max(15, interval // 60)

    # Power BI Premium supports 48 refreshes/day (every 30 min)
    # Power BI Pro supports 8 refreshes/day (every 3 hours)
    times = _build_time_slots(minutes)

    return {
        "name": name,
        "object_type": obj.get("object_type", ""),
        "refresh_class": "near_realtime",
        "recommendation": "scheduled_refresh",
        "schedule": {
            "enabled": True,
            "notifyOption": "MailOnFailure",
            "days": _DAYS_ALL,
            "times": times,
            "localTimeZoneId": _DEFAULT_TIMEZONE,
        },
        "frequencyMinutes": minutes,
        "source_interval_seconds": interval,
        "notes": (
            f"Scheduled refresh every {minutes} min. "
            "Requires Power BI Premium capacity for intervals < 180 min."
        ),
    }


def _batch_config(name, interval, obj):
    """Config for batch objects → standard daily/weekly refresh."""
    return {
        "name": name,
        "object_type": obj.get("object_type", ""),
        "refresh_class": "batch",
        "recommendation": "scheduled_refresh",
        "schedule": {
            "enabled": True,
            "notifyOption": "MailOnFailure",
            "days": _DAYS_ALL,
            "times": ["06:00"],
            "localTimeZoneId": _DEFAULT_TIMEZONE,
        },
        "frequencyMinutes": 1440,
        "source_interval_seconds": interval,
        "notes": "Standard daily refresh at 06:00 UTC.",
    }


# ── Helpers ──────────────────────────────────────────────────────


def _build_time_slots(interval_minutes):
    """Generate HH:MM time slots for a given refresh interval."""
    slots = []
    minute = 0
    while minute < 1440:  # 24 hours
        hh = minute // 60
        mm = minute % 60
        slots.append(f"{hh:02d}:{mm:02d}")
        minute += interval_minutes
    return slots
