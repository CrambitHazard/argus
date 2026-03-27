from modules.logger import log_activity
from modules.mechanics import apply_mechanics
from modules.narrative import generate_outputs
from modules.processor import process_logs
from utils.helpers import load_config


def main() -> None:
    """Run the Argus entry point."""
    config = load_config()
    log_activity(config)
    process_logs()
    apply_mechanics()
    generate_outputs()


if __name__ == "__main__":
    main()
