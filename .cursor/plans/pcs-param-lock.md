# PCS parameter lock (final suggestion)

**Status:** FINAL SUGGESTION for PCS benchmark under **effort=medium** and **≈$0.10/company** (2026-08-08).  
**Source:** live Stage A `evals/instances/tuning/014_2026-08-07_1045` (50-co, Luna, metered).  
**Caveat:** arms are single-call UAS; PCS cost ≈ `3 ×` arm mean.

## Locked equal-depth config (all 3 channels)

| Knob | Value | Why |
|---|---|---|
| `model` | `openai/gpt-5.6-luna` | Budget path; no Sol |
| `max_steps` | **50** | Best yield in the cheap steps ladder (~1.94f @ ~$0.023) |
| `reasoning_effort` | **medium** | User constraint; only effort tier with `3× ≤ $0.105` |
| `web_search_depth` | **medium** | Middle ground vs low/high; OFAT wash vs low on yield/cost; avoids unlucky-looking high |
| Channels | jobs, owned, third_party | Equal depth always-on |
| Domain filters | off | Prompt-only targeting |

**Projected $/company:** ≈ **$0.06–0.07** (3 × ~$0.020–0.023). Under $0.10 with headroom.

Wired into:
- `evals/configs/parallel_channel_search.yaml`
- `parallel_channel_search/channels.py` defaults

## Combinations considered

| Combo (per channel) | 3× $ | Yield signal | Decision |
|---|---:|---|---|
| steps **50** / medium / search **medium** | ~0.06–0.07 | steps=50 helped; search=medium ≈ low | **LOCK** |
| steps 50 / medium / search low | ~0.069 | Same family; slightly more data-aligned to baseline search | Acceptable alt |
| steps 10 / medium / search low (baseline) | ~0.065 | Weaker than steps=50 | Reject |
| steps 10 / medium / search high | ~0.064 | Cost OK; mean findings down (paired wins tied; noisy) | Reject for default |
| steps 100 / medium / search low | ~0.064 | No lift vs baseline | Reject |
| steps 10 / **high** / search low | **~0.128** | Higher yield proxy, over budget | Reject unless budget reopens |
| xhigh or max ×3 | ≥0.22 | Far over | Reject |

## Still open for implementation (not param choice)
- Live PCS runner + prompt wiring
- Merge/dedupe across channels
- Tiny paid smoke to confirm 3× metered cost
