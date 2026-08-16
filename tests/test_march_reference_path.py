"""Live March refs stay under evals/, never the snapshot folder."""

import subprocess
from pathlib import Path

from evals.paths import EVALS_PACKAGE_DIR, MARCH_STAGE2_JSONL, PROJECT_ROOT

_FORBIDDEN_IMPORTS = (
    "import legacy_agent_march_2026",
    "from legacy_agent_march_2026",
)


def test_march_jsonl_is_evals_reference_not_legacy_folder() -> None:
    assert MARCH_STAGE2_JSONL == (
        EVALS_PACKAGE_DIR / "references" / "march_2026_production.jsonl"
    )
    assert "legacy_agent_march_2026" not in str(MARCH_STAGE2_JSONL)


def _assert_moved_exit(main) -> None:
    try:
        main()
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("retired March command must exit instead of calling the API")
    assert "legacy_agent_march_2026" in message
    assert "PYTHONPATH=." in message


def test_live_march_runner_command_explains_the_move() -> None:
    from src.stage_2.production_agent_runner import main

    _assert_moved_exit(main)


def test_live_march_preset_command_explains_the_move() -> None:
    from src.tests.stage_2.run_preset_test import main

    _assert_moved_exit(main)


def test_live_python_does_not_import_march_snapshot() -> None:
    skip_parts = {
        "legacy_agent_march_2026",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
    }
    hits: list[str] = []
    for path in Path(PROJECT_ROOT).rglob("*.py"):
        if any(part in skip_parts for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in _FORBIDDEN_IMPORTS):
            hits.append(str(path.relative_to(PROJECT_ROOT)))
    assert hits == []


def _git_ignores(rel_path: str) -> bool:
    """True when `git check-ignore` would skip this path (file need not exist)."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel_path],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode == 0


def test_snapshot_secrets_and_runtime_files_are_gitignored() -> None:
    assert _git_ignores("legacy_agent_march_2026/credentials/perplexity_api_key.txt")
    assert _git_ignores("legacy_agent_march_2026/logs/run.log")
    assert _git_ignores("legacy_agent_march_2026/checkpoints/progress.json")
    assert not _git_ignores(
        "legacy_agent_march_2026/credentials/perplexity_api_key.txt.template"
    )
