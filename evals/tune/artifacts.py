"""Persist self-contained tuning experiment bundles for later viz / writeups."""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Union

from evals.paths import EVAL_RUNS_DIR, EVALS_PACKAGE_DIR, PROJECT_ROOT
from evals.tune.matrix import TuneArm

# Files copied from each arm run bundle into the instance (enough for viz/paper).
_ARM_COPY_NAMES = (
    "config.snapshot.json",
    "panel_ref.json",
    "predictions.jsonl",
    "scored.json",
    "status.json",
    "run.log",
)

_RESULTS_FIELDS = [
    "arm_id",
    "factor",
    "label",
    "model",
    "max_steps",
    "reasoning_effort",
    "web_search_depth",
    "mean_cost_usd",
    "mean_findings",
    "feasible",
    "n_companies",
    "cost_metric_source",
    "findings_metric_source",
    "arm_artifact_dir",
    "run_dir",
]


def _rel_to_project(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        try:
            return str(resolved.relative_to(EVALS_PACKAGE_DIR.resolve()))
        except ValueError:
            return str(resolved)


def _as_path(path: Union[Path, str]) -> Path:
    return path if isinstance(path, Path) else Path(path)


def copy_arm_run_artifacts(src: Union[Path, str], dest: Path) -> str:
    """Copy one arm's run bundle into dest (predictions, scored, traces, …)."""
    src_path = _as_path(src)
    dest.mkdir(parents=True, exist_ok=True)
    for name in _ARM_COPY_NAMES:
        src_file = src_path / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
    traces_src = src_path / "traces"
    if traces_src.is_dir():
        traces_dest = dest / "traces"
        if traces_dest.exists():
            shutil.rmtree(traces_dest)
        shutil.copytree(traces_src, traces_dest)
    return f"arms/{dest.name}"


def _score_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    knobs = row.get("knobs") or {}
    metric_source = row.get("metric_source") or {}
    return {
        "arm_id": row.get("arm_id"),
        "factor": row.get("factor"),
        "label": row.get("label"),
        "model": knobs.get("model"),
        "max_steps": knobs.get("max_steps"),
        "reasoning_effort": knobs.get("reasoning_effort"),
        "web_search_depth": knobs.get("web_search_depth"),
        "mean_cost_usd": row.get("mean_cost_usd"),
        "mean_findings": row.get("mean_findings"),
        "feasible": row.get("feasible"),
        "n_companies": row.get("n_companies"),
        "cost_metric_source": metric_source.get("cost"),
        "findings_metric_source": metric_source.get("findings"),
        "arm_artifact_dir": row.get("arm_artifact_dir"),
        "run_dir": row.get("run_dir"),
    }


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_RESULTS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_score_row_for_csv(row))


