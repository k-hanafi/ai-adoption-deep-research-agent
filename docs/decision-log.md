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
- Hill-climb panel (20-co, not bake-off): `evals/panel/hillclimb_panel.json`
- PCS hill-climb v1 live: `outputs/stage2/test_runs/pcs_hillclimb_20/`
- Agent rule: `.cursor/rules/decision-log.mdc`

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

**Status:** Effort table superseded by [[2026-08-13: Bake-off effort lock (UAS xhigh, PCS 3× medium, SGS digs high)]]. Dig-all signaled, scout knobs, and rescue-off still current. Scout *role* wording superseded by [[2026-08-11: SGS scouts are channel presence screens]].

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

**Presence bar:** amended by [[2026-08-13: SGS scouts are existence checks, not source-quality filters]]. Owned-surface detail: amended by [[2026-08-13: SGS owned includes official accounts; homepage is not a gate]].

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

**Open follow-ups:** re-smoke Tern+CoverTree on new prompts landed (see [[2026-08-13: Tern and CoverTree re-smoke still N=0]]). Prompt wording was not enough. Optional all-none name-based social rescue or stronger scouts (`fetch_url` / more steps) if `fast` still misses official accounts.

---

## 2026-08-13: Tern and CoverTree re-smoke still N=0

**Decision:** The owned/social prompt patch did **not** close the smoke false-negative. CoverTree and Tern Travel still gated to zero digs under `preset=fast`, `max_steps=2`, web_search only. Do not treat the prompt change as a recall fix until a later scout-tool or rescue change is smoked.

**Evidence:** `outputs/stage2/test_runs/sgs_smoke_covertree_tern_v2/` vs first smoke `outputs/stage2/test_runs/sgs_smoke_5co/` and March `outputs/stage2/production_results.jsonl`.

| Company | March n | March source | v1 digs / findings | v2 digs / findings | v2 cost | v2 duration |
|---|---:|---|---|---|---:|---:|
| CoverTree (`1314132`) | 1 | job-board repost (`jobright.ai`) | 0 / 0 | 0 / 0 | $0.022 | 4.9s |
| Tern Travel (`26492430`) | 6 | company YouTube webinar | 0 / 0 | 0 / 0 | $0.022 | 4.2s |

v2 owned rationales now mention official accounts and still emit `none` with zero URLs. CoverTree's March hit is a **jobs** aggregator listing, so the owned/social prompt was the wrong lever for that row. Tern is the owned/YouTube case the patch targeted, and `fast` search still did not return the channel.

**Why record this:** Prompt-only recall upgrades can look done in git and still miss the live failure mode. Next lever is scout capability (more steps, `fetch_url`, or a name-based rescue), not another wording pass.

**Alternatives rejected:** Calling this a successful prompt fix. Lowering τ (bins were still `none`).

**Open follow-ups:** scout-tool or all-none rescue experiment (user-approved spend). Cost-preview YAML. UAS bake-off YAML. 3-arch panel.

---

## 2026-08-13: SGS scouts are existence checks, not source-quality filters

**Decision:** SGS scouts answer only "does this room exist on the public web for this company?" They do not judge ATS quality, require current open roles, or look for GenAI adoption. Jobs is present if any jobs-related pages exist (ATS, careers, aggregators including JobRight, LinkedIn jobs, email-us hiring pages, stale listings). Owned is present if a website exists (including a thin/waitlist page) or official accounts exist. Third-party is present if any independent pages exist. `weak` is for name-collision doubt only, not for thin/email-only pages. Digs still own adoption extract. Empty dig findings are allowed.

**Why:** CoverTree's jobs scout used a quality bar (live board with roles). Email-only hiring and aggregators were treated as not worth a dig. That is stricter than the bake-off identity: skip a room only when it does not exist, so we do not pay Luna for a channel with nothing to search. Scouts are too cheap/weak to hunt AI signals.

