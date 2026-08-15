# SGS design card (Phase 1) — FROZEN

**Status:** FROZEN (2026-08-13 bake-off effort: SGS digs **high**, not max. Scout preset = **low**. Scout semantics = presence/existence screen. Owned = site + official accounts, homepage is not a gate. 2026-08-14: dig leash matches PCS, `max_steps=50` / `web_search_depth=medium`).  
**Identity:** Signal Gated Search = channel **presence scouts** + **dig every signaled channel at high**. Not equal-depth always-on PCS. Not single ungated UAS.  
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

## Locked policy: dig-all signaled at high

1. Run **3 parallel channel scouts** (jobs / owned / third_party).
2. Each scout answers: **does this room exist on the public web?** (not “did we find GenAI adoption?”).
3. Count channels that clear `signal_threshold` (`signal=true` and confidence ≥ threshold).
4. Dig **every** signaled channel. Every dig uses **`reasoning_effort=high`** (not max, not a count ladder):

| # signaled channels | Digs | Dig effort (each) |
|---:|---|---|
| 0 | none | — |
| 1 | 1× that channel | **high** |
| 2 | 2× those channels | **high** |
| 3 | 3× all channels | **high** |

Bake-off effort lock (2026-08-13): **UAS = xhigh**, **PCS = 3× medium**, **SGS digs = high**.

5. Digs extract **internal GenAI adoption** (PCS-like). Scouts only gate whether the room exists.
6. Merge/dedupe dig findings (PCS-like). Persist scout + gate traces always.
7. Agent API only. No domain-filter allowlists in v1 (prompt-only targeting, parity with PCS).

**Budget stance (locked):** Do not use `max` on SGS. CoverTree existence-bar smoke at 1× max cost **$0.165**. High is the SGS spend cap per dig. Count still changes how many rooms we pay for, not how hard each room is searched.

---

## Locked scout semantics: channel presence screen

**Motivation:** Skip a room only when it does not exist on the public web. Scouts do not judge source quality and do not hunt GenAI adoption. Digs do the adoption extract. A thin careers page or aggregator listing is still a jobs room.

| Channel | `signal=true` when… | `signal=false` when… |
|---|---|---|
| **jobs** | Any jobs-related pages exist for this employer (ATS, careers, aggregators, LinkedIn jobs, email-us hiring pages, stale listings) | No jobs-related pages at all (or only a different company with a similar name) |
| **owned** | A company website exists (including a thin/waitlist page) **or** official company accounts | No site AND no official accounts |
| **third_party** | Any independent pages exist (news, interviews, writeups, vendor stories, personal posts) | No independent pages. Empty directory stubs only |

**Operating point:** escalate on **most** cases where a diggable source exists (recall-leaning on **presence**). Provisional `signal_threshold=0.5` = escalate `moderate` + `strong` bins. Tune τ later on labeled presence labels (not adoption labels). Homepage is identity, not a gate: code must not require `homepage_url` to fire digs. Official company accounts can signal owned when the site is down or unretrieved.

**SGS vs PCS owned:** PCS owned stays host-based (company CMS on company domain; YouTube/LinkedIn posts default third_party). SGS owned is narrator-based (site **plus** official accounts). Bake-off identity difference is intentional after the Tern smoke FN.

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
| Packaging | Agent `preset=low` (stock low; more web than `fast`) |
| Role | **Presence screen** only (JSON); not adoption extract |
| Tools | `web_search`; no `fetch_url` on scouts |
| Planning tax | ~**$0.02** for 3× (user planning figure; smoke-measure before spend claims) |

### Digs (per signaled channel)

| Knob | Value | Notes |
|---|---|---|
| `model` | `openai/gpt-5.6-luna` | No Sol |
| `max_steps` | **50** | Matches PCS channel leash (was 10 / Tuning #14) |
| `web_search_depth` | **medium** | Matches PCS channel leash (was low / Tuning #14) |
| `reasoning_effort` | **high** (every dig) | Not max. Count does not change effort. |
| Dig input | **Cold start** (company identity only) | No scout URLs in the dig prompt/input. Scout URLs stay in traces. |

### Gate / thresholds

| Knob | Value |
|---|---|
| `signal_threshold` | **0.5** (provisional; presence operating point) |
| Dig-all signaled | **true** (every dig at high) |
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
