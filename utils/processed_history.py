"""Load recent processed day_state JSON files from disk."""

import re
from pathlib import Path
from typing import Any

from utils.file_io import read_json

_PROCESSED_DAY_STEM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _sorted_daily_json_paths(processed_dir: Path) -> list[Path]:
    """List ``YYYY-MM-DD.json`` files under ``processed_dir``, oldest first."""
    if not processed_dir.is_dir():
        return []
    paths = [
        p
        for p in processed_dir.glob("*.json")
        if _PROCESSED_DAY_STEM.match(p.stem)
    ]
    return sorted(paths, key=lambda p: p.stem)


def load_last_n_processed_day_states(
    processed_dir: Path,
    n: int,
    *,
    before_date: str | None = None,
) -> list[dict[str, Any]]:
    """Load up to ``n`` processed day_state dicts, oldest first among the slice.

    Files are chosen by lexicographic order on ``YYYY-MM-DD`` stems (valid
    calendar sort). The ``n`` most recent matching files are loaded.

    Args:
        processed_dir: Directory containing ``*.json`` day states.
        n: Maximum number of files to load (0 or negative yields ``[]``).
        before_date: If set (``YYYY-MM-DD``), only files strictly older than
            this date are considered (for glitch baseline without same-day file).

    Returns:
        List of parsed JSON objects, oldest → newest, length ≤ ``n``.
    """
    paths = _sorted_daily_json_paths(processed_dir)
    if before_date:
        paths = [p for p in paths if p.stem < before_date]
    if n <= 0:
        return []
    chosen = paths[-n:]
    return [read_json(p) for p in chosen]
