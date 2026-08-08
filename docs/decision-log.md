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
- **SGS** — channel scouts with gated dig (later; not PCS)

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

**Status:** Design freeze. Dry-run request builder landed 2026-08-08; live fan-out still open (see Open follow-ups).

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

## Open follow-ups (PCS)

- [x] Freeze prompts + Agent API knobs (design)
- [x] Confirm UAS package is live-ready (no rebuild needed; Tuning #14 proved live path)
- [x] Compose frozen prompts into per-channel Agent API request kwargs (dry-run snapshots)
- [x] Wire live PCS runner: parallel fan-out of 3 channel calls + per-channel cost ledger from usage
- [x] Merge/dedupe: normalize URL + (tool, url) across channels; keep provenance
- [ ] Tiny paid smoke to confirm 3× metered cost ≈ projection
- [ ] Optional Stage B: steps=50 × search=high if we want to re-test deeper search with the steps budget
- [ ] Lock UAS **bake-off** knobs in `evals/configs/unified_adaptive_search.yaml` (package works; yaml still baseline-ish, not Tuning #14 winner)
- [ ] SGS design + implement (next Phase 1 arch)
- [ ] 3-arch bake-off in eval suite (needs live PCS + live SGS + frozen UAS knobs)