**Evidence:** User lock 2026-08-13; CoverTree March hit was a JobRight aggregator listing (`jobright.ai`, now 404) plus a live `jobs@covertree.com` page. Prompts `prompts/signal_gated_search/scout_{shared_preamble,jobs,owned,third_party}.txt`; contracts `prompts/signal_gated_search/scout_contracts.md`.

**Alternatives rejected:** Keeping email-only / empty careers as `weak` (does not clear τ=0.5). Treating aggregator brands with "AI" in the name as adoption-related noise. Homepage code floor.

**Open follow-ups:** re-smoke CoverTree jobs room landed (see [[2026-08-13: CoverTree existence-bar smoke]]). Jobs scout still `none`. `fast` search may still miss pages even with a looser bar.

---

## 2026-08-13: CoverTree existence-bar smoke

**Decision:** Loosening scouts to existence checks **did** get CoverTree a dig and **matched March's finding count (1)**. It did **not** light the jobs room. The owned scout found `https://covertree.com` (`moderate`). The owned `max` dig recovered the same Senior Applied AI Engineer role March had, via LinkedIn jobs, using the safety valve (jobs-shaped URL reported from the owned room). Jobs and third_party scouts stayed `none` with zero URLs.

**Evidence:** `outputs/stage2/test_runs/sgs_smoke_covertree_existence/1314132.json` vs March `jobright.ai` listing (now 404) and prior smokes that were N=0.

| | March | v1/v2 smokes | Existence-bar smoke |
|---|---|---|---|
| Digs | (single UAS-style call) | 0 | 1 owned at `max` |
| Findings | 1 (JobRight aggregator) | 0 | 1 (LinkedIn jobs URL, owned channel tag) |
| Cost | March deep-research | ~$0.022 | **$0.165** |
| Duration | | ~5s | 141s |

**Why this matters:** The website-existence bar unblocked owned. The jobs-existence bar did not unblock jobs. `fast` still failed to retrieve LinkedIn jobs / `jobs@` in the jobs scout, and the finding leaked in through an owned dig. N=1 `max` is the expensive path (~$0.14 of the $0.165).

**Alternatives rejected:** Treating this as a jobs-scout success. It is an owned-scout + safety-valve success.

**Open follow-ups:** jobs scout still misses live hiring pages that a sibling dig can find. Scout-tool / more steps / rescue remain open if we want jobs to light on its own.

---

## 2026-08-13: Bake-off effort lock (UAS xhigh, PCS 3× medium, SGS digs high)

**Decision:** Freeze Stage 2 bake-off reasoning effort as:

| Architecture | Effort | Notes |
|---|---|---|
| UAS | **xhigh** | One Luna call. Package default + `evals/configs/unified_adaptive_search.yaml`. |
| PCS | **medium** × 3 | Already locked. Equal-depth, `max_steps=50`, search medium. |
| SGS digs | **high** | Every signaled channel. Not `max`. Count still decides *how many* rooms, not how hard. |

SGS `DIG_EFFORT_BY_COUNT` is 1/2/3 → high. Gate rationale `dig_all_signaled_high`. UAS `DEFAULT_REASONING_EFFORT` is `xhigh`.

**Why:** One-room SGS at `max` cost **$0.165** on CoverTree (dig alone $0.141). That is too high for the ~$0.10 Stage 2 target. High keeps SGS cheaper than max while still above PCS medium. UAS stays one deeper call (xhigh). PCS stays three mediums.

**Evidence:** User lock 2026-08-13; CoverTree existence-bar smoke `outputs/stage2/test_runs/sgs_smoke_covertree_existence/1314132.json`; `signal_gated_search/channels.py`; `evals/configs/{unified_adaptive_search,parallel_channel_search,signal_gated_search}.yaml`.

**Alternatives rejected:** Keeping SGS 1=max (cost). Flattening SGS to medium (collapses toward PCS plus scout tax). Changing PCS off 3× medium.

**Open follow-ups:** cost-preview YAML still uses old SGS Top-1 prior. 3-arch panel. Optional CoverTree re-smoke at high to re-measure $ vs the $0.165 max run.

---

