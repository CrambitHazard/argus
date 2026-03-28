"""Turn raw activity logs into session records."""

from datetime import datetime
from typing import Any

_GAP_SECONDS = 15
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_timestamp(value: str) -> datetime:
    """Parse a log ``timestamp`` string.

    Args:
        value: Local time string ``YYYY-MM-DD HH:MM:SS``.

    Returns:
        Parsed datetime.

    Raises:
        ValueError: If the string does not match the expected format.
    """
    return datetime.strptime(value, _TS_FORMAT)


def _format_timestamp(value: datetime) -> str:
    """Format datetime for session ``start_time`` / ``end_time`` fields.

    Args:
        value: Instant to format.

    Returns:
        String in ``YYYY-MM-DD HH:MM:SS`` form.
    """
    return value.strftime(_TS_FORMAT)


def build_sessions(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive log rows into sessions (same app/title, gap ≤ 15s).

    Args:
        logs: Log dicts with ``timestamp``, ``app``, ``window_title``; sorted
            oldest-first.

    Returns:
        Session dicts with ``start_time``, ``end_time``, ``duration_seconds``,
        ``app``, ``window_title`` (aligned with ``sample_day_state.json``
        ``events`` timing fields, without ``category``).
    """
    if not logs:
        return []

    sessions: list[dict[str, Any]] = []
    start = _parse_timestamp(str(logs[0]["timestamp"]))
    end = start
    app = str(logs[0].get("app", ""))
    window_title = str(logs[0].get("window_title", ""))

    for row in logs[1:]:
        t = _parse_timestamp(str(row["timestamp"]))
        row_app = str(row.get("app", ""))
        row_title = str(row.get("window_title", ""))
        gap = (t - end).total_seconds()

        if row_app == app and row_title == window_title and 0 <= gap <= _GAP_SECONDS:
            end = t
            continue

        duration = int((end - start).total_seconds())
        sessions.append(
            {
                "start_time": _format_timestamp(start),
                "end_time": _format_timestamp(end),
                "duration_seconds": duration,
                "app": app,
                "window_title": window_title,
            },
        )
        start = t
        end = t
        app = row_app
        window_title = row_title

    duration = int((end - start).total_seconds())
    sessions.append(
        {
            "start_time": _format_timestamp(start),
            "end_time": _format_timestamp(end),
            "duration_seconds": duration,
            "app": app,
            "window_title": window_title,
        },
    )
    return sessions


def process_logs() -> None:
    """Placeholder log processor."""
    print("process_logs")
