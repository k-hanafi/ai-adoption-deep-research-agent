# Phase 1 — Stage 2 architecture redesign (~$0.10/company)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Open a new chat for this phase.** Kickoff: research + lock configs; do not jump to Phase 2 API spikes.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | **Paused (2026-08-05)** for eval-suite infra pivot. Prior work kept: pricing baseline + Jam high smoke (Sol `high` = **$0.281** on rcid 610194). Path remains deepen Luna `medium`, not stock `high`. PCS/SGS not started. |
| **Next** | Resume after [eval-suite-infra.plan.md](./eval-suite-infra.plan.md) MVP (dry `run-tuning` + categorized dashboard). Then freeze UAS via held-out tuning, then PCS → SGS. |
| **Exit** | Three locked Stage 2 configs, each summing ≈ **$0.10/company**. |
| **Locked** | Stock Sol `high` rejected for UAS unit-cost path (Jam smoke). |
| **Awaiting** | Infra MVP greenlight, then systematic UAS hyperparam selection on tuning panel (not bake-off IDs). |

### Smoke evidence: Jam (rcid 610194), same Stage 2 prompt, max_steps=10

| Run | Model | Cost | Findings | Input tokens | Artifact |
|---|---|---|---|---|---|
| March production | GPT-5.2 (`deep-research`) | **$0.305** | 8 | 167,611 | `production_results.jsonl` |
| Luna smoke (Jul 31) | Luna (`medium`) | **$0.024** | 7 | 46,165 | `outputs/stage2/test_runs/luna_smoke_jam/result.json` |
| High smoke (Aug 4) | Sol (`high`) | **$0.281** | 8 | 72,472 | `outputs/stage2/test_runs/high_smoke_jam/result.json` |

**Verdict:** `high` ≈ March dollars, not a 10¢ upgrade. ~**12×** Luna medium on this company. Tune **medium** (more steps/search/effort on Luna), do not promote UAS to stock `high`.

### Pricing ledger draft (as_of 2026-08-04, docs + local priors)

