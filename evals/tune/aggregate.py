"""Aggregate arm results under the ~$0.10/company constraint."""

from __future__ import annotations

from typing import Any, Optional

from evals.paths import COST_CONSTRAINT_USD
from evals.tune.matrix import LUNA_BASELINE_PRIOR_USD, TuneArm


def soft_reference_findings_mean(panel_meta: dict[str, Any]) -> float:
    companies = panel_meta.get("companies") or []
    if not companies:
        return 0.0
    total = 0
    for row in companies:
        ref = row.get("march_reference") or {}
        total += int(ref.get("findings_count") or 0)
    return total / len(companies)


def score_arm_dry(
    arm: TuneArm,
    *,
    soft_findings_mean: float,
    n_companies: int,
) -> dict[str, Any]:
    mean_cost = round(LUNA_BASELINE_PRIOR_USD * arm.dry_cost_scale, 4)
    mean_findings = round(soft_findings_mean * arm.dry_findings_scale, 4)
    feasible = mean_cost <= COST_CONSTRAINT_USD
    return {
        "arm_id": arm.arm_id,
        "label": arm.label,
        "factor": arm.factor,
        "knobs": arm.runner_kwargs(),
        "n_companies": n_companies,
        "mean_cost_usd": mean_cost,
        "mean_findings": mean_findings,
        "feasible": feasible,
        "metric_source": {
            "cost": "dry_cost_prior",
            "findings": "dry_soft_reference",
        },
        "dry_cost_scale": arm.dry_cost_scale,
        "dry_findings_scale": arm.dry_findings_scale,
    }


def pick_winner(arm_scores: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    feasible = [row for row in arm_scores if row.get("feasible")]
    if not feasible:
        return None
    # Maximize mean findings, then minimize mean cost, then stable arm_id.
    return max(
        feasible,
        key=lambda r: (
            float(r.get("mean_findings") or 0.0),
            -float(r.get("mean_cost_usd") or 0.0),
            str(r.get("arm_id") or ""),
        ),
    )


def build_summary(
    *,
    architecture: str,
    stage: str,
    panel_id: str,
    dry_run: bool,
    arm_scores: list[dict[str, Any]],
    arm_run_dirs: dict[str, str],
) -> dict[str, Any]:
    winner = pick_winner(arm_scores)
    return {
        "architecture": architecture,
        "stage": stage,
        "panel_id": panel_id,
        "dry_run": dry_run,
        "constraint_usd_per_company": COST_CONSTRAINT_USD,
        "arms": arm_scores,
        "winner_arm_id": winner["arm_id"] if winner else None,
        "winner": winner,
        "arm_run_dirs": arm_run_dirs,
        "metric_note": (
            "Dry run uses labeled cost priors + soft march_reference findings. "
            "Not for production decisions."
            if dry_run
            else "Live metered metrics."
        ),
    }
