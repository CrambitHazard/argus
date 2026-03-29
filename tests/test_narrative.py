"""Tests for narrative input shaping."""

from modules.narrative import build_narrative_input


def test_build_narrative_input_limits_and_ordering() -> None:
    state = {
        "date": "2026-01-01",
        "metrics": {
            "total_time": 100,
            "app_usage": {"b.exe": 10, "a.exe": 30, "c.exe": 20},
            "category_usage": {"y": 5, "z": 50, "x": 50},
            "tag_usage": {"t1": 1, "t2": 2, "t3": 3, "t4": 4},
        },
        "divine_words": {"dominant": ["Focus"]},
        "glitches": [
            {"type": "time_spike", "category": "x", "description": "long text"},
        ],
    }
    out = build_narrative_input(state)
    assert out["date"] == "2026-01-01"
    assert out["summary"]["top_apps"] == ["a.exe", "c.exe"]
    assert out["summary"]["top_categories"] == ["x", "z"]
    assert out["summary"]["key_tags"] == ["t4", "t3", "t2"]
    assert out["metrics"]["total_time"] == 100
    assert out["metrics"]["category_usage"] == {"y": 5, "z": 50, "x": 50}
    assert out["divine_words"]["dominant"] == ["Focus"]
    assert out["glitches"] == [{"type": "time_spike", "category": "x"}]


def test_key_tags_fallback_to_day_tags_list() -> None:
    state = {
        "date": "d",
        "metrics": {"total_time": 0, "category_usage": {}, "tag_usage": {}},
        "tags": ["zebra", "apple", "mango", "banana"],
        "divine_words": {},
        "glitches": [],
    }
    out = build_narrative_input(state)
    assert out["summary"]["key_tags"] == ["apple", "banana", "mango"]
