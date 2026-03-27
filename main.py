from utils.helpers import load_config


def main() -> None:
    """Run the Argus entry point."""
    config = load_config()
    print("Config loaded", config)


if __name__ == "__main__":
    main()
