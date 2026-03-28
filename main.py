import re
import sys
from pathlib import Path

from modules.logger import log_activity
from modules.mechanics import apply_mechanics
from modules.narrative import generate_outputs
from modules.processor import build_day_state, process_logs
from utils.file_io import write_json
from utils.helpers import load_config

_LOG_STEM_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _latest_log_file(logs_dir: Path) -> Path | None:
    """Pick the newest daily log (``YYYY-MM-DD.json``), else newest ``*.json``.

    Args:
        logs_dir: Directory containing log JSON files.

    Returns:
        Path to the chosen file, or ``None`` if the directory has no JSON files.
    """
    if not logs_dir.is_dir():
        return None
    daily = [p for p in logs_dir.glob("*.json") if _LOG_STEM_DATE.match(p.stem)]
    if daily:
        return max(daily, key=lambda p: p.stem)
    any_json = list(logs_dir.glob("*.json"))
    if not any_json:
        return None
    return max(any_json, key=lambda p: p.stat().st_mtime)


def _run_process(config: dict) -> None:
    """Load latest log, build day state, write to the processed folder."""
    root = Path(__file__).resolve().parent
    logs_dir = root / Path(config["data_paths"]["logs"])
    proc_dir = root / Path(config["data_paths"]["processed"])
    latest = _latest_log_file(logs_dir)
    if latest is None:
        print(f"No log JSON files found in {logs_dir}")
        return
    state = build_day_state(latest)
    day_key = state.get("date") or latest.stem
    out_path = proc_dir / f"{day_key}.json"
    write_json(out_path, state)
    print(f"Processed {latest.name} -> {out_path}")


def main() -> None:
    """Run the Argus entry point.

    - ``python main.py log`` — activity logging only.
    - ``python main.py process`` — latest log → day state → ``data/processed/``.
    - Otherwise — full pipeline (log until Ctrl+C, then process, mechanics, outputs).
    """
    config = load_config()
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "process":
            _run_process(config)
            return
        if cmd == "log":
            log_activity(config)
            return
    log_activity(config)
    process_logs()
    apply_mechanics()
    generate_outputs()


if __name__ == "__main__":
    main()
