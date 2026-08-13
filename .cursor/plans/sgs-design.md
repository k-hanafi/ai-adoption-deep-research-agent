# SGS design card (Phase 1) — FROZEN

**Status:** FROZEN (2026-08-08 ladder; **2026-08-11 scout semantics** = channel **presence screen**).  
**Identity:** Signal Gated Search = channel **presence scouts** + **signal-count → dig effort ladder**. Not equal-depth always-on PCS. Not single ungated UAS.  
**Supersedes:** eval-harness §3.2 Ranked Top-1 Dig (+ optional rescue) as the bake-off default. That policy remains a future ablation only.  
**Scout role supersedes:** any earlier “adoption smoke” scout wording (scouts do **not** hunt GenAI adoption).

Related:
- Decision freezes: `docs/decision-log.md` → ladder entry (2026-08-08) + presence-screen entry (2026-08-11)
- Scout prompt contracts: `prompts/signal_gated_search/scout_contracts.md`
- Tuning priors: `evals/instances/tuning/014_2026-08-07_1045/summary.json`
- PCS freeze (unchanged): `.cursor/plans/pcs-param-lock.md`
- Config: `evals/configs/signal_gated_search.yaml`
- Scaffold: `signal_gated_search/{gate,channels,runner}.py` (gate still implements old Top-1; **impl must replace**)

---

## Locked policy: signal-count → effort ladder

1. Run **3 parallel channel scouts** (jobs / owned / third_party).
2. Each scout answers: **does a diggable channel source exist?** (not “did we find GenAI adoption?”).
3. Count channels that clear `signal_threshold` (`signal=true` and confidence ≥ threshold).
4. Dig **every** signaled channel, with dig **effort** chosen by dig count:

| # signaled channels | Digs | Dig effort (each) | Planning dig $ (Tuning #14 means) | + scouts (~$0.02) |
|---:|---|---|---:|---:|
| 0 | none | — | 0 | ~0.02 |
| 1 | 1× that channel | **max** | ~0.102 | ~**0.12** |
| 2 | 2× those channels | **high** | ~0.086 | ~**0.11** |
| 3 | 3× all channels | **medium** | ~0.065 | ~**0.09** |

5. Digs extract **internal GenAI adoption** (PCS-like). Scouts only gate whether the room is worth paying for.
6. Merge/dedupe dig findings (PCS-like). Persist scout + gate traces always.
7. Agent API only. No domain-filter allowlists in v1 (prompt-only targeting, parity with PCS).

**Budget stance (locked):** Dig paths may land **above** the ~$0.10/company Stage 2 target (especially 1-dig max ≈ 12¢ and 2-dig high ≈ 11¢). User accepts this and will argue professor headroom using Tuning #14 effort→findings lift. Production **average** may still sit nearer 10¢ if many companies are 0-dig (no diggable channels). Do not silently cut effort to force ≤10¢ without a new freeze.

---

## Locked scout semantics: channel presence screen

**Motivation:** Many startups lack a job board, have only a thin stealth landing page, and/or have no third-party coverage. Digging those empty rooms wastes the effort ladder. Scouts skip absent rooms; digs hunt adoption only where a source surface exists.

| Channel | `signal=true` when… | `signal=false` when… |
|---|---|---|
| **jobs** | Real careers/ATS/job-listing surface exists | No jobs surface, placeholder “email us,” empty board |
| **owned** | Substantial company-owned web presence beyond a thin acquisition/waitlist page | One-page signup/stealth landing, parked domain, almost no indexable content |
| **third_party** | Meaningful external coverage exists (news, podcasts, nontrivial writeups, vendor stories) | No real footprint; directory stubs only |

**Operating point:** escalate on **most** cases where a diggable source exists (recall-leaning on **presence**). Provisional `signal_threshold=0.5` = escalate `moderate` + `strong` bins. Tune τ later on labeled presence labels (not adoption labels).

**Evidence bins → confidence (code may hard-map):**

| Bin | Meaning | confidence |
|---|---|---:|
| `none` | Channel source basically absent | 0.0 |
| `weak` | Ambiguous / thin / stub-like | 0.35 |
| `moderate` | Clear diggable source exists | 0.65 |
| `strong` | Rich, obvious source surface | 0.90 |

---

## Locked knobs

### Scouts (all 3 channels)

| Knob | Value |
|---|---|
| Packaging | Agent `preset=fast` (stock mini quick lookup) |
| Role | **Presence screen** only (JSON); not adoption extract |
| Tools | `web_search`; no `fetch_url` on scouts |
| Planning tax | ~**$0.02** for 3× (user planning figure; smoke-measure before spend claims) |