**Sources:** [Perplexity Pricing](https://docs.perplexity.ai/docs/getting-started/pricing), [Presets](https://docs.perplexity.ai/docs/agent-api/presets), [Models](https://docs.perplexity.ai/docs/agent-api/models); March empirical from `outputs/stage2` / plan §0; Friday meeting intent from transcript (high-for-single / 3× medium parity, then user locked ≈$0.10).

| Item | Assumption | Notes |
|---|---|---|
| Bill | tokens + tool invocations from response `usage` | Widget medians are **not** billed |
| `web_search` | **$0.0025**/invocation | Official tool fee |
| `fetch_url` | **$0.00025**/invocation | Official tool fee |
| Luna `openai/gpt-5.6-luna` | **$0.20 / $1.20** per 1M in/out (low tier) | High tier $0.40/$1.80 above **272k** input |
| Sol `openai/gpt-5.6-sol` (`high`/`xhigh`) | **$5 / $30** per 1M in/out (low tier) | ~25× Luna on rates |
| `medium` preset | Luna, `max_steps=15`, `reasoning=medium`, `web_search`+`fetch_url` | Current docs freeze |
| `high` preset | **Sol**, `max_steps=15`, `reasoning=medium`, same tool shape as medium | Model swap, not deeper steps |
| `low` preset | Luna, `max_steps=5`, `reasoning=minimal` | PCS channel building block |
| `fast` preset | `gpt-5.4-mini`, `max_steps=1` | SGS scout building block |
| March empirical | **~$0.32**/company on GPT-5.2 `deep-research`, ~188k in / ~1.7k out | Load-bearing volume prior |
| Luna @ March volumes (token-only) | **~$0.040**/company | ~8× cheaper on tokens alone |
| Luna @ March volumes + ~20–24 searches | **~$0.09–0.11**/company | Tools dominate once tokens are cheap |
| Stock `high`/Sol @ research depth | **~$0.30–1.00+**/company | Fails ≈$0.10 unless tokens stay toy-widget-sized |
| Stage 2 unit-cost target | **≈ $0.10**/company | 9.45k × $0.10 ≈ **$945** ≤ ~$1k |
| Planning headroom | Prefer mean ≤ **$0.105** if variance high | 9.45k × $0.105 ≈ $992 |
| Friday intent (reconciled) | Spend Luna windfall on **capability**, not keep leftover pennies; keep UAS/PCS/SGS at **parity ≈ $0.10** | Literal “UAS=`high`/Sol” fails the budget at research depth; spirit = deepen Luna (or equal spend across arches) |
| `evals/cost_preview.py` PRIOR_USD | Still `medium=0.32`, `low=0.08`, `fast=0.02` | **Stale** (March GPT-5.2 era). Must retune after arch freezes |

**Friday smoke evidence (qualitative):** same company, March vs Luna ~12× cheaper; 5 shared findings / zero URL overlap; non-determinism is a first-class risk for Phase 3.

---

## Contract

**GOAL:** Redesign UAS, PCS, and SGS so each averages **~$0.10/company**, maximizing expected yield under that unit-cost budget (prod: 9.45k × $0.10 ≈ $945 ≤ ~$1k).

**CONSTRAINTS:**
- Broadly preserve architecture identities:
  - **UAS** — one agent / unified adaptive call per company
  - **PCS** — channel-parallel (jobs / owned / third_party style fan-out)
  - **SGS** — channel-parallel **with signal screening** (scout → dig / gated depth)
- Component costs must **add up ≈ $0.10** per architecture (freedom to change depths, models, channel counts, rescue paths).
- Stage 3 verification is **out of scope** for this phase (API research waits until Phase 1 exits).
- Prefer designs that emit stable **citation URLs + finding claims** (Phase 2 needs this contract).

**FORMAT (deliverables in this sub-plan + repo notes as needed):**
1. Pricing ledger (model/effort → $/call assumptions, dated).
2. Per-architecture design card: knobs, expected $/company, rationale vs March ~$0.32 and Luna ~12× cheaper.
3. Explicit “why this should raise yield” hypothesis per arch.
4. Open risks (non-determinism, URL overlap from Friday transcript).

**FAILURE:**
- Arch that cannot hit ~$0.10 without becoming a different architecture class.
- Cost model that ignores Stage 2 only (do not bake Stage 3 into the $0.10 ceiling).
- No citation/finding schema commitment for Phase 2.

---

## Research agenda (this phase chat)

1. Confirm current Perplexity/Luna price table used in `cost-preview` / ledger code.
2. Reconcile Friday intent: control drops ~10×; upgrade knobs so unit cost ≈ $0.10 not $0.02–0.03.
3. **UAS first:** research → propose → user approve → freeze. Then **PCS**, then **SGS** (same loop each). Do not batch-lock all three.
4. Sanity-check each freeze: 9.45k × unit cost ≤ ~$1k; leave headroom if variance is high.
5. After all three locked → update parent STATUS → hand off to Phase 2.

---

## Kickoff prompt (paste into new Phase 1 chat)

```
You are the Phase 1 implementer for this repo (not the master orchestrator).

Repo: deep-research-AI-agent (workspace root). Scaffolding already merged to main (PR #2).

First actions:
1. Read .cursor/plans/prod-architecture-eval.plan.md and .cursor/plans/phase-1-architecture-redesign.plan.md (and skim superseded eval-harness.plan.md only for pricing/layout history).
2. Create and check out branch phase-1-architecture from up-to-date main.
3. If master/phase plan files are still uncommitted locally, leave them uncommitted until a real Phase 1 milestone (or commit them on this branch with a substantive WHY-first message if the user asks).

Goal: research and lock Stage 2 configs at ~$0.10/company so 9.45k prod Stage 2 spend stays ≤ ~$1k.

Architecture identities (retune knobs freely, keep the class):
- UAS = one agent / unified adaptive call per company
- PCS = channel-parallel (jobs / owned / third_party)
- SGS = channel-parallel with signal screening (scout → dig / gated depth)

Out of scope: Stage 3 verification API research, full stratified eval, paid 200-company runs.

Sequencing (mandatory): research and lock ONE architecture at a time.
Do not propose or freeze PCS/SGS until the previous arch is approved.

1. Shared pricing baseline first (once): Perplexity/Luna vs cost-preview/ledger + Friday intent (target ≈ $0.10/company, not leftover pennies after ~12× cheaper Luna).
2. UAS only: research options → propose 1–2 candidates with component cost math + yield hypothesis → get my approval → freeze UAS in plan STATUS + yaml/config.
3. Then PCS only: same loop (research → propose → approve → freeze), using the locked UAS unit-cost target as the parity anchor.
4. Then SGS only: same loop, again targeting ≈ $0.10 and fair comparison with locked UAS/PCS.
5. After all three are locked: update parent + phase STATUS, give exit report (configs, $/company, 9.45k projection, hypotheses, risks incl. non-determinism).

At each arch step, stop and wait for my approval before moving to the next.
Ask clarifying questions before changing a shape in a way that abandons UAS/PCS/SGS.
```

---

## Changelog

- 2026-08-04: Created from Friday Jan meeting + master orchestrator Q&A.
