# Company input data

The live pipeline reads two **local** files that are not in git (Crunchbase
license). Drop your licensed copies here:

| File | Role |
|---|---|
| `44k_crunchbase_startups.csv` | Stage 1 input (full Crunchbase slice) |
| `stage2_input_dataset_p4_p5.jsonl` | Stage 2 / production queue (priority 4–5) |

`sample/` has fictional rows with the same columns so the schema is visible
without republishing the licensed dump.

```bash
# Demo the production CLI on the fictional Stage 2 sample (no paid calls)
python -m production dry-run --all \
  --dataset crunchbase_data/sample/stage2_input.sample.jsonl
```
