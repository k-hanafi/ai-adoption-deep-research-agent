# Phase 2 — Stage 3 citation verification (production package)

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**Scope of this plan:** ship production package `citation_verification/` end-to-end.  
**Out of scope here:** evals `run-verification` wiring, eval dashboards, hallucination-rate panels on the bake-off set (separate follow-up plan after the package exists).

---

## STATUS

| Field | State |
|---|---|
| **Current state** | **Commits 1–5 + Bugbot fix landed.** PR #28 ready; cloud Bugbot on tip commit reported **no issues**. |
| **Locked stack** | Perplexity **`fetch_url`** → OpenAI **`gpt-5.6-luna`** binary+logprobs (`reasoning.effort=none`). Terra superseded 2026-08-15. |
| **Package home** | Top-level `citation_verification/` (not under `evals/`). |
| **Next** | Human merge of PR #28 when ready. Evals `run-verification` is a separate follow-up plan. |
| **Exit (this plan)** | Package can verify findings in dry + live modes via `python -m citation_verification`, with real logprob confidence, cost metering, and package tests; single PR merge-ready after cloud Bugbot babysit. |
| **Decision log** | Packaging / logprobs / stack 2026-08-13; D1–D5 + delivery 2026-08-14. |

---

## Locked (do not reopen)

| Topic | Choice |
|---|---|
| Stack | Perplexity `fetch_url` + OpenAI logprob judge |
| Judge model | **`gpt-5.6-luna`** (same OpenAI logprob path; Terra retired for cost) |
| Not | Tavily-only fetch; Perplexity `web_search` for verify; Perplexity-only judge |
| Packaging | `citation_verification/` production package |
| Confidence ownership | **`log_probs_conf` computed in-package** from token logprobs (never ask the model to invent that number) |
| Model-emitted fields (D1) | `verification` ∈ {0,1}, `confidence_1_5`, `verification_reasoning`, `verification_critique` |
| `verification` meaning | **1 = verified** (page supports claim); **0 = hallucination** (page does not) |
| Claim text (D3) | **`evidence_description` only** |
| Package core fields (order) | `verification`, `log_probs_conf`, `confidence_1_5`, `verification_reasoning`, `verification_critique`, **then** ops/cost fields |
| Ops/cost fields (D2, trailing) | `fetch_ok`, `evidence_snippet`, `censored`, `margin`, `model_judge`, `cost_usd` (+ breakdown if useful), `error` |
| CLI (D5) | Simple: `--findings` JSONL + `--dry-run`/`--live`; optional `--url`/`--claim` debug |
| Fetch fail | System `UNVERIFIABLE` (not model “unsupported”) |
| Preprocess | No HTML→markdown; use snippet as-is + truncate + empty guard |
| Judge API knobs | `reasoning.effort=none`, `include=["message.output_text.logprobs"]`, strict JSON schema OK |
| Reference | taxonomy `two_pass_classifier/{confidence,request_builder,schema}.py` |

---

## Design decisions (status)

### D1 — Output fields — **locked 2026-08-14**

| Field | Who produces it | Notes |
|---|---|---|
| `verification` | Model (JSON schema) | **`Literal[0, 1]`**. 1 = verified; 0 = hallucination. Best for logprob span extract. |
| `log_probs_conf` | **Package** (`confidence.py`) | From `verification` token logprobs. Not model-emitted. |
| `confidence_1_5` | Model | Verbalized 1–5 backup |
| `verification_reasoning` | Model | Short why |
| `verification_critique` | Model | Short self-check |

Fetch failure / empty snippet → package-side unverifiable path (do not force model `0`).

### D2 — Package row extras — **locked 2026-08-14**

Persist ops/cost fields for observability and interpretability, **after** the core D1 fields:

Core (first): `verification`, `log_probs_conf`, `confidence_1_5`, `verification_reasoning`, `verification_critique`  
Then: `fetch_ok`, `evidence_snippet`, `censored`, `margin`, `model_judge`, `cost_usd` (and fetch/judge cost breakdown if cheap to keep), `error`

### D3 — Claim text — **locked 2026-08-14**

**Claim** = Stage 2 `evidence_description` only (kept simple). Judge compares that string to the fetched page snippet.

### D4 — Judge model — **locked 2026-08-14**

`gpt-5.6-luna` with `reasoning.effort=none` (required for logprobs). Same OpenAI Responses path as Terra. Judge ≠ Perplexity researcher wrapper.

Still open only as implementation defaults (not blocking PR1): Perplexity fetch wrapper model/preset (**proposal: cheapest Agent path that runs `fetch_url`**); sync-only v1 (**proposal: sync**).

