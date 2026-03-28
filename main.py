import sys

from modules.logger import log_activity
from modules.mechanics import apply_mechanics
from modules.narrative import generate_outputs
from modules.processor import process_logs
from utils.helpers import load_config


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
            process_logs(config)
            return
        if cmd == "log":
            log_activity(config)
            return
    log_activity(config)
    process_logs(config)
    apply_mechanics()
    generate_outputs()


if __name__ == "__main__":
    main()
