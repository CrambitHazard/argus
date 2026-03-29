"""Deterministic mechanics: Divine Word scores from day_state and JSON rules."""

import json
from pathlib import Path
from typing import Any

_DEFAULT_DOMINANT_COUNT = 3


def load_json_config(config_path: str | Path) -> dict[str, Any]:
    """Load a JSON object from disk; fail safe for missing or invalid files.

    Args:
        config_path: Path to a UTF-8 JSON file whose root is an object.

    Returns:
        The parsed dict, or an empty dict if the path is not a file, the JSON
        is invalid, or the root value is not an object.
    """
    path = Path(config_path)
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _category_seconds_for_conditions(
    category_usage: dict[str, Any],
    conditions: Any,
) -> float:
    """Sum seconds for each category name listed in ``conditions``.

    Args:
        category_usage: Map category name -> seconds (from ``day_state``).
        conditions: Iterable of category strings, or invalid types yield 0.

    Returns:
        Total seconds attributed to those categories (missing keys count as 0).
    """
    if not isinstance(conditions, list):
        return 0.0
    total = 0.0
    for cat in conditions:
        key = str(cat)
        raw = category_usage.get(key, 0)
        try:
            total += float(raw)
        except (TypeError, ValueError):
            continue
    return total


def _normalize_scores_to_unit_max(raw_scores: dict[str, float]) -> dict[str, float]:
    """Scale scores so the largest value is 1.0; all zero stays zero.

    Args:
        raw_scores: Non-negative weighted sums per divine word.

    Returns:
        Same keys, values in [0, 1]. If every value is 0, all outputs are 0.0.
        Avoids division by zero.
    """
    if not raw_scores:
        return {}
    peak = max(raw_scores.values())
    if peak <= 0.0:
        return {name: 0.0 for name in raw_scores}
    return {name: float(value) / peak for name, value in raw_scores.items()}


def compute_divine_words(
    day_state: dict[str, Any],
    config_path: str | Path,
) -> dict[str, Any]:
    """Score divine words from category time and weighted JSON rules.

    For each word in the config, matched seconds are the sum of
    ``metrics.category_usage`` over that word's ``conditions`` categories,
    multiplied by ``weight``. Scores are then max-normalized to [0, 1] for
    stable comparison. ``dominant_words`` are the top labels by normalized
    score (ties broken alphabetically), excluding zero scores.

    Args:
        day_state: Argus day state with ``metrics.category_usage``.
        config_path: Path to divine word rules (see ``data/config/divine_words.json``).

    Returns:
        ``scores``: normalized float per configured word (0 when no category match).
        ``dominant_words``: up to ``dominant_count`` names with score > 0, sorted
        best-first. Optional config key ``_settings`` may include
        ``"dominant_count": int`` (default 3).
    """
    rules = load_json_config(config_path)
    settings = rules.get("_settings", {})
    dominant_count = _DEFAULT_DOMINANT_COUNT
    if isinstance(settings, dict):
        try:
            dominant_count = max(1, int(settings.get("dominant_count", dominant_count)))
        except (TypeError, ValueError):
            dominant_count = _DEFAULT_DOMINANT_COUNT

    metrics = day_state.get("metrics", {})
    category_usage = metrics.get("category_usage", {})
    if not isinstance(category_usage, dict):
        category_usage = {}

    # 1) Raw weighted score = (sum of seconds in listed categories) * weight
    raw_scores: dict[str, float] = {}
    for word_label, rule in rules.items():
        if word_label.startswith("_"):
            continue
        if not isinstance(rule, dict):
            continue
        conditions = rule.get("conditions", [])
        try:
            weight = float(rule.get("weight", 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        matched_seconds = _category_seconds_for_conditions(category_usage, conditions)
        raw_scores[str(word_label)] = matched_seconds * weight

    # 2) Normalize so the strongest signal is 1.0 (deterministic, explainable)
    scores = _normalize_scores_to_unit_max(raw_scores)

    # 3) Stable ordering: higher score first, then label A-Z
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    dominant_words = [
        name for name, value in ranked[:dominant_count] if value > 0.0
    ]

    return {
        "scores": scores,
        "dominant_words": dominant_words,
    }


def apply_mechanics() -> None:
    """Placeholder mechanics step."""
    print("apply_mechanics")
