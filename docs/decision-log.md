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
- PCS confirm panel (20-co, not bake-off): `evals/panel/pcs_confirm_panel.json`
- PCS confirm 3× high live: `outputs/stage2/test_runs/pcs_confirm_20_high/`
- PCS confirm 3× medium live: `outputs/stage2/test_runs/pcs_confirm_20_medium/`
- PCS hill-climb v1 live (old prompts, 3× medium): `outputs/stage2/test_runs/pcs_hillclimb_20/`
- PCS hill-climb 3× medium v2 (current prompts): `outputs/stage2/test_runs/pcs_hillclimb_20_medium_v2/`
- PCS hill-climb 3× high probe (current prompts): `outputs/stage2/test_runs/pcs_hillclimb_20_high/`
- UAS hill-climb 20-co xhigh (package defaults): `outputs/stage2/test_runs/uas_hillclimb_20_xhigh/`
- SGS hill-climb 20-co high digs (package default): `outputs/stage2/test_runs/sgs_hillclimb_20_high/`
- SGS hill-climb 20-co matched leash (low scouts + 50/medium/high digs; vs PCS high): `outputs/stage2/test_runs/sgs_hillclimb_20_matched/`
- SGS skip panel (50-co March none/low, not bake-off): `evals/panel/sgs_skip_panel.json`
- SGS skip-rate 50-co live (package defaults): `outputs/stage2/test_runs/sgs_skip_50/`
- Paid per-company traces under `outputs/stage2/test_runs/` are local-only (gitignored). Runners and `summary.jsonl` stay in git.
- SGS hill-climb 20-co medium digs (measurement probe): `outputs/stage2/test_runs/sgs_hillclimb_20_medium/`
- SGS 5-co low-scout A/B smoke (measurement; later locked as default): `outputs/stage2/test_runs/sgs_smoke_5co_low_scouts/`
- Agent rule: `.cursor/rules/decision-log.mdc`
- Stage 3 verification plan: `.cursor/plans/phase-2-stage3-verification.plan.md`
- Stage 3 bulletproof plan: `.cursor/plans/bulletproof-citation-verifier.plan.md`
- Stage 3 package: `citation_verification/` (production; not under `evals/`)
- Stage 3 judge prompt: `prompts/citation_verification/judge.txt`
- Stage 3 CLI outputs: `python -m citation_verification --output-jsonl` / `--output-csv`
- Stage 3 gold e2e: `outputs/stage3/smokes/20260815_2100_gold_e2e/`
- Stage 3 Phase A smoke: `outputs/stage3/smokes/20260815_201259/`
- Stage 3 e2e5 smoke: `outputs/stage3/smokes/20260815_203606_e2e5/`
- Stage 3 bulletproof e2e5: `outputs/stage3/smokes/20260815_2218_e2e5_bp/`
- Stage 3 e2e5 after lenient judge: `outputs/stage3/smokes/20260815_2245_e2e5_bp_lenient/`
- March 2026 snapshot (runnable, not imported by live code): `legacy_agent_march_2026/`
- Frozen March dump for panel rebuilds (local, not in git): `evals/references/march_2026_production.jsonl`
- Production batch runner: `production/` (`python -m production {run,dry-run,status,dedupe,verify}`)
- Production writes (local, gitignored): `outputs/prod/{sgs,pcs,uas}/`
- Production verify branch: `prod-verifier` (worktree `deep-research-AI-agent-verifier`)
- Verify adaptive limiters: `citation_verification/limits.py`
- Production derived squash: `production/dedupe.py` (`findings_deduplicated.csv`)
- Production page cache: `production/pages.py` (`outputs/prod/{arch}/pages.jsonl`)

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

**Status:** Effort table superseded by [[2026-08-13: Bake-off effort lock (UAS xhigh, PCS 3× medium, SGS digs high)]]. Scout preset superseded by [[2026-08-14: SGS scouts locked to low]]. Dig leash (`max_steps` / `web_search_depth`) superseded by [[2026-08-14: SGS dig leash matches PCS]]. Dig-all signaled and rescue-off still current. Scout *role* wording superseded by [[2026-08-11: SGS scouts are channel presence screens]].

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

**Open follow-ups:** paid re-smoke of SQOR and Sudozi (then a wider hill-climb pass). Do not treat Ahoy/Secureframe extras as bugs to delete. 3× high cost probe landed (see [[2026-08-14: PCS 20-co 3× high cost probe]]).

---

## 2026-08-14: PCS 20-co 3× high cost probe

**Decision:** Record a same-panel PCS pass at **3× high** (not a bake-off lock). Package default stays 3× medium. 20 companies concurrent. New prompts from [[2026-08-14: Hill-climb prompt lock (jobs boards, unnamed tools, adopt vs product-AI)]].

**Why:** User asked what 3× high costs before any effort change.

**Evidence:** `outputs/stage2/test_runs/pcs_hillclimb_20_high/` (~147s wall clock). Total **$3.30167**, mean **$0.165**/co (2.53× the medium panel total $1.307, mean $0.065). Max $0.332 (Easy Fill, still 0 findings). 201 finding rows vs 70 on medium (confounded: high + new prompts). SQOR 0→8. One 429 on Sudozi owned. Mean is above the ~$0.10 / $0.105 Stage 2 target.

**Alternatives rejected:** Changing the PCS bake-off default to high. Re-running medium on the new prompts in this same job.

**Open follow-ups:** decide whether $0.165 mean is acceptable. Optional Sudozi owned retry after the 429. Same-prompt medium counterpart landed (see [[2026-08-14: PCS 20-co 3× medium v2 (current prompts)]]).

---

## 2026-08-14: PCS 20-co 3× medium v2 (current prompts)

**Decision:** Record a same-panel PCS pass at **3× medium** with the current prompt lock, so effort can be compared to [[2026-08-14: PCS 20-co 3× high cost probe]] with prompts held constant. Package default stays 3× medium. First wave was 20 concurrent (7 companies lost one channel to 429); those 7 were retried sequentially and all came back `error=None`.

**Why:** The earlier medium folder (`pcs_hillclimb_20/`) used pre-lock prompts, so 70 vs 201 findings mixed prompt change with effort. User asked for the clean A/B.

**Evidence:** `outputs/stage2/test_runs/pcs_hillclimb_20_medium_v2/` (`run_twenty_medium.py`, `summary.jsonl`, `*.429.json` backups). After retries: **$1.45879** panel total, mean **$0.07294**/co, **125** findings, 0 API errors. First-wave spend was $1.29757 plus $0.49168 retry = **$1.78925** paid. Same-prompt high is $3.30167 / 201 findings (2.26× cost, +76 findings / +61%). Prompt-only lift vs old medium: 70→125 (+55). Channel rows jobs/owned/tp: old 23/26/21, new-medium 44/37/44, high 79/63/59. Easy Fill and Oso still 0 at both efforts. Statsig 5 on new-medium vs 28 on high (largest effort gap). SQOR 0→6 from the prompt lock alone.

**Alternatives rejected:** Overwriting `pcs_hillclimb_20/`. Changing the PCS default to high.

**Open follow-ups:** decide medium vs high given +61% findings at 2.26× cost. Do not treat Easy Fill / Oso zeros as prompt bugs until a later pass. Optional high-run Sudozi owned retry still open.

---

## 2026-08-14: UAS 20-co xhigh hill-climb

**Decision:** Record a same-panel UAS pass at **package defaults** (one Luna call, `reasoning_effort=xhigh`, `max_steps=10`, `web_search_depth=low`). Measurement only. Not a bake-off lock. Not an architecture winner freeze. Package defaults unchanged.

**Why:** Need the one-call baseline on the same 20 IDs as the current-prompt PCS medium and high passes, so architecture (one adaptive call vs three always-on rooms) can be compared separately from effort.

**Evidence:** `outputs/stage2/test_runs/uas_hillclimb_20_xhigh/` (`run_twenty.py`, `summary.jsonl`, 20 per-rcid JSON). Terminal `PANEL_DONE` `ran=20 skipped=0 failed=0`. Wall clock ~179s. 20/20 `error=None`. No 429s, no timeouts. **117** findings, panel **$1.78222**, mean **$0.08911**/co (under the ~$0.10 / $0.105 Stage 2 target). Two zeros: Oso Electric and RightRev (`has_presence_no_evidence`).

Same-panel current-prompt PCS (from [[2026-08-14: PCS 20-co 3× medium v2 (current prompts)]] and [[2026-08-14: PCS 20-co 3× high cost probe]]):

| Run | Findings | Mean $ | Panel $ | Errors |
|---|---:|---:|---:|---|
| UAS xhigh (1 call) | 117 | $0.089 | $1.782 | 0 |
| PCS 3× medium | 125 | $0.073 | $1.459 | 0 after 429 retries |
| PCS 3× high | 201 | $0.165 | $3.302 | 1 (Sudozi owned 429) |

Per-company findings vs PCS: UAS beats medium on 6, ties 5, loses 9. UAS beats high on 2, ties 3, loses 15.

Load-bearing rows:

| Company | UAS | PCS med | PCS high | Note |
|---|---:|---:|---:|---|
| Tern Travel | 10 | 18 | 24 | One call under-visits vs three rooms (PCS medium already 3 jobs / 7 owned / 8 third_party) |
| Statsig | 12 | 5 | 28 | UAS beats medium cheaply ($0.044); high still far ahead |
| SQOR | 6 | 6 | 8 | Prompt lock recovered aggregator jobs for UAS too |
| Easy Fill AI | 2 | 0 | 0 | Only UAS found rows (founder LinkedIn Runway/Kling; contact-page chat assistant). Not a quality lock |
| Oso Electric | 0 | 0 | 0 | Consistent none across all three runs |
| RightRev | 0 | 3 | 4 | UAS spent the most ($0.146) and still returned empty |

**Alternatives rejected:** Treating this as a bake-off winner or a reason to change UAS defaults. Starting SGS on the same 20 in this pass. Re-running UAS at a different effort.

**Open follow-ups:** SGS on the same 20 landed (see [[2026-08-14: SGS 20-co medium vs high digs]]). PCS effort (3× medium vs 3× high) still open. Do not treat Easy Fill UAS extras or the RightRev UAS miss as prompt locks.

---

## 2026-08-14: SGS 20-co medium vs high digs

**Status:** Scout default superseded by [[2026-08-14: SGS scouts locked to low]]. Dig default (high) unchanged. The 20-co numbers in this entry were run with `fast` scouts.

**Decision:** Record two same-panel SGS passes on `hillclimb_pcs_v1_march_20`: digs at package-default **high**, and a measurement-only **medium** probe. Scouts stay stock `fast` presence screens. Package default stays high on every signaled room. Not a bake-off lock. Not an architecture winner freeze.

**Why:** Need SGS on the same 20 IDs as current-prompt UAS xhigh / PCS medium / PCS high before any bake-off. Medium is a cost and coverage probe only, so we can see whether cheaper digs keep most of the gated-fan-out lift.

**Evidence:** `outputs/stage2/test_runs/sgs_hillclimb_20_high/` and `outputs/stage2/test_runs/sgs_hillclimb_20_medium/` (`run_twenty_*.py`, `summary.jsonl`, 20 per-rcid JSON each). Concurrency 4. Timeout 600s. No 429s, no sequential retries, 20/20 `error=None` on both passes. Medium effort was an in-memory `DIG_EFFORT_BY_COUNT` patch in the probe script only; `signal_gated_search/channels.py` still reads `high`.

| Run | Findings | Mean $ | Min $ | Max $ | Panel $ | Paid |
|---|---:|---:|---:|---:|---:|---:|
| UAS xhigh | 117 | $0.089 | $0.044 | $0.146 | $1.782 | prior |
| SGS medium digs | 137 | $0.093 | $0.037 | $0.123 | $1.853 | **$1.853** |
| SGS high digs | 187 | $0.173 | $0.114 | $0.250 | $3.456 | **$3.456** |
| PCS 3× medium | 125 | $0.073 | $0.057 | $0.088 | $1.459 | prior |
| PCS 3× high | 201 | $0.165 | $0.068 | $0.332 | $3.302 | prior |
| March (same 20) | 39 | $0.414 | $0.075 | $1.198 | $8.283 | production dump |