def begin_partial_bundle(
    *,
    panel_path: Path,
    panel_meta: dict[str, Any],
    arms: Iterable[TuneArm],
    stage: str,
    architecture: str,
    dry_run: bool,
) -> Path:
    """Create a crash-recovery staging dir under evals/runs/ before the arm loop."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    partial_dir = EVAL_RUNS_DIR / f"_tuning_partial_{stamp}_{uuid.uuid4().hex[:6]}"
    partial_dir.mkdir(parents=True, exist_ok=False)
    arms_list = list(arms)
    (partial_dir / "panel.snapshot.json").write_text(
        json.dumps(panel_meta, indent=2) + "\n",
        encoding="utf-8",
    )
    (partial_dir / "matrix.json").write_text(
        json.dumps(
            {
                "stage": stage,
                "architecture": architecture,
                "panel_path": _rel_to_project(panel_path),
                "panel_id": panel_meta.get("panel_id"),
                "arms": [arm.to_dict() for arm in arms_list],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (partial_dir / "arms.jsonl").write_text("", encoding="utf-8")
    _write_results_csv(partial_dir / "results.csv", [])
    (partial_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "running",
                "dry_run": dry_run,
                "completed_arm_ids": [],
                "n_arms_planned": len(arms_list),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return partial_dir


def persist_completed_arm(
    partial_dir: Path,
    *,
    arm_id: str,
    run_dir: Union[Path, str],
    score: dict[str, Any],
) -> None:
    """Write one finished arm into the partial bundle (live mid-matrix safety)."""
    dest = partial_dir / "arms" / arm_id
    rel_arm = copy_arm_run_artifacts(run_dir, dest)
    row = dict(score)
    row["run_dir"] = _rel_to_project(_as_path(run_dir))
    row["arm_artifact_dir"] = rel_arm

    with (partial_dir / "arms.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")

    existing: list[dict[str, Any]] = []
    arms_jsonl = partial_dir / "arms.jsonl"
    for line in arms_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            existing.append(json.loads(line))
    _write_results_csv(partial_dir / "results.csv", existing)

    status_path = partial_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    completed = list(status.get("completed_arm_ids") or [])
    if arm_id not in completed:
        completed.append(arm_id)
    status["completed_arm_ids"] = completed
    status["status"] = (
        "complete"
        if len(completed) >= int(status.get("n_arms_planned") or 0)
        else "running"
    )
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def discard_partial_bundle(partial_dir: Path | None) -> None:
    """Remove staging dir after a successful finalize (best-effort)."""
    if partial_dir is None:
        return
    try:
        if partial_dir.is_dir() and partial_dir.name.startswith("_tuning_partial_"):
            shutil.rmtree(partial_dir)
    except OSError:
        pass


def write_tuning_bundle(
    instance_dir: Path,
    *,
    panel_path: Path,
    panel_meta: dict[str, Any],
    arms: Iterable[TuneArm],
    arm_scores: list[dict[str, Any]],
    arm_run_dirs: dict[str, Union[Path, str]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Write durable, self-contained experiment files under the Tuning instance.

    Layout:
      panel.snapshot.json   exact panel used
      matrix.json           arm definitions (knobs)
      arms.jsonl            one row per arm (dashboard / pandas friendly)
      results.csv           flat table for notebooks
      summary.json          already present; refreshed with relative paths
      arms/<arm_id>/        copied run artifacts (predictions, scored, config, …)
      manifest.json         index of files in this bundle
    """
    instance_dir.mkdir(parents=True, exist_ok=True)
    arms_list = list(arms)

    (instance_dir / "panel.snapshot.json").write_text(
        json.dumps(panel_meta, indent=2) + "\n",
        encoding="utf-8",
    )
    (instance_dir / "matrix.json").write_text(
        json.dumps(
            {
                "stage": summary.get("stage"),
                "architecture": summary.get("architecture"),
                "panel_path": _rel_to_project(panel_path),
                "panel_id": panel_meta.get("panel_id"),
                "arms": [arm.to_dict() for arm in arms_list],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    enriched_scores: list[dict[str, Any]] = []
    arm_relpaths: dict[str, str] = {}
    for score in arm_scores:
        arm_id = str(score["arm_id"])
        src = _as_path(arm_run_dirs[arm_id])
        dest = instance_dir / "arms" / arm_id
        rel_arm = copy_arm_run_artifacts(src, dest)
        arm_relpaths[arm_id] = rel_arm
        row = dict(score)
        row["run_dir"] = _rel_to_project(src)
        row["arm_artifact_dir"] = rel_arm
        enriched_scores.append(row)

    arms_jsonl = instance_dir / "arms.jsonl"
    with arms_jsonl.open("w", encoding="utf-8") as f:
        for row in enriched_scores:
            f.write(json.dumps(row) + "\n")

    _write_results_csv(instance_dir / "results.csv", enriched_scores)

    summary_path = instance_dir / "summary.json"
    updated = dict(summary)
    updated["arms"] = enriched_scores
    updated["arm_run_dirs"] = {
        arm_id: _rel_to_project(_as_path(path)) for arm_id, path in arm_run_dirs.items()
    }
    updated["arm_artifact_dirs"] = arm_relpaths
    updated["artifact_files"] = {
        "panel_snapshot": "panel.snapshot.json",
        "matrix": "matrix.json",
        "arms_jsonl": "arms.jsonl",
        "results_csv": "results.csv",
        "summary": "summary.json",
        "dashboard": "dashboard.html",
        "manifest": "manifest.json",
    }
    if updated.get("winner") and updated["winner"].get("arm_id"):
        wid = updated["winner"]["arm_id"]
        for row in enriched_scores:
            if row.get("arm_id") == wid:
                updated["winner"] = row
                break
    summary_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "instance_dir": _rel_to_project(instance_dir),
        "files": sorted(
            str(p.relative_to(instance_dir))
            for p in instance_dir.rglob("*")
            if p.is_file()
        ),
        "n_arms": len(enriched_scores),
        "winner_arm_id": updated.get("winner_arm_id"),
        "dry_run": updated.get("dry_run"),
        "note": (
            "Self-contained tuning bundle. Prefer arms.jsonl / results.csv for "
            "notebooks; arms/<arm_id>/ holds per-arm predictions and scores."
        ),
    }
    (instance_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return updated
