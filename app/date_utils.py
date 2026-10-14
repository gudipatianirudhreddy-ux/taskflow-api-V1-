"""Consistent due-date parsing for TaskAPI.

Database convention: due_date values are stored as naive UTC datetimes because
the existing SQLAlchemy columns use DateTime(timezone=False).
Incoming naive date/time values are interpreted in APP_TIMEZONE. Date-only
values mean midnight in APP_TIMEZONE. Returned API dates include a trailing Z
so clients know that the stored instant is UTC.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
except ZoneInfoNotFoundError as exc:
    raise RuntimeError("APP_TIMEZONE must be a valid IANA timezone, e.g. Asia/Kolkata") from exc


def normalize_due_date_input(value: datetime | date | str | None) -> datetime | None:
    """Convert an incoming date/datetime to naive UTC for database storage.

    Accepts YYYY-MM-DD, ISO datetime strings, UTC 'Z' suffixes, aware datetime
    objects, and naive datetimes. Naive values are interpreted in APP_TIMEZONE.
    Invalid strings raise ValueError rather than silently dropping the deadline.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Due date cannot be empty.")
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                "Invalid due date. Use YYYY-MM-DD or an ISO datetime such as "
                "2026-10-20T18:30:00+05:30."
            ) from exc
    else:
        raise ValueError("Due date must be an ISO date, ISO datetime, or null.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TIMEZONE)

    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def format_stored_due_date(value: datetime | None) -> str | None:
    """Serialize a stored UTC-naive datetime as an explicit UTC ISO string."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def current_local_datetime() -> datetime:
    """Return the current time as an aware datetime in APP_TIMEZONE."""
    return datetime.now(APP_TIMEZONE)
