"""
Real-time source detector for MicroStrategy.

Detects real-time dashboards by analysing refresh policies, cache
settings, subscription schedules, and cube refresh intervals.

Classifies each dossier / report / cube as:
  - batch       — standard scheduled refresh (≥ 1 h interval)
  - near_realtime — auto-refresh with interval < 1 h
  - streaming   — push/subscription-based or event-driven refresh
"""

import logging

logger = logging.getLogger(__name__)


# ── Classification thresholds (seconds) ──────────────────────────

_NEAR_REALTIME_THRESHOLD = 3600   # ≤ 1 hour → near-real-time
_STREAMING_THRESHOLD = 60          # ≤ 1 minute → streaming


# ── Public API ───────────────────────────────────────────────────


def detect_realtime_sources(data):
    """Analyse intermediate JSON data and classify each object's refresh mode.

    Args:
        data: dict with intermediate JSON data (dossiers, reports, cubes, etc.).

    Returns:
        dict with keys:
            objects: list of classified dicts (id, name, object_type,
                     refresh_class, refresh_interval_seconds, details).
            summary: dict with counts per class.
    """
    objects = []

    for dossier in data.get("dossiers", []):
        obj = _classify_dossier(dossier)
        objects.append(obj)

    for report in data.get("reports", []):
        obj = _classify_report(report)
        objects.append(obj)

    for cube in data.get("cubes", []):
        obj = _classify_cube(cube)
        objects.append(obj)

    summary = _build_summary(objects)
    logger.info(
        "Real-time detection: %d batch, %d near-realtime, %d streaming",
        summary.get("batch", 0),
        summary.get("near_realtime", 0),
        summary.get("streaming", 0),
    )
    return {"objects": objects, "summary": summary}


# ── Classifiers ──────────────────────────────────────────────────


def _classify_dossier(dossier):
    """Classify a dossier's refresh mode."""
    name = dossier.get("name", "")
    obj_id = dossier.get("id", "")

    interval = _extract_refresh_interval(dossier)
    is_subscription = _has_subscription(dossier)
    is_auto_refresh = dossier.get("auto_refresh", False) or dossier.get("autoRefresh", False)

    refresh_class = _classify_interval(interval, is_subscription)

    return {
        "id": obj_id,
        "name": name,
        "object_type": "dossier",
        "refresh_class": refresh_class,
        "refresh_interval_seconds": interval,
        "auto_refresh": is_auto_refresh,
        "has_subscription": is_subscription,
        "details": _build_details(dossier),
    }


def _classify_report(report):
    """Classify a report's refresh mode."""
    name = report.get("name", "")
    obj_id = report.get("id", "")

    interval = _extract_refresh_interval(report)
    is_subscription = _has_subscription(report)

    refresh_class = _classify_interval(interval, is_subscription)

    return {
        "id": obj_id,
        "name": name,
        "object_type": "report",
        "refresh_class": refresh_class,
        "refresh_interval_seconds": interval,
        "auto_refresh": False,
        "has_subscription": is_subscription,
        "details": _build_details(report),
    }


def _classify_cube(cube):
    """Classify an Intelligent Cube's refresh mode."""
    name = cube.get("name", "")
    obj_id = cube.get("id", "")

    policy = cube.get("refresh_policy", cube.get("refreshPolicy", "manual"))
    interval = _extract_refresh_interval(cube)

    # Cubes with "event" or "push" policies are streaming
    is_event = str(policy).lower() in ("event", "push", "event_driven", "realtime")
    is_subscription = is_event or _has_subscription(cube)

    refresh_class = _classify_interval(interval, is_subscription, is_event)

    return {
        "id": obj_id,
        "name": name,
        "object_type": "cube",
        "refresh_class": refresh_class,
        "refresh_interval_seconds": interval,
        "refresh_policy": policy,
        "has_subscription": is_subscription,
        "details": _build_details(cube),
    }


# ── Helpers ──────────────────────────────────────────────────────


def _extract_refresh_interval(obj):
    """Return the refresh interval in seconds, or None if not available."""
    # Direct field
    for key in ("refresh_interval", "refreshInterval", "refresh_interval_seconds",
                "autoRefreshInterval", "auto_refresh_interval"):
        val = obj.get(key)
        if val is not None:
            return _to_seconds(val)

    # Nested in scheduleInfo / cachePolicy
    for container_key in ("scheduleInfo", "schedule_info", "cachePolicy", "cache_policy"):
        container = obj.get(container_key, {})
        if isinstance(container, dict):
            for key in ("interval", "intervalSeconds", "interval_seconds",
                        "refreshIntervalMinutes", "refresh_interval_minutes"):
                val = container.get(key)
                if val is not None:
                    return _to_seconds(val, key)

    return None


def _to_seconds(value, key_hint=""):
    """Convert a numeric value to seconds, handling minute-based keys."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None

    if "minute" in key_hint.lower() or "Minutes" in key_hint:
        return int(val * 60)
    return int(val)


def _has_subscription(obj):
    """Check whether the object has subscription / event-driven delivery."""
    subs = obj.get("subscriptions", obj.get("subscription", []))
    if subs:
        return True
    # Some APIs flag it differently
    if obj.get("event_based", False) or obj.get("eventBased", False):
        return True
    return False


def _classify_interval(interval, is_subscription=False, is_event=False):
    """Return 'batch', 'near_realtime', or 'streaming'."""
    if is_event or is_subscription:
        return "streaming"
    if interval is None:
        return "batch"
    if interval <= _STREAMING_THRESHOLD:
        return "streaming"
    if interval <= _NEAR_REALTIME_THRESHOLD:
        return "near_realtime"
    return "batch"


def _build_details(obj):
    """Extract relevant detail fields for the classification record."""
    details = {}
    for key in ("cachePolicy", "cache_policy", "scheduleInfo", "schedule_info",
                "subscriptions", "subscription", "autoRefresh", "auto_refresh",
                "refreshPolicy", "refresh_policy"):
        val = obj.get(key)
        if val:
            details[key] = val
    return details


def _build_summary(objects):
    """Build a summary dict with counts per refresh class."""
    summary = {"batch": 0, "near_realtime": 0, "streaming": 0, "total": len(objects)}
    for obj in objects:
        cls = obj.get("refresh_class", "batch")
        summary[cls] = summary.get(cls, 0) + 1
    return summary
