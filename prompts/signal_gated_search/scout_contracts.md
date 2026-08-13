# SGS scout prompt contracts (presence screen)

**Status:** Live Agent instructions are `scout_*.txt`. Owned-surface detail amended 2026-08-13 (official accounts; homepage is not a gate).  
**SoT:** `.cursor/plans/sgs-design.md`  
**Separation of concerns:** scouts decide **channel source presence**; digs decide **GenAI adoption**. Never ask scouts for adoption findings.

Shared rules for all three contracts:
- No UAS / PCS / SGS product names in prompts.
- No dollar budget / effort ladder wording in prompts (code owns the ladder).
- Prefer recall on real presence: escalate most diggable sources (`τ=0.5` ⇒ moderate+).
- No URL ⇒ cannot be `moderate`/`strong`; force `none`.
- Homepage is identity, not a gate. Unreachable homepage is not by itself `none`.
- `rationale` must be about presence of a source surface, not about AI tools.

---

## Shared scout shell

### Contract

GOAL: For one assigned channel, decide whether a diggable source surface exists for this company, with enough fidelity that a later dig can search that room productively. Success = correct presence/absence calls on a labeled presence panel at the frozen operating point (escalate moderate+).

CONSTRAINTS:
- Agent `preset=fast` only; smoke-test depth, not multi-hop research
- Tools: `web_search` only (no `fetch_url` on scouts)
- Do not extract or judge internal GenAI adoption
- Do not dig sibling channels; soft awareness only to avoid mis-filing rooms
- Homepage is identity, not a required proof; do not emit `none` solely because it was not retrieved
- Output must be machine JSON matching the schema below

FORMAT:
- Single JSON object per scout call (see schema)
- `evidence_bin` ∈ {none, weak, moderate, strong}
- `confidence` must match the bin map: none=0.0, weak=0.35, moderate=0.65, strong=0.90
- `signal=true` iff bin is moderate or strong (at default τ=0.5); still emit bin+confidence so code can re-threshold
- `urls` / `snippets`: 1–3 presence proofs (careers URL, docs hub, article URL, etc.)

FAILURE (any of these = bad scout):
- Sets `signal=true` because the company “seems AI-related” with no channel source
- Sets `signal=true` on a one-page waitlist / empty careers stub / directory-only hit
- Returns adoption findings, tool names as the main claim, or full finding rows
- Omits URLs while claiming moderate/strong
- Emits `none` solely because the homepage was missing, down, or not returned by search
- Confuses rooms (e.g. treats a news article as owned, or a careers page as third_party) without noting the correct room

### Schema

```json
{
  "channel": "jobs|owned|third_party",
  "signal": true,
  "evidence_bin": "none|weak|moderate|strong",
  "confidence": 0.0,
  "urls": ["https://..."],
  "snippets": ["short presence proof..."],
  "rationale": "one sentence on why this channel is/is not diggable"
}
```

---

## Scout: jobs

### Contract

GOAL: Detect whether this company has a **real jobs/careers hiring surface** worth a jobs-channel dig (ATS, careers page with roles, or active job listings). Measurable success: high recall on companies with real boards; low escalate rate on companies with no hiring surface.

CONSTRAINTS:
- Shared scout shell constraints
- Count as present: Greenhouse/Lever/Ashby/Workable/etc., `/careers` or `/jobs` with actual roles, major job-board listings clearly for this employer
- Do not require that postings mention AI tools (that is the dig’s job)

FORMAT:
- Shared schema with `"channel": "jobs"`
- Prefer URLs that point at the board or a specific listing index

FAILURE:
- Shared failures
- Escalates on “We’re hiring! email jobs@…” with no board
- Escalates on an empty careers template with zero roles
- Misses an obvious live ATS / careers index (false negative)

---

## Scout: owned

### Contract

GOAL: Detect whether the company has a **diggable first-party narrator surface** (company site and/or official company accounts) so an owned dig has somewhere the company itself publishes. Measurable success: escalate when the site OR official LinkedIn/YouTube/GitHub/X exists; do not emit none just because the homepage did not load.

CONSTRAINTS:
- Shared scout shell constraints
- Company-controlled site **or** official company accounts (LinkedIn company page, YouTube/Vimeo channel, GitHub org, X, company-operated newsletter/CMS)
- Homepage is identity, not a required proof. Unreachable or stub site is not `none` if official accounts exist
- Stealth waitlist / empty official shells do **not** count
- Employee personal profiles are not official accounts (third_party)

FORMAT:
- Shared schema with `"channel": "owned"`
- URLs may be site hubs (docs, blog, about) **or** official account URLs. Do not require the marketing root.

FAILURE:
- Shared failures
- Escalates on waitlist-only / “coming soon” one-pagers with no official accounts
- Emits `none` solely because the homepage was missing, down, or not returned by search
- Rejects a small but real docs/blog site as “too small” (over-strict FN)
- Treats a live official LinkedIn company page or company YouTube channel as third_party
- Treats employee personal LinkedIn as an official company account

---

## Scout: third_party

### Contract

GOAL: Detect whether **meaningful independent coverage** of this company exists (news, independent interviews, vendor stories), such that a third_party dig has something to read. Measurable success: skip stealth firms with zero footprint; escalate when real coverage exists; do not score official company accounts as third_party.

CONSTRAINTS:
- Shared scout shell constraints
- Directory stubs (thin Crunchbase/LinkedIn-only cards with no narrative) are not enough alone
- One substantive article/podcast/case study can be enough for moderate
- Official company LinkedIn / YouTube / GitHub / X are owned, not third_party
- Do not require the coverage to already prove GenAI adoption
- Homepage down is not a reason to skip this room; search by company name

FORMAT:
- Shared schema with `"channel": "third_party"`
- URLs should be independent narrators (press, independent interview, case study), not the company homepage or official company accounts

FAILURE:
- Shared failures
- Escalates on empty profile stubs / tag pages with no article body
- Misses obvious press coverage (false negative)
- Treats the company’s own blog or official YouTube/LinkedIn as third_party (wrong room; that is owned)
- Emits `none` solely because the homepage was not retrieved

---

## Next step (prompts)

Turn each contract into `scout_shared_preamble.txt` + `scout_{jobs,owned,third_party}.txt` Agent instructions (still no dig prompts here). Keep warm-start urls/snippets stable so digs can reuse them.
