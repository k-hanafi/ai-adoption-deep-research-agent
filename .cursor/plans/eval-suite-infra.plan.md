# Eval-suite infra: tuning + archive foundation

Parent: [prod-architecture-eval.plan.md](./prod-architecture-eval.plan.md)

**SoT for this pivot.** Build systematic hyperparam / benchmark infrastructure in `evals/` before locking UAS/PCS/SGS production configs. Phase 1 architecture chat resumes only after dry tuning experiments are runnable.

Supersedes CLI naming in [eval-harness.plan.md](./eval-harness.plan.md) (`run-evals` → three `run-*` modes). That file remains scaffolding / pricing history.

---

## STATUS

| Field | State |
|---|---|
| **Current state** | PR1 merged. PR2 in flight: dark categorized landing + `run-tuning` / `run-benchmarks` / `run-verification` stubs under `evals/instances/`. |
| **Next** | Merge PR2, then PR3: dry `run-tuning --stage screen` real dashboard (arms / constraint / winner). |
| **Exit** | User can run dry `python -m evals run-tuning uas --stage screen`, see a Tuning instance in `open-dashboard`, open its dashboard (arms / constraint / winner). Benchmark + verification archive as stubs. |
| **Out of scope** | Stage 3 judge impl; full 200-company bake-off; freezing final arch YAML as prod winner; paid `--live` matrices in the first three PRs. |

---

## Locked product decisions (2026-08-05)

| Topic | Choice |
|---|---|
| Merge style | Sequential PRs onto `main` (Bugbot each, then merge, then next) |
| Visual system | Classifier Eval Suite design language (dark, dense, metadata sublines). Three category sections on the landing. |
| CLI | `run-tuning` / `run-benchmarks` / `run-verification` + `cost-preview` + `open-dashboard`. **No `run-evals`.** |
| Instance identity | Per-category run number + date + time, e.g. `Tuning #3 · Aug 5, 2026 at 10:44 AM` |
| Artifact root | Everything under `evals/` (standalone). Generated archive at `evals/instances/`. |
| MVP depth | Real **tuning** dashboard; benchmark + verification **stubs** only |
| Dry metrics | Labeled proxies (cost priors + soft march references) until live wiring |
| Methodology | Held-out tuning panel vs future bake-off panel. Stage A OFAT screen → Stage B small factorial. Mean `$/company ≤ ~$0.10` (drop if `> ~$0.105`). Maximize mean findings among feasible. `k≥2` on live winner later. |

---

## User loop

1. `python -m evals run-{tuning\|benchmarks\|verification} …` → one archived instance.
2. `python -m evals open-dashboard` → `evals/instances/index.html` (Tuning / Benchmark / Verification).
3. Click row → that instance’s `dashboard.html`.

---

## PR plan (3 sequential)

| PR | Branch | Scope |
|---|---|---|
| **PR1** | `cursor/eval-infra-plans-e253` | Plans + STATUS pivot only (this milestone) |
| **PR2** | `cursor/eval-infra-landing-cli-e253` | `evals/instances` layout, dark landing, CLI trio writing stubs, remove `run-evals` |
| **PR3** | `cursor/eval-infra-tuning-screen-e253` | UAS knob plumbing, matrix cost-preview, real dry Stage A `run-tuning` dashboard |

---

## Stage A screen matrix (PR3)

Baseline: Luna `medium`, `max_steps=10`, `reasoning.effort=medium`, search depth `medium`.

| Arm id | Change |
|---|---|
| `uas_screen_baseline` | none |
| `uas_screen_steps_15` | `max_steps=15` |
| `uas_screen_search_high` | search depth high |
| `uas_screen_effort_high` | `reasoning.effort=high` |

---

## Bake-off constraints (shape only; Phase 3 owns n)

Paired companies across UAS/PCS/SGS. Ideal 100+100, likely 50+50. Eval spend ≤ $150. Never tune on bake-off IDs. See [phase-3-eval-suite.plan.md](./phase-3-eval-suite.plan.md).

---

## Changelog

- 2026-08-05: Created for sequencing pivot. Locked UX/CLI/artifact decisions. Three-PR ship plan.
