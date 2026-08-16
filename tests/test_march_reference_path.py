"""Live March refs stay under evals/, never the snapshot folder."""

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
