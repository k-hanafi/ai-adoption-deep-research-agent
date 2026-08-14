# SGS scout prompt contracts (presence screen)

**Status:** Live Agent instructions are `scout_*.txt`. Presence bar amended 2026-08-13: existence check, not source-quality or adoption.  
**SoT:** `.cursor/plans/sgs-design.md`  
**Separation of concerns:** scouts decide **channel source presence**; digs decide **GenAI adoption**. Never ask scouts for adoption findings.

Shared rules for all three contracts:
- No UAS / PCS / SGS product names in prompts.
- No dollar budget / effort ladder wording in prompts (code owns the ladder).
- Prefer recall: if this room exists on the web for this company, escalate. Do not require adoption evidence or a polished source.
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
- Returns adoption findings, tool names as the main claim, or full finding rows
- Omits URLs while claiming moderate/strong
- Emits `none` solely because the homepage was missing, down, or not returned by search
- Emits `none` because pages in the room are thin, stale, email-only, or silent about AI
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

GOAL: Detect whether **any jobs/hiring pages exist** for this company on the public web (ATS, careers, aggregators, LinkedIn jobs, email-us hiring pages). Measurable success: escalate when anything jobs-related exists; skip only when there is no jobs footprint at all. Do not require open roles, a polished ATS, or AI mentions.

CONSTRAINTS:
- Shared scout shell constraints
- Count as present: ATS, `/careers` or `/jobs` (including empty or email-only), job-board/aggregator listings that name this employer (Indeed, LinkedIn Jobs, JobRight, Built In, Techstars, YC Work at a Startup, Wellfound, and similar)
- Do not require that postings mention AI tools (that is the dig’s job)
- Do not ignore an aggregator because its brand contains "AI"

FORMAT:
- Shared schema with `"channel": "jobs"`
- Prefer URLs that point at a jobs-related page (board, listing, or hiring contact page)

FAILURE:
- Shared failures
- Emits `none` because hiring is email-only, the board is empty, or listings look stale
- Misses aggregator listings or an obvious ATS / careers page (false negative)
- Treats JobRight (or similar) as adoption evidence or as a reason to skip

---

## Scout: owned

### Contract

GOAL: Detect whether this company has a **website or official first-party accounts**. A thin landing page still counts. Measurable success: escalate when a site or official LinkedIn/YouTube/GitHub/X exists; skip only when there is no first-party publishing at all.

CONSTRAINTS:
- Shared scout shell constraints
- Company-controlled site **or** official company accounts (LinkedIn company page, YouTube/Vimeo channel, GitHub org, X, company-operated newsletter/CMS)
- Homepage is identity, not a required proof. Unreachable site is not `none` if official accounts exist
- Waitlist / one-pager **does** count as a website
- Employee personal profiles are not official accounts (third_party)

FORMAT:
- Shared schema with `"channel": "owned"`
- URLs may be the site (even a thin root) **or** official account URLs

FAILURE:
- Shared failures
- Emits `none` because the site is a waitlist or one-pager
- Emits `none` solely because the homepage was missing, down, or not returned by search
- Treats a live official LinkedIn company page or company YouTube channel as third_party
- Treats employee personal LinkedIn as an official company account

---

## Scout: third_party

### Contract

GOAL: Detect whether **any independent pages about this company exist** (news, interviews, writeups, vendor stories, personal posts). Measurable success: escalate when independent pages exist; skip empty directory stubs and official company accounts (those are owned).

CONSTRAINTS:
- Shared scout shell constraints
- Empty directory stubs (thin Crunchbase/LinkedIn-style cards with no article) are `none`
- One independent page can be enough for moderate
- Official company LinkedIn / YouTube / GitHub / X are owned, not third_party
- Do not require the coverage to already prove GenAI adoption
- Homepage down is not a reason to skip this room; search by company name

FORMAT:
- Shared schema with `"channel": "third_party"`
- URLs should be independent narrators, not the company homepage or official company accounts

FAILURE:
- Shared failures
- Escalates on empty directory stubs with no article body
- Misses independent pages that exist (false negative)
- Treats the company’s own blog or official YouTube/LinkedIn as third_party (wrong room; that is owned)
- Emits `none` solely because the homepage was not retrieved

---

## Next step (prompts)

Turn each contract into `scout_shared_preamble.txt` + `scout_{jobs,owned,third_party}.txt` Agent instructions (still no dig prompts here). Keep warm-start urls/snippets stable so digs can reuse them.