## 2026-08-13: Hill-climb panel v1 (20 companies, not bake-off)

**Decision:** Write a 20-company **hill-climb** panel (`hillclimb_pcs_v1_march_20`) for PCS prompt/architecture iteration, then SGS/UAS on the same IDs. 5 high / 5 medium / 5 low / 5 none by March findings count. Soft refs only. Disjoint from `tuning_panel_v2` (those 50 IDs stay held out forever, including Jam). This is **not** the bake-off panel. Bake-off starts only after the user is happy on these 20. Swap IDs in `MEMBERSHIP` and regenerate if a company is a bad fit; do not silently reuse tuning-50.

Membership is chosen for failure-mode coverage, not random richness:

| Stratum | Stress |
|---|---|
| high | Company YouTube (Tern), ATS+YouTube (Chainguard), dense owned + noisy TP (ClickHouse), owned+YC jobs (Alguna), Ashby+blog (Vendelux) |
| medium | Owned+vendor CS (Statsig), podcast+blog (Unwrap), product-AI help center + Lever (Secureframe), aggregator jobs pair (SQOR), owned podcast transcripts (Blue Sky Robotics) |
| low | JobRight aggregator that 404s (CoverTree), clean Ashby (LiveKit), vendor CS (K1x), YT interview (Momentic), LinkedIn embedded on site (Sudozi) |
| none | AI sellers (Easy Fill, Sully.ai), SaaS with no GenAI found (RightRev), non-AI industrial (Oso Electric), non-AI insurance (Ahoy) |

**Why:** The last SGS smokes showed FNs that a 5-co convenience sample cannot keep exposing. PCS always-on is the coverage ceiling, so hill-climb it first on a stratified set that includes those FNs plus jobs/owned/third_party mix and use-vs-sell zeros. Tuning-50 stays untouched so later bake-off IDs are still unused.

**Evidence:** `evals/panel/hillclimb_panel.json`; builder `evals/panel/build_hillclimb_panel_v1.py`; path `evals/paths.py` `HILLCLIMB_PANEL_PATH`; tests `tests/test_hillclimb_panel.py`. Known regressions in-panel: Tern `26492430`, CoverTree `1314132`, Easy Fill `97943259`, Statsig `103497`.

**Alternatives rejected:** Reusing tuning-50 (holdout contamination). Jumping to 3-arch bake-off before the 20 are green. A none-only or jobs-only slice (would miss YouTube / vendor / use-vs-sell). Putting Jam on this panel (Jam is in the tuning holdout).

**Open follow-ups:** first paid PCS pass landed (see [[2026-08-14: PCS hill-climb v1 live 20-co]]). Iterate prompts until the user is happy. Then SGS/UAS on the same 20. Then bake-off on a **new** disjoint panel.

---

## 2026-08-14: PCS hill-climb v1 live 20-co

**Decision:** Record the first paid PCS pass on `hillclimb_pcs_v1_march_20`. Not bake-off. Not a prompt freeze. Membership unchanged.

**Why:** Need a coverage-ceiling baseline before editing PCS prompts. Sequential resume-safe run after the first process aborted at 10/20.

**Evidence:** `outputs/stage2/test_runs/pcs_hillclimb_20/` (`run_twenty.py`, `summary.jsonl`, per-rcid JSON). 20/20 companies wrote a live result. Total **$1.19131**, mean **$0.05957**/co (under the ~$0.10 target). Max $0.08858 (Secureframe). Two timeout rows: Sudozi owned+third_party (jobs still returned 1 finding, $0.015); RightRev all three channels (cost $0, so this none is not a real empty).

Soft March comparison (count only, not quality):

| Pattern | Companies |
|---|---|
| PCS ≥ March on positives | 14/15 (Tern 6=6; CoverTree 2>1 jobs; highs all ≥ March) |
| PCS miss vs March | SQOR (March 2 aggregator jobs, PCS 0) |
| PCS extra on March-none | Ahoy (privacy-policy ChatGPT + employee LinkedIn Assistants API); Sully.ai (ATS + Cursor/Claude LinkedIn) |
| PCS 0 on March-none | Easy Fill, Oso Electric; RightRev invalid (timeout) |

