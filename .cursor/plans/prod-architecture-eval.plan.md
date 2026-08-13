# Master Plan: Prod Architecture → Eval → Winner (Tuesday deliverable)

**SoT for orchestrator.** Continuity lives here, not in chat. Supersedes `.cursor/plans/eval-harness.plan.md` for goals/cost/stage naming; that file remains useful for scaffolding history and locked folder layout.

**Workflow:** This chat = master orchestrator (`/orch`). Open a **new chat per phase**, pointed at that phase’s sub-plan. After each phase milestone, update this STATUS block.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | Sequencing pivot active. PR1+PR2 merged (plans + categorized archive CLI). PR3 shipping dry Stage A `run-tuning`. Phase 1 arch redesign still paused. SoT: [eval-suite-infra.plan.md](./eval-suite-infra.plan.md). |
| **Next move** | Land PR3, then resume Phase 1 UAS freeze using held-out tuning results (dry first, paid optional). |
| **Tuesday deliverable** | Present eval results: winner architecture, cost/company, yield estimate for **9.45k** prod cohort under **≤~$1k** Stage 2 spend. |
| **Blocked on** | PR3 merge (dry Stage A tuning dashboard) before Phase 1 config freeze. |
| **Branch workflow** | Sequential PRs onto `main` for infra (`cursor/eval-infra-*-e253`). After infra: resume Phase 1 → Phase 2 → Phase 3. |

### Decisions locked (2026-08-04)

| Decision | Choice |
|---|---|
| Stage numbering | **1** = filter (frozen). **2** = research agent (3 architectures). **3** = post-citation verification (LLM judge). Do not call verification “Stage 5.” |
| Stage 2 cost target | **~$0.10/company** average (rounded). 9.45k × $0.10 ≈ **$945** → under ~$1k prod budget. |
| Stage 3 cost | No hard ceiling yet; must stay **cheap** relative to Stage 2. |
| Architecture shapes | Broadly **UAS / PCS / SGS**. Freedom to retune components (depths, fan-out, models) as long as each arch’s components **sum ≈ $0.10**. |
| Eval budget | **≤ $150** total for eval phase (expect ~3 full iterations of 3 archs + Stage 3). |
| Golden set size | Ideal **100 found + 100 not-found**. Likely cut to **50+50**; **defer cut decision to Phase 3** after Phase 1–2 assumptions lock. |
| Winner metric | **Not precision alone** (Stage 3 is architecture-agnostic). Track **yield with cost** (e.g. verified or raw findings per dollar / per company at comparable unit cost). Maximize yield while **9.45k Stage 2 spend ≤ ~$1k**. |
| Stage 3 API choice | **Partial spike 2026-08-13:** Perplexity does **not** expose usable logprobs (Gateway: `logprobs` only `false`; `top_logprobs` 400). Logprob judge path → OpenAI `reasoning.effort=none` (+ Tavily or hybrid fetch still open). See `docs/decision-log.md` [[2026-08-13: Perplexity APIs do not expose usable logprobs]]. |

### Open questions

- Exact Luna/Perplexity price table to use in cost models (Phase 1 must freeze a ledger).
- Whether Stage 3 runs on every eval iteration or only finalist (Phase 3 decision).
- Stratified cohort definitions / IDs for “found” vs “not found” (Phase 3).

### Sub-plans

0. [eval-suite-infra.plan.md](./eval-suite-infra.plan.md) (**active now**: tuning + archive UX foundation)
1. [phase-1-architecture-redesign.plan.md](./phase-1-architecture-redesign.plan.md) (paused until infra can run systematic hyperparam experiments)
2. [phase-2-stage3-verification.plan.md](./phase-2-stage3-verification.plan.md)
3. [phase-3-eval-suite.plan.md](./phase-3-eval-suite.plan.md)

---

## Backwards plan (from Tuesday)

```mermaid
flowchart LR
  Tue[Tuesday: winner + cost + yield for 9.45k]
  P3[Phase 3: stratified eval ≤$150]
  P2[Phase 3 depends on Stage 3 judge]
  P1[Phase 2 depends on Stage 2 configs + citation schema]
  Tue --> P3 --> P2 --> P1
```

Sequential because:

1. **Phase 1** freezes unit economics and citation/output contracts.
2. **Phase 2** builds Stage 3 against that contract.
3. **Phase 3** benchmarks the locked trio (+ Stage 3) and picks a winner.

---

## Phase contracts (summary)

### Phase 1 — Architecture redesign
**GOAL:** Three Stage 2 configs (UAS, PCS, SGS), each ≈ **$0.10/company**, effectiveness maximized under that budget.  
**EXIT:** Written cost ledger + locked knobs per arch; ready for implementation/tuning chat.  
**FAILURE:** Any arch with no credible path to ~$0.10, or designs that abandon UAS/PCS/SGS identity.

### Phase 2 — Stage 3 verification
**GOAL:** Cheap LLM judge over Perplexity citations: binary hallucination field (logprobs), plus prompt 1–5 confidence backup.  
**EXIT:** API choice locked post-spike; schema + smoke tests on known good/bad citations.  
**FAILURE:** Judge that systematically false-positives due to scrape mismatch without mitigation; no binary field for logprobs.

### Phase 3 — Eval suite + winner
**GOAL:** Stratified A/B of 3 archs (+ Stage 3) under **≤$150**; recommend prod config for 9.45k.  
**EXIT:** Winner, $/company, yield estimate, spend forecast ≤~$1k.  
**FAILURE:** Results that cannot compare archs fairly (unpaired companies, broken cost tracking, or overspend without a cut plan).

---

## Orchestrator rules

- Do not implement in the master chat. Delegate or open a phase chat.
- After every milestone/pivot: update **STATUS** here and the active phase sub-plan.
- If this chat is retired: next `/orch` reads this file first.
- Legacy plan: `.cursor/plans/eval-harness.plan.md` = scaffolding history only.
