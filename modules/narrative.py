"""Narrative pipeline: compress day_state into a minimal LLM-facing payload."""

from typing import Any


def _top_keys_by_usage(usage: dict[str, Any], limit: int) -> list[str]:
    """Return the top ``limit`` keys by numeric value, ties broken by key name.

    Args:
        usage: Map of name -> seconds (or other comparable totals).
        limit: Maximum number of keys to return (0 → ``[]``).

    Returns:
        Sorted-by-usage-descending key names, stable under equal values.
    """
    if limit <= 0 or not isinstance(usage, dict):
        return []
    pairs: list[tuple[str, float]] = []
    for key, raw in usage.items():
        name = str(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        pairs.append((name, value))
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return [name for name, _ in pairs[:limit]]


def _int_category_usage(category_usage: dict[str, Any]) -> dict[str, int]:
    """Copy category_usage with integer seconds."""
    out: dict[str, int] = {}
    if not isinstance(category_usage, dict):
        return out
    for key, raw in category_usage.items():
        try:
            out[str(key)] = int(raw)
        except (TypeError, ValueError):
            out[str(key)] = 0
    return out


def _slim_glitch_row(row: Any) -> dict[str, str]:
    """Keep only type and category for a compact glitch line."""
    if not isinstance(row, dict):
        return {"type": "", "category": ""}
    return {
        "type": str(row.get("type", "")),
        "category": str(row.get("category", "")),
    }


def build_narrative_input(day_state: dict[str, Any]) -> dict[str, Any]:
    """Derive a small, deterministic summary dict for LLM narrative generation.

    Pulls top apps/categories/tags by usage, core time totals, dominant divine
    words, and slim glitch rows. No model calls.

    Args:
        day_state: Full Argus processed day (``date``, ``metrics``, ``tags``,
            ``divine_words``, ``glitches``, etc.).

    Returns:
        Minimal structure: ``date``, ``summary`` (2 apps, 2 categories, 3 tags),
        ``metrics`` (``total_time``, full ``category_usage`` as ints),
        ``divine_words.dominant``, and ``glitches`` (``type`` + ``category`` only).
    """
    metrics = day_state.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    app_usage = metrics.get("app_usage", {})
    category_usage = metrics.get("category_usage", {})
    tag_usage = metrics.get("tag_usage", {})
    if not isinstance(app_usage, dict):
        app_usage = {}
    if not isinstance(category_usage, dict):
        category_usage = {}
    if not isinstance(tag_usage, dict):
        tag_usage = {}

    top_apps = _top_keys_by_usage(app_usage, 2)
    top_categories = _top_keys_by_usage(category_usage, 2)
    key_tags = _top_keys_by_usage(tag_usage, 3)

    if not key_tags:
        raw_tags = day_state.get("tags", [])
        if isinstance(raw_tags, list) and raw_tags:
            key_tags = sorted({str(t) for t in raw_tags})[:3]

    total_raw = metrics.get("total_time", 0)
    try:
        total_time = int(total_raw)
    except (TypeError, ValueError):
        total_time = 0

    divine = day_state.get("divine_words", {})
    if not isinstance(divine, dict):
        divine = {}
    dominant = divine.get("dominant", [])
    if not isinstance(dominant, list):
        dominant = []
    dominant_clean = [str(x) for x in dominant]

    glitches_raw = day_state.get("glitches", [])
    if not isinstance(glitches_raw, list):
        glitches_raw = []
    glitches_slim = [_slim_glitch_row(g) for g in glitches_raw]

    return {
        "date": str(day_state.get("date", "")),
        "summary": {
            "top_apps": top_apps,
            "top_categories": top_categories,
            "key_tags": key_tags,
        },
        "metrics": {
            "total_time": total_time,
            "category_usage": _int_category_usage(category_usage),
        },
        "divine_words": {
            "dominant": dominant_clean,
        },
        "glitches": glitches_slim,
    }


def generate_outputs() -> None:
    """Placeholder narrative / output generation."""
    print("generate_outputs")
