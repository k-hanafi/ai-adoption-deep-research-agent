# Phase 2 — Stage 3 citation verification (post-research guardrail)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Depends on Phase 1 exit** for full bake-off wiring. Package scaffold + API smokes can start now (stack locked below).

---

## STATUS

| Field | State |
|---|---|
| **Current state** | **Stack + packaging locked.** Build plan ready for `citation_verification/`. |
| **Locked stack** | Perplexity **`fetch_url`** (page text for known `source_url`) → OpenAI **binary + logprobs** (`reasoning.effort=none`) + prompt **1–5** backup. |
| **Next** | Implement package slices below; dry-run first; tiny paid smoke; then evals consumer. |
| **Exit** | Package runnable for prod + exercised via evals: schema, real logprobs, hallucination-rate check on eval companies. |
| **Decision log** | Packaging [[2026-08-13: Stage 3 is a production top-level package]]; no Perplexity logprobs [[2026-08-13: Perplexity APIs do not expose usable logprobs]]; stack [[2026-08-13: Stage 3 stack = Perplexity fetch_url + OpenAI logprob judge]]. |

---

## Locked design

### Why this stack

| Piece | Choice | Why |
|---|---|---|
| Fetch | Perplexity `fetch_url` | Same tool family Stage 2 uses; reduces Tavily≠Perplexity false “hallucination.” Input is an already-known citation URL (not discovery). |
| Judge | OpenAI, `reasoning.effort=none` | Only practical path to token **logprobs** for a confidence proxy. |
| Backup | Prompt confidence 1–5 | Survives if logprobs flake; not the primary score. |
| Package | Top-level `citation_verification/` | Production software; evals only imports it. |

**Not** Perplexity `web_search` for Stage 3: search rediscovers pages; verification needs the cited URL’s text.  
**Not** Tavily-only fetch: scrape mismatch risk (plan failure mode).  
**Not** Perplexity-only judge: no usable logprobs.

### I/O contract

**Input (per finding):** shared `contracts.Finding` (at least `finding_id`, `AI_tool_used`, `evidence_description` / claim text, `source_url`) plus company identity for traces.

**Output (per finding):**

| Field | Type | Notes |
|---|---|---|
| `verdict` | `SUPPORTED` \| `UNSUPPORTED` \| `UNVERIFIABLE` | Binary-ish; third class for fetch fail / empty snippet |
| `supported` | `bool \| null` | `null` when unverifiable |
| `label_logprob` | `float \| null` | Logprob of the chosen binary token (primary confidence) |
| `label_prob` | `float \| null` | `exp(logprob)` convenience |
| `confidence_1_5` | `int \| null` | Backup self-score |
| `evidence_snippet` | `str \| null` | Truncated Perplexity `fetch_url` snippet used |
| `fetch_ok` | `bool` | Whether fetch returned usable text |
| `cost_usd` | `float` | Fetch + judge for this finding |
| `model_judge` | `str` | OpenAI model id |
| `error` | `str \| null` | Transport / parse failures |

**Company rollup:** list of per-finding results + `CostLedger` components (`fetch_url`, `openai_judge`) + totals.

### Preprocessing

No HTML→markdown pipeline. Use Perplexity `snippet` as-is, with:

1. Empty / too-short → `UNVERIFIABLE` (do **not** map to `UNSUPPORTED`)
2. Truncate to a token/char budget before OpenAI
3. Optional whitespace normalize

### Judge shape (logprobs-safe)

- Ask for a **single classification token** first: `SUPPORTED` or `UNSUPPORTED` (plain text, **not** `json_schema`, which can empty logprobs).
- Request logprobs / `include` for that token under `reasoning.effort=none`.
- Optionally a second short line or second cheap call for `confidence_1_5` if one-shot parsing is messy; prefer one call if both fit without structured JSON.

---

## Packaging (locked)

**Production package:** top-level `citation_verification/` (peer of Stage 2 arches + `evals/`).

| Consumer | Role |
|---|---|
| **Prod** | Stage 2 winner → findings → `citation_verification` |
| **Evals** | Same import for pre-prod checks (`run-verification`) |

**Superseded as home:** `evals/hooks/stage3_judge.py` (thin wrap or delete when package lands).

---

## Target folder layout

Mirror Stage 2 package habits (thin CLI, `runner.py` public API, dry-run default):

```text
citation_verification/
  __init__.py              # export run / verify_finding
  __main__.py              # python -m citation_verification [--live]
  types.py                 # VerdictResult, VerifyResult (dataclasses)
  fetch.py                 # Perplexity Agent API fetch_url → snippet
  judge.py                 # OpenAI binary + logprobs + 1–5 backup
  runner.py                # verify_finding / verify_findings / run(company_result)
  prompting.py             # load judge prompt text
  cost.py                  # meter fetch + judge into CostComponent rows

prompts/citation_verification/
  judge.txt                # system/user template for binary judge

tests/
  test_citation_verification_types.py
  test_citation_verification_runner_dry.py
  test_citation_verification_judge_parse.py   # parse logprobs from fixtures
```