Tern (the SGS N=0 case) is 6 findings / 3 channels / $0.05054. CoverTree jobs room lit under always-on PCS.

**Alternatives rejected:** Treating RightRev as a confirmed none. Treating Ahoy/Sully extras as automatically correct (likely use-vs-sell / privacy-policy / employee-profile noise). Re-running the 18 clean rows.

**Open follow-ups:** timeout retries landed (see [[2026-08-14: PCS hill-climb timeout retries (Sudozi, RightRev)]]). Inspect Ahoy/Sully/Secureframe product-chatbot rows for prompt tightening. SQOR aggregator FN. User reviews this baseline before prompt edits. Then SGS/UAS on the same 20.

---

## 2026-08-14: PCS hill-climb timeout retries (Sudozi, RightRev)

**Decision:** Re-run only the two timeout companies from the v1 live pass. Same PCS knobs (3× medium). Per-channel timeout 600s for the retry only. Keep first-pass timeout JSONs as `*.timeout.json`. Rebuild `summary.jsonl` from the current 20 live files.

**Why:** RightRev’s empty was invalid (all three channels timed out at $0). Sudozi’s owned + third_party never ran, so the LinkedIn-on-site case was incomplete.

**Evidence:** `outputs/stage2/test_runs/pcs_hillclimb_20/{743085,42877}.json` plus `{743085,42877}.timeout.json`. Both retries `error=None` in ~30s.

| Company | First pass | Retry |
|---|---|---|
| Sudozi `743085` | 1 finding (jobs), owned+tp timeout, $0.015 | 1 finding (jobs, Vaia board), owned 0 / tp 0, **$0.06267** |
| RightRev `42877` | 0 findings, 3× timeout, $0 | 0 findings, 3 channels ran, **$0.06836**, `has_presence_no_evidence` |

Current-panel total (latest 20 rows): **$1.30686**, mean **$0.06534**. All-in metered including the two timeout attempts: **~$1.32**. No remaining API errors. RightRev is now a real none. Sudozi still misses March’s owned LinkedIn-on-site row (jobs-only).

**Alternatives rejected:** Re-running the 18 clean companies. Treating the first Sudozi jobs row as a complete company result.

**Open follow-ups:** prompt lock landed (see [[2026-08-14: Hill-climb prompt lock (jobs boards, unnamed tools, adopt vs product-AI)]]). Re-smoke SQOR, Sudozi, and the ops/help-center cases after the prompt change.

---

## 2026-08-14: Hill-climb prompt lock (jobs boards, unnamed tools, adopt vs product-AI)

**Decision:** After the 20-co PCS baseline, lock these prompt rules on **UAS, PCS, and SGS digs** (SGS scouts stay presence-only, but jobs/owned scout search lists match):

1. Jobs must search off-site boards (LinkedIn Jobs, YC Work at a Startup, Techstars, Wellfound, Built In, Indeed, JobRight), not only the company careers page.
2. A cited "we use AI in content creation" (or similar) is a finding even with no brand name. Label `unspecified AI …`. Never invent a vendor.
3. Adopt vs sell: AI that automates staff work (help-center / live-chat bot replacing a rep) is adopt. AI that processes customer requests or documents (including on a privacy/policy page) is operations adopt. AI for legal/compliance internally is adopt. Sell is only marketing that the **product** has AI features, with no internal-process claim.
4. Owned must search official accounts and company-hosted social walls (`/linkedin-posts`, `/news` embeds), not only the website blog.
5. One URL may emit many findings when the tool and/or use case differs. Do not cap count. Merge dedupe is `(tool, use_case, url)`, not `(tool, url)`.

V2 goal is **more** verified findings, not March-like counts.

**Why:** SQOR was a jobs-board + unnamed-tool miss. Sudozi owned missed a company LinkedIn wall. The earlier precision advice to drop Ahoy privacy-policy AI and Secureframe help-center bots was wrong for this project: those are operations / staff-replacement, not product marketing.

