"""Turn raw activity logs into session records."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.file_io import read_json

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

# ---------------------------------------------------------------------------
# Tags — edit here only. Sources:
#   1) Words from ``window_title`` (split, lowercase, deduped).
#   2) Each event's ``category`` (after categorization), if enabled.
#   3) ``title_phrase_to_tag``: if phrase appears in title, add semantic tag.
# ---------------------------------------------------------------------------
TAG_EXTRACTION: dict[str, Any] = {
    "min_length": 2,
    "replace_with_space": ".,;:()[]{}\"'·|–—/",
    "stopwords": [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    ],
    "include_categories_as_tags": True,
    "category_values_to_skip": ["general"],
    "title_phrase_to_tag": [
        ["elden ring", "gaming"],
        ["python", "coding"],
        ["cursor", "coding"],
        ["manga","reading"],
        ["novel","reading"],
        ["tethercraft","writing"],
        ["chemical","studying"]
    ],
}


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


def compute_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum session durations by total, app, and category.

    Args:
        events: Session-like dicts with ``duration_seconds``, ``app``, and
            optionally ``category`` (defaults to :data:`DEFAULT_CATEGORY`).

    Returns:
        ``total_time`` (seconds), ``app_usage`` and ``category_usage`` maps
        from name to summed seconds (ints).
    """
    total_time = 0
    app_usage: dict[str, int] = {}
    category_usage: dict[str, int] = {}

    for row in events:
        seconds = int(row.get("duration_seconds", 0))
        total_time += seconds
        app = str(row.get("app", ""))
        app_usage[app] = app_usage.get(app, 0) + seconds
        cat = str(row.get("category", DEFAULT_CATEGORY))
        category_usage[cat] = category_usage.get(cat, 0) + seconds

    return {
        "total_time": total_time,
        "app_usage": app_usage,
        "category_usage": category_usage,
    }


def _title_tokens(title: str, settings: dict[str, Any]) -> list[str]:
    """Split a window title into candidate tag strings.

    Args:
        title: Raw window title.
        settings: Normally :data:`TAG_EXTRACTION`.

    Returns:
        Lowercase word tokens after filtering by length and stopwords.
    """
    min_len = int(settings.get("min_length", 2))
    stops = {str(s).lower() for s in settings.get("stopwords", [])}
    text = title.lower()
    for ch in str(settings.get("replace_with_space", "")):
        text = text.replace(ch, " ")
    out: list[str] = []
    for word in text.split():
        w = word.strip("-_")
        if len(w) >= min_len and w not in stops:
            out.append(w)
    return out


def _phrase_rules_from_config(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """Build (phrase, tag) pairs longest-first for simple title substring checks.

    Args:
        cfg: Normally :data:`TAG_EXTRACTION`.

    Returns:
        List of ``(phrase_lower, tag_lower)`` sorted by phrase length descending.
    """
    raw = cfg.get("title_phrase_to_tag", [])
    pairs: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((str(item[0]).lower(), str(item[1]).lower()))
    pairs.sort(key=lambda x: -len(x[0]))
    return pairs


def _semantic_tags_from_title(title: str, phrase_rules: list[tuple[str, str]]) -> list[str]:
    """Map title text to semantic tags using substring rules.

    Args:
        title: Window title.
        phrase_rules: From :func:`_phrase_rules_from_config`.

    Returns:
        Tags implied by phrase matches (may repeat; caller dedupes).
    """
    hay = title.lower()
    out: list[str] = []
    for phrase, tag in phrase_rules:
        if phrase in hay:
            out.append(tag)
    return out


def extract_tags(events: list[dict[str, Any]]) -> list[str]:
    """Unique tags from window titles, categories, and phrase rules.

    Title words: split, lowercase, drop stopwords / short tokens.
    Categories: each event's ``category`` value (optional skip list).
    Phrases: see ``title_phrase_to_tag`` in :data:`TAG_EXTRACTION`.

    Args:
        events: Session-like dicts with ``window_title`` and optionally
            ``category``.

    Returns:
        Sorted list of distinct tags.
    """
    cfg = TAG_EXTRACTION
    phrase_rules = _phrase_rules_from_config(cfg)
    skip_cats = {str(s).lower() for s in cfg.get("category_values_to_skip", [])}
    include_cat = bool(cfg.get("include_categories_as_tags", True))
    seen: dict[str, None] = {}
    for row in events:
        title = str(row.get("window_title", ""))
        for token in _title_tokens(title, cfg):
            seen[token] = None
        for tag in _semantic_tags_from_title(title, phrase_rules):
            seen[tag] = None
        if include_cat:
            cat = str(row.get("category", "")).strip().lower()
            if cat and cat not in skip_cats:
                seen[cat] = None
    return sorted(seen.keys())


_DAY_STEM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _date_for_day_state(path: Path, logs: list[dict[str, Any]]) -> str:
    """Pick ``YYYY-MM-DD`` from the log filename or the first log row.

    Args:
        path: Path to the daily JSON log file.
        logs: Raw log entries (may be empty).

    Returns:
        Date string, or empty if it cannot be inferred.
    """
    stem = path.stem
    if _DAY_STEM_RE.match(stem):
        return stem
    if logs:
        ts = str(logs[0].get("timestamp", ""))
        if len(ts) >= 10:
            prefix = ts[:10]
            if _DAY_STEM_RE.match(prefix):
                return prefix
    return ""


def build_day_state(log_file_path: str | Path) -> dict[str, Any]:
    """Load a daily log file and produce sessions, metrics, and tags.

    Args:
        log_file_path: JSON file of log entries (array), e.g. ``YYYY-MM-DD.json``.

    Returns:
        Dict with ``date``, ``events`` (categorized sessions), ``metrics``,
        ``tags``, and ``anomalies`` (empty list for now).

    Raises:
        FileNotFoundError: If the log file is missing.
        json.JSONDecodeError: If the file is not valid JSON.
        OSError: If the file cannot be read.
    """
    path = Path(log_file_path)
    raw = read_json(path)
    logs: list[dict[str, Any]] = raw if isinstance(raw, list) else []

    events = build_sessions(logs)
    apply_categories_to_sessions(events)
    metrics = compute_metrics(events)
    tags = extract_tags(events)

    return {
        "date": _date_for_day_state(path, logs),
        "events": events,
        "metrics": metrics,
        "tags": tags,
        "anomalies": [],
    }


def process_logs() -> None:
    """Placeholder log processor."""
    print("process_logs")