March min/max from `evals/panel/hillclimb_panel.json` `march_reference.cost_usd` (matches `outputs/stage2/production_results.jsonl` for these 20 rcids). Min Blue Sky Robotics $0.075; max Alguna $1.198.

SGS high: 19/20 companies dug 3 rooms (Easy Fill 2). SGS medium: 19/20 dug 3 rooms (Easy Fill 1, $0.037 min). Oso 0 findings at both SGS efforts. Two-pass paid total **$5.309**.

**Alternatives rejected:** Changing the SGS bake-off default to medium. Treating this as a winner freeze. Starting bake-off on this panel. Overwriting PCS/UAS/old smoke folders. Using tuning-50 IDs.

**Open follow-ups:** bake-off still later, on a **new** disjoint panel (never tuning-50 or this hill-climb set). PCS effort (3× medium vs 3× high) still open. Do not treat Ahoy/Secureframe extras as bugs. Scout preset A/B on the original 5-co set landed (see [[2026-08-14: SGS 5-co low-scout smoke]]); default stays `fast`.

---

## 2026-08-14: SGS 5-co low-scout smoke

**Status:** "Default stays `fast`" superseded by [[2026-08-14: SGS scouts locked to low]]. This entry remains the measurement A/B, not the lock.

**Decision:** Measurement only. Same 5 rcids as [[2026-08-13: SGS paid 5-company smoke]], `scout_preset=low` in-memory, digs stay package-default **high**. Package default and YAML stay `scout_preset: fast`. Not a bake-off lock. Not mixed into the 20-co medium/high dig A/B.

**Why:** Need a scout-cost A/B against the original fast-scout 5-co smoke before considering a stronger always-on filter.

**Evidence:** `outputs/stage2/test_runs/sgs_smoke_5co_low_scouts/` (`run_smoke.py`, `summary.jsonl`, 5 per-rcid JSON). Sequential. `error=None` on all 5. Tern hung across several aborted resumes, then completed in 118s on a clean retry. Override is `run(..., scout_preset="low")` only; `signal_gated_search/channels.py` and `evals/configs/signal_gated_search.yaml` still read `fast`.

| Company | Low scout $ | Low dig $ | Low total | Findings | Rooms lit | Fast 5-co rooms (old prompts) |
|---|---:|---:|---:|---:|---|---|
| Easy Fill AI | $0.017 | $0.114 | $0.131 | 0 | owned+tp | none |
| CoverTree | $0.014 | $0.106 | $0.120 | 7 | all 3 | none |
| Statsig | $0.019 | $0.159 | $0.177 | 24 | all 3 | owned |
| Tern Travel | $0.021 | $0.098 | $0.119 | 32 | all 3 | none |
| Jam | $0.013 | $0.120 | $0.133 | 33 | all 3 | owned+tp |
| **5-co** | **$0.082** | **$0.597** | **$0.679** | **96** | | |

3× low scouts: **$0.082** panel, mean **$0.016**/co. 3× fast on the same 5 (old smoke): **$0.110**, mean **$0.022**/co. Low is cheaper as a filter. Total spend is 2.4× the old 5-co ($0.679 vs $0.283) because more rooms lit and then paid high digs, not because scouts got expensive.

Room caveat: the Aug 13 fast 5-co used older prompts (CoverTree/Tern all-`none`). Same-day current-prompt **fast** on the 20-co high pass already lights the same rooms on the 4 overlapping companies (Easy Fill owned+tp; CoverTree/Statsig/Tern all 3). Jam is not on that 20; low newly lit jobs vs the old fast `none` (name-collision case). Findings vs that current-prompt fast overlap are mixed (Statsig 24 vs 14; CoverTree 7 vs 9; Tern 32 vs 37; Easy Fill 0 vs 1).

**Alternatives rejected:** Changing the default to `low`. Mixing this into the 20-co dig A/B. Starting bake-off.

**Open follow-ups:** keep `fast` unless a later same-prompt Jam (or empty-room) miss needs a stronger scout. Rescue/tooling still open if `fast` misses rooms that exist.

**Completion (2026-08-14 later):** 5/5 live JSON, all `error=None`. Resumed mid-run: Easy Fill / CoverTree / Statsig were already complete; Tern and Jam were the only new paid companies (2 company runs). Leftover hung `run_smoke.py` copies (all stuck on Tern, 0% CPU, 30 min to 2 h) were stopped so they would not race-write or start Jam in parallel. A later resume with a 1320s per-company hard cap finished Tern in 118s and Jam in 83s. Exact ledger: 3× low scout **$0.08231** (mean **$0.01646**/co) vs 3× fast **$0.10966** (mean **$0.02193**/co). Digs **$0.59716** vs fast **$0.17286**. Panel total **$0.67947** vs **$0.28252**. Package default still `fast`.

---

## 2026-08-14: SGS vs PCS high gap diagnosis

**Status:** still current on scout-miss / leash / merge. Jobs 64 vs 79 scoreboard refined by [[2026-08-14: SGS vs PCS high jobs-hole refinement]].

**Decision:** Record, do not freeze. On the same 20 current-prompt hill-climb companies, SGS high lost to PCS high on findings (187 vs 201) and cost more (mean $0.173 vs $0.165) because the gate almost never skipped a room, and each SGS dig is a shallower room than a PCS channel. Not an architecture winner. Package defaults stay as they are.

**Why:** Need a cited cause before anyone "fixes" SGS by changing scout prompts or declaring the gate dead. The cheap scout cannot close a depth gap if 19/20 companies still pay for 2–3 high digs.

**Evidence:** Existing artifacts only (`outputs/stage2/test_runs/sgs_hillclimb_20_high/`, `sgs_hillclimb_20_medium/`, `pcs_hillclimb_20_high/`, `pcs_hillclimb_20_medium_v2/`). No new paid calls.

| Claim | Result |
|---|---|
| Scout false negatives (PCS found a room SGS never dug) | **Killed.** 0 companies, 0 PCS rows in undug rooms. Only Easy Fill skipped a room (high: jobs=`none`; medium: jobs+third_party=`none`). PCS also found 0 there. |
| Scout tax + almost-full digs | **Confirmed for cost.** High: 19× dig_count=3, 1× dig_count=2. Medium: 19×3, 1×1 (Easy Fill). |
| Weaker per-room knobs | **Load-bearing for the findings gap.** SGS dig = Luna steps=10 / search=`low` / effort=high (`evals/configs/signal_gated_search.yaml`, ledger `gpt-5_6-luna_steps10_high_search_low`). PCS channel = Luna steps=50 / search=`medium` / effort=high (`evals/configs/parallel_channel_search.yaml` + high override, ledger `gpt-5_6-luna_steps50_high_search_medium`). Jobs/owned/third_party prompts are the same contract. |
| Merge / row-splitting | **Killed as primary.** Same merge (`parallel_channel_search/merge.py`, (tool, use_case, url)). Mean rows/URL 1.79 vs 1.87. On 42 shared URLs: 94 SGS rows vs 96 PCS rows. Gap is pages opened (PCS-only URLs 68 vs SGS-only 59), not fewer splits of the same page. |
| Cost split (mean / company) | SGS high: scout $0.022 + dig $0.151 = $0.173 (3.00 scouts, 2.95 digs; $0.007/scout, $0.051/dig). PCS high: $0.165 across 2.95 channels ($0.056/channel). SGS medium extra vs PCS medium is almost entirely the $0.021 scout tax (digs $0.071 ≈ PCS 3× $0.073). |

Per-channel findings on rooms SGS actually dug (high): jobs 64 vs 79, owned 58 vs 63, third_party 65 vs 60. Company wins 9–9–2; net −14 is Statsig (−14) and Alguna (−11) minus Tern (+13) and Sully (+8). Sudozi PCS owned 429, so SGS +2 there is partly a PCS miss.

**Alternatives rejected:** Treating scout FNs as the cause. Treating merge/splitting as the cause. Changing SGS or PCS package defaults. Declaring SGS dead (medium SGS beat medium PCS 137 vs 125). Starting a paid match-knob run in this pass.

**Open follow-ups:** Optional later probe, not started: SGS digs with PCS-matched knobs (steps=50, search=medium) on a cheap subset (Statsig / Alguna / Vendelux / ClickHouse / Tern) to isolate the leash. Do not change `DEFAULT_DIG_MAX_STEPS` or `DEFAULT_DIG_WEB_SEARCH_DEPTH` until that lands. PCS effort (3× medium vs 3× high) still open. Jobs-tag scoreboard refined in [[2026-08-14: SGS vs PCS high jobs-hole refinement]].

---

## 2026-08-14: SGS scouts locked to low

**Decision:** Lock SGS `scout_preset` to **low** as the package and YAML default. Digs stay **high** on every signaled room. Scout role stays presence / existence screen. Not a bake-off winner freeze. UAS xhigh and PCS 3× medium stay as they are.

**Why:** User freeze 2026-08-14: low is cheap enough; intuition is it says "yes" more truthfully because it accesses more web; do not over-index on the 5-co debate. Parent measurement note (mixed; does not fight the lock): 5-co low smoke mean scout $0.016 vs fast $0.022. The "low lights more rooms" comparison was vs Aug 13 old-prompt fast. Same-day current-prompt fast on the 20 already lit most rooms. Easy Fill low opened owned+tp, paid $0.114 digs, 0 findings (over-trigger risk). Measurement evidence is mixed; this is an explicit user freeze.

**Evidence:** User lock 2026-08-14. `signal_gated_search/channels.py` `DEFAULT_SCOUT_PRESET`. `evals/configs/signal_gated_search.yaml`. 5-co low smoke `outputs/stage2/test_runs/sgs_smoke_5co_low_scouts/`. 20-co SGS high/medium (`outputs/stage2/test_runs/sgs_hillclimb_20_high/`, `sgs_hillclimb_20_medium/`) were still run with fast scouts.

**Alternatives rejected:** Keep `fast` as default. Treat the 5-co A/B as a bake-off winner. Change dig effort. Over-index on the 5-co room-lighting debate vs old-prompt fast.

**Open follow-ups:** 20-co SGS numbers remain valid as `fast` scout measurements. Rescue/tooling still open if `low` misses rooms that exist. PCS effort still open. Bake-off still later on a new disjoint panel.

---

## 2026-08-14: SGS vs PCS high jobs-hole refinement

**Decision:** Record, do not freeze. Do **not** iterate SGS jobs prompts, merge, or scout role on the 187 vs 201 gap. The next lever is a **4-company SGS dig-knob match** (steps=50, search=medium, effort still high), in-memory, new folder. Package defaults stay 10 / low until that lands. Not started this turn. No paid calls this turn.

**Why:** Channel-tagged jobs 64 vs 79 looks like a jobs hole. After dropping rows whose URL is not a job page, the counts are **61 vs 62**. Eighteen PCS "jobs" rows are room leaks (company blogs, LinkedIn profiles, vendor CS). Eight of those 18 are the Statsig Statbot blog. SGS jobs already opens Greenhouse / Ashby / YC / LinkedIn / Wellfound on this panel. The real misses are specific high-yield pages a 10-step / search-low dig did not fetch.

**Evidence:** Existing artifacts only (`outputs/stage2/test_runs/pcs_hillclimb_20_high/`, `sgs_hillclimb_20_high/`, plus medium/UAS for "who else found it"). URL-normalized: PCS-only 69 URLs (106 rows), SGS-only 59 (93), shared 42 (95 vs 94 rows).

