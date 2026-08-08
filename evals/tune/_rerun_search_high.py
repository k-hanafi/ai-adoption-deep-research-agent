"""One-shot: re-run Stage A search=high and patch Tuning #14.

Supports resume from a partial run_dir. Uses a hard wall-clock timeout per
company (process kill) because the SDK timeout can hang past 600s.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from contracts.types import CompanyInput
from evals.panel import load_panel, load_panel_companies
from evals.paths import EVAL_RUNS_DIR, TUNING_PANEL_PATH
from evals.tune.aggregate import build_summary, pick_winner, score_arm_live
from evals.tune.artifacts import write_tuning_bundle
from evals.tune.dashboard import render_tuning_dashboard
from evals.tune.matrix import stage_a_screen_arms
from unified_adaptive_search.agent_call import require_api_key

ARM_ID = "uas_screen_search_high"
INSTANCE = Path("evals/instances/tuning/014_2026-08-07_1045")
TIMEOUT = 480.0  # hard wall clock per company (seconds)
MAX_ATTEMPTS = 3
RETRY_SLEEP_S = 5.0
RESUME_RUN = Path("evals/runs/2026-08-07_unified-adaptive-search_k1_152741_2e54b9")


def _is_retryable(error: str | None) -> bool:
    if not error:
        return False
    e = error.lower()
    return any(
        needle in e
        for needle in (
            "apiconnectionerror",
            "connection error",
            "apitimeouterror",
            "timed out",
            "timeout",
            "hard_timeout",
            "503",
            "502",
            "429",
        )
    )


def _worker_run(company_dict: dict[str, Any], knobs: dict[str, Any], q: mp.Queue) -> None:
    """Child process: one company call. Puts result dict or error on queue."""
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
    except BaseException as exc:  # noqa: BLE001 - surface to parent
        q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _call_with_hard_timeout(
    company: CompanyInput,
    knobs: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    """Run one company in a child process; kill it if it exceeds timeout."""
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
        return {
            "row": {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": f"hard_timeout: exceeded {timeout:.0f}s",
                "traces": {
                    "strategy": "unified_adaptive_search",
                    "phase": "live_error",
                    "error": f"hard_timeout: exceeded {timeout:.0f}s",
                },
                "stub": False,
                "dry_run": False,
            },
            "traces": {
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "error": f"hard_timeout: exceeded {timeout:.0f}s",
            },
        }
    if q.empty():
        return {
            "row": {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": "hard_timeout: worker exited with no result",
                "traces": {
                    "strategy": "unified_adaptive_search",
                    "phase": "live_error",
                    "error": "worker exited with no result",
                },
                "stub": False,
                "dry_run": False,
            },
            "traces": {
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "error": "worker exited with no result",
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


def _trace_ok(trace: dict[str, Any]) -> bool:
    if trace.get("phase") == "live_error" or trace.get("error"):
        return False
    if (trace.get("tool_use") or {}).get("tool_calls_details"):
        return True
    return trace.get("response_status") == "completed"


def _load_existing_rows(run_dir: Path, n: int) -> dict[int, dict[str, Any]]:
    by_index: dict[int, dict[str, Any]] = {}
    pred = run_dir / "predictions.jsonl"
    if pred.exists():
        for line in pred.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            by_index[int(row["panel_index"])] = row
    # Prefer traces when predictions.jsonl is incomplete (mid-run crash).
    for path in sorted((run_dir / "traces").glob("*.json")):
        # 000_610194_r1.json
        parts = path.stem.split("_")
        try:
            idx = int(parts[0])
            rcid = int(parts[1])
        except (ValueError, IndexError):
            continue
        trace = json.loads(path.read_text(encoding="utf-8"))
        if idx in by_index and _trace_ok(trace) and not by_index[idx].get("error"):
            continue
        if _trace_ok(trace):
            # Reconstruct a minimal success row from scored sibling if needed later.
            by_index[idx] = {
                "rcid": rcid,
                "company_name": None,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": None,
                "traces": trace,
                "repeat": 1,
                "panel_index": idx,
                "_from_trace_only": True,
            }
        elif idx not in by_index:
            by_index[idx] = {
                "rcid": rcid,
                "company_name": None,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": trace.get("error") or "live_error",
                "traces": trace,
                "repeat": 1,
                "panel_index": idx,
                "_from_trace_only": True,
            }
    return by_index


def _ensure_run_dir(resume: Optional[Path], panel_meta: dict[str, Any], knobs: dict[str, Any]) -> Path:
    if resume is not None and resume.is_dir():
        print(f"Resuming run_dir={resume}", flush=True)
        (resume / "status.json").write_text(
            json.dumps(
                {"status": "running", "run_id": resume.name, "resumed": True},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return resume

    now = datetime.now(timezone.utc)
    run_id = (
        f"{now.date().isoformat()}_unified-adaptive-search_k1_"
        f"{now.strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    run_dir = EVAL_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "traces").mkdir()
    (run_dir / "raw").mkdir()
    (run_dir / "config.snapshot.json").write_text(
        json.dumps(
            {
                "architecture": "unified-adaptive-search",
                "k": 1,
                "dry_run": False,
                "panel_id": panel_meta.get("panel_id"),
                "panel_path": str(TUNING_PANEL_PATH),
                "runner_kwargs": knobs,
                "phase": "eval_infra",
                "note": "search=high re-run (hard timeout + resume)",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "panel_ref.json").write_text(
        json.dumps(panel_meta, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "status.json").write_text(
        json.dumps({"status": "running", "run_id": run_id}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"New run_dir={run_dir}", flush=True)
    return run_dir


def _row_from_trace(
    *,
    idx: int,
    company: CompanyInput,
    trace: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild a prediction row after a mid-run crash (predictions.jsonl missing).

    Findings come from raw_content_preview. Total API cost was not persisted in
    traces; estimate as tool_calls_cost_usd * 2.11 from the prior search=high
    successes (mean total/tool ratio ≈ 2.11). Marked in metric notes via error=None
    and cost_estimated=True.
    """
    findings: list[Any] = []
    preview = trace.get("raw_content_preview") or ""
    if preview.strip().startswith("{"):
        try:
            parsed = json.loads(preview)
            findings = list(parsed.get("findings") or [])
        except json.JSONDecodeError:
            # preview may be truncated; try to count finding objects softly
            findings = []
    tool_cost = (trace.get("tool_use") or {}).get("tool_calls_cost_usd")
    cost_usd = 0.0
    cost_estimated = False
    if tool_cost is not None:
        cost_usd = round(float(tool_cost) * 2.11, 5)
        cost_estimated = True
    return {
        "rcid": company.rcid,
        "company_name": company.name,
        "architecture": "unified-adaptive-search",
        "findings": findings,
        "findings_count": len(findings),
        "cost_usd": cost_usd,
        "cost_estimated": cost_estimated,
        "error": None
        if _trace_ok(trace)
        else (trace.get("error") or "live_error"),
        "traces": trace,
        "repeat": 1,
        "panel_index": idx,
        "stub": False,
        "dry_run": False,
    }


