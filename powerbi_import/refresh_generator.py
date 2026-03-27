"""
Refresh generator — convert MSTR cache/subscription schedules to PBI refresh config.

Reads MicroStrategy scheduling metadata (cache policies, subscriptions,
triggered schedules) and generates Power BI dataset refresh configuration
compatible with the PBI REST API ``/refreshSchedule`` endpoint.
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FREQUENCY_MAP = {
    "hourly": "Daily",      # PBI doesn't support sub-daily via config — map to daily with times
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "once": "Daily",
}

_DAY_MAP = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

# PBI Pro limit: max 8 refreshes per day
_MAX_DAILY_REFRESHES = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_day(day):
    return _DAY_MAP.get(day.lower().strip(), day.capitalize())


def _build_time_slots(interval_hours, start_hour=6, end_hour=22):
    """Generate evenly spaced time slots, capped at Pro limit."""
    slots = []
    hour = start_hour
    while hour <= end_hour and len(slots) < _MAX_DAILY_REFRESHES:
        slots.append(f"{hour:02d}:00")
        hour += interval_hours
    return slots


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_refresh_config(schedules, cache_policies=None):
    """Convert MSTR schedule/cache metadata to a PBI refresh configuration.

    Args:
        schedules: list of MSTR schedule dicts (from reports/dossiers/cubes).
            Expected keys: ``frequency``, ``time``, ``days``, ``timezone``,
            ``interval_hours``.
        cache_policies: optional list of cache policy dicts with
            ``expiry_minutes``, ``enabled``.

    Returns:
        dict with PBI-compatible ``refreshSchedule`` structure.
    """
    if not schedules:
        return _default_config()

    # Use the first schedule as primary (most common pattern)
    primary = schedules[0] if isinstance(schedules, list) else schedules
    freq = _FREQUENCY_MAP.get(
        primary.get("frequency", "daily").lower(), "Daily"
    )

    # Build time slots
    times = primary.get("times") or primary.get("time")
    if isinstance(times, str):
        times = [times]
    if not times:
        interval = primary.get("interval_hours")
        if interval and freq == "Daily":
            times = _build_time_slots(interval)
        else:
            times = ["06:00"]

    # Cap at Pro limit
    notes = []
    if len(times) > _MAX_DAILY_REFRESHES:
        notes.append(
            f"Reduced from {len(times)} to {_MAX_DAILY_REFRESHES} daily refreshes (PBI Pro limit)"
        )
        times = times[:_MAX_DAILY_REFRESHES]

    # Days (for weekly/monthly)
    days = primary.get("days", [])
    if isinstance(days, str):
        days = [d.strip() for d in days.split(",")]
    days = [_normalise_day(d) for d in days]

    # Timezone
    tz = primary.get("timezone", "UTC")

    config = {
        "enabled": True,
        "frequency": freq,
        "times": times,
        "timezone": tz,
        "notifyOption": "MailOnFailure",
    }
    if days and freq in ("Weekly", "Monthly"):
        config["days"] = days
    if notes:
        config["notes"] = notes

    # Cache policy hints
    if cache_policies:
        enabled = [cp for cp in cache_policies if cp.get("enabled", True)]
        if enabled:
            min_expiry = min(cp.get("expiry_minutes", 60) for cp in enabled)
            config["cacheExpiryMinutes"] = min_expiry

    return config


def generate_subscription_config(subscriptions):
    """Convert MSTR subscriptions to PBI notification definitions.

    Args:
        subscriptions: list of MSTR subscription dicts.

    Returns:
        list of notification config dicts.
    """
    notifications = []
    for sub in (subscriptions or []):
        notif = {
            "name": sub.get("name", "Subscription"),
            "type": sub.get("delivery_type", "email"),
            "enabled": sub.get("enabled", True),
        }
        if sub.get("recipients"):
            notif["recipients"] = sub["recipients"]
        if sub.get("schedule"):
            notif["schedule"] = sub["schedule"]
        notifications.append(notif)
    return notifications


def generate_refresh_json(schedules=None, subscriptions=None, cache_policies=None):
    """Generate a complete refresh + notification configuration.

    Returns:
        dict with ``refreshSchedule`` and ``notifications`` keys.
    """
    return {
        "refreshSchedule": generate_refresh_config(
            schedules or [], cache_policies
        ),
        "notifications": generate_subscription_config(subscriptions),
    }


def _default_config():
    """Return a sensible default refresh config."""
    return {
        "enabled": True,
        "frequency": "Daily",
        "times": ["06:00"],
        "timezone": "UTC",
        "notifyOption": "MailOnFailure",
    }
