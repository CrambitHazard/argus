"""Turn raw activity logs into session records."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.glitches import detect_glitches
from modules.mechanics import compute_divine_words
from utils.file_io import read_json, write_json
from utils.helpers import load_config
from utils.processed_history import load_last_n_processed_day_states

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
        "title_contains": ["code", "vscode", "GitHub"],
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
# Tags — edit here only.
#   * ``title_phrase_to_tag``: phrases in the window title → semantic tags on
#     each **session** (``events[].tags``). Also drives ``metrics.tag_usage``.
#   * Optional extras for the day-level ``tags`` list (off by default):
#     ``include_title_word_tags``, ``include_categories_in_day_tags_list``.
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
    "include_title_word_tags": False,
    "include_categories_in_day_tags_list": False,
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


def _recompute_session_durations(
    sessions: list[dict[str, Any]], sampling_interval_seconds: int,
) -> None:
    """Assign ``duration_seconds`` so time is attributed until the next session.

    Each session (except the last) gets duration = next ``start_time`` minus
    this ``start_time``. The last session uses ``end_time - start_time``, or
    ``sampling_interval_seconds`` when that span is zero (single sample).

    Args:
        sessions: Session dicts from the merge pass; updated in place.
        sampling_interval_seconds: Config ``log_interval_seconds`` (minimum 1).
    """
    n = len(sessions)
    if n == 0:
        return
    starts = [_parse_timestamp(str(s["start_time"])) for s in sessions]
    ends = [_parse_timestamp(str(s["end_time"])) for s in sessions]
    interval = max(1, int(sampling_interval_seconds))
    for i in range(n - 1):
        delta = (starts[i + 1] - starts[i]).total_seconds()
        sessions[i]["duration_seconds"] = max(0, int(delta))
    last = n - 1
    span = int((ends[last] - starts[last]).total_seconds())
    if span > 0:
        sessions[last]["duration_seconds"] = span
    else:
        sessions[last]["duration_seconds"] = interval


def build_sessions(
    logs: list[dict[str, Any]],
    sampling_interval_seconds: int = 5,
) -> list[dict[str, Any]]:
    """Merge consecutive log rows into sessions (same app/title, gap ≤ 15s).

    Args:
        logs: Log dicts with ``timestamp``, ``app``, ``window_title``; sorted
            oldest-first.
        sampling_interval_seconds: From config; used for the last session's
            duration when only one sample exists in that session.

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
    _recompute_session_durations(sessions, sampling_interval_seconds)
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


def apply_semantic_tags_to_sessions(sessions: list[dict[str, Any]]) -> None:
    """Set ``tags`` on each session from ``title_phrase_to_tag`` substring rules.

    Args:
        sessions: Session dicts with ``window_title``; updated in place.
    """
    rules = _phrase_rules_from_config(TAG_EXTRACTION)
    for row in sessions:
        title = str(row.get("window_title", ""))
        ordered: dict[str, None] = {}
        for tag in _semantic_tags_from_title(title, rules):
            ordered.setdefault(tag, None)
        row["tags"] = list(ordered.keys())


