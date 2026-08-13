# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **Python 3 CLI / batch research pipeline** (the "Deep Research AI Agent"). There is **no web server, database, Docker, or long-running service** to start. You run it as one-off `python -m ...` commands that call external LLM/search APIs and write file artifacts (JSONL, CSV, static HTML dashboards). See `README.md` for the full command list and architecture.

### Running things

- Standard commands live in `README.md` (see the "Eval CLI" section) and are the source of truth. Entry points: `python -m evals <command>`, `python -m unified_adaptive_search`, `python -m parallel_channel_search`, `python -m src.stage_1.*`, `python -m src.stage_2.production_agent_runner`.
- **Everything defaults to dry-run / no-network.** Dry-run paths exercise the real runner, prompt builders, request snapshots, cost ledger, and dashboard rendering without spending money. This is the way to validate changes without API keys.
- Run tests with `python3 -m pytest tests/`. Do NOT rely on a bare `pytest` on PATH: the console script installs to `~/.local/bin`, which is not on PATH here.

### API keys (only needed for live/paid runs)

- Live runs need `OPENAI_API_KEY` (Stage 1), `TAVILY_API_KEY` (Stage 1), and `PERPLEXITY_API_KEY` (Stage 2). Provide them as env vars or as `credentials/<service>_api_key.txt` files (gitignored; templates are tracked). Loading logic is in `src/config.py`.
- Without keys, stick to the default dry-run paths and `python -m evals cost-preview <arch>` (pure estimate, no calls).

### Gotchas

- **No linter/formatter is configured** (no ruff/flake8/black/mypy config). For a quick sanity check, byte-compile with `python3 -m py_compile $(git ls-files '*.py')`.
- **Signal-Gated Search (SGS) has no live path** yet: `python -m signal_gated_search --live` (and the live runner) raises `NotImplementedError`. Dry-run only.
- **Generated eval artifacts are gitignored.** `python -m evals run-tuning ...` writes to `evals/instances/**` and `evals/runs/**`, which `.gitignore` excludes (only `.gitkeep` is tracked). Do not try to commit these outputs. Pipeline outputs under `outputs/**` are likewise gitignored.
