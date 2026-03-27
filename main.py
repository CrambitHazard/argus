from pathlib import Path

from utils.file_io import read_json, write_json
from utils.helpers import load_config


def main() -> None:
    """Run the Argus entry point."""
    config = load_config()
    print("Config loaded", config)

    root = Path(__file__).resolve().parent
    log_path = root / "data" / "logs" / "test.json"
    sample = {"message": "sample log entry", "level": "info", "count": 1}
    write_json(log_path, sample)
    loaded = read_json(log_path)
    print("Round-trip JSON:", loaded)


if __name__ == "__main__":
    main()