| Class | Verdict | Load-bearing examples |
|---|---|---|
| Missed URL / shallow leash | **Primary.** | Statsig `statbot-ai-manual-tasks-hackathon` (PCS high 20 rows; SGS medium 7; SGS high 0). Alguna YC `nhVNFAe-product-engineer` (PCS 7; neither SGS). Vendelux Ashby `6faa20f1` (PCS 3; UAS 2; both SGS 0). ClickHouse: 5 PCS-only jobs-shaped URLs. |
| Empty dig after yes | **Mostly not a findings bug.** | Alguna owned dig $0.054 / 0 findings. PCS owned 4 rows were YC + Dover **job** URLs leaking into owned. Sully owned=0; PCS owned was a LinkedIn post + job-board mirror. |
| Room leak (PCS) | Inflates jobs tags. | Statsig Statbot blog tagged `jobs`. ClickHouse `/blog/agentic-coding` tagged `jobs`. |
| Split / collapse | Secondary. | Alguna YC FDE 5 vs 1. Tern YouTube 13 vs 6. Shared-URL row totals nearly tie. |
| Scout miss | Still killed. | 19/20 dug all 3. Easy Fill skipped jobs; PCS also 0. |
| Merge / prompt miss | Still killed as primary. | Same `(tool, use_case, url)` merge. No fetched-page refusal evidenced. |

SGS medium finding Statbot while SGS high missed it is the same prompts under a short leash (variance), not a missing jobs-overlay sentence.

**Alternatives rejected:** Jobs-prompt rewrite as the first lever (would "fix" a leak-inflated 79 vs 64). Treating Alguna owned empty-dig as a page to recover (PCS owned was jobs leak). Merge key change. Scout-role change. Starting the paid 4-co probe without user go-ahead. Starting bake-off.

**Open follow-ups:** Proposed 4-co SGS match-knob smoke, waiting for user go-ahead (Statsig `103497`, Alguna `95038033`, ClickHouse `545293`, Vendelux `977674`). Success: Statbot hackathon URL; YC `nhVNFAe-product-engineer`; ≥2 of 5 ClickHouse PCS-only jobs URLs; Ashby `6faa20f1` or ≥3 distinct Vendelux Ashby IDs. New folder. Do not overwrite the 20-co runs. Do not change `DEFAULT_DIG_MAX_STEPS` / `DEFAULT_DIG_WEB_SEARCH_DEPTH` until that lands. PCS effort still open. Bake-off still later on a new disjoint panel. **Parked 2026-08-14:** user asked to finish PCS failure-mode iteration before any SGS work (see [[2026-08-14: PCS owned early-exit iteration]]).

---

## 2026-08-14: PCS owned early-exit iteration

**Status:** SEARCH FOCUS path-construction wording superseded by [[2026-08-14: PCS owned advice must generalize]]. Safety-valve "do not finish owned" rule still current.

**Decision:** Iterate PCS **owned** only. A jobs-shaped or third_party-shaped safety-valve row does not finish the owned search. Owned must construct and fetch `/linkedin-posts`, `/blog`, `/news`, help center, and policy paths from the homepage before leaving the domain. SGS owned overlay and UAS prompt unchanged this pass. Package knobs stay 3× medium. Not a bake-off lock. Not smoked yet.

**Why:** User asked to hill-climb from PCS result data only, then SGS later. Inside the current-prompt pair (medium 125 vs high 201), the remaining thin companies are owned misses, not jobs-board misses.

**Evidence:** `outputs/stage2/test_runs/pcs_hillclimb_20_medium_v2/` and `pcs_hillclimb_20_high/`. March URLs from `outputs/stage2/production_results.jsonl` (soft).

| Class | Verdict |
|---|---|
| Owned early-exit after safety valve | **Primary.** Sudozi medium owned returned `talents.vaia.com/...` (job mirror) and never opened `sudozi.com/linkedin-posts` (March Claude). Prompt already named `/linkedin-posts`. |
| Owned blog miss at both efforts | **Primary.** Unwrap owned=0 at medium and high. High owned spent $0.086. March `unwrap.ai/blog-post/three-ways-chatgpt-can-help-you-write-better-code` absent. |
| Effort under-open | Open lock. High-only 71 URLs / 103 rows. Statsig 5 vs 28. Not this prompt pass. |
| Sudozi high owned 429 | Measurement incomplete. Retry after this change or later. |
| Easy Fill / Oso zeros | Still not a prompt bug. High Easy Fill $0.332, `has_presence_no_evidence`. |
| Room leaks / Ahoy / Secureframe | Intentional. Do not delete. |

**Alternatives rejected:** Jobs-prompt rewrite (SQOR already recovered 0→6 on the prompt lock). Changing PCS default to high in this pass. Starting the SGS match-knob probe. Another synonym-only `/linkedin-posts` mention without the "do not finish after safety valve" rule. Editing SGS `dig_owned.txt` in the same slice.

**Open follow-ups:** Paid 2-co PCS medium re-smoke, waiting for user go-ahead: Sudozi `743085` (pass: `sudozi.com/linkedin-posts`) and Unwrap `169806` (pass: the March ChatGPT blog URL, or any `unwrap.ai/blog` owned row). New folder. Do not overwrite the 20-co PCS runs. Then decide medium vs high. Then SGS. Prompt wording refined in [[2026-08-14: PCS owned advice must generalize]].

---

## 2026-08-14: PCS owned advice must generalize

**Decision:** Hill-climb misses are **eval measurements**, not prompt recipes. PCS owned SEARCH FOCUS must state source-shape and budget rules that could apply to any of the ~9.45k production companies. Do not tell the model to construct `/linkedin-posts` or a fixed path list from the homepage. Keep the general safety-valve rule: an off-room hit does not finish the owned room. Keep first-party indexes (blog/newsroom, help/policy, company-hosted social or embed walls the site actually has) as shapes, not as a Sudozi URL template. SGS overlay still unchanged. Knobs unchanged.

**Why:** The 20-co panel exists to expose failure *classes*. Writing the recovery URL into the prompt overfits the hill-climb set and will not help companies whose wall is `/news`, a CMS embed, or a LinkedIn company feed with no `/linkedin-posts` path. That repeats the locked writing rule: March (and this panel) inform source shapes, not few-shots.

**Evidence:** User correction 2026-08-14. Prior SEARCH FOCUS in [[2026-08-14: PCS owned early-exit iteration]] said "Construct and fetch these paths when they exist: /linkedin-posts, /blog, /news…". Sudozi March URL is `sudozi.com/linkedin-posts?...`. That path is a panel instance, not a production contract. Files: `prompts/parallel_channel_search/channel_owned.txt`; tests `tests/test_pcs_prompting.py`.

**Alternatives rejected:** Keeping the construct-and-fetch path list. Adding Unwrap's blog slug or Sudozi's query string to the prompt. Copying the same path list into SGS/UAS.

**Open follow-ups:** Same 2-co medium smoke, still waiting. Those two URLs remain the *pass check* for whether the general rule worked, not text to add to the prompt. PCS high confirm on a new 20 started (see [[2026-08-14: PCS confirm panel v1]]).

---

## 2026-08-14: PCS confirm panel v1

**Decision:** Draw a new 20-company **PCS confirmation** panel (`pcs_confirm_v1_march_20`) and run PCS at **3× high** on it. Seeded stratified sample, not hand-picked failure modes. Disjoint from `tuning_panel_v2` (including Jam) and `hillclimb_pcs_v1_march_20`. **Not a bake-off panel.** Bake-off still needs a later disjoint set (never tuning-50, never hill-climb 20, never this confirm 20).

**Why:** User asked for one more PCS test on a fresh stratified 20 at high, after the hill-climb set. A seeded sample with a March-channel mix (jobs-only / owned-only / third_party-only / mixed / fill) tests whether current prompts generalize. It does not re-select Sudozi/Unwrap-shaped companies.

**Evidence:** Builder `evals/panel/build_pcs_confirm_panel_v1.py` seed `20260814`. Panel `evals/panel/pcs_confirm_panel.json`. Path `evals/paths.py` `PCS_CONFIRM_PANEL_PATH`. Tests `tests/test_pcs_confirm_panel.py`. Run folder `outputs/stage2/test_runs/pcs_confirm_20_high/` (5 workers, 600s timeout, resume-safe). Current owned prompt includes the general early-exit rule. Package default stays 3× medium.

Membership (March count / March channels):

| Stratum | Companies |
|---|---|
| high | Zivy Inc 6 owned; Spaxel 3 tp; Alpine Physician Partners 3 owned+tp; Total Life 3 jobs; Beanstalk Consulting 3 owned |
| medium | Charlie Health 2 jobs; Alysio 2 tp; Scorability 2 jobs; CloudCruise 2 owned; Hamming AI 2 jobs+tp |
| low | ROR Partners 1 tp; Conduktor 1 jobs; HealthLeap 1 jobs; NinetyEight 1 owned; Nourish 1 owned |
| none | Truentity Health; AESIRX.IO LTD; North Shore Therapeutics; Entrust Investment Services; Claimbrite |

**Alternatives rejected:** Reusing the hill-climb 20. Sampling from the tuning holdout. Treating this 20 as the bake-off panel. Hand-picking another Sudozi/Unwrap analog set.

**Open follow-ups:** Live 3× high landed (see [[2026-08-14: PCS confirm 20-co 3× high]]). Then SGS. Bake-off panel still later and disjoint.

---

## 2026-08-14: PCS confirm 20-co 3× high

**Decision:** Record the paid PCS 3× high pass on `pcs_confirm_v1_march_20`. Measurement only. Package default stays 3× medium. Not a bake-off. Not a reason to rewrite prompts around NinetyEight.

**Why:** Need a generalization check of current PCS prompts + high effort on IDs that were not used to hill-climb.

**Evidence:** `outputs/stage2/test_runs/pcs_confirm_20_high/` (`run_twenty_high.py`, `summary.jsonl`, 20 per-rcid JSON). 5 workers. Timeout 600s. Wall ~376s. 20/20 `error=None`. No 429s. **195** findings, panel **$3.418**, mean **$0.171**/co (min $0.103 Beanstalk, max $0.327 Charlie Health). Channel rows jobs/owned/tp: 58/66/71.

Same-knob hill-climb high (`pcs_hillclimb_20_high/`): 201 findings, mean $0.165.

Soft March: 14/15 positives at or above March count. One miss: NinetyEight `5229877` (March 1 owned blog `ninetyeightla.com/food-for-thought/marketing-gen-z-chatgpt`; PCS all three channels ran, 0 findings, $0.147, `has_presence_no_evidence`). March-none extras: Truentity 8, Claimbrite 2, AESIRX.IO 1. Two none stayed 0 (Entrust, North Shore).

**Alternatives rejected:** Adding the NinetyEight blog URL to the owned prompt. Treating Truentity extras as a lock. Promoting this panel to bake-off.

**Open follow-ups:** Same-prompt medium counterpart landed (see [[2026-08-14: PCS confirm 20-co 3× medium]]). SGS next when the user says so. PCS effort still open. Bake-off still later on a new disjoint panel.

---

## 2026-08-14: PCS confirm 20-co 3× medium

**Decision:** Record the same-panel PCS pass at **3× medium** on `pcs_confirm_v1_march_20`, so effort can be compared to [[2026-08-14: PCS confirm 20-co 3× high]] with prompts held constant. Package default stays 3× medium. Not bake-off.

**Why:** User asked for the medium counterpart on the new 20, and for the highest concurrency that does not hit HTTP 429 rate limits.

**Evidence:** `outputs/stage2/test_runs/pcs_confirm_20_medium/`. First wave used 8 company workers (24 in-flight channel calls). **15/20 hit 429.** Those were backed up as `*.429.json` and retried sequentially. CloudCruise sequential retry then timed out all three channels at $0 (`95651351.timeout.json`); a second sequential retry came back `error=None`, 5 findings, $0.059. Final 20/20 `error=None`.

Clean panel (latest 20 JSON): **122** findings, **$1.418**, mean **$0.071**/co (min $0.052 Beanstalk, max $0.089 Conduktor). Channel rows jobs/owned/tp: 27/48/47. High counterpart: 195 / $3.418 / mean $0.171. High lift: **+73 findings (+60%) at 2.41× cost**. High wins 16, ties 4, medium wins 0. 429-attempt spend $1.145. All-in paid **$2.563**.

Same shape as the hill-climb same-prompt pair (125 vs 201, $0.073 vs $0.165).

**Concurrency lesson:** 8 company workers is too high on medium (calls finish faster, so the API sees more new requests). 5 company workers (15 in-flight) was clean on this panel at high. Treat **5** as the evidenced safe max until a later probe.

