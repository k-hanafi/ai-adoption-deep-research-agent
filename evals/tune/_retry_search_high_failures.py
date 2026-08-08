"""Retry only failed companies on the search=high re-run, then re-patch Tuning #14."""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import time
from pathlib import Path
from typing import Any

from contracts.types import CompanyInput
from evals.panel import load_panel, load_panel_companies
from evals.paths import TUNING_PANEL_PATH
from evals.tune.aggregate import build_summary, pick_winner, score_arm_live
from evals.tune.artifacts import write_tuning_bundle
from evals.tune.dashboard import render_tuning_dashboard
from evals.tune.matrix import stage_a_screen_arms
from unified_adaptive_search.agent_call import require_api_key

ARM_ID = "uas_screen_search_high"
INSTANCE = Path("evals/instances/tuning/014_2026-08-07_1045")
RUN_DIR = Path("evals/runs/2026-08-07_unified-adaptive-search_k1_152741_2e54b9")
TIMEOUT = 480.0
MAX_ATTEMPTS = 5
RETRY_SLEEP_S = 15.0


def _worker_run(company_dict: dict[str, Any], knobs: dict[str, Any], q: mp.Queue) -> None:
    try:
        from evals.architectures import run_company

        company = CompanyInput.from_mapping(company_dict)
        result = run_company(
            "unified-adaptive-search",
            company,
            dry_run=False,
            **knobs,
        )
        q.put({"ok": True, "row": result.to_dict(), "traces": result.traces})
    except BaseException as exc:  # noqa: BLE001
        q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _call_with_hard_timeout(
    company: CompanyInput,
    knobs: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    q: mp.Queue = ctx.Queue()
    company_dict = {
        "rcid": company.rcid,
        "name": company.name,
        "homepage_url": company.homepage_url,
        "short_description": company.short_description,
        "research_priority_score": company.research_priority_score,
        "online_presence_score": company.online_presence_score,
        "category_list": company.category_list,
    }
    proc = ctx.Process(target=_worker_run, args=(company_dict, knobs, q))
    proc.start()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join(10)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
        err = f"hard_timeout: exceeded {timeout:.0f}s"
        return {
            "row": {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": err,
                "traces": {
                    "strategy": "unified_adaptive_search",
                    "phase": "live_error",
                    "error": err,
                },
                "stub": False,
                "dry_run": False,
            },
            "traces": {
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "error": err,
            },
        }
    if q.empty():
        err = "hard_timeout: worker exited with no result"
        return {
            "row": {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": err,
                "traces": {
                    "strategy": "unified_adaptive_search",
                    "phase": "live_error",
                    "error": err,
                },
                "stub": False,
                "dry_run": False,
            },
            "traces": {
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "error": err,
            },
        }
    payload = q.get()
    if not payload.get("ok"):
        err = payload.get("error") or "unknown worker error"
        return {
            "row": {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": err,
                "traces": {
                    "strategy": "unified_adaptive_search",
                    "phase": "live_error",
                    "error": err,
                },
                "stub": False,
                "dry_run": False,
            },
            "traces": {
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "error": err,
            },
        }
    return {"row": payload["row"], "traces": payload["traces"]}


def _is_fail(row: dict[str, Any]) -> bool:
    return bool(row.get("error") or (row.get("traces") or {}).get("phase") == "live_error")


def main() -> None:
    require_api_key()
    arm = next(a for a in stage_a_screen_arms() if a.arm_id == ARM_ID)
    knobs = {**arm.runner_kwargs(), "timeout": TIMEOUT}
    panel_path = TUNING_PANEL_PATH
    panel_meta = load_panel(panel_path)
    companies = load_panel_companies(panel_path)

    run_dir = RUN_DIR.resolve()
    pred_path = run_dir / "predictions.jsonl"
    rows = [
        json.loads(line)
        for line in pred_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_index = {int(r["panel_index"]): r for r in rows}
    failed = sorted(i for i, r in by_index.items() if _is_fail(r))
    print(
        f"Retrying {len(failed)} failed search=high companies in {run_dir.name}",
        flush=True,
    )
    print(f"Knobs: {knobs}", flush=True)
    print(f"Indexes: {failed}", flush=True)

    for panel_index in failed:
        company = companies[panel_index]
        last_err = by_index[panel_index].get("error")
        success = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(
                f"START idx={panel_index} attempt={attempt}/{MAX_ATTEMPTS} "
                f"rcid={company.rcid} {company.name} prev={last_err}",
                flush=True,
            )
            if attempt > 1:
                time.sleep(RETRY_SLEEP_S)
            out = _call_with_hard_timeout(company, knobs, timeout=TIMEOUT)
            row = out["row"]
            traces = out["traces"]
            row["repeat"] = 1
            row["panel_index"] = panel_index
            row["company_name"] = company.name
            row["rcid"] = company.rcid
            by_index[panel_index] = row
            (run_dir / "traces" / f"{panel_index:03d}_{company.rcid}_r1.json").write_text(
                json.dumps(traces, indent=2) + "\n", encoding="utf-8"
            )
            ordered = [by_index[i] for i in sorted(by_index)]
            with pred_path.open("w", encoding="utf-8") as f:
                for r in ordered:
                    f.write(json.dumps(r) + "\n")
            if _is_fail(row):
                last_err = row.get("error")
                print(f"  FAIL {last_err}", flush=True)
                continue
            print(
                f"  OK cost={row.get('cost_usd')} findings={row.get('findings_count')}",
                flush=True,
            )
            success = True
            break
        if not success:
            print(
                f"  GIVE UP idx={panel_index} rcid={company.rcid} err={last_err}",
                flush=True,
            )

    ordered = [by_index[i] for i in range(len(companies))]
    with pred_path.open("w", encoding="utf-8") as f:
        for r in ordered:
            f.write(json.dumps(r) + "\n")

    n_err = sum(1 for r in ordered if _is_fail(r))
    scored = {
        "architecture": "unified-adaptive-search",
        "panel_id": panel_meta.get("panel_id"),
        "n_companies": len(companies),
        "n_predictions": len(ordered),
        "k": 1,
        "total_findings": sum(int(r.get("findings_count") or 0) for r in ordered),
        "total_findings_all_repeats": sum(
            int(r.get("findings_count") or 0) for r in ordered
        ),
        "total_cost_usd": sum(float(r.get("cost_usd") or 0.0) for r in ordered),
        "n_errors": n_err,
        "phase": "eval_infra",
        "note": (
            f"search=high failure retry: hard_timeout={TIMEOUT}s "
            f"attempts<={MAX_ATTEMPTS} backoff={RETRY_SLEEP_S}s"
        ),
    }
    (run_dir / "scored.json").write_text(
        json.dumps(scored, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": run_dir.name,
                "n_errors": n_err,
                "rerun_of": ARM_ID,
                "failure_retry": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Retry complete: errors={n_err}/{len(ordered)} "
        f"mean_cost={scored['total_cost_usd']/len(ordered):.4f} "
        f"mean_findings={scored['total_findings']/len(ordered):.2f}",
        flush=True,
    )

    instance_dir = INSTANCE.resolve()
    summary = json.loads((instance_dir / "summary.json").read_text(encoding="utf-8"))
    arms = stage_a_screen_arms()
    arm_scores = []
    arm_run_dirs: dict[str, Path] = {}
    for a in arms:
        if a.arm_id == ARM_ID:
            arm_run_dirs[a.arm_id] = run_dir
            arm_scores.append(
                score_arm_live(a, run_dir=run_dir, n_companies=len(companies))
            )
            continue
        prior = next(
            (row for row in (summary.get("arms") or []) if row.get("arm_id") == a.arm_id),
            None,
        )
        if prior is None:
            raise RuntimeError(f"missing prior arm {a.arm_id}")
        prior_run = Path(str(prior.get("run_dir")))
        if not prior_run.is_absolute():
            prior_run = Path.cwd() / prior_run
        if not prior_run.is_dir():
            prior_run = instance_dir / "arms" / a.arm_id
        arm_run_dirs[a.arm_id] = prior_run
        if (prior_run / "scored.json").is_file():
            arm_scores.append(
                score_arm_live(a, run_dir=prior_run, n_companies=len(companies))
            )
        else:
            arm_scores.append(prior)

    summary_core = build_summary(
        architecture=str(summary.get("architecture") or "unified-adaptive-search"),
        stage=str(summary.get("stage") or "screen"),
        panel_id=str(summary.get("panel_id") or panel_meta.get("panel_id")),
        dry_run=False,
        arm_scores=arm_scores,
        arm_run_dirs={k: str(v) for k, v in arm_run_dirs.items()},
    )
    for key in (
        "kind",
        "n",
        "title",
        "full_name",
        "cli",
        "stub",
        "created_at",
        "git_sha",
        "notes",
    ):
        if key in summary:
            summary_core[key] = summary[key]
    summary_core["notes"] = (
        str(summary.get("notes") or "")
        + f" Retried {len(failed)} search=high failures "
        f"({n_err} still failing after retry)."
    ).strip()

    dest_arm = instance_dir / "arms" / ARM_ID
    if dest_arm.exists():
        shutil.rmtree(dest_arm)

    updated = write_tuning_bundle(
        instance_dir,
        panel_path=panel_path,
        panel_meta=panel_meta,
        arms=arms,
        arm_scores=arm_scores,
        arm_run_dirs=arm_run_dirs,
        summary=summary_core,
    )
    (instance_dir / "dashboard.html").write_text(
        render_tuning_dashboard(
            title=str(updated.get("title") or summary.get("title")),
            summary=updated,
            instance_dir=instance_dir,
        ),
        encoding="utf-8",
    )
    winner = pick_winner(arm_scores)
    print(f"Patched {instance_dir}", flush=True)
    print(f"Dashboard: {instance_dir / 'dashboard.html'}", flush=True)
    print(f"Winner now: {winner.get('arm_id') if winner else None}", flush=True)


if __name__ == "__main__":
    main()
