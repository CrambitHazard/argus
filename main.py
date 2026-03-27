import sys

from modules.logger import log_activity
from modules.mechanics import apply_mechanics
from modules.narrative import generate_outputs
from modules.processor import process_logs
from utils.helpers import load_config


def main() -> None:
    """Run the Argus entry point.

    With argument ``log``, only activity logging runs. Otherwise the full
    pipeline runs (log, then process, mechanics, outputs).
    """
    config = load_config()
    log_only = len(sys.argv) > 1 and sys.argv[1] == "log"
    log_activity(config)
    if log_only:
        return
    process_logs()
    apply_mechanics()
    generate_outputs()


if __name__ == "__main__":
    main()
