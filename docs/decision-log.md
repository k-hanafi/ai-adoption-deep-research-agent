# Decision log: Stage 2 architectures & eval design

Living notes for the project write-up. **Agents maintain this file** under `.cursor/rules/decision-log.mdc` until the project finishes.

## Agent contract

| Rule | Behavior |
|---|---|
| Append-only history | New `## YYYY-MM-DD: …` sections; do not rewrite past decisions |
| Supersede, don’t delete | Mark old entry `superseded by [[…]]`; add full new entry |
| Self-heal | Fix broken paths, stale checkboxes, contradictory “current” claims when noticed |
| Evidence-backed | Link repo paths, tuning instance IDs, metrics; no invented freezes |
| Scope | Design/config/eval locks only; skip plumbing trivia |

Human: skim this file when writing the paper/portfolio narrative. Agents: update it whenever a decision lands.

## Related artifacts

- Tuning instance: `evals/instances/tuning/014_2026-08-07_1045/`
- PCS param lock: `.cursor/plans/pcs-param-lock.md`
- March channel evidence: `.cursor/plans/pcs-march-channel-evidence.md`
- PCS prompts: `prompts/parallel_channel_search/`
- PCS config: `evals/configs/parallel_channel_search.yaml`
- SGS design freeze: `.cursor/plans/sgs-design.md`
- SGS scout contracts: `prompts/signal_gated_search/scout_contracts.md`
- SGS config: `evals/configs/signal_gated_search.yaml`
- SGS paid 5-co smoke: `outputs/stage2/test_runs/sgs_smoke_5co/`
- Agent rule: `.cursor/rules/decision-log.mdc`
- Stage 3 verification plan: `.cursor/plans/phase-2-stage3-verification.plan.md`
- Stage 3 package: `citation_verification/` (production; not under `evals/`)
- Stage 3 judge prompt: `prompts/citation_verification/judge.txt`

---

## 2026-08: Stage 2 cost target

**Decision:** Design UAS / PCS / SGS so each averages about **$0.10/company** Stage 2 spend (planning headroom mean ≤ ~$0.105). For ~9.45k companies that is ~$945 ≤ ~$1k.

**Why:** Luna cut token cost vs March GPT-5.2 (~$0.32/co). Friday intent was to spend the windfall on capability at parity across architectures, not leave leftover pennies and not jump to Sol/`high` (Jam smoke: Sol high ≈ $0.28, not a 10¢ upgrade).

**Evidence:** Phase 1 pricing ledger; Jam smokes (March / Luna medium / Sol high); Tuning #14 live OFAT on held-out panel.

**Rejected:** Stock Sol `high` as the UAS “upgrade”; keeping unit cost at ~$0.02 after Luna.

---

## 2026-08: Architecture identities

**Decision:** Keep three named systems for the bake-off:
- **UAS** — one adaptive Agent API call per company (knobs, not fan-out)
- **PCS** — three equal-depth channel extractors (jobs / owned / third_party), then merge
- **SGS** — channel scouts with gated dig (not PCS)

**SGS detail:** superseded in specificity by [[2026-08-08: SGS design frozen (signal-count effort ladder)]] (signal-count → effort ladder; dig-all signaled).

**Why:** Separates hypotheses: single deep thread vs forced breadth vs gated depth. Fair comparison needs each class to hit roughly the same $/company.

---

## 2026-08: PCS equal depth

**Decision:** All three PCS channels use the **same** model/steps/effort/search knobs. Always run all three (no scout gate).

**Why:** March positives are often single-channel; a generalist can starve a room. Equal depth is coverage insurance so jobs/owned/third_party each get dedicated budget. It is **not** because March mass is equal thirds (owned ~45%, jobs ~26%, third_party ~22%).

**Rejected for PCS v1:** Mixed always-on depths as default; scout→dig (that is SGS).

---

## 2026-08: PCS targeting = prompts only

**Decision:** Steer channels with specialist prompts. **No** hard `search_domain_filter` allowlists for v1.

**Why:** Owned evidence is a long tail of company domains; allowlists would be brittle and likely destructive to recall. Prompts define rooms; merge cleans overlap.

---

## 2026-08: How channel prompts are written

**Decision:**
1. Shared mission + sibling map + channel contract (no UAS/SGS names).
2. March informs **source shapes** (where evidence lived), not finding few-shots (which tools/companies/use cases).
3. Sibling rules steer **search budget**, not a veto: if an agent finds qualifying internal-use evidence off-room, it should still report it; merge dedupes. Hard exclude remains use-vs-sell only.

**Why:** Avoid repeating-cohort bias and avoid dropping real findings on fuzzy boundaries. Cross-architecture contamination would bias the bake-off story.

**Files:** `prompts/parallel_channel_search/{shared_preamble,channel_jobs,channel_owned,channel_third_party}.txt`

