# Phase 2 — Stage 3 citation verification (post-research guardrail)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Depends on Phase 1 exit** (Stage 2 citation/finding contract + frozen arch configs).  
**Open a new chat for this phase** only after Phase 1 STATUS says exited.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | Blocked on Phase 1. |
| **Next** | After Phase 1: spike API options for evidence fetch + binary judge + logprobs. |
| **Exit** | Stage 3 shipped enough for Phase 3 eval (schema + runnable judge + smoke). |

---

## Contract

**GOAL:** Cheap Stage 3 judge that, for each finding citation from Stage 2 (Perplexity), classifies **hallucination vs supported**, with:
- **Binary field** suitable for **logprob** confidence proxy
- **Prompt-based confidence 1–5** as backup
- Cost kept **cheap** (no hard $/company ceiling yet)

**CONSTRAINTS:**
- Do not redesign Stage 2 architectures here.
- API choice is a **research spike in this phase** (deferred from master Q5 until Phase 1 done).
- Known risk: Tavily scrape ≠ Perplexity’s view of the page → false “hallucination.” Must measure or mitigate (e.g. hybrid: Perplexity/cheap fetch for page text → OpenAI binary+logprobs).
- Check whether Perplexity APIs expose logprobs; do not assume they do.

**FORMAT:**
1. Spike report: Tavily+OpenAI vs Perplexity(+?) vs hybrid; logprob availability; scrape-mismatch risk.
2. Chosen design + schema fields (binary, logprob, conf_1_5, raw evidence snippet optional).
3. Minimal implementation + smoke on hand-picked true/false citation examples.
4. Rough $/finding or $/company Stage 3 add-on.

**FAILURE:**
- No binary field / no path to logprobs.
- Shipping Tavily-only without acknowledging mismatch risk.
- Judge coupled to a single architecture (must be arch-agnostic).

---

## Research agenda (start after Phase 1)

1. Perplexity: can we get logprobs on a classification token? If not, what cheap output can feed an OpenAI judge?
2. Tavily+OpenAI (taxonomy pattern): false-positive rate on citations Perplexity used.
3. Hybrid recommendation with cost estimate.
4. Implement chosen path; wire into eval hooks.

---

## Kickoff prompt (paste into new Phase 2 chat)

```
You are implementing Phase 2 only.
Read: .cursor/plans/prod-architecture-eval.plan.md and .cursor/plans/phase-2-stage3-verification.plan.md
Prerequisite: Phase 1 STATUS must show locked Stage 2 configs.
Goal: Stage 3 citation verification (binary + logprobs + 1–5 backup), cheap, arch-agnostic.
Start with API spike (Perplexity logprobs? Tavily mismatch? hybrid), then implement the winner.
Update plan STATUS when spike lands and when smoke passes.
```

---

## Changelog

- 2026-08-04: Created; formerly discussed as “Stage 5,” now correctly **Stage 3**.