**Alternatives rejected:** Leaving CloudCruise as a $0 timeout empty. Changing the PCS default to high. Treating 8 workers as safe.

**Open follow-ups:** Decide medium vs high given the same +60% / ~2.4× pattern on two disjoint 20s. Last PCS failure-mode pass landed (see [[2026-08-14: PCS hill-climb closed, no further prompt iteration]]). SGS next. Bake-off still later on a new disjoint panel.

---

## 2026-08-14: PCS hill-climb closed, no further prompt iteration

**Decision:** Stop PCS prompt/merge iteration. No new owned or jobs wording. The general owned early-exit rule stays. Package default stays **3× medium** unless the user later accepts high’s ~$0.17 mean. Next work is SGS hill-climb. This confirm 20 is not the bake-off panel.

**Why:** User asked for a last PCS deep dive on the confirm 20 (plus the hill-climb 20 for classes that repeat). Remaining holes are effort, architecture identity, or one-off URLs. Another wording pass would overfit the panel.

**Evidence:** Confirm medium/high `outputs/stage2/test_runs/pcs_confirm_20_{medium,high}/`. Hill-climb current-prompt pair `pcs_hillclimb_20_medium_v2/` and `pcs_hillclimb_20_high/`.

| Class | Generalizable? | Action |
|---|---|---|
| Effort under-open | **Yes.** +60% findings at ~2.4× cost on both 20s (125→201, 122→195). High-only confirm URLs: 35 jobs pages, 18 LinkedIn posts, 14 owned pages. | Open lock, not a prompt. |
| Always-on empty-room tax | **Yes.** Zivy/Spaxel jobs=0 with 17–25 other rows. Hill Blue Sky/Momentic jobs=0. | Leave. That is PCS. SGS skips empty rooms. |
| Residual use-vs-sell on AI sellers | **Yes, residual.** Truentity owned rows are product summaries/reports. Claimbrite engineer portfolios describe building the product. Hamming Cursor/Devin is real adopt. | Do not tighten. Prior tighten almost dropped Ahoy/Secureframe. |
| Safety-valve room leaks | **Yes.** Confirm 16 jobs-tagged non-jobs URLs. Hill 18. | Leave. Intentional. |
| True none after full spend | **Yes.** Entrust, North Shore; hill Easy Fill, Oso. High spends more to confirm empty. | Leave. |
| March exact-URL miss | **No.** Charlie Health / Beanstalk / Conduktor / Nourish missed March URLs and still beat March counts. | Do not chase tokens/slugs. |
| NinetyEight 0 at both efforts | **No.** One March blog. | Do not write that URL into the prompt. |

**Alternatives rejected:** Another owned construct-and-fetch pass. Tightening use-vs-sell. Treating Alysio/Scorability owned=0 as a bug (March was jobs/tp). Promoting the confirm 20 to bake-off.

**Open follow-ups:** SGS hill-climb next. Decide PCS bake-off effort (3× medium vs 3× high) when ready. Bake-off panel still later and disjoint from tuning-50, hill-climb 20, and this confirm 20. CloudCruise medium JSON restored (see [[2026-08-14: CloudCruise medium timeout overwrite restored]]).

---

## 2026-08-14: CloudCruise medium timeout overwrite restored

**Decision:** Keep the latest clean CloudCruise medium JSON as the confirm-20 row. Do not treat the $0 timeout overwrite as the panel result.

**Why:** A second timeout retry finished after a successful 5-finding run and overwrote `95651351.json`. A third sequential retry landed clean.

**Evidence:** `outputs/stage2/test_runs/pcs_confirm_20_medium/95651351.json` is now `error=None`, 7 findings, $0.079, 38.5s. Prior failures kept as `95651351.429.json`, `95651351.timeout.json`, `95651351.timeout2.json`. Clean 20-JSON panel is now **124** findings, **$1.437**, mean **$0.072**. High counterpart still 195 / $3.418. Lift is +71 findings (+57%) at 2.38× cost, same class as the earlier +60% / ~2.4× read.

**Alternatives rejected:** Leaving the timeout JSON as the official row. Recomputing the whole medium pass.

**Open follow-ups:** none for CloudCruise. SGS next.

---

## 2026-08-14: SGS digs inherit PCS owned early-exit

**Decision:** Copy the PCS owned extract refinements into SGS `dig_owned.txt` only. A jobs- or third_party-shaped safety-valve row does not finish the owned dig. SEARCH FOCUS is first-party indexes (blog/newsroom, help/policy, company-hosted social or embed walls the site actually has), then official accounts. Keep SGS identity: official accounts are owned-shaped; homepage does not have to load. Do not construct a fixed path list. Jobs and third_party dig overlays already matched the hill-climb prompt lock. Scouts stay presence/existence until a separate lock.

**Why:** User asked that PCS prompt refinements land in SGS before scout work. The last PCS owned pass was the early-exit + generalize rule. SGS owned still had the older "open `/linkedin-posts`" construct line.

**Evidence:** `prompts/signal_gated_search/dig_owned.txt`. Tests: `tests/test_sgs_prompting.py`. PCS source: `prompts/parallel_channel_search/channel_owned.txt` and [[2026-08-14: PCS owned advice must generalize]].

**Alternatives rejected:** Rewriting SGS scouts in the same slice. Changing dig `max_steps` / `web_search_depth` in this slice. Editing SGS third_party toward the PCS host-based YouTube split.

**Open follow-ups:** Dig leash match landed (see [[2026-08-14: SGS dig leash matches PCS]]). Existence scouts stay. ~$0.10/co is unlikely on companies that light all 3 rooms.

---

## 2026-08-14: SGS dig leash matches PCS

**Decision:** SGS digs use the same leash as a PCS channel: `max_steps=50`, `web_search_depth=medium`. Reasoning effort stays **high** on every signaled dig. Scouts stay **existence/presence** (`low`, no `fetch_url`). Package + YAML + design card updated. Path budget headroom raised to $0.25/co.

**Why:** User locked this after the PCS close-out. The hill-climb 20 gap (SGS high 187 vs PCS high 201) was mostly a shorter leash, not a jobs-prompt hole. User also kept existence scouts, so SGS will still dig almost every room that has a site / careers page / any press.

**Cost implication (stated):** This will not hit ~$0.10 on companies that light 3 rooms. Planning math: ~$0.02 scouts + up to 3× PCS-high-depth digs ≈ PCS high (~$0.17) plus scout tax. Savings only appear when a room truly does not exist (N=0/1/2). Empty-of-evidence rooms (Zivy/Spaxel jobs=0) still get a full dig.

**Evidence:** `signal_gated_search/channels.py`, `evals/configs/signal_gated_search.yaml`, `.cursor/plans/sgs-design.md`. Prior diagnosis: [[2026-08-14: SGS vs PCS high gap diagnosis]].

**Alternatives rejected:** Yield-hint scouts (user declined). Keeping steps=10 / search=low. Waiting for the 4-co match-knob smoke before changing defaults.

**Open follow-ups:** Paid confirm landed (see [[2026-08-15: SGS matched-leash 20 vs PCS high]]). Existence scouts skipped 0 rooms on this panel.

---

## 2026-08-15: SGS matched-leash 20 vs PCS high

**Decision:** Record the paid SGS pass on `hillclimb_pcs_v1_march_20` with current package defaults: `scout_preset=low`, digs Luna `max_steps=50` / `web_search_depth=medium` / `reasoning_effort=high`, PCS extract locks on digs. Measurement only. Not a bake-off. Package defaults unchanged. Do not treat this panel as proof that existence scouts cut unit cost.

**Why:** User asked for a same-20 compare that holds dig knobs and extract teaching constant, so the only intended difference is SGS presence scouts skipping rooms that do not exist.

**Evidence:** `outputs/stage2/test_runs/sgs_hillclimb_20_matched/` vs `pcs_hillclimb_20_high/`. 20/20 `error=None`. Wall ~490s. Old shallow SGS high (`sgs_hillclimb_20_high/`, fast scouts) stays as the prior measurement.

| System | Findings | Mean $ | Panel $ | Rooms skipped |
|---|---:|---:|---:|---|
| SGS matched (this run) | **221** | $0.171 | $3.416 | **0** (20× dig_count=3) |
| PCS 3× high | 201 | $0.165 | $3.302 | n/a (always 3) |
| SGS high old (fast + 10/low) | 187 | $0.173 | $3.456 | 1 (Easy Fill jobs) |

SGS wins 14, PCS 3, ties 3. Scout tax mean **$0.018**/co. Dig spend mean $0.153. Leash check: Statsig Statbot URL recovered (was 0 on old SGS high). Alguna YC `nhVNFAe` and Vendelux Ashby `6faa20f1` still absent. Easy Fill jobs flipped `none`→`moderate`, still 0 findings, $0.237.

**What this means:** Matching the PCS leash closed the findings gap and then some. Existence scouts did **not** save money here because every company had a site, some hiring footprint, and some independent pages. SGS paid PCS-high digs plus the scout tax. Cost savings from this gate need rooms that truly do not exist, which this March-positive-heavy 20 almost never has.

**Alternatives rejected:** Calling this a bake-off win. Changing scout semantics after one panel. Overwriting `sgs_hillclimb_20_high/`. Treating Alguna/Vendelux URL misses as a new prompt class (same variance class as before).

**Open follow-ups:** Bake-off still later on a new disjoint panel. PCS effort (3× medium vs 3× high) still open. Yield-hint remains the only way to skip empty-of-evidence rooms. Optional later panel with more true-absent rooms if we want to measure scout savings. Skip-rate panel landed (see [[2026-08-15: SGS skip-rate 50 on March none/low]]).

---

## 2026-08-15: SGS skip-rate 50 on March none/low

**Decision:** Record a paid SGS-only pass on a new 50-company March none/low panel (`sgs_skip_v1_march_50`, seed `20260815`). Package defaults only: `scout_preset=low`, digs Luna `max_steps=50` / `web_search_depth=medium` / `reasoning_effort=high`. Measurement only. Not a bake-off. Do not start PCS on this panel unless the user later asks. Package defaults unchanged.

**Why:** The hill-climb 20 skipped 0 rooms. That panel was March-positive-heavy, so it could not test the cost-save claim: existence scouts save money only when a room does not exist. This panel is 40 March-none + 10 March-low, disjoint from tuning-50, hill-climb 20, and the PCS confirm 20.

**Evidence:** `evals/panel/sgs_skip_panel.json`, builder `evals/panel/build_sgs_skip_panel_v1.py`, live `outputs/stage2/test_runs/sgs_skip_50/`. 50/50 `error=None`. No 429s or timeouts. Wall ~1096s.

| Slice | n | Findings | Mean $ | Panel $ | dig_count | Rooms skipped |
|---|---:|---:|---:|---:|---|---:|
| All | 50 | **184** | $0.157 | $7.851 | 38×3, 12×2, 0×1, 0×0 | **12 / 150 (8%)** |
| March low | 10 | 91 | $0.160 | $1.598 | 10×3 | 0 |
| March none | 40 | 93 | $0.156 | $6.253 | 28×3, 12×2 | 12 |

Scout tax mean **$0.020**/co ($0.984). Dig spend mean $0.137 ($6.867). Owned lit **50/50** `strong`. Jobs skipped 11 (10 `none` + 1 `weak`). Third-party skipped 1 (`none`). All 12 skips were March-none. March-none still produced 93 findings (18/40 companies ≥1). Vs the 3-dig $0.171 rate this is ~$0.70 under the $8.60 planning number, still far above the $0.10 target.

**What this means:** March none ≠ no website, and often ≠ no adoption either. Existence scouts can skip a missing jobs room, but almost every company still has a site and some independent pages, so the gate still pays 2–3 high digs plus the scout tax. The cost-save hypothesis did **not** hold as a unit-cost story.

**Alternatives rejected:** Calling this a bake-off. Starting PCS on this panel. Overwriting `sgs_hillclimb_20_matched/` or `sgs_hillclimb_20_high/`. Changing scout semantics after one none/low panel.

