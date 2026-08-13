# Phase 2 — Stage 3 citation verification (post-research guardrail)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Depends on Phase 1 exit** (Stage 2 citation/finding contract + frozen arch configs).  
**Open a new chat for this phase** only after Phase 1 STATUS says exited.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | Partial spike + packaging lock. **Perplexity does not expose usable logprobs** (2026-08-13). **Package home locked:** top-level production `citation_verification/` (not under `evals/`). Full Stage 3 still blocked on Phase 1 exit + remaining fetch/judge spike. |
| **Next** | Confirm OpenAI `reasoning.effort=none` binary+logprobs path; choose fetch path (Perplexity `fetch_url` hybrid preferred over Tavily-only); implement `citation_verification/`; wire evals as consumer. |
| **Exit** | Stage 3 package runnable for prod + exercised via evals (`run-verification` / panel smoke): schema, logprobs path, hallucination-rate check on eval companies. |
| **Spike / locks** | Logprobs: `docs/decision-log.md` [[2026-08-13: Perplexity APIs do not expose usable logprobs]]. Packaging: [[2026-08-13: Stage 3 is a production top-level package]]. |

---

## Packaging (locked)

**Production package:** top-level `citation_verification/` (peer of `unified_adaptive_search/`, `parallel_channel_search/`, `signal_gated_search/`, and `evals/`).

| Consumer | Role |
|---|---|
| **Prod** | After bake-off picks a Stage 2 winner, run that arch on the prod cohort, then run Stage 3 on those findings. |
| **Evals** | Import the **same** package to validate before prod: logprobs extraction works, hallucination rate is acceptable on the eval company set. CLI: `python -m evals run-verification` becomes a thin consumer, not the implementation home. |

**Superseded:** `evals/hooks/stage3_judge.py` as the Stage 3 home (legacy stub; may become a thin wrapper or be deleted when the package lands). Tree sketch in `eval-harness.plan.md` that buried Stage 3 under `evals/hooks/` is outdated for packaging.

Stage 3 is **not** a fourth competing research architecture. It is arch-agnostic verification over shared `contracts.Finding` rows.

---

## Contract

**GOAL:** Cheap Stage 3 judge that, for each finding citation from Stage 2 (Perplexity), classifies **hallucination vs supported**, with:
- **Binary field** suitable for **logprob** confidence proxy
- **Prompt-based confidence 1–5** as backup
- Cost kept **cheap** (no hard $/company ceiling yet)

**CONSTRAINTS:**
- Do not redesign Stage 2 architectures here.
- Implement as production package `citation_verification/`; evals only consumes it.
- API choice is a **research spike in this phase** (deferred from master Q5 until Phase 1 done).
- Known risk: Tavily scrape ≠ Perplexity’s view of the page → false “hallucination.” Must measure or mitigate (e.g. hybrid: Perplexity/cheap fetch for page text → OpenAI binary+logprobs).
- Check whether Perplexity APIs expose logprobs; do not assume they do.

**FORMAT:**
1. Spike report: Tavily+OpenAI vs Perplexity(+?) vs hybrid; logprob availability; scrape-mismatch risk.
2. Chosen design + schema fields (binary, logprob, conf_1_5, raw evidence snippet optional).
3. Minimal `citation_verification/` implementation + smoke on hand-picked true/false citation examples; evals consumer wired.
4. Rough $/finding or $/company Stage 3 add-on.

**FAILURE:**
- No binary field / no path to logprobs.
- Shipping Tavily-only without acknowledging mismatch risk.
- Judge coupled to a single architecture (must be arch-agnostic).
- Implementation living only inside `evals/` (blocks clean prod reuse).

---

## Research agenda (start after Phase 1)

1. Perplexity: can we get logprobs on a classification token? If not, what cheap output can feed an OpenAI judge?
2. Tavily+OpenAI (taxonomy pattern): false-positive rate on citations Perplexity used.
3. Hybrid recommendation with cost estimate.
4. Implement chosen path in `citation_verification/`; wire evals `run-verification` as consumer.

---

## Kickoff prompt (paste into new Phase 2 chat)

```
You are implementing Phase 2 only.
Read: .cursor/plans/prod-architecture-eval.plan.md and .cursor/plans/phase-2-stage3-verification.plan.md
Prerequisite: Phase 1 STATUS must show locked Stage 2 configs.
Goal: Stage 3 citation verification (binary + logprobs + 1–5 backup), cheap, arch-agnostic.
Package as top-level citation_verification/ for prod; evals only consumes it.
Start with API spike (Perplexity logprobs? Tavily mismatch? hybrid), then implement the winner.
Update plan STATUS when spike lands and when smoke passes.
```

---

## Changelog

- 2026-08-13: Packaging lock: Stage 3 is production top-level `citation_verification/`; evals only tests/consumes it. Supersedes `evals/hooks/` as home.
- 2026-08-13: Docs spike: Perplexity Gateway accepts `logprobs` only as `false`; rejects `top_logprobs`. Agent API examples return empty `logprobs: []` / `top_logprobs: 0` (schema stubs, not token probs). Logprob confidence proxy must come from OpenAI (or similar) with `reasoning.effort=none`.
- 2026-08-04: Created; formerly discussed as “Stage 5,” now correctly **Stage 3**.