---

## 2026-08-08: PCS prompts + Agent API knobs frozen (design)

**Decision:** User approved freeze of PCS channel prompts and equal-depth Agent API knobs for the bake-off path.

**Locked knobs:** Luna / `max_steps=50` / `reasoning_effort=medium` / `web_search_depth=medium` on jobs+owned+third_party.

**Locked prompts:** `prompts/parallel_channel_search/{shared_preamble,channel_jobs,channel_owned,channel_third_party}.txt`.

**Status:** Design freeze. Live package + Jam smoke confirmed 2026-08-08 (see [[2026-08-08: PCS one-company live smoke confirmed]]). Shared preamble extract-teaching amended by [[2026-08-13: PCS and SGS extract prompts share UAS use-vs-sell teaching]]. Channel files unchanged.

**Evidence:** Tuning #14; `evals/configs/parallel_channel_search.yaml`; user approval 2026-08-08.

---

## 2026-08: PCS knobs from Tuning #14 (final under effort=medium)

**Status:** superseded in wording by [[2026-08-08: PCS prompts + Agent API knobs frozen (design)]] (same knobs; that entry is the freeze).

**Decision (equal-depth, all channels):**

| Knob | Value |
|---|---|
| `model` | `openai/gpt-5.6-luna` |
| `max_steps` | `50` |
| `reasoning_effort` | `medium` |
| `web_search_depth` | `medium` |

**Projected cost:** ≈ **$0.06–0.07/company** (3 × ~$0.02–0.023 from medium-effort UAS arms). Under the ~$0.10 target.

**Why (by knob):**
- **effort=medium:** Only discrete effort tier whose 3× projection stays ≤ ~$0.105. `high` ×3 ≈ **$0.128**; `xhigh`/`max` far over. User also locked “stay on medium effort” for this PCS pass.
- **max_steps=50:** In the cheap ladder, steps barely move dollars but steps=50 had the best findings (~1.94 vs baseline ~1.66). steps=100 did not help.
- **web_search_depth=medium:** Middle ground between low and high. OFAT: medium ≈ wash vs low; high finished cost-feasible (~$0.021) but mean findings looked worse (paired win-count vs baseline was tied 15–15, so partly noise). Prefer medium over high for the freeze; do not treat high as proven better.

**Rejected under ~$0.10 + medium effort:**
- `effort=high|xhigh|max` per channel (budget)
- Default `search=high` (no clear yield win; noisy)
- steps=100 (no lift)
- Relying on stock dynamic `preset=low` without explicit knobs

**Fairness note for write-up:** UAS’s ~10¢ single-call winner in Tuning #14 was `effort=max` (~$0.10, ~2.8f). PCS at this lock spends less (~7¢) because equal-depth × discrete effort has no mid tier near $0.033/call. That is a constraint of the design, not a claim PCS should stay cheap forever.

**Config:** `evals/configs/parallel_channel_search.yaml`

---

## Template for new entries

```md
## YYYY-MM-DD: <short title>

**Decision:** …

**Why:** …

**Evidence:** … (paths, metrics, n)

**Alternatives rejected:** …

**Open follow-ups:** …
```

---

## 2026-08-08: Decision log is agent-maintained

**Decision:** `docs/decision-log.md` is the project’s incremental decision record. Cursor agents must append and self-heal it for the rest of the project via `.cursor/rules/decision-log.mdc` (`alwaysApply: true`).

**Why:** Write-up and continuity should not depend on chat memory. Decisions need a dated, evidence-linked trail that survives new sessions.

**Evidence:** Rule file `.cursor/rules/decision-log.mdc`; this log.

---

## 2026-08-08: PCS dry-run request builder (prompt compose + explicit knobs)

**Decision:** PCS dry-run composes frozen channel prompts into three equal-depth Agent API request kwargs (explicit model/steps/effort/search tools, no dynamic `preset`). Live fan-out stays unwired until the next PR.

**Why:** Unblocks eval wiring and request inspection without paid calls. Reuses the UAS request shape so the bake-off compares channel fan-out vs one adaptive call, not different API packaging.

**Evidence:** `parallel_channel_search/{prompting,agent_call,runner}.py`; dry-run `traces.request_snapshots`.

**Alternatives rejected:** Importing UAS `agent_call` internals (keeps PCS package identity); shipping live fan-out in the same slice.

**Open follow-ups:** live parallel fan-out + metered ledger; merge/dedupe; one-company paid smoke.

---

## 2026-08-08: PCS live parallel fan-out + per-channel metering

**Decision:** Live PCS fans out one equal-depth Agent API call per enabled channel (ThreadPoolExecutor), tags findings with `channel`, and meters each `CostComponent` from usage. Transport failures skip that component without dropping sibling channel costs.