**Evidence:** User lock 2026-08-14. Prompts: `prompts/parallel_channel_search/`, `prompts/signal_gated_search/dig_*.txt` + `scout_{jobs,owned}.txt`, `prompts/stage_2_perplexity_prompt.txt`. Merge: `parallel_channel_search/merge.py`. Tests: `tests/test_pcs_prompting.py`, `tests/test_sgs_prompting.py`.

**Alternatives rejected:** Dropping privacy-policy or help-center-bot rows as sell. Biasing prompts or merge toward March finding counts. Jobs search limited to company-owned boards.

**Open follow-ups:** paid re-smoke of SQOR and Sudozi (then a wider hill-climb pass). Do not treat Ahoy/Secureframe extras as bugs to delete.

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
- [x] Lock UAS **bake-off** knobs: `reasoning_effort=xhigh` in package default + `evals/configs/unified_adaptive_search.yaml` (see [[2026-08-13: Bake-off effort lock (UAS xhigh, PCS 3× medium, SGS digs high)]])
- [x] SGS **design** freeze (dig-all signaled. Effort table superseded: SGS digs high, not 1=max)
- [x] SGS digs = **high** on every signaled channel (see [[2026-08-13: Bake-off effort lock (UAS xhigh, PCS 3× medium, SGS digs high)]])
- [x] SGS scout semantics = **presence screen** (see [[2026-08-11: SGS scouts are channel presence screens]])
- [x] SGS digs = **cold start** (see [[2026-08-13: SGS digs are cold start]])
- [x] SGS gate ladder + prompt compose (PR `sgs/02-gate-compose`)
- [x] SGS gate prefers envelope `channel_id` over the model `channel` field (see [[2026-08-13: SGS gate reads envelope channel_id before the model channel field]])
- [x] SGS dry orchestrator (scout snapshots → gate → 0–3 dig snapshots)
- [x] SGS live fan-out + merge + `--live` CLI
- [x] SGS paid path smokes (5-co March strata; see [[2026-08-13: SGS paid 5-company smoke]])
- [x] SGS owned = site **or** official accounts; homepage is not a gate (see [[2026-08-13: SGS owned includes official accounts; homepage is not a gate]])
- [x] Re-smoke Tern Travel on the new owned/social prompts (still N=0. See [[2026-08-13: Tern and CoverTree re-smoke still N=0]])
- [x] SGS scouts = existence checks, not source-quality or adoption (see [[2026-08-13: SGS scouts are existence checks, not source-quality filters]])
- [x] Re-smoke CoverTree jobs room on the existence-bar prompts (owned lit, jobs still `none`. See [[2026-08-13: CoverTree existence-bar smoke]])
- [ ] Scout-tool or all-none rescue if `fast` presence screens still return empty rooms that exist
- [ ] Optional extra SGS smoke if we want the N=3/`medium` row before bake-off
- [x] Hill-climb PCS first paid pass on `evals/panel/hillclimb_panel.json` (20-co, $1.19 total; see [[2026-08-14: PCS hill-climb v1 live 20-co]])
- [x] Retry PCS timeouts on Sudozi + RightRev (see [[2026-08-14: PCS hill-climb timeout retries (Sudozi, RightRev)]])
- [x] Hill-climb prompt lock: external job boards, unnamed-tool findings, owned social walls, adopt vs product-AI (see [[2026-08-14: Hill-climb prompt lock (jobs boards, unnamed tools, adopt vs product-AI)]])
- [ ] Re-smoke affected hill-climb companies after the prompt lock (SQOR, Sudozi, then a wider pass)
- [ ] Hill-climb PCS until user is happy (maximize findings, not March-like counts)
- [ ] Then SGS / UAS on the same 20 before bake-off
- [ ] 3-arch bake-off in eval suite (only after the 20-co hill-climb is green; new disjoint panel, never tuning-50 or this hill-climb set)
