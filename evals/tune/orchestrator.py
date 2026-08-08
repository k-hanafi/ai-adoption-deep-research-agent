"""Orchestrate run-tuning stages and archive a Tuning instance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from evals.archive import create_instance
from evals.architectures import resolve_architecture
from evals.panel import load_panel
from evals.paths import MAX_USD_PER_TUNING_RUN, TUNING_PANEL_PATH
from evals.runner import run_panel
from evals.tune.aggregate import (
    build_summary,
    score_arm_dry,
    score_arm_live,
    soft_reference_findings_mean,
)
from evals.tune.artifacts import (
    begin_partial_bundle,
    discard_partial_bundle,
    persist_completed_arm,
    write_tuning_bundle,
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
            f"(ceiling ${MAX_USD_PER_TUNING_RUN:.0f} per tuning run)."
        )

    panel_path = Path(panel) if panel else TUNING_PANEL_PATH
    panel_meta = load_panel(panel_path)
    companies = panel_meta.get("companies") or []
    n_companies = len(companies)
    if n_companies < 1:
        raise ValueError(f"tuning panel is empty: {panel_path}")

    # Paid path only: abort before arms if matrix prior exceeds the run ceiling.
    # Dry runs stay free so you can still exercise the harness without a budget.
    # Lazy import avoids cost_preview ↔ tune package cycle at module load.
    if not dry_run:
        from evals.cost_preview import preview_matrix

        preview = preview_matrix(
            architecture,
            matrix=stage,
            k=1,
            panel=panel_path,
        )
        estimate = float(preview.estimated_total_usd)
        if estimate > MAX_USD_PER_TUNING_RUN:
            raise ValueError(
                f"Tuning matrix estimate ${estimate:.2f} exceeds "
                f"MAX_USD_PER_TUNING_RUN=${MAX_USD_PER_TUNING_RUN:.2f}. "
                "Aborting before paid arms. Shrink the panel/matrix or raise "
                "the ceiling in evals/paths.py after an explicit budget change."
            )
        print(
            f"Cost gate passed: matrix estimate ${estimate:.2f} "
            f"<= ceiling ${MAX_USD_PER_TUNING_RUN:.2f}."
        )

    soft_mean = soft_reference_findings_mean(panel_meta)
    arms = stage_a_screen_arms()
    arm_scores: list[dict[str, Any]] = []
    arm_run_dirs: dict[str, Path] = {}

    # Crash safety: completed arms land under evals/runs/_tuning_partial_*/
    # even if the process dies before the Tuning instance is archived.
    partial_dir = begin_partial_bundle(
        panel_path=panel_path,
        panel_meta=panel_meta,
        arms=arms,
        stage=stage,
        architecture=spec.cli_key,
        dry_run=dry_run,
    )
    print(f"Partial tuning bundle (crash recovery): {partial_dir}")
    bundle_finalized_in_partial = False
    partial_discarded = False
    instance_dir: Optional[Path] = None

    try:
        for arm in arms:
            run_dir = run_panel(
                spec.cli_key,
                panel=panel_path,
                k=1,
                dry_run=dry_run,
                runner_kwargs=arm.runner_kwargs(),
            )
            arm_run_dirs[arm.arm_id] = run_dir
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
            persist_completed_arm(
                partial_dir,
                arm_id=arm.arm_id,
                run_dir=run_dir,
                score=scored,
            )

        summary_core = build_summary(
            architecture=spec.cli_key,
            stage=stage,
            panel_id=str(panel_meta.get("panel_id") or panel_path.name),
            dry_run=dry_run,
            arm_scores=arm_scores,
            arm_run_dirs={k: str(v) for k, v in arm_run_dirs.items()},
        )

        # Finalize the self-contained bundle into the partial dir BEFORE catalog
        # archive, so a create_instance / promote failure cannot lose arm artifacts.
        write_tuning_bundle(
            partial_dir,
            panel_path=panel_path,
            panel_meta=panel_meta,
            arms=arms,
            arm_scores=arm_scores,
            arm_run_dirs=arm_run_dirs,
            summary={
                **summary_core,
                "title": "partial-tuning-bundle",
                "kind": "tuning",
                "dry_run": dry_run,
            },
        )
        bundle_finalized_in_partial = True

        def _dashboard(title: str, summary: dict[str, Any]) -> str:
            return render_tuning_dashboard(
                title=title, summary=summary, instance_dir=None
            )

        live_flag = "" if dry_run else " --live"
        notes = (
            "Stage A OFAT screen (dry proxies). Self-contained artifact bundle."
            if dry_run
            else "Stage A OFAT screen (live metered usage). Self-contained artifact bundle."
        )
        instance_dir = create_instance(
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
                **{
                    k: summary_core[k]
                    for k in ("arms", "winner", "arm_run_dirs", "metric_note")
                },
            },
            dashboard_renderer=_dashboard,
        )

        # Promote durable files into the archived Tuning instance.
        summary = json.loads((instance_dir / "summary.json").read_text(encoding="utf-8"))
        updated = write_tuning_bundle(
            instance_dir,
            panel_path=panel_path,
            panel_meta=panel_meta,
            arms=arms,
            arm_scores=arm_scores,
            arm_run_dirs=arm_run_dirs,
            summary=summary,
        )
        # Drop staging as soon as the instance holds the full bundle (do not wait
        # on the cosmetic dashboard rewrite).
        discard_partial_bundle(partial_dir)
        partial_discarded = True

        (instance_dir / "dashboard.html").write_text(
            render_tuning_dashboard(
                title=str(updated["title"]),
                summary=updated,
                instance_dir=instance_dir,
            ),
            encoding="utf-8",
        )
        return instance_dir
    except Exception:
        if not partial_discarded:
            # Leave partial_dir for recovery when the instance may be incomplete.
            hint = (
                "Full bundle is already in the partial dir (archive/promote failed)."
                if bundle_finalized_in_partial
                else "Completed arms (if any) are under the partial dir."
            )
            print(
                f"Tuning stopped early. {hint} Path: {partial_dir}",
                flush=True,
            )
        elif instance_dir is not None:
            print(
                f"Instance bundle is complete at {instance_dir}; "
                "a later dashboard refresh failed.",
                flush=True,
            )
        raise
