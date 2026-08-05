# AGENTS.md

## Cursor Cloud specific instructions

### What this project is

A Python 3.12 command-line research pipeline (no web server, no frontend build). It classifies startups (Stage 1) and runs a Perplexity deep-research agent (Stage 2), plus an `evals/` harness that compares three architecture packages (`parallel_channel_search`, `signal_gated_search`, `unified_adaptive_search`).

### Environment

- Dependencies live in a virtualenv at `.venv` (created by the startup update script). Run tools with `.venv/bin/python` (for example `.venv/bin/python -m evals ...`).
- Runtime deps are just `httpx` and `perplexityai` (see `requirements.txt`).

### Running the app (no API keys needed)

The eval harness runs in dry-run/stub mode by default and needs no secrets. Commands are documented in `README.md` under "Eval CLI"; the core ones:

- `.venv/bin/python -m evals cost-preview unified-adaptive-search` (planning estimate, no API calls)
- `.venv/bin/python -m evals run-evals <arch>` (writes a bundle to `outputs/evals/runs/<run_id>/` including `dashboard.html`)
- `.venv/bin/python -m evals open-dashboard --no-open` (use `--no-open` in this headless VM; without it the CLI calls `webbrowser.open` and will fail/hang)

Architecture keys: `parallel-channel-search`, `signal-gated-search`, `unified-adaptive-search` (aliases `pcs`, `sgs`, `uas`).

### Live mode and the Stage 1 / Stage 2 pipelines (need paid API keys)

- `--live` eval runs and the `src/stage_1` / `src/stage_2` runners call OpenAI, Tavily, and Perplexity and cost real money. PCS/SGS are Phase 1 stubs and raise `NotImplementedError` under `--live`.
- Keys are read (see `src/config.py`) from `credentials/<service>_api_key.txt` first, then env vars `OPENAI_API_KEY`, `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`. Set them as Cursor secrets before running live paths.

### Testing / linting

There is no test suite, no lint config, and no build step in this repo. "Verifying" a change means running the relevant CLI command above and checking the generated bundle/output.

### Gotcha

- Importing `src/config.py` creates output directories (`outputs/`, `logs/`, `checkpoints/`) as a side effect at import time. This is expected.
