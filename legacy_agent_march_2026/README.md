# March 2026 production agent (frozen snapshot)

This folder is a **runnable copy** of the first production system: Stage 1
filter plus the March Stage 2 Perplexity `deep-research` batch runner.

It is **not** imported by the live v2 repo. Live architectures (SGS, PCS, UAS)
and the upcoming `production/` CLI live outside this folder. Do not add
cross-imports in either direction.

## What is in here

| Path | Role |
|---|---|
| `src/stage_1/` | Website check, Tavily pass, GPT priority scorer |
| `src/stage_2/production_agent_runner.py` | March full-set runner (resume, budget cap, pause/stop) |
| `src/tests/stage_2/` | March hyperparameter A/B scripts |
| `prompts/stage_2_perplexity_prompt.txt` | March deep-research prompt |
| `crunchbase_data/` | Licensed dumps local-only (see `crunchbase_data/README.md`) |
| `outputs/production_results.jsonl` | March master results (local only, not in git, ~69MB) |
| `presentation/production_results.html` | March findings dashboard |

## How to run the old agent

Work from **this folder** so `src.config` resolves here, not the live repo root.

```bash
cd legacy_agent_march_2026

# Copy real keys into credentials/ (templates are already here)
# or export PERPLEXITY_API_KEY / OPENAI_API_KEY / TAVILY_API_KEY

# Inspect the queue without spending
PYTHONPATH=. python -m src.stage_2.production_agent_runner --dry-run

# Small paid sample
PYTHONPATH=. python -m src.stage_2.production_agent_runner \
    --sample-size 50 --budget-cap 50 --concurrency 5
```

Master JSONL/CSV write to `outputs/production_results.jsonl` and
`outputs/production_results.csv` under this folder.

## Results files

The March dump is too large for git (~69MB JSONL, ~12MB CSV). If you cloned
this repo and the files are missing, copy them from the machine that ran
March, or ask Khaled. Panel rebuilds in live v2 read a separate copy at
`evals/references/march_2026_production.jsonl` (also local-only).
