"""Tests for processed day_state file loading."""

import json
import tempfile
from pathlib import Path

from utils.processed_history import load_last_n_processed_day_states


def test_load_last_n_oldest_first_and_before_date() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for stem in ["2026-01-01", "2026-01-02", "2026-01-03"]:
            p = d / f"{stem}.json"
            p.write_text(json.dumps({"date": stem}), encoding="utf-8")
        out = load_last_n_processed_day_states(d, 2, before_date="2026-01-03")
        assert [s["date"] for s in out] == ["2026-01-01", "2026-01-02"]
        out2 = load_last_n_processed_day_states(d, 2)
        assert [s["date"] for s in out2] == ["2026-01-02", "2026-01-03"]


def test_non_daily_json_ignored() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "notes.json").write_text("{}", encoding="utf-8")
        (d / "2026-05-01.json").write_text("{\"date\":\"x\"}", encoding="utf-8")
        assert len(load_last_n_processed_day_states(d, 5)) == 1