**Why:** Equal-depth coverage insurance needs real parallel spend, not a single adaptive thread. Per-channel ledger rows make the ~3× cost projection falsifiable in a one-company smoke.

**Evidence:** `parallel_channel_search/{agent_call,runner}.py`; dry-run path unchanged.

**Alternatives rejected:** Sequential channel calls (slower, same dollars); importing UAS `execute_agent_call` (PCS keeps package identity and channel tagging).

**Open follow-ups:** cross-channel merge/dedupe upgrade; CLI `--live` smoke; paid one-company confirm.

---

## 2026-08-08: PCS merge dedupe by normalized (tool, url)

**Decision:** Merge keeps the first finding per normalized `(AI_tool_used, source_url)` across channels. URL normalize lowercases scheme/host, strips fragments and trailing slashes. Channel provenance on the kept row is preserved; `finding_id` is renumbered after merge.

**Why:** Sibling rooms may report the same evidence. Deduping only within a channel would double-count in the bake-off score. First-wins with jobs → owned → third_party order matches the runner's stable channel order.

**Evidence:** `parallel_channel_search/merge.py`.

**Alternatives rejected:** Keying on channel too (old stub); hard domain allowlists at merge time.

**Open follow-ups:** CLI `--live` smoke; paid one-company confirm of 3× metered cost.

---

## 2026-08-08: PCS CLI live smoke entrypoint

**Decision:** `python -m parallel_channel_search` defaults to dry-run and accepts `--live` plus explicit knobs (same shape as UAS CLI). Eval harness already forwards `dry_run=False` into `run()`.

**Why:** One-company paid smoke should be a deliberate CLI flag, not an accidental panel spend. Keeps bake-off readiness checkable without opening the full eval suite.

**Evidence:** `parallel_channel_search/__main__.py`; `evals/configs/parallel_channel_search.yaml` notes.

**Open follow-ups:** user-approved one-company paid smoke to confirm 3× metered cost ≈ projection.

---

## 2026-08-08: PCS one-company live smoke confirmed

**Decision:** PCS live package is bake-off-ready for Stage 2 implementation. One-company paid smoke on Jam (`rcid=610194`) metered three equal-depth channels and landed inside the projected band.

**Evidence (Jam live smoke):**
- Duration ≈ 41s (parallel fan-out)
- Ledger: jobs `$0.03174` + owned `$0.01743` + third_party `$0.02092` = **`$0.07009`** (projection ≈ `$0.06–0.07`)
- Findings: 19 merged, channel-tagged (jobs 8 / owned 4 / third_party 7); `error=None`
- Dry-run still returns zero-cost ledger with `dry_run_no_api`

**Why this closes PCS impl:** Live path, metering, merge, and CLI smoke entrypoint all exercised on a real company under frozen knobs.

**Open follow-ups (not PCS package work):** optional Stage B search=high re-test; UAS bake-off yaml lock; SGS impl; 3-arch panel bake-off. No paid 50-co PCS tuning planned.

---

## 2026-08-08: SGS design frozen (signal-count effort ladder)

**Status:** Ladder / dig knobs still current. Scout *role* wording superseded by [[2026-08-11: SGS scouts are channel presence screens]].

**Decision:** Freeze Signal Gated Search bake-off design as **3 scouts → dig every signaled channel**, with dig `reasoning_effort` chosen by dig count:

| # signaled | Digs | Dig effort | Planning path $ (digs + ~$0.02 scouts) |
|---:|---|---|---:|
| 0 | 0 | — | ~0.02 |
| 1 | 1 | **max** | ~0.12 |
| 2 | 2 | **high** | ~0.11 |
| 3 | 3 | **medium** | ~0.09 |

**Locked dig knobs (each dig):** Luna / `max_steps=10` / `web_search_depth=low` / effort from table.  
**Locked scouts:** Agent `preset=fast` × 3; signal JSON only.  
**Locked gate:** dig-all signaled; `signal_threshold=0.5`; rescue **off**; `max_digs_per_company=3`.  
**Card:** `.cursor/plans/sgs-design.md`. **Config:** `evals/configs/signal_gated_search.yaml`.

**Why:** PCS cannot afford 3× high (~$0.13). SGS spends high/max only when few channels signal, concentrating Tuning #14’s effort→findings lift (medium 1.66f → high 2.30f → max 2.80f) on the rooms that matter. User accepts dig paths **above** the ~$0.10 target and will ask the professor for headroom on that basis. Ranked Top-1 Dig (§3.2) is superseded as the default (kept as ablation only).

**Evidence:** Tuning #14 `evals/instances/tuning/014_2026-08-07_1045/summary.json`; user freeze approval 2026-08-08.

**Alternatives rejected:** Ranked Top-1 + optional rescue as default; forcing dig effort down to guarantee ≤$0.10/path; dig-all at equal medium only (collapses toward PCS + scout tax without the high/max upside).

