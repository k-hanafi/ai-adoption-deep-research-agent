"""Live entry point that refuses to run the retired March batch agent."""

from src.stage_2 import moved_message


def main() -> None:
    raise SystemExit(moved_message())


if __name__ == "__main__":
    main()
