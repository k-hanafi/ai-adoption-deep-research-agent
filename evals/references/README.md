# Frozen evaluation references

`march_2026_production.jsonl` is a **local copy** of the March Stage 2 master
dump. Panel builders (`evals/panel/build_*.py`) and `evals.paths.MARCH_STAGE2_JSONL`
read this file.

It is not committed (about 69MB). It is also not imported from
`legacy_agent_march_2026/`. After you materialize the March snapshot outputs,
copy once:

```bash
cp legacy_agent_march_2026/outputs/production_results.jsonl \
   evals/references/march_2026_production.jsonl
```

Already-built panels under `evals/panel/*.json` do not need this file at
runtime. You only need it to regenerate a panel.
