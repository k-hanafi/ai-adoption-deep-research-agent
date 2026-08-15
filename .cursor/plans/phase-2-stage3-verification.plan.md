# Phase 2 — Stage 3 citation verification (production package)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Scope of this plan:** ship production package `citation_verification/` end-to-end.  
**Out of scope here:** evals `run-verification` wiring, eval dashboards, hallucination-rate panels on the bake-off set (separate follow-up plan after the package exists).

---

## STATUS

| Field | State |
|---|---|
| **Current state** | Stack + packaging locked. **Awaiting user design locks** (schema + knobs below) before coding PRs. |
| **Locked stack** | Perplexity **`fetch_url`** → OpenAI Responses binary+logprobs (`reasoning.effort=none`), taxonomy Pass A extraction pattern. |
| **Package home** | Top-level `citation_verification/` (not under `evals/`). |
| **Next** | User answers §Design decisions needed → freeze schemas → PR1. |
| **Exit (this plan)** | Package can verify findings in dry + live modes via `python -m citation_verification`, with real logprob confidence, cost metering, and package tests. |
| **Decision log** | Packaging / logprobs / stack entries 2026-08-13. |

---

## Locked (do not reopen)

| Topic | Choice |
|---|---|
| Stack | Perplexity `fetch_url` + OpenAI logprob judge |
| Not | Tavily-only fetch; Perplexity `web_search` for verify; Perplexity-only judge |
| Packaging | `citation_verification/` production package |
| Confidence ownership | Computed in-package from token logprobs (never ask model to emit logprob confidence) |
| Fetch fail | System `UNVERIFIABLE` (not model `UNSUPPORTED`) |
| Preprocess | No HTML→markdown; use snippet as-is + truncate + empty guard |
| Judge API knobs | `reasoning.effort=none`, `include=["message.output_text.logprobs"]`, strict JSON schema OK (taxonomy-proven) |
| Reference | `k-hanafi/ai-startups-taxonomy-research` → `two_pass_classifier/{confidence,request_builder,schema}.py` |

---

## Design decisions needed from you

Answer these before PR1. Draft proposals are marked **proposal**; say lock / change.

### D1 — Model JSON schema (what OpenAI must emit)

Taxonomy Pass A emits: `ai_native` (0/1) + short reasoning + sources + critique.

**Proposal for Stage 3 judge schema:**

```text
supported: Literal[0, 1]          # 1 = page supports the claim; 0 = does not
support_reasoning: str            # ≤100 words, why
support_critique: str             # ≤100 words, self-check / doubt
```

**Questions:**
1. Lock field name `supported` (0/1), or prefer another name?
2. Keep `support_reasoning` + `support_critique` in v1, or binary-only (smaller/cheaper)?
3. Include verbalized `confidence_1_5` (1–5) in the **model** schema for v1, or defer (logprob is primary)?

### D2 — Package output schema (what we persist / return in Python)

Separate from the model schema. This is the product row after fetch+judge.

**Proposal `VerdictResult` fields:**

| Field | Type | Source |
|---|---|---|
| `finding_id` | int | input |
| `source_url` | str | input |
| `fetch_ok` | bool | fetch |
| `evidence_snippet` | str \| null | fetch (truncated) |
| `supported` | int \| null | model 0/1; null if unverifiable |
| `verdict` | `SUPPORTED` \| `UNSUPPORTED` \| `UNVERIFIABLE` | derived |
| `sampled_probability` | float \| null | confidence.py (P of chosen label) |
| `p_supported` | float \| null | renormalized P(supported=1) |
| `margin` | float \| null | taxonomy-style |
| `censored` | bool \| null | opposing digit missing |
| `confidence_extraction_ok` | bool | extractor succeeded |
| `confidence_1_5` | int \| null | only if D1 includes it |
| `support_reasoning` | str \| null | model (if kept) |
| `model_judge` | str | config |
| `cost_usd` | float | fetch + judge |
| `error` | str \| null | transport/parse |

**Questions:**
4. Lock this row shape, or add/drop fields?
5. Prefer taxonomy names (`sampled_probability`) vs shorter (`label_prob`)?

### D3 — What text is the “claim”?

Judge compares **claim** vs **page snippet**.

**Proposal claim bundle** (concat into user message):
- `AI_tool_used`
- `use_case`
- `business_function`
- `evidence_description`
- company `name` (context only)

**Questions:**
6. Lock that bundle, or claim = `evidence_description` only?

### D4 — Models / knobs

**Proposals:**
- Judge model: `gpt-5.6-luna` (or your taxonomy default if you prefer nano/mini for cost)
- `top_logprobs`: `5`
- Snippet max chars before judge: `12000` (tune after smoke)
- Perplexity fetch wrapper: cheapest Agent path that still runs `fetch_url` (need your preference: specific model id vs `preset=fast`)