def compute_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum session durations by total, app, category, and semantic tags.

    Args:
        events: Session-like dicts with ``duration_seconds``, ``app``, optional
            ``category``, and optional ``tags`` (list of strings).

    Returns:
        ``total_time``, ``app_usage``, ``category_usage``, and ``tag_usage``
        (seconds per semantic tag from ``title_phrase_to_tag``).
    """
    total_time = 0
    app_usage: dict[str, int] = {}
    category_usage: dict[str, int] = {}
    tag_usage: dict[str, int] = {}

    for row in events:
        seconds = int(row.get("duration_seconds", 0))
        total_time += seconds
        app = str(row.get("app", ""))
        app_usage[app] = app_usage.get(app, 0) + seconds
        cat = str(row.get("category", DEFAULT_CATEGORY))
        category_usage[cat] = category_usage.get(cat, 0) + seconds
        for tag in row.get("tags", []):
            t = str(tag).strip().lower()
            if t:
                tag_usage[t] = tag_usage.get(t, 0) + seconds

    return {
        "total_time": total_time,
        "app_usage": app_usage,
        "category_usage": category_usage,
        "tag_usage": tag_usage,
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
    """Distinct day-level tags: union of each session's ``tags`` by default.

    Optional: ``include_title_word_tags`` and
    ``include_categories_in_day_tags_list`` in :data:`TAG_EXTRACTION`.

    Args:
        events: Sessions after :func:`apply_semantic_tags_to_sessions`.

    Returns:
        Sorted list of distinct tag strings.
    """
    cfg = TAG_EXTRACTION
    seen: dict[str, None] = {}
    for row in events:
        for tag in row.get("tags", []):
            t = str(tag).strip().lower()
            if t:
                seen[t] = None
    if cfg.get("include_title_word_tags", False):
        phrase_rules = _phrase_rules_from_config(cfg)
        for row in events:
            title = str(row.get("window_title", ""))
            for token in _title_tokens(title, cfg):
                seen[token] = None
            for tag in _semantic_tags_from_title(title, phrase_rules):
                seen[tag] = None
    if cfg.get("include_categories_in_day_tags_list", False):
        skip_cats = {str(s).lower() for s in cfg.get("category_values_to_skip", [])}
        for row in events:
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


def build_day_state(
    log_file_path: str | Path,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a daily log file and produce sessions, metrics, and tags.

    Args:
        log_file_path: JSON file of log entries (array), e.g. ``YYYY-MM-DD.json``.
        config: Optional loaded config (for ``log_interval_seconds``). If
            omitted, :func:`utils.helpers.load_config` is used.

    Returns:
        Dict with ``date``, ``events`` (categorized sessions with ``tags``),
        ``metrics`` (includes ``tag_usage``), ``tags``, and ``anomalies``.

    Raises:
        FileNotFoundError: If the log file is missing.
        json.JSONDecodeError: If the file is not valid JSON.
        OSError: If the file cannot be read.
    """
    path = Path(log_file_path)
    raw = read_json(path)
    logs: list[dict[str, Any]] = raw if isinstance(raw, list) else []

    cfg = config if config is not None else load_config()
    interval = int(cfg.get("log_interval_seconds", 5))
    events = build_sessions(logs, sampling_interval_seconds=interval)
    apply_categories_to_sessions(events)
    apply_semantic_tags_to_sessions(events)
    metrics = compute_metrics(events)
    tags = extract_tags(events)

    return {
        "date": _date_for_day_state(path, logs),
        "events": events,
        "metrics": metrics,
        "tags": tags,
        "anomalies": [],
    }


def enrich_day_state_with_mechanics(
    state: dict[str, Any],
    config: dict[str, Any],
    project_root: Path,
) -> None:
    """Attach ``divine_words`` and ``glitches`` to ``state`` (mutates in place).

    Divine words use ``compute_divine_words`` and config path
    ``divine_words_config``. Glitches use ``detect_glitches`` against the last
    ``glitch_lookback_days`` processed files strictly before ``state["date"]``.

    Args:
        state: Output of :func:`build_day_state`.
        config: Loaded Argus config (paths and optional mechanics keys).
        project_root: Repository root (parent of ``modules/``).
    """
    divine_rel = config.get("divine_words_config", "data/config/divine_words.json")
    divine_path = project_root / Path(divine_rel)
    divine_result = compute_divine_words(state, divine_path)
    state["divine_words"] = {
        "scores": divine_result["scores"],
        "dominant": divine_result["dominant_words"],
    }

    proc_rel = config.get("data_paths", {}).get("processed", "data/processed/")
    proc_dir = project_root / Path(proc_rel)
    try:
        lookback = int(config.get("glitch_lookback_days", 7))
    except (TypeError, ValueError):
        lookback = 7
    lookback = max(0, lookback)
    current_date = str(state.get("date", ""))
    past_states = load_last_n_processed_day_states(
        proc_dir,
        lookback,
        before_date=current_date or None,
    )
    state["glitches"] = detect_glitches(state, past_states)


def _pick_latest_log_file(logs_dir: Path) -> Path | None:
    """Newest ``YYYY-MM-DD.json`` in a directory, else newest ``*.json`` by mtime.

    Args:
        logs_dir: Folder under the project that holds raw daily logs.

    Returns:
        Chosen file path, or ``None`` if there are no JSON files.
    """
    if not logs_dir.is_dir():
        return None
    daily = [p for p in logs_dir.glob("*.json") if _DAY_STEM_RE.match(p.stem)]
    if daily:
        return max(daily, key=lambda p: p.stem)
    any_json = list(logs_dir.glob("*.json"))
    if not any_json:
        return None
    return max(any_json, key=lambda p: p.stat().st_mtime)


def process_logs(config: dict[str, Any]) -> None:
    """Load latest raw log, build day state, save under ``data/processed``."""
    root = Path(__file__).resolve().parent.parent
    logs_dir = root / Path(config["data_paths"]["logs"])
    proc_dir = root / Path(config["data_paths"]["processed"])
    latest = _pick_latest_log_file(logs_dir)
    if latest is None:
        print(f"No log JSON files found in {logs_dir}")
        return
    state = build_day_state(latest, config)
    if not state.get("date"):
        state["date"] = latest.stem
    enrich_day_state_with_mechanics(state, config, root)
    day_key = state.get("date") or latest.stem
    out_path = proc_dir / f"{day_key}.json"
    write_json(out_path, state)
    print(f"Processed {latest.name} -> {out_path}")
