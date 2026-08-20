# Data that is and is not in git

This repo ships **code, prompts, eval scoreboards, and fictional schema
samples**. It does not ship the licensed Crunchbase dump or the full
production finding tables.

| Kind | In git? | Where |
|---|---|---|
| Full Crunchbase slice (~44k rows) | No | Local `crunchbase_data/44k_crunchbase_startups.csv` |
| Stage 2 queue (priority 4–5) | No | Local `crunchbase_data/stage2_input_dataset_p4_p5.jsonl` |
| Fictional input sample | Yes | `crunchbase_data/sample/` |
| Production findings / traces | No | Local `outputs/prod/{sgs,pcs,uas}/` |
| Fictional findings sample | Yes | `outputs/prod/sample/findings.sample.csv` |
| March master dump (~69MB) | No | Local `evals/references/march_2026_production.jsonl` |
| Eval panel + `summary.jsonl` | Yes | `evals/panel/`, `outputs/stage2/test_runs/` |

Eval `summary.jsonl` files are small scoreboards (company id, cost, finding
count). They are kept as measurement evidence. Per-company Agent dumps stay
local.

To run production against the fictional sample:

```bash
python -m production dry-run --all \
  --dataset crunchbase_data/sample/stage2_input.sample.jsonl
```

Git history still contains the old dumps until a history rewrite, which we
are not doing unless Crunchbase or the PI asks.