**Public API (sketch):**

```python
# One finding
verify_finding(finding: Finding, *, dry_run: bool = True) -> VerdictResult

# Many findings (prod / eval batch)
verify_findings(findings: list[Finding], *, dry_run: bool = True) -> VerifyResult

# Optional: accept ArchitectureResult and attach scores
run(stage2_result: ArchitectureResult, *, dry_run: bool = True) -> VerifyResult
```

Dry-run: no paid APIs; returns ledger-shaped stubs + `dry_run_no_api` (same spirit as UAS/PCS/SGS).

---

## Build plan (slices)

Each slice: implement → unit/dry tests green → commit. Paid smokes only with explicit user OK.

### Slice A — Skeleton + types + dry runner

**Build:** Package tree, `types.py`, `runner.py` dry path, `__main__.py` (`--live` flag present but live unwired), empty/short-URL → `UNVERIFIABLE` logic without network.

**Verify:** `python -m citation_verification` dry; `pytest tests/test_citation_verification_*.py`.

### Slice B — Perplexity `fetch_url` client

**Build:** `fetch.py`: given URL, Agent API call with tools=`[{type: fetch_url}]`, extract `fetch_url_results.contents[].snippet`, meter `$0.00025` + token cost from usage. Cheap/small model or minimal steps; force fetch of the given URL in instructions/input.

**Verify:** Unit test with recorded fixture payload; optional **one-URL paid smoke** (user-approved).

### Slice C — OpenAI logprob judge

**Build:** `judge.py` + `prompts/citation_verification/judge.txt`. `reasoning.effort=none`, binary token, parse logprob, backup 1–5. No `json_schema` on the logprob call.

**Verify:** Fixture-based parse tests; optional **one-claim paid smoke** proving `label_logprob` is non-null.

### Slice D — Wire runner + cost ledger

**Build:** `verify_finding` = fetch → (if ok) judge → `VerdictResult`; batch helper; cost components `fetch_*` + `judge_*`.

**Verify:** Dry end-to-end; one hand-picked true citation + one false citation live smoke (user-approved).

### Slice E — Evals consumer (thin)

**Build:** `evals` `run-verification` imports `citation_verification` (replace stub). Archive instance shows per-finding verdicts + costs. Keep package ownership outside evals.

**Verify:** `python -m evals run-verification` dry on a small finding set; later live panel for hallucination-rate read.

### Slice F — Eval quality gate (pre-prod)

**Build:** Script or eval mode: run Stage 3 on eval-set findings (from bake-off or March soft refs), report:

- % `SUPPORTED` / `UNSUPPORTED` / `UNVERIFIABLE`
- logprob distribution (are probs real, not always ~1.0?)
- spot-check disagreement rate vs human on a tiny labeled slice

**Verify:** User accepts “hallucination rate / unverifiable rate good enough for prod,” then freeze config.

---

## Cost sketch (tool fees only; judge tokens extra)

| Findings / company | `fetch_url` @ $0.00025 |
|---:|---:|
| ~1 (March positive median) | ~$0.00025 |
| ~2 (bake-off-ish) | ~$0.00050 |

OpenAI judge will dominate Stage 3 $; keep model small and output tiny. Revisit after Slice D smoke.

---

## Failure modes (do not ship)

- No binary field / no real logprobs path
- Fetch fail → labeled `UNSUPPORTED` (must be `UNVERIFIABLE`)
- Tavily-only without mismatch mitigation
- Judge coupled to UAS/PCS/SGS internals
- Implementation only under `evals/`

---

## Kickoff prompt (implementation chat)

```
Implement Stage 3 as top-level citation_verification/ only.
Read: .cursor/plans/phase-2-stage3-verification.plan.md and docs/decision-log.md
Stack: Perplexity fetch_url → OpenAI reasoning.effort=none binary+logprobs (+ 1–5 backup).
Follow slices A→D first (dry before live). Evals is a thin consumer later (slice E).
Do not put implementation under evals/. Do not open PRs for tiny doc-only tweaks.
Update this plan STATUS as slices land.
```

---

## Changelog

- 2026-08-13: Stack lock + full build plan for `citation_verification/` (fetch_url + OpenAI logprob judge; slices A–F).
- 2026-08-13: Packaging lock: Stage 3 is production top-level `citation_verification/`; evals only tests/consumes it. Supersedes `evals/hooks/` as home.
- 2026-08-13: Docs spike: Perplexity Gateway accepts `logprobs` only as `false`; rejects `top_logprobs`. Logprob confidence proxy must come from OpenAI with `reasoning.effort=none`.
- 2026-08-04: Created; formerly discussed as “Stage 5,” now correctly **Stage 3**.