**Open follow-ups:** replace stub gate with ladder; scout/dig prompts; live runner + ledger; paid path smokes; professor budget ask.

---

## 2026-08-11: SGS scouts are channel presence screens

**Decision:** SGS scouts detect whether a **diggable channel source exists** (jobs board / substantial owned web / third-party coverage). They do **not** hunt internal GenAI adoption. Digs remain the adoption extractors. Escalate on most real presence cases; provisional `signal_threshold=0.5` (evidence bins: none/weak/moderate/strong → 0.0/0.35/0.65/0.90).

**Owned-surface detail:** amended by [[2026-08-13: SGS owned includes official accounts; homepage is not a gate]].

**Why:** Many startups lack a job board, have only a stealth landing page, or have no press footprint. Digging empty rooms wastes the effort ladder. Separation of concerns: scout = corpus/presence screen; dig = adoption research. Adoption-smoke scouts were too strict and mixed two jobs.

**Evidence:** User design lock 2026-08-11; card `.cursor/plans/sgs-design.md`; contracts `prompts/signal_gated_search/scout_contracts.md`.

**Alternatives rejected:** Scout-as-adoption-smoke (prior draft); requiring Fortune-500-sized presence before escalate; keeping Ranked Top-1 as default.

**Open follow-ups:** write live `scout_*.txt` from contracts; dig prompt contracts; presence-labeled τ sweep; gate ladder impl.

---

## 2026-08-13: SGS digs are cold start

**Decision:** SGS dig Agent calls start from **company identity only** (same as a PCS channel). Do **not** pass scout URLs, snippets, or bins into dig `instructions` or `input`. Scout outputs stay in traces for debugging.

**Why:** Scouts prove room presence, not adoption leads. Feeding `fast` URLs into a high/max dig risks anchoring search on the wrong pages. Digs have full tool loops; SGS’s bake-off identity is gating + effort ladder, not cheap breadcrumbs.

**Evidence:** User lock 2026-08-13; `.cursor/plans/sgs-design.md`; `prompts/signal_gated_search/dig_shared_preamble.txt`.

**Alternatives rejected:** Warm-start hints in dig input (even with “not a cage” wording).

**Open follow-ups:** live fan-out (gate ladder + dry orchestrator landed).

---

## 2026-08-13: PCS and SGS extract prompts share UAS use-vs-sell teaching

**Decision:** Amend PCS `shared_preamble.txt` and SGS `dig_shared_preamble.txt` so both carry the same extract teaching as UAS, minus few-shots: quoted use-vs-sell INCLUDE/EXCLUDE lines, a per-function internal-use catalog (recognize in your room, do not leave the room), and stricter SPECIFICITY (no vague "AI coding tool"). Channel overlay files unchanged. No JSON few-shots.

**Why:** Bake-off fairness. UAS still had concrete use-vs-sell quotes and a function catalog. PCS/SGS had the same rule in abstract form. Few-shots were rejected (famous-tool templates, wrong-room examples, SGS digs already passed a presence screen).

**Evidence:** User lock 2026-08-13; `prompts/stage_2_perplexity_prompt.txt` as the UAS source; `prompts/parallel_channel_search/shared_preamble.txt`; `prompts/signal_gated_search/dig_shared_preamble.txt`.

**Alternatives rejected:** Copying UAS few-shots A–E; copying UAS’s full all-room source tour into shared (would collapse channel identity).