**Questions:**
7. Lock judge model id?
8. Lock fetch Agent model / preset?
9. Sync Responses only for v1 (like taxonomy two-pass), or plan Batch API in a later PR?

### D5 — CLI / public API surface

**Proposal:**
```bash
python -m citation_verification --dry-run --findings path.jsonl
python -m citation_verification --live --findings path.jsonl
python -m citation_verification --live --url URL --claim "..."
```

Library:
```python
verify_finding(finding, *, dry_run=True) -> VerdictResult
verify_findings(findings, *, dry_run=True) -> VerifyResult
```

**Questions:**
10. Need `run(ArchitectureResult)` helper in v1, or findings-list only?

---

## Target package layout

```text
citation_verification/
  __init__.py
  __main__.py
  types.py                 # VerdictResult, VerifyResult, cost rollup
  schema.py                # OpenAI strict judge schema (D1)
  fetch.py                 # Perplexity fetch_url
  judge.py                 # OpenAI Responses request + raw parse
  confidence.py            # port taxonomy BinaryConfidence (decision key = supported)
  runner.py                # fetch → judge → VerdictResult
  prompting.py
  cost.py
  config.py                # model ids, top_logprobs, snippet cap, censor width

prompts/citation_verification/
  judge.txt

tests/
  test_citation_verification_types.py
  test_citation_verification_runner_dry.py
  test_citation_verification_confidence.py
  test_citation_verification_fetch_parse.py
  fixtures/                # anonymized Responses JSON for confidence tests
```

---

## PR plan (package only)

Sequential PRs onto `main`. Each PR green on its own. **No evals changes in these PRs.**

| PR | Branch suffix idea | Delivers | Done when |
|---|---|---|---|
| **PR1** | `citation-skeleton` | Package skeleton: `types` (D2 draft), dry `runner`/`__main__`, empty-URL → `UNVERIFIABLE`, config stubs, dry tests | `python -m citation_verification --dry-run` works; pytest dry tests green; live paths raise “not wired” |
| **PR2** | `citation-fetch` | `fetch.py` + parse `fetch_url_results` + cost component + fixture unit test | Dry runner can inject fixture snippets; optional **1-URL paid smoke** (user OK) |
| **PR3** | `citation-confidence` | Port/adapt taxonomy `confidence.py` + fixtures + offline tests (no API) | Pytest proves extract on supported/unsupported/censored fixtures |
| **PR4** | `citation-judge` | `schema.py` + `judge.txt` + `judge.py` request builder (`reasoning=none`, logprobs, strict schema) | Offline request-shape tests; optional **1-claim paid smoke** shows non-empty logprobs |
| **PR5** | `citation-wire` | Wire `verify_finding` = fetch → judge → confidence → `VerdictResult`; batch `verify_findings`; full cost ledger; live CLI | Dry E2E; user-approved **2-finding live smoke** (1 true citation, 1 false); package README usage |

**After PR5 (not in this plan):** separate plan/PRs for evals consumer + eval-set quality gates.

### PR dependency graph

```text
PR1 skeleton
  → PR2 fetch
  → PR3 confidence   (can parallel with PR2 after PR1)
  → PR4 judge        (needs PR3 for extract; schema from D1)
  → PR5 wire         (needs PR2+PR4)
```

Preferred sequence if serial: **1 → 2 → 3 → 4 → 5**.  
Allowed parallel: **PR2 ∥ PR3** after PR1.

### Per-PR rules

- Default `dry_run=True`; `--live` explicit
- No evals/ edits
- Paid smokes only with your OK
- Author = Khaled; no Cursor attribution trailers
- Update this STATUS + decision log when a design lock or PR lands

---

## Cost sketch (package v1)

| Piece | Ballpark |
|---|---|
| `fetch_url` tool | $0.00025 / finding URL |
| OpenAI judge | dominates; depends on D4 model + schema verbosity |

---

## Failure modes (package)

- No real logprobs / empty `logprobs[]` shipped as “confidence”
- Fetch fail labeled `UNSUPPORTED`
- Second confidence extractor living outside the package
- Scope creep into evals inside these PRs

---

## Kickoff (after D1–D5 answered)

```
Implement citation_verification/ per .cursor/plans/phase-2-stage3-verification.plan.md PR plan.
Respect locked D1–D5 answers in docs/decision-log.md.
Start PR1 only. No evals/ changes. Dry before live.
```

---

## Changelog

- 2026-08-13: Package-only PR plan (PR1–PR5); evals testing removed from this plan; explicit D1–D5 design questions for user.
- 2026-08-13: Align judge pattern with taxonomy Pass A + production-owned `confidence.py`.
- 2026-08-13: Stack lock + packaging lock + logprobs spike notes.
- 2026-08-04: Created; formerly “Stage 5,” now Stage 3.
