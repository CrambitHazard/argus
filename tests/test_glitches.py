"""Tests for glitch detection."""

from modules.glitches import detect_glitches


def _state(category_usage: dict[str, float]) -> dict:
    return {"metrics": {"category_usage": category_usage}}


def test_empty_past_returns_no_glitches() -> None:
    assert detect_glitches(_state({"x": 100}), []) == []


def test_spike_when_today_exceeds_threshold() -> None:
    past = [_state({"fun": 100}), _state({"fun": 100})]
    today = _state({"fun": 200})  # avg 100, today 200 -> 2.0x > 1.8
    out = detect_glitches(today, past)
    assert any(g["type"] == "time_spike" and g["category"] == "fun" for g in out)


def test_drop_when_today_below_threshold() -> None:
    past = [_state({"work": 100}), _state({"work": 100})]
    today = _state({"work": 40})  # avg 100, today 40 -> 0.4x < 0.5
    out = detect_glitches(today, past)
    assert any(g["type"] == "time_drop" and g["category"] == "work" for g in out)


def test_missing_category_in_past_counts_as_zero() -> None:
    past = [_state({"a": 0}), _state({"a": 0})]
    today = _state({"a": 10})
    # baseline avg 0 -> skip
    assert detect_glitches(today, past) == []


def test_stable_sorting() -> None:
    past = [_state({"b": 50, "a": 50}), _state({"b": 50, "a": 50})]
    today = _state({"a": 100, "b": 100})  # 2x both -> spikes
    out = detect_glitches(today, past)
    cats = [g["category"] for g in out if g["type"] == "time_spike"]
    assert cats == sorted(cats)
