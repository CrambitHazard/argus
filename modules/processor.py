"""Turn raw activity logs into session records."""

from datetime import datetime
from typing import Any

_GAP_SECONDS = 15
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Categories — edit this list only. Order matters: first matching rule wins.
# Each rule: category name, substrings to find in window title, in app name.
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[dict[str, Any]] = [
    {
        "category": "entertainment",
        "title_contains": ["youtube", "manga"],
        "app_contains": [],
    },
    {
        "category": "coding",
        "title_contains": ["code", "vscode"],
        "app_contains": ["code.exe", "Cursor.exe", "devenv.exe"],
    },
    {
        "category": "research",
        "title_contains": ["chatgpt", "arxiv"],
        "app_contains": [],
    },
    {
        "category": "study",
        "title_contains": ["iris", "chemical"],
        "app_contains": [],
    }
]

DEFAULT_CATEGORY = "general"


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


def categorize_event(event: dict[str, Any]) -> str:
    """Pick a category from ``CATEGORY_RULES`` using app and window title.

    Args:
        event: Dict with ``app`` and ``window_title`` (e.g. a session dict).

    Returns:
        Category string, or ``DEFAULT_CATEGORY`` when no rule matches.
    """
    title = str(event.get("window_title", "")).lower()
    app = str(event.get("app", "")).lower()
    for rule in CATEGORY_RULES:
        label = str(rule["category"])
        for needle in rule.get("title_contains", []):
            if str(needle).lower() in title:
                return label
        for needle in rule.get("app_contains", []):
            if str(needle).lower() in app:
                return label
    return DEFAULT_CATEGORY


def apply_categories_to_sessions(sessions: list[dict[str, Any]]) -> None:
    """Set ``category`` on each session using :func:`categorize_event`.

    Args:
        sessions: Session dicts from :func:`build_sessions`; updated in place.
    """
    for row in sessions:
        row["category"] = categorize_event(row)


def process_logs() -> None:
    """Placeholder log processor."""
    print("process_logs")
