"""Tests for diary generation (mocked LLM)."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from modules.narrative import (
    build_diary_fact_sheet,
    generate_diary,
    narrative_input_to_text_block,
    _build_diary_prompt,
)


def test_narrative_input_to_text_block_includes_metrics() -> None:
    payload = {
        "date": "2026-01-05",
        "summary": {
            "top_apps": ["a.exe"],
            "top_categories": ["coding"],
            "key_tags": ["reading"],
        },
        "metrics": {"total_time": 100, "category_usage": {"coding": 100}},
        "divine_words": {"dominant": ["Focus"]},
        "glitches": [{"type": "time_spike", "category": "coding"}],
    }
    text = narrative_input_to_text_block(payload)
    assert "2026-01-05" in text
    assert "coding: 100" in text
    assert "time_spike" in text


def test_build_diary_prompt_bans_metrics_speak() -> None:
    p = _build_diary_prompt("Calendar date: X.")
    assert "REFERENCE" in p
    assert "Calendar date: X." in p
    assert "tracker" in p.lower()
    assert "700" in p or "words" in p
    assert "first person" in p.lower()


def test_build_diary_fact_sheet_avoids_raw_json_labels() -> None:
    payload = {
        "date": "2026-02-02",
        "summary": {
            "top_apps": ["Cursor.exe", "opera.exe"],
            "top_categories": [],
            "key_tags": ["reading"],
        },
        "metrics": {"total_time": 120, "category_usage": {"coding": 120}},
        "divine_words": {"dominant": ["Focus"]},
        "glitches": [],
    }
    sheet = build_diary_fact_sheet(payload)
    assert "Cursor.exe" not in sheet
    assert "code editor" in sheet
    assert "web browser" in sheet
    assert "2026-02-02" in sheet


@patch("modules.narrative.generate_text", return_value="Today was quiet.")
def test_generate_diary_writes_file(mock_gen: object) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = {"data_paths": {"outputs": "out/"}}
        payload = {
            "date": "2026-02-02",
            "summary": {"top_apps": [], "top_categories": [], "key_tags": []},
            "metrics": {"total_time": 0, "category_usage": {}},
            "divine_words": {"dominant": []},
            "glitches": [],
        }
        out = generate_diary(payload, config=cfg, project_root=root)
        path = root / "out" / "2026-02-02_diary.md"
        disk = path.read_text(encoding="utf-8")
        assert out == disk
        assert "# 2026-02-02" in out
        assert "Dear diary," in out
        assert "Today was quiet." in out
        assert out.rstrip().endswith("Me")
        mock_gen.assert_called_once()
        call_prompt = mock_gen.call_args[0][0]
        assert "2026-02-02" in call_prompt
        assert "REFERENCE" in call_prompt


@patch("modules.narrative.generate_text", return_value="")
def test_generate_diary_empty_api_writes_notice(mock_gen: object) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = {"data_paths": {"outputs": "out/"}}
        payload = {
            "date": "2026-03-01",
            "summary": {"top_apps": [], "top_categories": [], "key_tags": []},
            "metrics": {"total_time": 0, "category_usage": {}},
            "divine_words": {"dominant": []},
            "glitches": [],
        }
        out = generate_diary(payload, config=cfg, project_root=root)
        assert "[Argus] No diary text" in out
        path = root / "out" / "2026-03-01_diary.md"
        disk = path.read_text(encoding="utf-8")
        assert disk == out
        assert "# 2026-03-01" in disk
        assert "Dear diary," in disk
        assert disk.rstrip().endswith("Me")


def test_generate_diary_accepts_json_string() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = {"data_paths": {"outputs": "o/"}}
        s = json.dumps(
            {
                "date": "d",
                "summary": {"top_apps": [], "top_categories": [], "key_tags": []},
                "metrics": {"total_time": 0, "category_usage": {}},
                "divine_words": {"dominant": []},
                "glitches": [],
            },
        )
        with patch("modules.narrative.generate_text", return_value="x"):
            generate_diary(s, config=cfg, project_root=root)
        md = (root / "o" / "d_diary.md").read_text(encoding="utf-8")
        assert "# d" in md
        assert "Dear diary," in md
        assert "\nx\n" in md
        assert md.rstrip().endswith("Me")


@patch("modules.narrative.generate_text", return_value="Body.")
def test_generate_diary_uses_diary_author_name_env(mock_gen: object) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = {"data_paths": {"outputs": "out/"}}
        payload = {
            "date": "2026-04-01",
            "summary": {"top_apps": [], "top_categories": [], "key_tags": []},
            "metrics": {"total_time": 0, "category_usage": {}},
            "divine_words": {"dominant": []},
            "glitches": [],
        }
        with patch.dict(os.environ, {"DIARY_AUTHOR_NAME": "Alex"}, clear=False):
            out = generate_diary(payload, config=cfg, project_root=root)
        assert out.rstrip().endswith("Alex")
