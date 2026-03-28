"""Tests for session building, durations, semantic tags, and metrics."""

from modules.processor import (
    apply_categories_to_sessions,
    apply_semantic_tags_to_sessions,
    build_sessions,
    compute_metrics,
    extract_tags,
)


def test_session_durations_partition_timeline() -> None:
    """Duration runs until the next session start; last uses span or interval."""
    logs = [
        {"timestamp": "2026-01-01 10:00:00", "app": "a.exe", "window_title": "X"},
        {"timestamp": "2026-01-01 10:00:05", "app": "a.exe", "window_title": "X"},
        {"timestamp": "2026-01-01 10:00:30", "app": "b.exe", "window_title": "Y"},
    ]
    sessions = build_sessions(logs, sampling_interval_seconds=5)
    assert len(sessions) == 2
    assert sessions[0]["duration_seconds"] == 30
    assert sessions[1]["duration_seconds"] == 5


def test_semantic_tags_and_tag_usage_on_sessions() -> None:
    """Phrase rules attach tags to sessions; metrics count time per tag."""
    logs = [
        {
            "timestamp": "2026-01-01 12:00:00",
            "app": "x.exe",
            "window_title": "Learn Python basics",
        },
        {
            "timestamp": "2026-01-01 12:00:20",
            "app": "x.exe",
            "window_title": "Learn Python basics",
        },
    ]
    sessions = build_sessions(logs, sampling_interval_seconds=10)
    apply_categories_to_sessions(sessions)
    apply_semantic_tags_to_sessions(sessions)
    for s in sessions:
        assert "coding" in s["tags"]
    metrics = compute_metrics(sessions)
    total_coding = sum(s["duration_seconds"] for s in sessions)
    assert metrics["tag_usage"].get("coding", 0) == total_coding
    assert "coding" in extract_tags(sessions)


def test_extract_tags_unions_session_tags() -> None:
    logs = [
        {
            "timestamp": "2026-01-01 08:00:00",
            "app": "a.exe",
            "window_title": "Some manga reader",
        },
    ]
    sessions = build_sessions(logs, sampling_interval_seconds=5)
    apply_semantic_tags_to_sessions(sessions)
    assert "reading" in sessions[0]["tags"]
    assert "reading" in extract_tags(sessions)
