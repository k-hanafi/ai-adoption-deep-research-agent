# Phase 3 — Eval suite + winner recommendation

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Depends on Phase 1** (locked Stage 2 configs) **and Phase 2** (Stage 3 judge usable).  
**Open a new chat for this phase** when presenting toward Tuesday.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | Blocked on Phases 1–2. |
| **Next** | After deps: freeze golden-set size under $150, build/run stratified eval, pick winner. |
| **Exit** | Tuesday-ready: winner arch, $/company, yield + 9.45k spend forecast. |

---

## Contract

**GOAL:** Fair stratified benchmark of **UAS vs PCS vs SGS** (with Stage 3 applied consistently), under **≤ $150** eval spend across ~**3 iterations**, producing a prod recommendation that **maximizes yield** for **9.45k** companies at Stage 2 **≤ ~$1k** (≈ $0.10/company target).

**CONSTRAINTS:**
- Stratify: companies Stage 2 **found** something about vs **found nothing** (definitions from prior March/current cohorts; freeze IDs in this phase).
- Same companies run across all three architectures (paired).
- Ideal **100+100**; **likely 50+50**. **Decide sample size here** after Phase 1–2 unit costs are known (do not freeze n in Phase 1).
- Precision/Stage 3 pass rate is **reported** but **not the decisive arch picker** (Stage 3 is arch-agnostic). Decisive: **yield incorporating cost** under the prod $1k ceiling.
- Expect ~3 iterations; cut n or Stage 3 frequency before blowing $150.

**FORMAT:**
1. Golden set manifest (IDs, stratum, freeze date).
2. Eval harness runbook + cost tracker vs $150.
3. Results table: per arch → $/company, raw yield, Stage-3-verified yield, $/finding, projected 9.45k spend.
4. Winner recommendation + risks (non-determinism from Friday same-company URL mismatch).

**FAILURE:**
- Unpaired company sets across archs.
- No cost tracking / cannot project 9.45k spend.
- Overspend eval budget without an explicit cut decision recorded in STATUS.
- Declaring a winner on precision alone.

---

## Decision deferred to this phase

- Final **n** (100+100 vs 50+50 vs other) given measured Stage 2+3 unit costs.
- Whether Stage 3 runs on **every** iteration or only on the final comparison pass.

---

## Kickoff prompt (paste into new Phase 3 chat)

```
You are implementing Phase 3 only.
Read: .cursor/plans/prod-architecture-eval.plan.md and .cursor/plans/phase-3-eval-suite.plan.md
Prerequisites: Phase 1 locked configs; Phase 2 Stage 3 smoke-passed.
Goal: stratified eval ≤$150; recommend winner for 9.45k prod under ~$1k Stage 2.
First: cost the ideal 100+100 × 3 archs × ~3 iters (+ Stage 3); cut to 50+50 or trim Stage 3 frequency if needed; freeze n in STATUS; then run.
Winner metric: yield with cost, not precision alone.
```

---

## Changelog

- 2026-08-04: Created from Friday meeting + master Q&A (sample cut deferred here).