### D5 — CLI — **locked 2026-08-14**

Keep simple, keep necessary:

```bash
python -m citation_verification --dry-run --findings path.jsonl
python -m citation_verification --live --findings path.jsonl
python -m citation_verification --live --url URL --claim "..."   # one-off debug
```

Library: `verify_finding` / `verify_findings`.  
No `run(ArchitectureResult)` in v1.

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
  confidence.py            # port taxonomy BinaryConfidence (decision key = verification)
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

## Delivery mode (locked 2026-08-14)

**One GitHub PR**, **five commits** (slices below). Not five stacked PRs.

### Bugbot workflow (per slice + final PR)

| Gate | When | What |
|---|---|---|
| **Local Bugbot** | After **each** of the five commits | In Cursor IDE: `/review-bugbot` → fix → re-run until **no findings**. Do not start the next slice until clean. |
| **Cloud Bugbot babysit** | After all five commits are on the PR | Open/update the single PR; cloud agent loops: read Bugbot comments → fix → push → wait → until Bugbot is clean / merge-ready. |

**Notes:**
- Local `/review-bugbot` is an **IDE / Agents View** command (not headless CLI yet). Cloud coding agents cannot invoke it from the shell; the human (or IDE agent) runs that gate on the Mac.
- Cloud babysit uses GitHub Bugbot comments on the PR (same pattern as prior hotfix PRs in this repo).
- Prefer fixing real bugs; dismiss only clearly invalid findings with a short reason.

### Slice commits (same content as old PR1–PR5)

| Commit | Delivers | Done when |
|---|---|---|
| **1 skeleton** | Package skeleton: `types`, dry `runner`/`__main__`, empty-URL → unverifiable, config stubs, dry tests | `python -m citation_verification --dry-run` works; pytest dry tests green; live paths raise “not wired”; **local Bugbot clean** |
| **2 fetch** | `fetch.py` + parse `fetch_url_results` + cost component + fixture unit test | Fixture parse tests green; optional 1-URL paid smoke (user OK); **local Bugbot clean** |
| **3 confidence** | Port/adapt taxonomy `confidence.py` + fixtures + offline tests | Pytest extract on supported/unsupported/censored fixtures; **local Bugbot clean** |
| **4 judge** | `schema.py` + `judge.txt` + `judge.py` (`reasoning=none`, logprobs, strict schema) | Offline request-shape tests; optional 1-claim paid smoke; **local Bugbot clean** |
| **5 wire** | Wire fetch → judge → confidence → `VerdictResult`; batch; live CLI | Dry E2E; user-approved 2-finding live smoke; **local Bugbot clean** → open PR → **cloud Bugbot babysit to merge-ready** |

**After this PR merges:** separate plan for evals consumer + eval-set quality gates.

### Branch / PR rules

- Branch: `cursor/citation-verification-8475` (or continue existing Stage 3 branch if already tracking)
- Default `dry_run=True`; `--live` explicit
- No `evals/` edits in this PR
- Paid smokes only with user OK
- Author = Khaled; no Cursor attribution trailers
- Update this STATUS + decision log as commits land

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

## Kickoff

```
Implement citation_verification/ as ONE PR with FIVE commits per
.cursor/plans/phase-2-stage3-verification.plan.md delivery mode.
Respect locked D1–D5 in docs/decision-log.md.
After each commit: human/IDE runs /review-bugbot until none, then continue.
After commit 5: open PR; cloud agent babysits GitHub Bugbot until merge-ready.
No evals/ changes. Dry before live.
```

---

## Changelog

- 2026-08-14: Delivery mode = one PR / five commits; local Bugbot per slice + cloud Bugbot babysit on final PR.
- 2026-08-14: Lock D2 trailing cost/ops fields + D5 simple CLI; design freeze complete → PR1 next.
- 2026-08-14: Lock `verification` as 0/1 (1=verified, 0=hallucination); claim = `evidence_description` only.
- 2026-08-14: Lock D1 field names + D4 `gpt-5.6-terra`; clarify `log_probs_conf` is package-computed; explain claim text; propose D5 CLI.
- 2026-08-13: Package-only PR plan (PR1–PR5); evals testing removed from this plan; explicit D1–D5 design questions for user.
- 2026-08-13: Align judge pattern with taxonomy Pass A + production-owned `confidence.py`.
- 2026-08-13: Stack lock + packaging lock + logprobs spike notes.
- 2026-08-04: Created; formerly “Stage 5,” now Stage 3.
