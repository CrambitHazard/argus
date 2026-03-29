"""Narrative pipeline: compress day_state into a minimal LLM-facing payload."""

import json
import os
import re
from pathlib import Path
from typing import Any

from utils.api import generate_text
from utils.helpers import load_config


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


def _verbal_minutes_band(seconds: int) -> str:
    """Rough natural-language duration (no seconds in output)."""
    if seconds <= 0:
        return "hardly any time at all"
    minutes = max(1, round(seconds / 60.0))
    if minutes == 1:
        return "about a minute"
    return f"about {minutes} minutes"


def _humanize_app(name: str) -> str:
    """Turn a process name into something a diarist might say aloud."""
    raw = str(name).strip()
    low = raw.lower()
    if "cursor" in low:
        return "my code editor"
    if "vscode" in low or low.endswith("code.exe"):
        return "VS Code"
    if any(b in low for b in ("opera", "chrome", "firefox", "edge", "brave", "safari")):
        return "the web browser"
    if "github" in low:
        return "GitHub Desktop"
    if "explorer" in low:
        return "File Explorer"
    cleaned = re.sub(r"\.exe$", "", raw, flags=re.I).strip()
    return cleaned or "another program"


def _glitch_plain_english(row: dict[str, str]) -> str:
    """One human clue from a glitch row (for the fact sheet only)."""
    gtype = str(row.get("type", "")).strip()
    cat = str(row.get("category", "")).strip()
    if gtype == "time_spike" and cat:
        return (
            f"Compared to my own recent rhythm, I spent an unusually heavy stretch on "
            f"{cat}-type stuff today."
        )
    if gtype == "time_drop" and cat:
        return (
            f"Compared to my usual weeks, I barely touched {cat}-type work today."
        )
    if gtype and cat:
        return f"Something shifted in how much {cat}-type activity showed up today."
    return ""


def build_diary_fact_sheet(data: dict[str, Any]) -> str:
    """Plain-language memory cues for the model (not diary copy, not JSON).

    Args:
        data: Parsed narrative_input dict.

    Returns:
        Short factual paragraphs the model must internalize, not quote.
    """
    paragraphs: list[str] = []
    date = str(data.get("date", "that day"))
    summary = data.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    apps_raw = summary.get("top_apps", [])
    apps = [a for a in apps_raw if isinstance(a, (str, int, float))] if isinstance(apps_raw, list) else []
    tags_raw = summary.get("key_tags", [])
    tags = [t for t in tags_raw if isinstance(t, (str, int, float))] if isinstance(tags_raw, list) else []

    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    try:
        total_sec = int(metrics.get("total_time", 0))
    except (TypeError, ValueError):
        total_sec = 0
    cat_usage = metrics.get("category_usage", {})
    if not isinstance(cat_usage, dict):
        cat_usage = {}

    paragraphs.append(
        f"Calendar date: {date}. Roughly {_verbal_minutes_band(total_sec)} at the machine is "
        f"all the on-screen time this entry can lean on—the rest of the day is yours to leave vague.",
    )

    if len(apps) >= 2:
        paragraphs.append(
            "Where I mostly parked myself: "
            f"{_humanize_app(str(apps[0]))}, then {_humanize_app(str(apps[1]))}."
        )
    elif len(apps) == 1:
        paragraphs.append(f"Where I mostly lived on the machine: {_humanize_app(str(apps[0]))}.")
    else:
        paragraphs.append("No clear main window stood out in the capture.")

    if cat_usage:
        bits: list[str] = []
        for key in sorted(cat_usage.keys(), key=str):
            try:
                sec = int(cat_usage[key])
            except (TypeError, ValueError):
                sec = 0
            label = str(key).replace("_", " ")
            bits.append(f"{_verbal_minutes_band(sec)} that felt {label}-ish")
        paragraphs.append("Rough shape of the day on screen: " + "; ".join(bits) + ".")
    else:
        paragraphs.append("No clear split of activity types was captured.")

    if tags:
        paragraphs.append(
            "Kinds of activity that kept surfacing in titles/keywords: "
            + ", ".join(str(t) for t in tags)
            + ".",
        )

    divine = data.get("divine_words", {})
    if not isinstance(divine, dict):
        divine = {}
    dom = divine.get("dominant", [])
    if isinstance(dom, list) and dom:
        words = ", ".join(str(x) for x in dom)
        paragraphs.append(
            f"Three shorthand mood words I might associate with today if pressed: {words}. "
            "Use them like scribbles in a margin, not like a lab readout.",
        )

    glitches = data.get("glitches", [])
    if isinstance(glitches, list):
        for row in glitches:
            if isinstance(row, dict):
                line = _glitch_plain_english(
                    {
                        "type": str(row.get("type", "")),
                        "category": str(row.get("category", "")),
                    },
                )
                if line:
                    paragraphs.append(line)

    paragraphs.append(
        "This block is not diary prose; turn it only into remembered scenes and feelings.",
    )
    return "\n\n".join(paragraphs)


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


