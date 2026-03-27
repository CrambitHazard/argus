from modules.logger import log_activity
from modules.mechanics import apply_mechanics
from modules.narrative import generate_outputs
from modules.processor import process_logs


def main() -> None:
    """Run the Argus entry point."""
    log_activity()
    process_logs()
    apply_mechanics()
    generate_outputs()


if __name__ == "__main__":
    main()
