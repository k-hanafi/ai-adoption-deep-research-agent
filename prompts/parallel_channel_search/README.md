# Parallel Channel Search prompts

**Status:** draft for review (DESIGN ONLY). Not wired into the live PCS runner yet. Not a prod freeze.

## Layout

| File | Role |
|---|---|
| `shared_preamble.txt` | Shared mission, sibling map, use-vs-sell, standards, JSON schema |
| `channel_jobs.txt` | Jobs specialist contract (`{shared_preamble}` placeholder) |
| `channel_owned.txt` | Owned specialist contract |
| `channel_third_party.txt` | Third-party specialist contract |

Compose at runtime: expand `{shared_preamble}` from `shared_preamble.txt`, then fill company fields (`company_id`, `company_name`, `homepage_url`, `short_description`).

## Design rules baked in

- Equal-depth specialists; prompt-only targeting (no domain filter allowlists)
- Each agent knows the overall goal + sibling rooms; no UAS/SGS language
- Source-shape steering only (where to look), not March finding few-shots (what adoption looks like)
- Sibling rooms steer **search budget**, not a veto: report qualifying evidence even if off-room; merge dedupes
- Hard exclude remains use-vs-sell only

Evidence basis: `.cursor/plans/pcs-march-channel-evidence.md`.
