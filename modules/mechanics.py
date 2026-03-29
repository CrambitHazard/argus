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


def _float_metric(mapping: dict[str, Any], key: str) -> float:
    """Parse a numeric value from a metrics map, or 0.0 if missing/invalid."""
    raw = mapping.get(key, 0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _seconds_for_condition_label(
    category_usage: dict[str, Any],
    tag_usage: dict[str, Any],
    label: str,
) -> float:
    """Seconds for one condition string, using categories and/or semantic tags.

    Argus stores broad **categories** (e.g. entertainment) in
    ``category_usage`` and phrase-driven **tags** (e.g. reading, writing) in
    ``tag_usage``. The same label rarely needs both; when it appears in both,
    we take the **max** so one session is not double-counted.

    Args:
        category_usage: ``metrics.category_usage``.
        tag_usage: ``metrics.tag_usage``.
        label: One entry from a divine word's ``conditions`` list.

    Returns:
        Seconds attributed to that label for scoring.
    """
    key = str(label)
    cat_part = _float_metric(category_usage, key)
    tag_part = _float_metric(tag_usage, key)
    return max(cat_part, tag_part)


def _matched_seconds_for_conditions(
    category_usage: dict[str, Any],
    tag_usage: dict[str, Any],
    conditions: Any,
) -> float:
    """Sum per-label seconds for all strings in ``conditions``.

    Args:
        category_usage: Map category -> seconds.
        tag_usage: Map tag -> seconds.
        conditions: List of labels to match in either map (see above).

    Returns:
        Total seconds for the divine word's condition list.
    """
    if not isinstance(conditions, list):
        return 0.0
    total = 0.0
    for item in conditions:
        total += _seconds_for_condition_label(
            category_usage,
            tag_usage,
            str(item),
        )
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
    """Score divine words from category + tag time and weighted JSON rules.

    Each ``conditions`` label is matched against **both**
    ``metrics.category_usage`` and ``metrics.tag_usage`` (semantic tags from
    phrase rules). Per label we use ``max(category_seconds, tag_seconds)`` so
    overlapping keys are not double-counted; labels in the list are **summed**
    (e.g. Creation: reading + writing).

    Args:
        day_state: Argus day state with ``metrics.category_usage`` and
            ``metrics.tag_usage``.
        config_path: Path to divine word rules (see ``data/config/divine_words.json``).

    Returns:
        ``scores``: max-normalized floats. ``dominant_words``: top names with
        score > 0. Optional ``_settings.dominant_count`` in the JSON config.
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
    tag_usage = metrics.get("tag_usage", {})
    if not isinstance(tag_usage, dict):
        tag_usage = {}

    # 1) Raw weighted score = (sum over conditions, each max(cat, tag)) * weight
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
        matched_seconds = _matched_seconds_for_conditions(
            category_usage,
            tag_usage,
            conditions,
        )
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