**Open follow-ups:** SGS paid 5-co smoke landed (see [[2026-08-13: SGS paid 5-company smoke]]). Envelope `channel_id` wins over a mislabeled model `channel` (hotfix #23).

---

## 2026-08-13: SGS gate reads envelope channel_id before the model channel field

**Decision:** `decide_gate` maps a scout row to a room in this order: `assigned_channel`, then envelope `channel_id`, then the model's `channel` field. A mislabeled or unknown model value must not reroute or drop a valid envelope.

**Why:** Live scout rows will typically carry both tags. Trusting the model undoes the assigned-room override (same policy as Parallel Channel Search forcing parsed findings onto the envelope room) and can send dig spend to the wrong source or skip a real presence hit.

**Evidence:** Bugbot on PR #21 after merge; hotfix PR #23; `signal_gated_search/gate.py`; `tests/test_sgs_gate.py` (`test_envelope_channel_id_wins_over_model_channel`, `test_unknown_model_channel_does_not_drop_valid_envelope`).

**Alternatives rejected:** Preferring `channel` because dry-run fixtures already set it. That field remains the fallback when no envelope is present.

**Open follow-ups:** live runner tags envelope `channel_id` on scout rows (see live fan-out entry).

---

## 2026-08-13: SGS dry orchestrator (scout snapshots then gated dig snapshots)

**Decision:** Dry-run SGS always composes three presence-scout Agent API snapshots, runs the frozen gate, then composes 0–3 cold dig snapshots. Default dry injects empty (`none`) scout rows so N=0. Tests pass `scout_outputs` to inspect N=1/2/3 effort. Ledger always lists `scout_*`. `dig_{channel}` rows appear only when the gate would spend. Live fan-out stays unwired.

**Why:** You can inspect the expensive dig requests (and confirm they do not carry scout URLs) without paying. Empty default scouts stay honest: dry-run did not observe presence, so it does not pretend a dig would fire.

**Evidence:** `signal_gated_search/runner.py`; `tests/test_sgs_runner.py`; `evals.runner.run_panel("sgs", dry_run=True)` on the fixture panel.

**Alternatives rejected:** Always snapshot three hypothetical digs at medium (would hide the gate). Shipping live ThreadPool in the same slice.

**Open follow-ups:** paid 5-co smoke landed (see [[2026-08-13: SGS paid 5-company smoke]]). Cost-preview prior refresh.

---

## 2026-08-13: SGS live scout/dig fan-out + merge + CLI

**Decision:** Live SGS fans out three presence scouts (ThreadPool), runs the frozen gate, then fans out 0–3 cold digs at the shared effort ladder. Findings merge with the PCS `(tool, url)` dedupe. Transport failure skips that component without dropping siblings. `python -m signal_gated_search` stays dry by default. `--live` is the paid one-company smoke. Scout rows passed to the gate carry envelope `channel_id` / `assigned_channel` so a mislabeled model `channel` cannot reroute spend.

**Why:** Same grain as the PCS live PR: metering has to be real or the bake-off cannot compare gated spend to always-on equal depth. Dry-run is unchanged so inspect-without-paying still works.

**Evidence:** `signal_gated_search/{runner,agent_call,__main__}.py`; `tests/test_sgs_live.py` (mocked API). Digs wrap PCS `execute_agent_call`.

**Alternatives rejected:** Sequential scout/dig calls (same dollars, slower). A second merge implementation. Paid smoke inside this PR.

**Open follow-ups:** paid 5-co smoke landed (see [[2026-08-13: SGS paid 5-company smoke]]). Cost-preview YAML still uses the old Top-1 prior.

---

## 2026-08-13: SGS paid 5-company smoke

**Decision:** Signal Gated Search live path is bake-off-ready for Stage 2 implementation. A 5-company paid smoke on March strata exercised N=0, N=1/`max`, and N=2/`high`. Metering, gate, merge, and `--live` all worked (`error=None` on every company). N=3/`medium` did not appear in this set.

**Evidence:** `outputs/stage2/test_runs/sgs_smoke_5co/` (gitignored JSON). Dry first: 36 pytest, `python -m signal_gated_search` on Jam, `evals.runner.run_panel("sgs", dry_run=True)` fixture panel, dry compose on the 5 live picks. Then live, sequential, `dry_run=False`. Total metered **`$0.28252`**.

| Company | rcid | March n | SGS gate | Effort | Cost | Findings | Notes |
|---|---:|---:|---|---|---:|---:|---|
| Easy Fill AI | 97943259 | 0 | N=0 | (scouts only) | $0.022 | 0 | Matches ~$0.02 scout-tax prior |
| CoverTree | 1314132 | 1 jobs | N=0 | (scouts only) | $0.022 | 0 | Presence FN vs March |
| Statsig | 103497 | 2 owned+tp | N=1 owned | **max** | $0.151 | 11 owned | Dig alone $0.128; above ~$0.12 path prior |
| Tern Travel | 26492430 | 6 owned | N=0 | (scouts only) | $0.019 | 0 | Presence FN: owned scout said no first-party site despite `https://www.tern.travel/` |
| Jam | 610194 | 8 owned+tp | N=2 owned+tp | **high** | $0.068 | 13 | Jobs correctly `none` (name collision). Close to PCS Jam `$0.070` |

Jam is on the tuning-panel holdout; the other four are not. Scout bins were honest `none` (not URL-downgraded). N=0 scouts finished in ~4s; N=1 Statsig ~205s; N=2 Jam ~69s.

**Why this closes SGS impl:** Live fan-out, frozen gate, cold digs, and component ledger ran on real companies. The N=1/`max` overrun is the cost the user already accepted asking the professor for headroom on.

**Alternatives rejected:** Parallelizing the 5 companies (inner ThreadPool already fans out; sequential isolates failures). Forcing a third company until N=3 lights up (would be extra spend, not required to ship the package).

**Open follow-ups:** optional extra smoke if we want the N=3/`medium` row before bake-off. Presence FN on owned/social patched in prompts (see [[2026-08-13: SGS owned includes official accounts; homepage is not a gate]]); re-smoke Tern after that change. Cost-preview YAML still uses the old Top-1 prior. UAS bake-off YAML lock; 3-arch panel.

---

## 2026-08-13: SGS owned includes official accounts; homepage is not a gate

**Decision:** SGS owned presence is **narrator-based**: company site **or** official company accounts (LinkedIn company page, YouTube/Vimeo channel, GitHub org, X, company-operated CMS/newsletter). Homepage is identity, not a gate. Scouts must not emit `none` solely because the site is missing, down, or not returned by search. Official accounts can light owned (and independent coverage can still light third_party) even when the website fails. Employee personal posts stay third_party. Gate, ladder, and `rescue_enabled=false` unchanged. No code path keys digs on `homepage_url`.

SGS owned **digs** may search official socials. Company YouTube/LinkedIn are owned-shaped. Independent interviews stay third_party. This diverges from PCS, which keeps a host-based split (YouTube/LinkedIn posts default third_party).

**Why:** Paid smoke Tern Travel (`rcid=26492430`) gated N=0 after all three `fast` scouts returned `none`. March evidence was a company YouTube webinar. The owned scout was a website checker; a homepage miss zeroed owned even though socials existed. Lowering τ would not have helped (`none`, not `weak`). A homepage floor would have coupled spend to Stage 1 URL and still missed a down-site + rich-socials case.

**Evidence:** User lock 2026-08-13; smoke `outputs/stage2/test_runs/sgs_smoke_5co/26492430.json`; prompts `prompts/signal_gated_search/scout_{shared_preamble,owned,third_party,jobs}.txt` and `dig_{shared_preamble,owned,third_party}.txt`; tests in `tests/test_sgs_prompting.py`.

**Alternatives rejected:** Homepage floor / always-dig-owned-if-URL-exists (user: website may be down; socials should still motivate digs). Lowering `signal_threshold` to include `weak`. All-none rescue (still optional later). Changing the gate to require a homepage.

**Open follow-ups:** re-smoke Tern (and ideally a down-site + socials case) on the new prompts. Optional all-none name-based social rescue if `fast` scouts still miss official accounts.

---

## 2026-08-14: Stage 3 delivery = one PR, five commits + Bugbot gates

**Decision:** Ship `citation_verification/` as **one GitHub PR** with **five slice commits** (not five stacked PRs). After each commit: **local `/review-bugbot` until no findings**. After all five: open the PR and **cloud-Bugbot babysit** until merge-ready.

**Why:** Same decomposition as the old PR1–PR5 plan without stacked-rebase mess. Local Bugbot catches issues early; cloud Bugbot is the merge gate.

**Evidence:** User lock 2026-08-14; Phase 2 plan delivery section. Local Bugbot is IDE `/review-bugbot` (CLI not available yet).

**Open follow-ups:** Implement commits 1–5; human runs local Bugbot between slices; cloud agent babysits final PR.

---

## 2026-08-14: Stage 3 D2/D5 locked (trailing cost fields + simple CLI)

**Decision:**
- **D2:** Persist observability fields **after** core outputs: `fetch_ok`, `evidence_snippet`, `censored`, `margin`, `model_judge`, `cost_usd` (+ breakdown if useful), `error`.
- **D5:** Simple CLI: `--findings` JSONL with `--dry-run`/`--live`, plus optional `--url`/`--claim` debug. Library `verify_finding` / `verify_findings` only (no `ArchitectureResult` helper in v1).

**Why:** Cost/ops at the end keeps the human-facing verification fields first while preserving interpretability. Minimal CLI covers batch prod + one-off debug without extra surface area.

**Evidence:** User lock 2026-08-14; Phase 2 plan.

**Open follow-ups:** PR1 skeleton (design freeze complete for package v1).

---

## 2026-08-14: Stage 3 verification=0/1 and claim=evidence_description

**Decision:**
- Model field `verification` is **`Literal[0, 1]`**: **1 = verified**, **0 = hallucination**.
- Claim text for the judge is Stage 2 **`evidence_description` only**.

**Why:** Binary digits are best for logprob span extraction (same as taxonomy Pass A). Evidence-only keeps the judge prompt simple.

**Evidence:** User lock 2026-08-14; Phase 2 plan D1/D3.

**Open follow-ups:** D2 ops fields; D5 CLI proposal; fetch wrapper model; then PR1.

---

## 2026-08-14: Stage 3 D1/D4 locks (Terra judge + output field names)

**Decision:**
- **D1 product fields:** `verification`, `log_probs_conf`, `confidence_1_5`, `verification_reasoning`, `verification_critique`.
- **`log_probs_conf` is package-computed** from the decision token’s logprobs (taxonomy Pass A pattern). Model must **not** be asked to emit `log_probs_conf`.
- Model JSON emits: `verification`, `confidence_1_5`, `verification_reasoning`, `verification_critique`.
- **D4 judge model:** `gpt-5.6-terra` with `reasoning.effort=none` (logprobs requirement). Different model from Stage 2 Luna researchers on purpose.

**Why:** User field names for the verification agent; terra as a distinct judge tier vs research agents; keep logprob confidence honest by deriving it from logits.

**Evidence:** User answers 2026-08-14; OpenAI model id `gpt-5.6-terra`; taxonomy `two_pass_classifier/confidence.py`.

**Status:** `verification` type and D3 claim superseded in specificity by [[2026-08-14: Stage 3 verification=0/1 and claim=evidence_description]].

**Still open:** D2 ops fields; D5 CLI (proposal: findings JSONL + optional `--url/--claim`); fetch wrapper model/preset.

**Open follow-ups:** Lock remaining Ds; then PR1.

---

## 2026-08-13: Stage 3 stack = Perplexity fetch_url + OpenAI logprob judge

**Decision:** Stage 3 stack is **hybrid**: (1) Perplexity Agent API **`fetch_url`** to load text for each finding’s `source_url`, (2) OpenAI judge with **`reasoning.effort=none`**, strict JSON binary int (taxonomy Pass A shape) + **`include=message.output_text.logprobs`** / `top_logprobs`, confidence **computed in-package** (not model-emitted), plus optional verbalized **1–5** backup. Empty/failed fetch → **`UNVERIFIABLE`**, not unsupported. No HTML→markdown preprocessing by default. Package build plan: `.cursor/plans/phase-2-stage3-verification.plan.md`.

**Why:** Perplexity cannot return usable logprobs. OpenAI can, but only with reasoning off. Fetching with Perplexity’s own `fetch_url` keeps Stage 3’s page view in the same tool family as Stage 2 and avoids Tavily scrape mismatch false hallucinations. Stage 3 already has the citation URL, so `web_search` is the wrong tool.

**Evidence:** User direction 2026-08-13; prior logprobs spike [[2026-08-13: Perplexity APIs do not expose usable logprobs]]; fetch_url docs/pricing (`$0.00025`/invocation); OpenAI GPT-5.x logprobs require `reasoning.effort=none`. **Reference:** taxonomy production Pass A in `k-hanafi/ai-startups-taxonomy-research` (`two_pass_classifier/{confidence,request_builder,schema}.py`, `evals/logprob_extract.py` thin adapter).

**Alternatives rejected:** Perplexity-only judge; Tavily-only fetch; Perplexity `web_search` for verification; forbidding `json_schema` on the logprob call (taxonomy Pass A proves schema+logprobs work at `reasoning.effort=none`); putting the extractor only inside `evals/`.

**Open follow-ups:** User lock D1–D5 in Phase 2 plan (model schema, package output schema, claim bundle, models, CLI); then PR1–PR5 for `citation_verification/` only. Evals verification wiring is a **separate** follow-up plan after the package ships.

---

## 2026-08-13: Stage 3 is a production top-level package

**Decision:** Stage 3 lives as its own top-level package, **`citation_verification/`**, peer to the Stage 2 architectures and to `evals/`. It is **production software**: after bake-off picks a Stage 2 winner, prod runs that arch, then runs Stage 3 on the prod findings. Evals only **import and exercise** the same package (logprobs validity, hallucination rate on the eval company set) before prod spend. Stage 3 must **not** live inside `evals/`.

**Why:** Packaging follows ownership. Stage 3 is a post-research production guardrail, not an eval-only report. Burying it under `evals/hooks/` would make prod depend on harness internals and signal the wrong product boundary. Keeping one package means eval validation and prod verification cannot drift.

**Evidence:** User lock 2026-08-13. Prior scaffolding stub `evals/hooks/stage3_judge.py` and tree sketch in `.cursor/plans/eval-harness.plan.md` are **superseded for packaging home** (thin eval adapter may still call the package). Phase 2 plan: `.cursor/plans/phase-2-stage3-verification.plan.md`.

**Alternatives rejected:**
- Implementing Stage 3 only inside `evals/hooks/` (eval-specific)
- A fourth competing Stage 2 architecture identity (Stage 3 is arch-agnostic verification, not a research strategy)
- Separate eval-only and prod-only judges (drift risk)

**Open follow-ups:** Implement `citation_verification/` (fetch + OpenAI logprob judge); wire `python -m evals run-verification` as a consumer; retire or thin-wrap `evals/hooks/stage3_judge.py`.

---

## 2026-08-13: Perplexity APIs do not expose usable logprobs

**Decision:** Reject Perplexity-alone as the Stage 3 logprob confidence path. Binary hallucination/supported scoring that needs token logprobs must use a provider that returns them (planned: OpenAI with `reasoning.effort=none`). Perplexity may still be used for page fetch / evidence text if a hybrid wins the rest of the spike.

**Why:** Stage 3’s primary confidence proxy is logprob on a binary classification token. Without real logprobs, a Perplexity-only judge cannot meet the plan contract (binary + logprob + 1–5 backup).

**Evidence (official docs, 2026-08-13):**
- Gateway Chat Completions (`docs.perplexity.ai` Create Chat Completion / `/router/v1/chat/completions`): **Honored** list does not include logprobs. **`logprobs` accepted only at default `false`**. **`top_logprobs` rejected with HTTP 400**.
- Agent API quickstart / response examples: output text shows `"logprobs": []` and response-level `"top_logprobs": 0` (empty stubs for OpenAI-shaped schema; not populated token probabilities).
- Third-party integrations (e.g. LangChain `ChatPerplexity` capability table) mark Logprobs as unsupported, consistent with the above.

**Alternatives rejected:** Assuming Perplexity’s OpenAI-compatible schema means logprobs work; using empty `logprobs: []` as a confidence signal.

**Open follow-ups:** Lock Stage 3 stack after remaining spike (Tavily vs Perplexity/`fetch_url` for page text + OpenAI binary judge); watch OpenAI gotcha that structured `json_schema` can empty logprobs even with `reasoning.effort=none` (prefer plain binary token output for the logprob field).

---

## Open follow-ups (PCS)

- [x] Freeze prompts + Agent API knobs (design)
- [x] Confirm UAS package is live-ready (no rebuild needed; Tuning #14 proved live path)
- [x] Compose frozen prompts into per-channel Agent API request kwargs (dry-run snapshots)
- [x] Wire live PCS runner: parallel fan-out of 3 channel calls + per-channel cost ledger from usage
- [x] Merge/dedupe: normalize URL + (tool, url) across channels; keep provenance
- [x] CLI `--live` entrypoint for one-company smoke
- [x] Tiny paid smoke to confirm 3× metered cost ≈ projection (Jam `$0.070`)
- [ ] Optional Stage B: steps=50 × search=high if we want to re-test deeper search with the steps budget
- [ ] Lock UAS **bake-off** knobs in `evals/configs/unified_adaptive_search.yaml` (package works; yaml still baseline-ish, not Tuning #14 winner)
- [x] SGS **design** freeze (signal-count effort ladder; see [[2026-08-08: SGS design frozen (signal-count effort ladder)]])
- [x] SGS scout semantics = **presence screen** (see [[2026-08-11: SGS scouts are channel presence screens]])
- [x] SGS digs = **cold start** (see [[2026-08-13: SGS digs are cold start]])
- [x] SGS gate ladder + prompt compose (PR `sgs/02-gate-compose`)
- [x] SGS gate prefers envelope `channel_id` over the model `channel` field (see [[2026-08-13: SGS gate reads envelope channel_id before the model channel field]])
- [x] SGS dry orchestrator (scout snapshots → gate → 0–3 dig snapshots)
- [x] SGS live fan-out + merge + `--live` CLI
- [x] SGS paid path smokes (5-co March strata; see [[2026-08-13: SGS paid 5-company smoke]])
- [x] SGS owned = site **or** official accounts; homepage is not a gate (see [[2026-08-13: SGS owned includes official accounts; homepage is not a gate]])
- [ ] Re-smoke Tern Travel on the new owned/social prompts
- [ ] Optional extra SGS smoke if we want the N=3/`medium` row before bake-off
- [ ] 3-arch bake-off in eval suite (needs frozen UAS knobs; PCS + SGS live ready)
- [x] Stage 3 spike: Perplexity logprobs? (**No** usable logprobs; see [[2026-08-13: Perplexity APIs do not expose usable logprobs]])
- [x] Stage 3 packaging: top-level production `citation_verification/` (see [[2026-08-13: Stage 3 is a production top-level package]])
- [x] Stage 3 stack: Perplexity `fetch_url` + OpenAI logprob judge (see [[2026-08-13: Stage 3 stack = Perplexity fetch_url + OpenAI logprob judge]])
- [x] Stage 3 D1 field names + D4 Terra judge (see [[2026-08-14: Stage 3 D1/D4 locks (Terra judge + output field names)]])
- [x] Stage 3 `verification` 0/1 + claim=`evidence_description` (see [[2026-08-14: Stage 3 verification=0/1 and claim=evidence_description]])
- [x] Stage 3 D2 trailing cost/ops fields + D5 simple CLI (see [[2026-08-14: Stage 3 D2/D5 locked (trailing cost fields + simple CLI)]])
- [x] Stage 3 delivery: one PR / five commits + local then cloud Bugbot (see [[2026-08-14: Stage 3 delivery = one PR, five commits + Bugbot gates]])
- [x] `citation_verification/` commits 1–5 on branch `cursor/citation-verification-8475` (package only; evals out of scope)
- [x] Cloud Bugbot babysit on Stage 3 package PR #28 (tip commit clean: no issues)
- [ ] Later (separate plan): evals `run-verification` consumer + eval-set quality gates