**Open follow-ups:** Bake-off still later on a **new** disjoint panel (never tuning-50, hill-climb 20, PCS confirm 20, or this skip 50). PCS effort (3× medium vs 3× high) still open. Yield-hint remains the only way to skip empty-of-evidence rooms that still exist. Syndication squash (same sentence, different boards) is locked in [[2026-08-16: Squash syndicated copies, keep duty splits]].

---

## 2026-08-15: Paid per-company traces stay local, not in git

**Decision:** Drop per-company Agent JSON (and `test_results.csv`) from git. Keep runners (`*.py`) and `summary.jsonl` scoreboards. `.gitignore` no longer un-ignores `outputs/stage2/test_runs/**/*.json`.

**Why:** One commit of traces was ~150k lines. That makes review, clone, and checkout painful, and the numbers already live in `summary.jsonl` plus this log. Traces stay on disk for local debugging.

**Evidence:** `.gitignore` (`!outputs/stage2/test_runs/**/*.py`, `!outputs/stage2/test_runs/**/summary.jsonl`). Folders still on disk: `outputs/stage2/test_runs/sgs_skip_50/`, `sgs_hillclimb_20_matched/`, `pcs_confirm_20_*`, `pcs_hillclimb_20_*`.

**Alternatives rejected:** Keeping full traces in git as "evidence." A follow-up delete commit that still leaves 150k lines in history (this commit was unpushed, so rewrite it instead).

**Open follow-ups:** Optional later: a pull script if a cloud agent needs a specific `{rcid}.json` from local or object storage.

---

## 2026-08-15: Tavily Extract is the only paid backup fetch

**Decision:** Keep Perplexity `fetch_url` as the primary page load. The **only paid backup** is **Tavily Extract** (key already in this repo). After that: raw `httpx`, then browser last. **No Jina Reader** (no key, do not add a vendor that needs a new secret).

**Why:** Gold showed Perplexity can return the wrong document with the requested URL still on the row (`example.com` → MOT page). A second pair of eyes that is not `fetch_url` is the fix. Tavily Extract is URL-in, text-out, and Stage 1 already uses Tavily. Jina would be a third account for no extra product need.

**Evidence:** User lock 2026-08-15; plan WS4 in `.cursor/plans/bulletproof-citation-verifier.plan.md`; Tavily client `src/stage_1/tavily.py`; gold poison case `outputs/stage3/smokes/20260815_2100_gold_e2e/`.

**Alternatives rejected:** Jina Reader in the chain. Browser-first. Tavily Search (wrong tool: we already have the URL).

**Open follow-ups:** Implemented on `cursor/bulletproof-citation-verifier`. Remaining: live expanded gold re-score (WS9).

---

## 2026-08-15: Bulletproof citation verifier plan