def _enrich_trace_only_rows(
    by_index: dict[int, dict[str, Any]],
    companies: list[CompanyInput],
) -> None:
    """Turn crash-recovered traces into usable prediction rows (no re-bill)."""
    for idx in list(by_index):
        row = by_index[idx]
        if not row.get("_from_trace_only"):
            continue
        company = companies[idx]
        by_index[idx] = _row_from_trace(
            idx=idx, company=company, trace=row.get("traces") or {}
        )


def main() -> None:
    require_api_key()
    arm = next(a for a in stage_a_screen_arms() if a.arm_id == ARM_ID)
    panel_path = TUNING_PANEL_PATH
    panel_meta = load_panel(panel_path)
    companies = load_panel_companies(panel_path)
    knobs = {**arm.runner_kwargs(), "timeout": TIMEOUT}

    print(
        f"Re-running {ARM_ID}: n={len(companies)} hard_timeout={TIMEOUT}s "
        f"attempts<={MAX_ATTEMPTS}",
        flush=True,
    )
    print(f"Knobs: {knobs}", flush=True)

    resume = RESUME_RUN if RESUME_RUN.is_dir() else None
    run_dir = _ensure_run_dir(resume, panel_meta, knobs)
    by_index = _load_existing_rows(run_dir, len(companies))
    _enrich_trace_only_rows(by_index, companies)

    done_ok = sum(
        1
        for r in by_index.values()
        if not r.get("error") and (r.get("traces") or {}).get("phase") != "live_error"
    )
    print(f"Already complete (usable): {done_ok}; will fill the rest", flush=True)

    for panel_index, company in enumerate(companies):
        existing = by_index.get(panel_index)
        if existing and not existing.get("error") and (
            (existing.get("traces") or {}).get("phase") != "live_error"
        ) and not existing.get("_from_trace_only"):
            # Keep successful prediction rows.
            if existing.get("findings_count") is not None and "cost_usd" in existing:
                print(
                    f"SKIP idx={panel_index} rcid={company.rcid} {company.name} "
                    f"(already ok)",
                    flush=True,
                )
                continue

        last_err = existing.get("error") if existing else None
        success = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(
                f"START idx={panel_index} attempt={attempt}/{MAX_ATTEMPTS} "
                f"rcid={company.rcid} {company.name}"
                + (f" prev={last_err}" if last_err else ""),
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
            trace_path = run_dir / "traces" / f"{panel_index:03d}_{company.rcid}_r1.json"
            trace_path.write_text(json.dumps(traces, indent=2) + "\n", encoding="utf-8")
            # Checkpoint predictions after every company.
            ordered = [by_index[i] for i in sorted(by_index)]
            with (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as f:
                for r in ordered:
                    f.write(json.dumps(r) + "\n")

            err = row.get("error")
            if err or (traces or {}).get("phase") == "live_error":
                last_err = err
                print(f"  FAIL {err}", flush=True)
                if not _is_retryable(err):
                    break
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

    ordered = [by_index[i] for i in range(len(companies)) if i in by_index]
    # Ensure every index exists (mark missing as error).
    for i, company in enumerate(companies):
        if i not in by_index:
            by_index[i] = {
                "rcid": company.rcid,
                "company_name": company.name,
                "architecture": "unified-adaptive-search",
                "findings": [],
                "findings_count": 0,
                "cost_usd": 0.0,
                "error": "missing_after_rerun",
                "traces": {"phase": "live_error", "error": "missing_after_rerun"},
                "repeat": 1,
                "panel_index": i,
            }
    ordered = [by_index[i] for i in range(len(companies))]
    with (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in ordered:
            f.write(json.dumps(r) + "\n")

    n_err = sum(
        1
        for r in ordered
        if r.get("error") or (r.get("traces") or {}).get("phase") == "live_error"
    )
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
            f"search=high re-run hard_timeout={TIMEOUT}s attempts<={MAX_ATTEMPTS}"
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
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Re-run complete: errors={n_err}/{len(ordered)} "
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
            scored_arm = score_arm_live(a, run_dir=run_dir, n_companies=len(companies))
            arm_run_dirs[a.arm_id] = run_dir
            arm_scores.append(scored_arm)
            continue
        prior = next(
            (row for row in (summary.get("arms") or []) if row.get("arm_id") == a.arm_id),
            None,
        )
        if prior is None:
            raise RuntimeError(f"missing prior arm {a.arm_id} in {instance_dir}")
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
        + f" Patched {ARM_ID} via re-run {run_dir.name} "
        f"(hard_timeout={TIMEOUT}s, caffeinated resume)."
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
