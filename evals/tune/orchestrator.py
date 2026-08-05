"""Orchestrate run-tuning stages and archive a Tuning instance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from evals.archive import create_instance
from evals.architectures import resolve_architecture
from evals.panel import load_panel
from evals.paths import TUNING_PANEL_PATH
from evals.runner import run_panel
from evals.tune.aggregate import (
    build_summary,
    score_arm_dry,
    score_arm_live,
    soft_reference_findings_mean,
)
from evals.tune.dashboard import render_tuning_dashboard
from evals.tune.matrix import stage_a_screen_arms
from unified_adaptive_search.agent_call import require_api_key


def run_tuning(
    architecture: str,
    *,
    stage: str = "screen",
    dry_run: bool = True,
    panel: Optional[Path] = None,
    cli: str = "",
) -> Path:
    """Run a tuning stage and archive under evals/instances/tuning/."""
    if stage == "factorial":
        raise NotImplementedError(
            "Stage B factorial is scaffolded for a follow-up. "
            "Use --stage screen for the Stage A MVP."
        )
    if stage != "screen":
        raise ValueError(f"Unknown tuning stage {stage!r}")

    spec = resolve_architecture(architecture)
    if spec.cli_key != "unified-adaptive-search":
        raise ValueError(
            "Stage A screen MVP supports UAS only "
            f"(got {spec.cli_key!r}). PCS/SGS tuning comes later."
        )

    if not dry_run:
        # Refuse early with a clear message before any arm loop starts.
        require_api_key()
        print(
            "Live tuning: paid UAS panel runs with metered usage. "
            "Run `python3 -m evals cost-preview uas --matrix screen` first "
            "and approve spend before large matrices."
        )

    panel_path = Path(panel) if panel else TUNING_PANEL_PATH
    panel_meta = load_panel(panel_path)
    companies = panel_meta.get("companies") or []
    n_companies = len(companies)
    if n_companies < 1:
        raise ValueError(f"tuning panel is empty: {panel_path}")

    soft_mean = soft_reference_findings_mean(panel_meta)
    arms = stage_a_screen_arms()
    arm_scores: list[dict[str, Any]] = []
    arm_run_dirs: dict[str, str] = {}

    for arm in arms:
        run_dir = run_panel(
            spec.cli_key,
            panel=panel_path,
            k=1,
            dry_run=dry_run,
            runner_kwargs=arm.runner_kwargs(),
        )
        arm_run_dirs[arm.arm_id] = str(run_dir)
        if dry_run:
            scored = score_arm_dry(
                arm,
                soft_findings_mean=soft_mean,
                n_companies=n_companies,
            )
        else:
            scored = score_arm_live(
                arm,
                run_dir=run_dir,
                n_companies=n_companies,
            )
        scored["run_dir"] = str(run_dir)
        arm_scores.append(scored)

    summary_core = build_summary(
        architecture=spec.cli_key,
        stage=stage,
        panel_id=str(panel_meta.get("panel_id") or panel_path.name),
        dry_run=dry_run,
        arm_scores=arm_scores,
        arm_run_dirs=arm_run_dirs,
    )

    def _dashboard(title: str, summary: dict[str, Any]) -> str:
        return render_tuning_dashboard(title=title, summary=summary)

    live_flag = "" if dry_run else " --live"
    notes = (
        "Stage A OFAT screen (dry proxies)."
        if dry_run
        else "Stage A OFAT screen (live metered usage)."
    )
    return create_instance(
        kind="tuning",
        cli=cli
        or f"python -m evals run-tuning {spec.short_alias} --stage {stage}{live_flag}",
        architecture=spec.cli_key,
        full_name=spec.full_name,
        dry_run=dry_run,
        stub=False,
        notes=notes,
        extra={
            "stage": stage,
            "panel_id": summary_core["panel_id"],
            "n_arms": len(arms),
            "winner_arm_id": summary_core.get("winner_arm_id"),
            "constraint_usd_per_company": summary_core["constraint_usd_per_company"],
            **{k: summary_core[k] for k in ("arms", "winner", "arm_run_dirs", "metric_note")},
        },
        dashboard_renderer=_dashboard,
    )
