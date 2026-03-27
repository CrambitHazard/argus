import json
from pathlib import Path
from typing import Any


def read_json(filepath: str | Path) -> Any:
    """Load JSON from a file."""
    path = Path(filepath)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath: str | Path, data: Any) -> None:
    """Write data to a JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
