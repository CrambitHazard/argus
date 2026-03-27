"""Activity logging: foreground window and process, stored as JSON."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
import win32gui
import win32process


def _project_root() -> Path:
    """Return the Argus project root (directory containing ``config.json``).

    Returns:
        Absolute path to the repository root.
    """
    return Path(__file__).resolve().parent.parent


def _daily_log_path(config: dict[str, Any]) -> Path:
    """Build the log file path for today's date.

    Args:
        config: Application config; uses ``data_paths.logs`` when present.

    Returns:
        Path to ``data/logs/YYYY-MM-DD.json`` under the project root.
    """
    day = datetime.now().strftime("%Y-%m-%d")
    logs_rel = config.get("data_paths", {}).get("logs", "data/logs/")
    log_dir = _project_root() / Path(logs_rel)
    return log_dir / f"{day}.json"


def _capture_entry() -> dict[str, Any]:
    """Read the focused window title and owning process name.

    Returns:
        Dict matching ``data/logs/sample_log.json``: ``timestamp`` (local
        ``YYYY-MM-DD HH:MM:SS``), ``app`` (executable name), ``window_title``.
        ``app`` is empty when the process cannot be resolved.
    """
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd) if hwnd else ""
    app = ""
    if hwnd:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            app = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            app = ""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "timestamp": stamp,
        "app": app,
        "window_title": title,
    }


def _append_entry_json(path: Path, entry: dict[str, Any]) -> None:
    """Read JSON array from disk, append one object, write back.

    Args:
        path: Log file path (created with parent dirs if missing).
        entry: Object to append to the array.

    Raises:
        OSError: If the file cannot be read or written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
        if not isinstance(data, list):
            data = []
    else:
        data = []
    data.append(entry)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def log_activity(config: dict[str, Any]) -> None:
    """Poll the active window on an interval and append JSON log rows forever.

    Args:
        config: Must include ``log_interval_seconds`` (sleep between samples).

    Raises:
        KeyError: If ``log_interval_seconds`` is missing.
        KeyboardInterrupt: If the process is interrupted.
    """
    interval = int(config["log_interval_seconds"])
    while True:
        entry = _capture_entry()
        out_path = _daily_log_path(config)
        _append_entry_json(out_path, entry)
        print(json.dumps(entry, ensure_ascii=False))
        time.sleep(interval)
