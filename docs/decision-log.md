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

**Open follow-ups:** SGS live fan-out (dry orchestrator is on `sgs/03-dry-runner`). Envelope `channel_id` now wins over a mislabeled model `channel` (hotfix #23).

---

## 2026-08-13: SGS gate reads envelope channel_id before the model channel field

**Decision:** `decide_gate` maps a scout row to a room in this order: `assigned_channel`, then envelope `channel_id`, then the model's `channel` field. A mislabeled or unknown model value must not reroute or drop a valid envelope.

**Why:** Live scout rows will typically carry both tags. Trusting the model undoes the assigned-room override (same policy as Parallel Channel Search forcing parsed findings onto the envelope room) and can send dig spend to the wrong source or skip a real presence hit.

**Evidence:** Bugbot on PR #21 after merge; hotfix PR #23; `signal_gated_search/gate.py`; `tests/test_sgs_gate.py` (`test_envelope_channel_id_wins_over_model_channel`, `test_unknown_model_channel_does_not_drop_valid_envelope`).

**Alternatives rejected:** Preferring `channel` because dry-run fixtures already set it. That field remains the fallback when no envelope is present.

**Open follow-ups:** live runner should keep tagging envelope `channel_id` on scout snapshots.

---

## 2026-08-13: SGS dry orchestrator (scout snapshots then gated dig snapshots)

**Decision:** Dry-run SGS always composes three presence-scout Agent API snapshots, runs the frozen gate, then composes 0–3 cold dig snapshots. Default dry injects empty (`none`) scout rows so N=0. Tests pass `scout_outputs` to inspect N=1/2/3 effort. Ledger always lists `scout_*`. `dig_{channel}` rows appear only when the gate would spend. Live fan-out stays unwired.

**Why:** You can inspect the expensive dig requests (and confirm they do not carry scout URLs) without paying. Empty default scouts stay honest: dry-run did not observe presence, so it does not pretend a dig would fire.

**Evidence:** `signal_gated_search/runner.py`; `tests/test_sgs_runner.py`; `evals.runner.run_panel("sgs", dry_run=True)` on the fixture panel.

**Alternatives rejected:** Always snapshot three hypothetical digs at medium (would hide the gate). Shipping live ThreadPool in the same slice.

**Open follow-ups:** live scout/dig fan-out, merge, `--live` CLI, paid path smokes.

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
- [ ] SGS live fan-out + merge + `--live` CLI
- [ ] SGS paid path smokes (after live PR, user-approved spend)
- [ ] 3-arch bake-off in eval suite (needs live SGS + frozen UAS knobs; PCS live ready)