**Status:** superseded in delivery by [[2026-08-15: PR 28 merged, bulletproof verifier is its own PR]] (PR #28 merge lock). Name-missing → null superseded by [[2026-08-15: Lenient judge, no literal-anchor null]]. Quality locks that still stand: 32k after chrome-strip, Tavily backup, no Phase B before the gold gate.

**Decision:** Write `.cursor/plans/bulletproof-citation-verifier.plan.md` and treat it as the pre-merge quality plan for Stage 3. User locks: take **all** proposed approaches (not a subset); verifier cost is **not** a constraint (meter everything, do not cheap out); raise `MAX_SNIPPET_CHARS` to **32,000 after chrome-strip** so it is ≥ Stage 2 high page budget; do **not** merge PR #28 until Khaled says; do **not** start Phase B 221+124 except as an optional post-gate step.

Stage 2 has no `MAX_SNIPPET_CHARS`. The research-agent page cap is `web_search.max_tokens_per_page` in PCS/UAS/SGS `agent_call.py`: **1,000 / 2,000 / 4,000** tokens (low / medium bake-off / high). Stage 2 `fetch_url` has no token or char knob. Today's verifier cap is 12,000 chars, below the high equivalent (~16,000 chars).

Second fetch order: **superseded by [[2026-08-15: Tavily Extract is the only paid backup fetch]]**. Name missing after one targeted refetch → `verification=null`, not `0`. Name present and fact wrong → `0`. Unread or incomplete page → `null`.

**Why:** Gold/e2e showed the judge is fine on a real snippet and fetch is the production risk (MOT-on-example.com, empty-fetch flake, timeout, python.org hero miss, RightRev 12k chrome with "Jagan Reddy" absent). A domain-mismatch guard cannot catch a wrong document that still labels the requested URL.

**Evidence:** Plan file; Stage 2 ladder in `unified_adaptive_search/agent_call.py`, `parallel_channel_search/agent_call.py`, `signal_gated_search/agent_call.py`; bake-off yaml `evals/configs/parallel_channel_search.yaml` (`web_search_depth: medium`); gold `outputs/stage3/smokes/20260815_2100_gold_e2e/`; Phase A `outputs/stage3/smokes/20260815_201259/`; e2e5 `outputs/stage3/smokes/20260815_203606_e2e5/`; Tavily already in `src/stage_1/tavily.py`.

**Alternatives rejected:** Shipping a subset of the proposed approaches. Keeping 12k to save judge tokens. Auto-nulling LinkedIn/YouTube/Indeed. Treating name-missing as `0` without targeted refetch. Starting the 221+124 panel before the merge gate. Merging PR #28 from this turn.

**Open follow-ups:** Implement WS0–WS9 in the plan. Khaled merge call after the expanded gold re-score.

---

## 2026-08-15: Gold e2e: retry empty fetch, surface title, stricter names

**Status:** clause (3) (every distinctive name must appear) superseded by [[2026-08-15: Lenient judge, no literal-anchor null]]. Retry-empty-fetch and persist title still stand.

**Decision:** After a 24-case live gold e2e ($0.148): (1) retry empty `fetch_url` output once, (2) persist `fetched_url` / `fetched_title` on every live row so a human can spot a wrong document, (3) judge `verification=1` only if every distinctive name in the claim (person, company, product, tool) appears in the snippet or a clear synonym. Dead/unreadable fetches stay `verification=null`. A fetched page that does not support the claim stays `0`.

**Why:** The gold run showed three production risks. Perplexity `fetch_url` on `https://example.com/` returned a UK MOT page while still labeling the URL `example.com`, so a domain-mismatch guard cannot catch it. The same Wikipedia Copilot URL succeeded, then later returned no `fetch_url_results` (empty-fetch flake → false NA). The judge verified a RightRev claim that named “Jagan Reddy” even though that name was not in the snippet (loose true-positive). LinkedIn / Indeed / YouTube often *did* return real text, so those hosts are not an automatic null.

**Evidence:** `outputs/stage3/smokes/20260815_2100_gold_e2e/` (19/24 on the first labels; 5 fails were 2 over-exact support claims, 1 empty-fetch flake, 1 LinkedIn-teaser inspect heuristic, 1 named-attribution looseness). Re-fetch dump: example.com title `Instant Vehicle MOT Status Lookup`.

**Alternatives rejected:** Treating every LinkedIn/YouTube row as null (gold fetched real JD/transcript text). Host-label-must-appear-in-snippet (would false-null ATS hosts like `jobs.ashbyhq.com`). Switching fetch vendor in this pass.

**Status:** second-fetch vendor and remaining gold gaps superseded by [[2026-08-15: Bulletproof citation verifier plan]]. PR #28 merge lock superseded by [[2026-08-15: PR 28 merged, bulletproof verifier is its own PR]].

**Open follow-ups:** See bulletproof plan merge gate.

---

## 2026-08-15: Unjudged rows stay verification=null

**Decision:** Pipeline failures and unjudged rows emit **`verification=null`**, **`unverifiable=true`**, and an **`error`** reason so the row is undeclared and must be re-run. **`verification=0` is only allowed** when Terra actually judged a real page snippet and decided the page does not support the claim. If the judge never ran, ran on non-page text (empty fetch, too-short snippet, Perplexity `fetch_url` tool-error string), or parse/logprob extract is unusable: **null, not 0**. JSONL/CSV outputs pass through finding identity plus a clickable **`source_url`** for human review: `finding_id`, `source_url`, `evidence_description`/`claim`, and extras when present (`company_name`, `rcid`, `channel`, `AI_tool_used`, `use_case`, `business_function`, `source_type`, `architecture`). CLI flags: `--output-jsonl PATH` and `--output-csv PATH`.

**Why:** A failed fetch or broken judge is not a hallucination. Phase A smoke showed Perplexity can put a long `[fetch_url: no content could be retrieved … dns_failed_to_resolve]` string in `contents.snippet`. That cleared the 40-char floor, so Terra labeled it `verification=0`. Treating that as hallucination poisons metrics and hides rows that need a re-run or a human click.

**Evidence:** User lock 2026-08-15; Phase A smoke `outputs/stage3/smokes/20260815_201259/`; `citation_verification/fetch.py` `_unusable_snippet_reason`; `citation_verification/runner.py` unverifiable paths; `tests/fixtures/citation_fetch_tool_error.json`; CLI writers in `citation_verification/__main__.py`.

**Alternatives rejected:** Mapping fetch/judge/logprob failures to `verification=0`; dropping finding URL from outputs; starting the 20-company Phase B panel to rediscover the same contract bug.

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

**Status:** CLI file outputs extended by [[2026-08-15: Unjudged rows stay verification=null]] (`--output-jsonl` / `--output-csv`).

**Evidence:** User lock 2026-08-14; Phase 2 plan.

**Open follow-ups:** PR1 skeleton (design freeze complete for package v1).

---

## 2026-08-14: Stage 3 verification=0/1 and claim=evidence_description

**Decision:**
- Model field `verification` is **`Literal[0, 1]`**: **1 = verified**, **0 = hallucination**.
- Claim text for the judge is Stage 2 **`evidence_description` only**.

**Why:** Binary digits are best for logprob span extraction (same as taxonomy Pass A). Evidence-only keeps the judge prompt simple.

**Evidence:** User lock 2026-08-14; Phase 2 plan D1/D3.

**Status:** Model field is still 0/1. Package output may be `null` when the row was not judged; see [[2026-08-15: Unjudged rows stay verification=null]].

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

**Status:** `verification` type and D3 claim superseded in specificity by [[2026-08-14: Stage 3 verification=0/1 and claim=evidence_description]]. D4 model superseded by [[2026-08-15: Stage 3 judge is OpenAI Luna]].

**Still open:** D2 ops fields; D5 CLI (proposal: findings JSONL + optional `--url/--claim`); fetch wrapper model/preset.

**Open follow-ups:** Lock remaining Ds; then PR1.

---

## 2026-08-13: Stage 3 stack = Perplexity fetch_url + OpenAI logprob judge

**Decision:** Stage 3 stack is **hybrid**: (1) Perplexity Agent API **`fetch_url`** to load text for each finding’s `source_url`, (2) OpenAI judge with **`reasoning.effort=none`**, strict JSON binary int (taxonomy Pass A shape) + **`include=message.output_text.logprobs`** / `top_logprobs`, confidence **computed in-package** (not model-emitted), plus optional verbalized **1–5** backup. Empty/failed fetch → **`UNVERIFIABLE`**, not unsupported. No HTML→markdown preprocessing by default. Package build plan: `.cursor/plans/phase-2-stage3-verification.plan.md`.

**Status:** Fetch-failure UNVERIFIABLE still current; judge parse/transport and logprob-extract failures now use the same `verification=null` contract. See [[2026-08-15: Unjudged rows stay verification=null]].

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
- [x] Optional Stage B-style probe: PCS 3× high on the 20-co hill-climb panel (mean $0.165, not a default lock; see [[2026-08-14: PCS 20-co 3× high cost probe]])
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
- [x] SGS 5-co low vs fast scout A/B smoke (measurement; later locked as default; see [[2026-08-14: SGS 5-co low-scout smoke]])
- [x] SGS scouts locked to **low** as package/YAML default (see [[2026-08-14: SGS scouts locked to low]])
- [ ] Scout-tool or all-none rescue if `low` presence screens still return empty rooms that exist
- [x] Optional extra SGS smoke if we want the N=3/`medium` row before bake-off (20-co medium-dig probe landed; see [[2026-08-14: SGS 20-co medium vs high digs]]. Old 1=max / 3=medium ladder is not the default.)
- [x] Hill-climb PCS first paid pass on `evals/panel/hillclimb_panel.json` (20-co, $1.19 total; see [[2026-08-14: PCS hill-climb v1 live 20-co]])
- [x] Retry PCS timeouts on Sudozi + RightRev (see [[2026-08-14: PCS hill-climb timeout retries (Sudozi, RightRev)]])
- [x] Hill-climb prompt lock: external job boards, unnamed-tool findings, owned social walls, adopt vs product-AI (see [[2026-08-14: Hill-climb prompt lock (jobs boards, unnamed tools, adopt vs product-AI)]])
- [x] Re-smoke the 20-co panel after the prompt lock at 3× medium (see [[2026-08-14: PCS 20-co 3× medium v2 (current prompts)]])
- [x] UAS on the same 20 at package-default xhigh (117 findings, mean $0.089; see [[2026-08-14: UAS 20-co xhigh hill-climb]])
- [ ] Decide PCS effort (3× medium vs 3× high) from the same-prompt pair
- [x] PCS-only failure-mode pass: owned early-exit as a general rule, not a path recipe (see [[2026-08-14: PCS owned advice must generalize]])
- [ ] Paid PCS medium re-smoke Sudozi `743085` + Unwrap `169806` on the owned early-exit prompt
- [x] Hill-climb PCS until user is happy (closed: no further prompt iteration; see [[2026-08-14: PCS hill-climb closed, no further prompt iteration]])
- [x] SGS digs inherit PCS owned early-exit + general first-party indexes (see [[2026-08-14: SGS digs inherit PCS owned early-exit]])
- [x] Keep SGS scouts as existence/presence (user declined yield-hint; see [[2026-08-14: SGS dig leash matches PCS]])
- [x] Then SGS on the same 20 before bake-off (medium + high digs; see [[2026-08-14: SGS 20-co medium vs high digs]])
- [x] Diagnose SGS high vs PCS high on the same 20 (shallower digs + scout tax on almost-full fan-out; see [[2026-08-14: SGS vs PCS high gap diagnosis]])
- [x] SGS dig leash matches PCS (steps=50, search=medium) as package/YAML default (see [[2026-08-14: SGS dig leash matches PCS]])
- [x] Paid confirm of the new SGS leash on the hill-climb 20 (221 findings, mean $0.171, 0 rooms skipped; see [[2026-08-15: SGS matched-leash 20 vs PCS high]])
- [x] SGS skip-rate 50 on March none/low (184 findings, mean $0.157, 12/150 rooms skipped; see [[2026-08-15: SGS skip-rate 50 on March none/low]])
- [x] Paid per-company traces stay local / gitignored (see [[2026-08-15: Paid per-company traces stay local, not in git]])
- [x] PCS confirm panel v1 (20 unused March IDs, seeded; see [[2026-08-14: PCS confirm panel v1]])
- [x] Record PCS 3× high on `pcs_confirm_v1_march_20` (195 findings, mean $0.171; see [[2026-08-14: PCS confirm 20-co 3× high]])
- [x] Record PCS 3× medium on the same confirm 20 (124 findings after CloudCruise restore, mean $0.072; 8-wide 429s, safe concurrency 5; see [[2026-08-14: PCS confirm 20-co 3× medium]] and [[2026-08-14: CloudCruise medium timeout overwrite restored]])
- [x] Confirm-medium runner skips only success JSON and detects 429 from the error field (see [[2026-08-15: Confirm-medium runner no longer locks failed JSON or false 429s]])
- [x] 3-arch bake-off skipped: SGS is the production Stage 2 architecture (see [[2026-08-16: Skip bake-off, ship SGS on the full prod set]])
- [x] Park March agent in `legacy_agent_march_2026/` (see [[2026-08-16: March agent retired to legacy_agent_march_2026]])
- [x] SGS production batch runner on branch `prod_runner` after this PR merges (see [[2026-08-16: Skip bake-off, ship SGS on the full prod set]] and [[2026-08-16: PR2 production runner landed]])
- [x] Re-land the production runner on `main` by reverting the accidental-merge revert (see [[2026-08-16: Re-land production runner on main]])
- [x] Persist raw findings, then write a derived syndication squash (keep duty splits) on its own branch. See [[2026-08-16: Save raw findings, dedupe as a derived view]] and [[2026-08-16: Production dedupe is a derived CSV]]
- [x] Production `verify` implementation on its own branch (thin wrap already exists) (see [[2026-08-16: Production verify is a resume-safe finding batch]])
- [x] Stage 3 spike: Perplexity logprobs? (**No** usable logprobs; see [[2026-08-13: Perplexity APIs do not expose usable logprobs]])
- [x] Stage 3 packaging: top-level production `citation_verification/` (see [[2026-08-13: Stage 3 is a production top-level package]])
- [x] Stage 3 stack: Perplexity `fetch_url` + OpenAI logprob judge (see [[2026-08-13: Stage 3 stack = Perplexity fetch_url + OpenAI logprob judge]])
- [x] Stage 3 D1 field names + D4 Terra judge (see [[2026-08-14: Stage 3 D1/D4 locks (Terra judge + output field names)]]; model now Luna, [[2026-08-15: Stage 3 judge is OpenAI Luna]])
- [x] Stage 3 judge switched to OpenAI `gpt-5.6-luna` (see [[2026-08-15: Stage 3 judge is OpenAI Luna]])
- [x] Stage 3 `verification` 0/1 + claim=`evidence_description` (see [[2026-08-14: Stage 3 verification=0/1 and claim=evidence_description]])
- [x] Stage 3 D2 trailing cost/ops fields + D5 simple CLI (see [[2026-08-14: Stage 3 D2/D5 locked (trailing cost fields + simple CLI)]])
- [x] Stage 3 delivery: one PR / five commits + local then cloud Bugbot (see [[2026-08-14: Stage 3 delivery = one PR, five commits + Bugbot gates]])
- [x] `citation_verification/` commits 1–5 on branch `cursor/citation-verification-8475` (package only; evals out of scope)
- [x] Cloud Bugbot babysit on Stage 3 package PR #28 (tip commit clean: no issues)
- [x] Unjudged / failed rows stay `verification=null` (re-run), not hallucination 0; outputs keep finding URL (see [[2026-08-15: Unjudged rows stay verification=null]])
- [x] Gold e2e: retry empty fetch, surface title, stricter names (see [[2026-08-15: Gold e2e: retry empty fetch, surface title, stricter names]])
- [x] Bulletproof verifier plan written (see [[2026-08-15: Bulletproof citation verifier plan]])
- [x] Implement bulletproof workstreams WS0–WS8 on `cursor/bulletproof-citation-verifier` (see [[2026-08-15: PR 28 merged, bulletproof verifier is its own PR]])
- [x] Lenient Terra judge; no literal-anchor `null` (see [[2026-08-15: Lenient judge, no literal-anchor null]])
- [x] Re-run 14-row e2e5_bp after the lenient-judge change (14×`1`, $0.491; see `outputs/stage3/smokes/20260815_2245_e2e5_bp_lenient/`)
- [ ] WS9 live expanded gold re-score (paid, Khaled spend approval). Do not start Phase B 221+124 first.
- [ ] Later (separate plan): evals `run-verification` consumer + eval-set quality gates
- [x] Paid verify `--limit 20` smoke after adaptive finding-level concurrency (see [[2026-08-17: Verify is finding-level with adaptive API caps]])

---

## 2026-08-15: Confirm-medium runner no longer locks failed JSON or false 429s

**Decision:** Treat the confirm-medium `*.429.json` files as **false positives**, not as 15 real rate limits. Keep the restored CloudCruise success row as the panel result. Fix the runner so a later timeout or 429 cannot freeze or overwrite a good company JSON.

**Why:** The old detector JSON-serialized the whole payload and matched the substring `429`. That fires on costs such as `0.1429` and on LinkedIn job IDs. Every `pcs_confirm_20_medium/*.429.json` has `error: null`. Resume also skipped any existing `{rcid}.json`, so a timeout written to the canonical path (CloudCruise) stayed locked until a human restored it.

**Evidence:** `outputs/stage2/test_runs/pcs_confirm_20_medium/run_twenty_medium.py` now checks the `error` field only, skips resume only when that field is empty, backs up failed files and retries them, and refuses to overwrite a successful JSON with a later failure. Default concurrency is **5** company workers (15 in-flight), matching confirm-high. Same resume and keep-success guards landed on `pcs_confirm_20_high/run_twenty_high.py`, `sgs_skip_50/run_fifty.py`, and `sgs_hillclimb_20_matched/run_twenty.py`. Real `RateLimitError` strings still live in `pcs_hillclimb_20_medium_v2/*.429.json`.

**Conflict with earlier log:** [[2026-08-14: PCS confirm 20-co 3× medium]] said 15/20 hit 429 and counted $1.145 retry spend. That 429 count is not trustworthy. The clean 20-JSON panel (124 findings, mean $0.072 after CloudCruise restore) still stands. The “5 workers is the evidenced safe max” lesson now rests on confirm-high (clean at 5) and hill-climb medium v2 (real 429s at 20-wide), not on this folder’s backups.

**Alternatives rejected:** Rewriting the 2026-08-14 metrics in place. Re-running the paid confirm-medium panel just to rebuild backups.

**Open follow-ups:** none for the runner. PCS effort and bake-off panel still open.

---

## 2026-08-15: PR 28 merged, bulletproof verifier is its own PR

**Decision:** Merge PR #28 (`citation_verification/` package v1) to main. Put the bulletproof work (32k after chrome-strip, claim windows, name-missing → null, Tavily Extract backup, constrained Luna, expanded gold) on a **new branch and PR**, not as extra commits on #28. Do **not** run the paid expanded gold re-score (WS9) or the 221+124 Phase B panel until Khaled approves that spend.

**Why:** #28 was blocked only by a `docs/decision-log.md` conflict with main's search-depth lock. The package on #28 is the fact-checker skeleton. Gold already showed fetch, not the judge, is the production risk. Landing v1 on main lets the quality work review on its own diff.

**Evidence:** PR #28 merge commit `79b049a`. Conflict resolution commit `72e8fb3` on `cursor/citation-verification-8475`. Implementation branch `cursor/bulletproof-citation-verifier`. Plan `.cursor/plans/bulletproof-citation-verifier.plan.md`. Offline gate: `PYTHONPATH=. python3 -m pytest tests/test_citation_verification_*.py -q`.

**Alternatives rejected:** Holding #28 until the whole bulletproof plan landed. Squashing #28's five slice commits. Starting Phase B to discover bugs the plan already names.

**Open follow-ups:** Live expanded gold re-score (WS9). Khaled merge call on the bulletproof PR. Phase B 221+124 remains optional after that gate.

---

## 2026-08-15: Lenient judge, no literal-anchor null

**Decision:** The package must not declare `verification=null` because a distinctive string from the claim is missing (exact quote, punctuation, `Cursor.`, writer-side words like `Cognition's`). After a real page is fetched, **Terra decides**. Prefer `verification=1` when the finding exists in any form: paraphrase, synonym, reordered names, partial quote, or a role stand-in (CEO / author / the company). `verification=0` only when (1) the substance is not on the page at all, or (2) the page only sells/markets the tool and the claim says they use it internally. Unread or broken fetches stay `null`. Wrong exact name is not a veto if the quote/fact and a stand-in are there.

**Why:** The 14-row bulletproof e2e (`20260815_2218_e2e5_bp`) returned 11 `null`s, all `snippet_missing_claim_anchors`. Browser review showed most pages did support the finding. The literal matcher was rejecting real citations. Stage 2 Perplexity researchers are expected to rarely invent a page-level fact, so prod should be lenient on `1` and keep the hallucination rate low.

**Evidence:** User lock 2026-08-15 (Q1 unread=`null`, Q2 off-topic=`0`, Q3 role stand-in=`1`, Q4 sell-vs-use=`0`, Q5 judge-only). Baseline smoke `outputs/stage3/smokes/20260815_2218_e2e5_bp/` (3×`1`, 11×`null`). Re-run `outputs/stage3/smokes/20260815_2245_e2e5_bp_lenient/` (14×`1`, 0×`0`, 0×`null`, $0.491). Prompt `prompts/citation_verification/judge.txt`. Combine/runner no longer emit `snippet_missing_claim_anchors` as a verdict.

**Alternatives rejected:** Keeping the all-anchors-must-appear package veto. Fuzzy package string matching. Treating unread links as `0`. Treating sell-pages as `1` just because the tool name appears.

**Open follow-ups:** WS9 gold re-score still gated.

---

## 2026-08-15: Stage 3 judge is OpenAI Luna

**Decision:** Stage 3 judge model is OpenAI **`gpt-5.6-luna`** on the same Responses + `reasoning.effort=none` + logprobs path. Fallback token rates: **$0.20 / $0.02 cached / $1.20** per 1M. Still not Perplexity Luna (no usable logprobs). Fetch stays Perplexity `fetch_url`.

**Why:** The 14-row lenient e2e cost $0.491, of which **$0.408 was Terra**. Luna is 10× cheaper on input and output. Same binary+logprob contract, same prompt. "Judge ≠ researcher family" is not worth 10× unit cost on a high-volume 0/1 check.

**Evidence:** User lock 2026-08-15. Cost split `outputs/stage3/smokes/20260815_2245_e2e5_bp_lenient/` (fetch $0.084, Terra $0.408). OpenAI pricing: Terra $2/$12, Luna $0.20/$1.20. Config `citation_verification/config.py`.

**Alternatives rejected:** Keeping Terra. Moving the judge to Perplexity (logprobs still unusable). Dropping logprobs to save more.

**Open follow-ups:** Optional cheap Luna re-smoke of the same 14 rows to confirm logprobs still extract. WS9 still gated.

---

## 2026-08-16: Squash syndicated copies, keep duty splits

**Status:** persistence/timing superseded by [[2026-08-16: Save raw findings, dedupe as a derived view]]. Duty-split vs syndication rule still stands.

**Decision:** Finding merge keeps **duty splits** (one sentence, three distinct use cases = three findings). It squashes **syndicated copies** only: the same tool + same use case + the same claim, posted on multiple job boards or re-extracted by a second channel with slightly different wording. Do this in `merge_findings` at the **end of each company**, before the result is written. The same function can replay on old traces. Do not dedupe mid-search. Do not make a post-hoc notebook the source of truth.

**Why:** `(tool, use_case, url)` already keeps duty splits and already drops exact same-URL copies. It misses Terralytiq-style mirrors (careers + LinkedIn + Techstars) and Loman-style channel rewrites of one Gusto post. Dropping URL from the key would also collapse two real pages that happen to name the same tool and use. Evidence-text similarity, gated on similar tool + similar use case, is the extra pass. Search should still visit every board. A unique sentence can live on only one of them.

**Evidence:** User lock 2026-08-16 after the SGS skip-50 184-row review. Current merge: `parallel_channel_search/merge.py`, called from `parallel_channel_search/runner.py` and `signal_gated_search/runner.py`. Old production JSONL helper `_deduplicate_jsonl` in `src/stage_2/production_agent_runner.py` is resume-safe company-level (best row per `rcid`+`preset`), not finding-level.

**Alternatives rejected:** Squashing the ~30 duty-split rows. Deduping while a channel is still searching. Post-hoc-only squash after a full run (evals and CSV would keep two counts). An LLM judge for merge (nondeterministic, paid).

**Open follow-ups:** Implement the second pass in `merge_findings` (normalize tool/use, compare evidence text, first channel wins). Add tests from Terralytiq / Dreamwave (squash) vs Verifiable / Synqly duty lists (keep). Replay on `outputs/stage2/test_runs/sgs_skip_50/` to replace the 184 headline. Old Perplexity production runner should call the same merge before write if it stays in the path.

---

## 2026-08-16: Save raw findings, dedupe as a derived view

**Decision:** Write the **raw** finding list first (everything the channels emitted, including syndicated copies). Run syndication squash **only after that write**. The squashed list is a derived view, not a replacement. Raw stays on disk so a hungry merge can be undone without a new paid run. Scoreboards and evals read the derived view by default. You can rebuild derived anytime the merge rules change.

**Why:** Merge thresholds will get tuned. If squash overwrites the only copy, a bad rule silently deletes evidence. Saving raw first is the undo button. Search still does not dedupe mid-flight.

**Evidence:** User lock 2026-08-16. Policy for *what* to squash remains [[2026-08-16: Squash syndicated copies, keep duty splits]]. Current write path: `parallel_channel_search/runner.py` and `signal_gated_search/runner.py` call `merge_findings` before persist.

**Alternatives rejected:** Squashing in memory and writing only the reduced list (previous timing). Deduping while a channel is still searching. Waiting for an entire multi-thousand-company run to finish before computing derived for company 1 (raw still saves incrementally; derived can attach per company after that company's raw is on disk, and can be rebuilt for the whole run later).

**Open follow-ups:** Shape the on-disk fields (`findings` = raw, `findings_deduped` = derived, plus both counts). Implement after the merge tests exist. Replay skip-50 raw vs derived so 184 stays auditable. Prod path: SGS batch runner writes raw first; squash and Stage 3 run after (see [[2026-08-16: Skip bake-off, ship SGS on the full prod set]]).

---

## 2026-08-16: Skip bake-off, ship SGS on the full prod set

**Decision:** Do **not** run the 3-arch bake-off. **SGS** is the production Stage 2 architecture for the full P4+P5 set (`crunchbase_data/stage2_input_dataset_p4_p5.jsonl`, 9,420 companies). Package defaults stay: `scout_preset=low`, digs Luna `max_steps=50` / `web_search_depth=medium` / `reasoning_effort=high`. Workflow is three sequential jobs: (1) SGS production runner writes raw findings to disk, (2) syndication squash as a derived view, (3) Stage 3 verification. Stage 3 does not have to be production-complete before (1) starts.

**Why:** User lock 2026-08-16. Hill-climb and skip-rate already showed SGS at or above PCS high on findings. Waiting for a disjoint bake-off panel delays the dataset. Dedup and verification can run on saved findings, so they are not blockers for paid search.

**Evidence:** User said bake-off is skipped and SGS is the ship choice. Closest SGS batch scripts are panel smokes (`outputs/stage2/test_runs/sgs_skip_50/run_fifty.py`, `sgs_hillclimb_20_matched/run_twenty.py`), not a full-set runner. Per-company API is `signal_gated_search.run()`. March-era scale runner `src/stage_2/production_agent_runner.py` still talks to the old Perplexity `deep-research` preset, not SGS. Cost band from paid SGS: mean **$0.171** on the hill-climb 20, **$0.157** on the skip 50. Full-set planning should use ~$0.16/co (~$1.5k), not the old $0.10 / ~$945 target.

**Alternatives rejected:** Running the disjoint 3-arch bake-off first. Reusing the March `production_agent_runner.py` as the prod path. Blocking the full-set run on syndication squash or a finished Stage 3 verifier.

**Open follow-ups:** Build the SGS production batch runner on branch `prod_runner` after `retire-legacy` merges (resume, concurrency, budget cap, incremental raw persist). Then derived squash ([[2026-08-16: Save raw findings, dedupe as a derived view]]). Stage 3 can keep landing in parallel (WS9 still gated).

---

## 2026-08-16: March agent retired to legacy_agent_march_2026

**Decision:** Move the March 2026 production system into a root-level runnable snapshot, `legacy_agent_march_2026/`. Copy shared Stage 1 (live Stage 1 stays). Move March-only Stage 2 (runner, A/B scripts, dashboard). Live code must not import that folder. Panel rebuilds read a frozen copy at `evals/references/march_2026_production.jsonl` (local, ~69MB, not in git). `prompts/stage_2_perplexity_prompt.txt` stays in the live tree because UAS still loads it. PR1 branch is `retire-legacy`. PR2 (`prod_runner`) starts only after this merges to `main`.

**Why:** The old batch runner still talks to Perplexity `deep-research`. Mixing it with the v2 SGS/PCS/UAS production path would make the wrong CLI easy to run on 9,420 companies. A standalone snapshot keeps March reproducible without being on the live import path.

**Evidence:** User lock 2026-08-16 (plan-mode spec). Snapshot README `legacy_agent_march_2026/README.md`. Live `MARCH_STAGE2_JSONL` in `evals/paths.py`. Master path constants removed from live `src/config.py`.

**Alternatives rejected:** Parking only `production_results.*` under `outputs/legacy/`. Letting live panel builders read `legacy_agent_march_2026/outputs/`. Moving the UAS prompt into the snapshot (would break live UAS). Committing the 69MB JSONL.

**Open follow-ups:** PR2 `prod_runner` after this merges.

---

## 2026-08-16: PR2 production runner landed

**Decision:** Ship a top-level `production/` package that batches SGS (default), PCS, or UAS over `crunchbase_data/stage2_input_dataset_p4_p5.jsonl` (9,420 companies). Live `run` requires `--limit N` or explicit `--all`. Writes raw findings under `outputs/prod/{sgs,pcs,uas}/`. `dedupe` exists but raises a clear not-implemented error until syndication squash. `verify` thin-wraps `citation_verification/` (dry-run default, `--live` opt-in) and renames Stage 3 `error` to `verification_error`. Resume is per architecture. Default concurrency is 4. Ctrl+C finishes in-flight companies and starts no new ones. No `--budget-cap` and no March pause/Enter loop.

**Why:** Bake-off was skipped and SGS is the ship architecture. The March runner is retired. Panel smokes are not a 9,420-company runner. A dedicated package keeps the three-step workflow (raw write, later squash, then verify) and makes accidental full-set spend hard.

**Evidence:** User lock for PR2 on branch `prod_runner` (from main `ca1015b`). Per-company APIs: `signal_gated_search.run`, `parallel_channel_search.run`, `unified_adaptive_search.run`. Keep-success and 429/timeout requeue from `outputs/stage2/test_runs/sgs_skip_50/run_fifty.py`. CLI: `python -m production {run,dry-run,status,dedupe,verify}`. Offline tests: `tests/test_production_runner.py`.

**Alternatives rejected:** Reusing `legacy_agent_march_2026` or restoring the live March runner. Squashing syndicated copies inside `run`. Starting the paid 9,420-company job in this PR. A `--budget-cap` in v1.

**Open follow-ups:** Syndication squash (`dedupe` writes `findings_deduplicated.csv`). Paid `--limit` batches after Khaled approval. Do not start `--all` until a small paid batch looks right.

---

## 2026-08-16: Prod resume retries only 429/timeout

**Decision:** Production `run --limit N` parks companies whose `{rcid}.json` already has a **permanent** (non-429/timeout) error. Those files stay on disk and do not consume the slice. 429 and timeout files are still backed up and requeued. `status` next-rcids and `dry-run` use the same queue rule. `remaining` still counts every non-success company, including parked errors. `status` spend sums `cost_usd` from canonical JSON and sidecar backups, so a 429 that was unlinked still counts.

**Why:** Bugbot on PR #32. The first draft requeued every failed JSON, copied from the 50-co panel scripts. On a 9,420-company `--limit` loop, one permanent error at the front would be paid again on every slice and would block later companies from entering the queue. Unlinking a 429 sidecar also hid that spend if status only read the canonical file.

**Evidence:** `production/persist.py` `is_parked_error` / `is_runnable` / `sum_recorded_spend`. `production/run.py` `_prepare_todo` / `remaining_companies`. `production/status.py` `next_rows`. Tests: `tests/test_production_runner.py` `test_permanent_error_does_not_consume_next_limit`, `test_status_spend_includes_429_backup`.

**Alternatives rejected:** Retrying every failure on each slice (panel-script behavior). Treating parked errors as `done` (hides them from `remaining` / `errors`). Adding a `--retry-failed` flag in v1 (delete the JSON to retry).

**Open follow-ups:** Syndication squash (`dedupe` writes `findings_deduplicated.csv`). Paid `--limit` batches after Khaled approval. Do not start `--all` until a small paid batch looks right.

---

## 2026-08-16: Re-land production runner on main

**Decision:** Restore `production/` on `main` by reverting `d1dca56` (the revert of accidental PR #32). After this lands, the next paid slice starts from `main`. Syndication squash (`dedupe`) and production `verify` work stay on their own branches so they can land while a long run is in flight.

**Why:** The same PR #32 commits cannot be re-merged. They are already ancestors of `main`. A PR from `prod_runner` would have an empty diff. The runner has now paid-smoked 202 companies (concurrency 8 then 10, $33.28, zero 429s). Khaled wants the 1,000-company slice on `main` so verifier and duplicator work do not share the runner branch.

**Evidence:** Revert commit `d1dca56`. Live writes under `outputs/prod/sgs/` (202 done, 9,218 remaining). CLI unchanged from [[2026-08-16: PR2 production runner landed]].

**Alternatives rejected:** Opening a PR from `prod_runner` (empty diff). Starting `--all`. Implementing `dedupe` or `verify` on the same branch as the live run.

**Open follow-ups:** Merge the restore PR. Start `--limit 1000 --concurrency 10` from `main` after merge. Implement `dedupe` on its own branch. Fuller `verify` landed on `prod-verifier` (see [[2026-08-16: Production verify is a resume-safe finding batch]]). Do not start `--all` until Khaled asks.

---

## 2026-08-16: Production verify is a resume-safe finding batch

**Status:** superseded by [[2026-08-17: Verify is finding-level with adaptive API caps]] for pool shape, default concurrency, and per-finding CSV rebuild. Deduped-only input, `--limit` as findings, resume, unread→null, and Ctrl+C still stand.

**Decision:** `python -m production verify` is no longer an in-memory overwrite. It reads only `findings_deduplicated.csv` (raw `findings.csv` is refused). Live and dry-run require `--limit N` or `--all`. `--limit` is **findings**, not companies. Default concurrency is 4 companies in flight, findings sequential inside a company. Each finished finding is appended to `findings_verified.jsonl` and `findings_verified.csv` is rebuilt so the spreadsheet can be watched mid-run. Resume skips complete `0`/`1`/permanent-null rows. 429/timeout rows are requeued and do not count as done. `verify --status` prints done / remaining / parked / retryable / spend. Ctrl+C finishes in-flight companies and starts no new ones.

Wrong or thin fetches stay `verification=null`, not `0`: a LinkedIn/Indeed listings rail (`fetch_listings_rail`) and a YouTube watch page with almost no body after chrome (`thin_page_snippet`). The judge does not run on those pages.

**Why:** The old verify loop paid every finding, then wrote the CSV once. A crash threw away the night. Phase B also stamped a K1x LinkedIn rail and thin Tern YouTube intros as hallucinations. Those are unread pages. Folding them into `0` poisons the Stage 2 lie rate.

**Evidence:** User lock 2026-08-16 (limit, append, runner robustness, deduplicated input). Phase B rows: K1x LinkedIn job `4424441175`, Tern `watch?v=2dUAlrrSnSg`. Code: `production/verify.py`, `production/persist.py` verified jsonl helpers, `citation_verification/text.py` `unread_reason`. Tests: `tests/test_production_runner.py` (`test_verify_limit_resumes_and_appends`, `test_verify_requeues_429_and_does_not_repay_complete`), `tests/test_citation_verification_text.py`, `tests/test_citation_verification_live_rules.py`. Offline: `PYTHONPATH=. python3 -m pytest tests/test_citation_verification_*.py tests/test_production_runner.py -q` (88 passed).

**Alternatives rejected:** Keeping the one-shot in-memory verify. Silently falling back to raw `findings.csv`. Treating listings rails or thin YouTube as `verification=0`. Bringing back the literal-anchor package veto.

**Open follow-ups:** `dedupe` must write `findings_deduplicated.csv` before a real verify can start. Paid `--limit 20` smoke after a slice exists. WS9 gold re-score still gated. When invoking from this worktree, pass `--output-root` at the main-tree `outputs/prod` so verify reads the live run.

---

## 2026-08-16: Production dedupe is a derived CSV

**Decision:** `python -m production dedupe` reads `findings.csv` and writes `findings_deduplicated.csv`. Raw is untouched. `run` still writes the exact-key merge only. No LLM. First row in file order wins. `finding_id` stays the raw id. Dropped rows vanish from the derived file. The CLI prints `in` / `out` / `dropped`. `findings_count` on kept rows is the post-squash count for that company.

Squash when the same company has similar tool + similar use, and either (1) the same URL (use-case reword or tool alias), or (2) a different URL with similar evidence that is **not** two primary job postings. ChatGPT vs Copilot on one page stays. Duty splits stay. Cloaked-style iOS vs Android (Wellfound / Ashby / LinkedIn jobs) stay. Jobright / Vaia / ListenNotes mirrors squash. xAI vs VentureBeat stays when evidence overlap is low.

**Why:** Verify should not pay to judge the same CareAsOne sentence twice. File-size gain is tiny (~1%). A derived file is the undo button if the overlap cut is hungry. Different role postings are separate attestations, not one flyer on two boards.

**Evidence:** User lock 2026-08-16 (five product calls). Code: `production/dedupe.py`. Tests: `tests/test_production_dedupe.py`, `test_dedupe_writes_derived_csv_and_leaves_raw`. Copied onto `prod-verifier` 2026-08-17 so one PR can ship `run → dedupe → verify`.

**Alternatives rejected:** Changing `merge_findings` / what `run` writes. An LLM judge. Renumbering `finding_id`. Extra `also_source_urls` or dropped-rows audit file. Squashing Cloaked role clusters. Dropping URL from the key.

**Open follow-ups:** Live slice already has `outputs/prod/sgs/findings_deduplicated.csv` (~31k). Rebuild after the Stage 2 job adds more raw rows. Tune `USE_SIMILAR` / `EVIDENCE_SIMILAR` only if spot-checks look hungry.

---

## 2026-08-17: Verify is finding-level with adaptive API caps

**Decision:** `python -m production verify --concurrency N` is a **finding** thread pool (default **32**), not a company pool. Findings from the same company run in parallel. Under that pool, Perplexity `fetch_url`, OpenAI judge, and Tavily Extract each have an AIMD in-flight cap: start below the ceiling, +1 after 12 successes, halve on 429, sleep `Retry-After` or exponential backoff, retry in-call up to 5 times, then surface a retryable error for batch resume. Browser last-resort stays hard-capped at 2 and off unless `CITATION_VERIFICATION_BROWSER=1`. CSV appends one row per finding; rebuild from jsonl at start and end (last-write-wins). Release the fetch slot before the judge runs so the two APIs do not share one door.

Starting caps: fetch 12 (max 48), judge 20 (max 64), Tavily 8 (max 24).

**Why:** Phase B at 5 companies wide had 0 HTTP 429s. Mean worker time was ~51s because fetch/page-read is slow, not because OpenAI Luna is slow. The old 4-company cap was borrowed from Stage 2 Agent-API 429s. A company with 30 findings then occupied one slot for ~25 minutes. Sitting near Perplexity and OpenAI limits needs finding-level fan-out plus a door that closes on 429 instead of a guessed company width.

**Evidence:** User lock 2026-08-17 (dedupe done; build a verifier that works close to Perplexity and OpenAI rate limits). Phase B wall-clock diagnosis: fetch/Tavily/page-read, not Luna. Code: `citation_verification/limits.py`, `citation_verification/{fetch,judge,backup_fetch}.py`, `production/verify.py`, `production/persist.py` `append_verified_csv`. Tests: `tests/test_citation_verification_limits.py`, `tests/test_citation_verification_judge.py` `test_execute_judge_retries_429_then_succeeds`, `tests/test_production_runner.py` `test_verify_runs_findings_in_parallel`.

**Alternatives rejected:** Keeping company-sequential verify and only raising `--concurrency`. One shared limiter for fetch+judge (would idle OpenAI while Perplexity is the bottleneck). Rebuilding the full CSV after every finding (O(n²) at tens of thousands of rows). Guessing a fixed 48-wide fetch with no backoff.

**Open follow-ups:** Paid smoke landed 2026-08-17: 40 findings (first 20 plus a resume `--limit 20` that correctly took the next 20), 38×`1` / 2×`0` / 0 null, $0.249, 0 HTTP 429s, wall ~2.6 min for the first 20. Two `0`s cited truncated snippets (Legion Health). Do not start `--all` until Khaled asks. WS9 gold still gated.

---

## 2026-08-17: Dedupe CLI lives on the verifier worktree too

**Decision:** Copy `production/dedupe.py` and its tests onto `prod-verifier` so one branch can `run → dedupe → verify`. The squash rules are unchanged from [[2026-08-16: Production dedupe is a derived CSV]] (locked on the live tree). This worktree still refuses to verify raw `findings.csv`.

**Why:** The live checkout (`prod-retry-connection`) has the working dedupe and the derived CSV. This worktree had the real verify and a stub `dedupe`. A PR to `main` needs both commands.

**Evidence:** `production/dedupe.py`, `tests/test_production_dedupe.py`, `test_dedupe_writes_derived_csv_and_leaves_raw`. Live slice: `outputs/prod/sgs/findings.csv` ~32.5k rows, `findings_deduplicated.csv` ~31.1k.

**Alternatives rejected:** Two PRs (verify-only then dedupe-only) while both sides edit `__main__.py`. Running verify from the live tree (still the old thin wrap).

**Open follow-ups:** Paid `--limit 20` smoke. Do not `git checkout` the live folder.

---

## 2026-08-17: Persist page extracts so the judge can re-run without a second scrape

**Decision:** Live `python -m production verify` writes every page extract (success, empty, listings rail, 429) to `outputs/prod/{arch}/pages.jsonl` before the verdict stamp. Last write per **source URL** wins. The operator CSV is unchanged (no snippet column). Default live uses a reusable cache hit and fetches on miss. `--from-cache` never calls Perplexity/Tavily/httpx: it re-runs Luna on findings that already have a page (including complete stamps) and skips the rest without consuming `--limit`. 429/timeout cache rows are audit-only and do not block a refetch. A `0` from a short extract stays a `0`. Unread stays null.

**Why:** The scrape is the slow, paid step. The judge prompt can change. Without a sidecar, every Luna re-run re-pays Perplexity. Putting 32k-character pages on `findings_verified.csv` would wreck the spreadsheet Khaled opens in Excel.

**Evidence:** Code: `production/pages.py`, `production/verify.py`, `citation_verification/runner.py` `cached_page` / `persist_page`. Tests: `tests/test_production_pages.py` (cache write, fetch-explodes still judges from disk, CSV columns unchanged, 429 cache not reused). Offline: `PYTHONPATH=. python3 -m pytest tests/test_citation_verification_*.py tests/test_production_runner.py tests/test_production_dedupe.py tests/test_production_pages.py -q` (116 passed). Paid `--limit 5` from this worktree onto live `outputs/prod/sgs`: rcid 6631 fids 3-7, 4×`1` / 1×`0`, ~81s, 0 HTTP 429s, 8 `pages.jsonl` lines (first fetch plus targeted refetch, last write per URL wins). `--from-cache --limit 5` replay: all `cache=hit`, ~8s, judge-only ~$0.0002-$0.0005/finding.

**Alternatives rejected:** Snippet column on the Excel CSV. Cache key `(rcid, finding_id)` (would re-scrape the same job post for every claim). Folding unread into `0`. Judge-said-truncated → N/A (reverted earlier). Replaying complete stamps on default `--limit` (that flag stays "next N not-done").

**Open follow-ups:** Do not start `--all`. Do not merge until Khaled says so. After merge, run verify from the live folder only once that folder is on a commit that contains this code (merge `main` into `prod-retry-connection` when Stage 2 is in a safe state, or wait until it finishes). Until then, keep verifying from this worktree with `--output-root` at live `outputs/prod`. Rebuild `findings_deduplicated.csv` if raw `findings.csv` has grown. Leave the Legion Health and Entendre `0`s unless Khaled asks to requeue.
