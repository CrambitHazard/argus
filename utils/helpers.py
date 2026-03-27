"""Small helpers shared across Argus."""

import json
from pathlib import Path


def load_config(config_path: str | None = None) -> dict:
    """Read ``config.json`` and return its contents as a dictionary.

    Args:
        config_path: Optional path to the JSON file. When omitted, resolves to
            ``config.json`` at the project root (parent of ``utils/``).

    Returns:
        The parsed configuration mapping.

    Raises:
        FileNotFoundError: If the config file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parent.parent / "config.json"
    )
    text = path.read_text(encoding="utf-8")
    return json.loads(text)
