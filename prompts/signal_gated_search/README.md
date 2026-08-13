# Signal Gated Search prompts

**Scout semantics (frozen):** presence screen, not adoption extract.  
Design card: `.cursor/plans/sgs-design.md`  
Contracts: [`scout_contracts.md`](./scout_contracts.md)

## Scout prompts (drafted)

| File | Role |
|---|---|
| `scout_shared_preamble.txt` | Shared presence-detector shell |
| `scout_jobs.txt` | Jobs-room presence overlay |
| `scout_owned.txt` | Owned-room presence overlay |
| `scout_third_party.txt` | Third-party presence overlay |

Composer will substitute `{shared_preamble}` and company placeholders.  
API `response_format` will enforce JSON shape; code maps `evidence_bin` → confidence → `signal`.

## Dig prompts

| File | Role |
|---|---|
| `dig_shared_preamble.txt` | Adoption extract (PCS-like). Cold start. Presence is not adoption. |
| `dig_jobs.txt` | Jobs-room extract overlay (PCS `channel_jobs.txt`) |
| `dig_owned.txt` | Owned-room extract overlay (SGS: site + official accounts; diverges from PCS host-only owned) |
| `dig_third_party.txt` | Third-party extract overlay (independent narrators; official company accounts are owned) |

Dig `response_format` reuses the PCS findings schema. Scout URLs are traces only, not dig input.