def _parse_narrative_input(narrative_input: Any) -> dict[str, Any]:
    """Normalize ``narrative_input`` to a dict (from JSON string if needed).

    Args:
        narrative_input: Output of :func:`build_narrative_input` or equivalent JSON.

    Returns:
        Parsed dict, or empty dict if input is invalid.
    """
    if isinstance(narrative_input, str):
        try:
            narrative_input = json.loads(narrative_input)
        except json.JSONDecodeError:
            return {}
    if not isinstance(narrative_input, dict):
        return {}
    return narrative_input


def narrative_input_to_text_block(data: dict[str, Any]) -> str:
    """Turn narrative_input into a fixed-layout text block for the model.

    Args:
        data: Parsed narrative_input dict.

    Returns:
        Multi-line string listing only fields present in the structure.
    """
    lines: list[str] = []
    lines.append(f"Date: {data.get('date', '(unknown)')}")
    summary = data.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    lines.append(f"Top apps by tracked time: {summary.get('top_apps', [])}")
    lines.append(f"Top categories by tracked time: {summary.get('top_categories', [])}")
    lines.append(f"Key activity tags: {summary.get('key_tags', [])}")
    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    total_sec = metrics.get("total_time", 0)
    try:
        ts = int(total_sec)
    except (TypeError, ValueError):
        ts = 0
    approx_min = ts // 60
    lines.append(
        f"Total tracked screen time: {ts} seconds "
        f"(about {approx_min} minutes; use for natural phrasing, do not invent extra time)",
    )
    cat = metrics.get("category_usage", {})
    lines.append("Category time (seconds, as recorded):")
    if isinstance(cat, dict) and cat:
        for key in sorted(cat.keys(), key=str):
            lines.append(f"  - {key}: {cat[key]}")
    else:
        lines.append("  (none)")
    divine = data.get("divine_words", {})
    if not isinstance(divine, dict):
        divine = {}
    lines.append(f"Dominant day themes (computed): {divine.get('dominant', [])}")
    glitches = data.get("glitches", [])
    lines.append("Software-flagged deviations vs recent days:")
    if isinstance(glitches, list) and glitches:
        for row in glitches:
            if isinstance(row, dict):
                lines.append(
                    f"  - {row.get('type', '')} (category: {row.get('category', '')})",
                )
            else:
                lines.append(f"  - {row!r}")
    else:
        lines.append("  (none listed)")
    return "\n".join(lines)


def _build_diary_prompt(fact_sheet: str) -> str:
    """Assemble instructions plus a plain-language reference (not JSON).

    Args:
        fact_sheet: Output of :func:`build_diary_fact_sheet`.

    Returns:
        Full user prompt for :func:`utils.api.generate_text`.
    """
    return (
        "Write the diary entry I would actually write tonight—only that. "
        "It must read like a real person recounting their day, not like someone narrating a spreadsheet "
        "or explaining an app export.\n\n"
        "WHAT THIS IS NOT\n"
        "- Not a walkthrough of measurements.\n"
        "- Not sentences that say how things were \"recorded\", \"tracked\", \"flagged\", \"categorized\", "
        "\"summarized\", or \"shown by\" anything.\n"
        "- Not quoting the REFERENCE block below; it exists so you stay honest, not so you paraphrase it "
        "line by line.\n\n"
        "BANNED VOCABULARY IN THE DIARY (including close variants)\n"
        "tracker, log, logged, log file, metric, metrics, data set, JSON, category (as technical jargon), "
        "tag (as technical jargon), software, program output, analyzer, breakdown, spike, glitch, "
        "deviation, seconds, timestamp, captured (as surveillance), dominant theme (as report language), "
        "according to, the summary, computed, calculated, .exe\n\n"
        "VOICE\n"
        "- First person only: I, me, my.\n"
        "- Tools in human words: \"the browser\", \"the editor\", \"GitHub\", not filenames.\n"
        "- Everyday words like \"coding\" or \"reading\" are fine when they describe what I felt I was doing.\n"
        "- Mood words from the reference (e.g. Focus, Drift, Creation) may appear once or twice, casually, "
        "as if I jotted them in the margin—not as a verdict from a machine.\n\n"
        "LENGTH\n"
        "- Target ~700–1,200 words when the day had real on-screen substance.\n"
        "- If the day was almost empty on-screen, still write ~320–450 words about the thin slice I do "
        "remember and the rest as honest fog—without mentioning why the slice is thin in technical terms.\n"
        "- \"## What happened today\": at least 5 paragraphs of scenes and movement, not stat recaps.\n"
        "- \"## Key behaviors\": at least 3 paragraphs about attention habits, restlessness, or flow—in "
        "plain language.\n"
        "- \"## Reflection\": at least 2 paragraphs; gentle, specific, human.\n\n"
        "MARKDOWN (exact headings, space after ##)\n"
        "## What happened today\n\n"
        "(your paragraphs)\n\n"
        "## Key behaviors\n\n"
        "(your paragraphs)\n\n"
        "## Reflection\n\n"
        "(your paragraphs)\n\n"
        "GROUND TRUTH\n"
        "- Stay consistent with the REFERENCE: no invented apps or major activities that contradict it.\n"
        "- Do not fabricate people, meetings, or trips.\n\n"
        "REFERENCE (internal only—translate into memory, do not explain it)\n"
        f"{fact_sheet}"
    )


