"""Deterministic anomaly detection: compare today vs recent category baselines."""

from typing import Any

# Today must exceed this multiple of the past-day average to count as a spike.
_SPIKE_FACTOR = 1.8
# Today must fall below this fraction of the past-day average to count as a drop.
_DROP_FACTOR = 0.5


def _category_usage(day_state: dict[str, Any]) -> dict[str, float]:
    """Extract ``metrics.category_usage`` as string keys and float seconds.

    Args:
        day_state: Argus day_state dict.

    Returns:
        Mapping category -> seconds; empty dict if missing or invalid.
    """
    metrics = day_state.get("metrics", {})
    raw = metrics.get("category_usage", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key)
        try:
            out[name] = float(value)
        except (TypeError, ValueError):
            out[name] = 0.0
    return out


def detect_glitches(
    current_day_state: dict[str, Any],
    past_day_states: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Find categories where today diverges strongly from recent daily averages.

    Baseline for each category is the arithmetic mean of that category's
    seconds across ``past_day_states``. Missing categories in a past day count
    as 0 for that day. Comparisons run only when the baseline average is
    strictly positive (avoids divide-by-zero and undefined ratios).

    Args:
        current_day_state: Today's structured day state.
        past_day_states: Prior days (e.g. last N), oldest-to-newest or any order;
            each must follow the same shape as ``current_day_state``.

    Returns:
        A list of glitch dicts with ``type`` (``time_spike`` | ``time_drop``),
        ``category``, and ``description``. Sorted by ``category`` then ``type``
        for stable output.
    """
    if not past_day_states:
        return []

    today = _category_usage(current_day_state)
    n_past = len(past_day_states)

    # Every category seen today or in any past window
    all_categories: set[str] = set(today.keys())
    for past in past_day_states:
        all_categories |= set(_category_usage(past).keys())

    # Sum per category across past days (missing -> 0 per day)
    past_totals: dict[str, float] = {c: 0.0 for c in all_categories}
    for past in past_day_states:
        usage = _category_usage(past)
        for cat in all_categories:
            past_totals[cat] += float(usage.get(cat, 0.0))

    findings: list[dict[str, str]] = []

    for category in sorted(all_categories):
        today_seconds = float(today.get(category, 0.0))
        baseline_avg = past_totals[category] / n_past

        if baseline_avg <= 0.0:
            # No meaningful baseline; skip ratio-based rules
            continue

        ratio = today_seconds / baseline_avg

        if ratio > _SPIKE_FACTOR:
            findings.append(
                {
                    "type": "time_spike",
                    "category": category,
                    "description": (
                        f"{category} usage is about {ratio:.1f}x your recent daily "
                        f"average (threshold {_SPIKE_FACTOR}x)"
                    ),
                },
            )
        elif ratio < _DROP_FACTOR:
            findings.append(
                {
                    "type": "time_drop",
                    "category": category,
                    "description": (
                        f"{category} usage is about {ratio:.1f}x your recent daily "
                        f"average (below {_DROP_FACTOR}x)"
                    ),
                },
            )

    findings.sort(key=lambda row: (row["category"], row["type"]))
    return findings
