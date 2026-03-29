"""Tests for Divine Word engine."""

from pathlib import Path

from modules.mechanics import compute_divine_words, load_json_config


def test_compute_divine_words_normalization_and_dominant() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = root / "data" / "config" / "divine_words.json"
    day_state = {
        "metrics": {
            "category_usage": {
                "coding": 100,
                "entertainment": 50,
                "learning": 0,
            },
        },
    }
    out = compute_divine_words(day_state, cfg)
    assert "scores" in out and "dominant_words" in out
    # Focus = (coding + learning) * 1 = 100; Drift = entertainment * 1 = 50; max=100
    assert out["scores"]["Focus"] == 1.0
    assert out["scores"]["Drift"] == 0.5
    assert out["dominant_words"][0] == "Focus"


def test_load_json_config_missing_file() -> None:
    assert load_json_config(Path("/nonexistent/path/divine.json")) == {}


def test_no_category_usage_all_zero_scores() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = root / "data" / "config" / "divine_words.json"
    out = compute_divine_words({"metrics": {}}, cfg)
    for v in out["scores"].values():
        assert v == 0.0
    assert out["dominant_words"] == []