### Digs (per signaled channel)

| Knob | Value | Notes |
|---|---|---|
| `model` | `openai/gpt-5.6-luna` | No Sol |
| `max_steps` | **10** | Matches Tuning #14 effort arms |
| `web_search_depth` | **low** | Matches Tuning #14 effort arms |
| `reasoning_effort` | **max** if 1 dig; **high** if 2; **medium** if 3 | The spend dial |
| Dig input | **Cold start** (company identity only) | No scout URLs in the dig prompt/input. Scout URLs stay in traces. |

### Gate / thresholds

| Knob | Value |
|---|---|
| `signal_threshold` | **0.5** (provisional; presence operating point) |
| Dig-all signaled | **true** (effort ladder applies) |
| `rescue_enabled` | **false** |
| `max_digs_per_company` | **3** |
| Channel prior | unused for dig selection under dig-all |
| Domain filters | off |

### Signal schema (scouts)

```json
{
  "channel": "jobs|owned|third_party",
  "signal": true,
  "evidence_bin": "none|weak|moderate|strong",
  "confidence": 0.0,
  "urls": ["https://..."],
  "snippets": ["why this is a diggable source surface..."],
  "rationale": "one sentence about presence, not adoption"
}
```

Rules: no qualifying URL ⇒ force `none` / `signal=false`. Do not set `signal=true` because the company “seems AI-ish.” Digs own adoption judgment.

---

## Why this is SGS (vs PCS / UAS)

| | PCS (frozen) | UAS (Tuning #14 winner) | **SGS (this freeze)** |
|---|---|---|---|
| Always pays | 3× medium-depth extract | 1× max | 3× presence scouts + 0–3 digs |
| Depth | Equal medium (cannot afford 3× high) | One max thread | **Effort rises as dig count falls** |
| Breadth | Forced all rooms | None | Scout which rooms exist; dig only those |
| Over-$0.10 paths | Avoided by design (~7¢ Jam smoke) | ~10¢ flat | **Accepted** on 1–2 dig paths |

**Analogy:** three cheap flashlights check whether each room **exists and has furniture**. If one room is real, hire an expensive specialist for that room (max). If two are real, two strong specialists (high). If all three are real, three solid specialists (medium). Empty rooms get no hire.

---

## Cost + yield priors (for professor pitch)

**Tuning #14 effort ladder (single call, n=50):**

| Effort | Mean $/call | Mean findings |
|---|---:|---:|
| medium | 0.0216 | 1.66 |
| high | 0.0428 | 2.30 |
| max | 0.1016 | 2.80 |

Pitch: PCS cannot buy high/max on all three channels. SGS skips empty rooms (common for stealth/small startups) and spends high/max only when few diggable rooms exist.

**Risks:**
- Presence **FP:** dig a stub careers page / thin site → wasted dig $.
- Presence **FN:** skip a small-but-real owned page that had the only adoption evidence.
- Measure escalate-rate by channel early; τ is an operating point on presence P/R, not a magic constant.

---

## Explicit non-goals / later ablations

- Ranked Top-1 Dig + rescue (old §3.2 default): ablation only
- Scout-as-adoption-smoke (rejected 2026-08-11): too strict; wrong separation of concerns
- Dig warm-start from scout URLs (rejected 2026-08-13): risk of anchoring the expensive model; SGS identity is gating + effort ladder, not cheap breadcrumbs
- Dig steps=50 / search=medium on the 3-dig row: optional later
- Search-API scouts: out unless Agent-API-only rule reopens
- Trained presence classifier / conformal τ: v2 after rubric scouts ship
- Changing frozen PCS or UAS bake-off YAML: out of scope here

---

## Impl follow-ups (not done in freeze)

- [ ] Replace `signal_gated_search/gate.py` Top-1 policy with signal-count → effort schedule
- [x] Scout prompts: `prompts/signal_gated_search/scout_{shared_preamble,jobs,owned,third_party}.txt`
- [x] Dig prompts: `prompts/signal_gated_search/dig_{shared_preamble,jobs,owned,third_party}.txt` (channel overlays copy PCS)
- [ ] Live runner + component ledger (`scout_*`, `dig_{channel}` with effort tag)
- [ ] Tiny paid smoke: scout tax + presence escalate-rate + one path per dig-count bucket
- [ ] Dashboard: escalate-rate histogram + mean $/company by dig-count bucket
- [ ] Threshold sweep on labeled **presence** panel (freeze τ from data)