def _diary_author_name() -> str:
    """Resolve the diary sign-off name from the environment.

    Returns:
        ``DIARY_AUTHOR_NAME`` if set and non-empty after stripping; otherwise ``Me``.
    """
    return (os.environ.get("DIARY_AUTHOR_NAME") or "Me").strip() or "Me"


def _wrap_diary_markdown(date_str: str, body: str, author: str) -> str:
    """Format a diary entry as Markdown with title, salutation, and signature.

    Args:
        date_str: Calendar date string for the ``#`` title line.
        body: Main entry text (model output or failure notice).
        author: Name printed after the horizontal rule.

    Returns:
        Full Markdown document string with trailing newline after the author line.
    """
    return (
        f"# {date_str}\n\n"
        "Dear diary,\n\n"
        f"{body.rstrip()}\n\n"
        "---\n\n"
        f"{author}\n"
    )


def _diary_output_path(
    project_root: Path,
    config: dict[str, Any],
    date_str: str,
) -> Path:
    """Resolve ``data/outputs/{date}_diary.md`` from config."""
    rel = config.get("data_paths", {}).get("outputs", "data/outputs/")
    out_dir = project_root / Path(rel)
    safe = date_str.strip() or "unknown"
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
        safe = safe.replace(ch, "-")
    return out_dir / f"{safe}_diary.md"


def generate_diary(
    narrative_input: dict[str, Any] | str,
    *,
    config: dict[str, Any] | None = None,
    project_root: Path | None = None,
) -> str:
    """Build a grounded diary entry from narrative_input and save it under data/outputs.

    Parses JSON if a string is passed, formats DATA for the model, calls
    OpenRouter via :func:`utils.api.generate_text`, then saves Markdown
    ``{date}_diary.md`` with a title (date), ``Dear diary,``, the body, and a
    sign-off from ``DIARY_AUTHOR_NAME`` (default ``Me``).

    Args:
        narrative_input: Dict or JSON string matching :func:`build_narrative_input`.
        config: Argus config; defaults to :func:`utils.helpers.load_config`.
        project_root: Repo root; defaults to parent of ``modules/``.

    Returns:
        Full Markdown file contents written to disk (including wrapper), or the
        wrapped failure notice if the API returned nothing.
    """
    data = _parse_narrative_input(narrative_input)
    cfg = config if config is not None else load_config()
    root = project_root if project_root is not None else Path(__file__).resolve().parent.parent

    fact_sheet = build_diary_fact_sheet(data)
    prompt = _build_diary_prompt(fact_sheet)
    diary_text = generate_text(prompt, max_tokens=4096, timeout_seconds=300.0)

    date_str = str(data.get("date", "unknown"))
    out_path = _diary_output_path(root, cfg, date_str)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not diary_text.strip():
        diary_text = (
            "[Argus] No diary text was returned from the model.\n\n"
            "Look in the terminal for lines starting with [OpenRouter]. Typical causes:\n"
            "- OPENROUTER_API_KEY missing or wrong in .env\n"
            "- OPENROUTER_MODEL not available on your account or misspelled\n"
            "- No credits / rate limit / network error\n"
            "- Model returned an empty or unsupported response shape\n"
            "- Read timeout: set OPENROUTER_TIMEOUT=600 in .env for slow models or networks\n\n"
            "Fix the issue and run diary generation again.\n"
        )
        print(f"[Argus] Wrote failure notice to {out_path}")

    author = _diary_author_name()
    markdown = _wrap_diary_markdown(date_str, diary_text, author)
    out_path.write_text(markdown, encoding="utf-8")

    return markdown


def generate_outputs() -> None:
    """Placeholder narrative / output generation."""
    print("generate_outputs")
