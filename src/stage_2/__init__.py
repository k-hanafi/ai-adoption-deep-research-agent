"""March Stage 2 batch runner was moved. This package is a pointer only."""

MOVED_TO = "legacy_agent_march_2026"


def moved_message() -> str:
    return (
        "The March 2026 production runner is no longer on the live import path. "
        f"cd {MOVED_TO} and run: "
        "PYTHONPATH=. python -m src.stage_2.production_agent_runner --dry-run"
    )
