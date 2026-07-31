"""Thin adapter: run_panel(architecture, panel) -> run_dir."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from contracts.types import CompanyInput
from evals.architectures import resolve_architecture, run_company
from evals.dashboard.landing import ensure_landing_stub, update_landing_index
from evals.panel import load_panel, load_panel_companies
from evals.paths import EVAL_RUNS_DIR, FIXTURE_PANEL_PATH


def _make_run_id(cli_key: str, k: int) -> str:
    # Date + architecture + k name the experiment. A short suffix keeps
    # same-day re-runs from silently overwriting prior artifact bundles.
    # Use one UTC clock for both date and time so midnight does not mix zones.
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return f"{now.date().isoformat()}_{cli_key}_k{k}_{stamp}_{suffix}"


def run_panel(
    architecture: str,
    panel: Optional[Union[Path, str, list[CompanyInput]]] = None,
    *,
    k: int = 1,
    dry_run: bool = True,
    run_id: Optional[str] = None,
) -> Path:
    """Run one architecture against a panel and write a run artifact bundle.

    Phase 1: fixture panel + dry/stub runners. Writes predictions and a stub
    dashboard.html under outputs/evals/runs/<run_id>/.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    spec = resolve_architecture(architecture)
    if isinstance(panel, list):
        companies = panel
        panel_meta = {"panel_id": "inline", "reference_kind": "soft"}
        panel_path = None
    else:
        panel_path = Path(panel) if panel else FIXTURE_PANEL_PATH
        panel_meta = load_panel(panel_path)
        companies = load_panel_companies(panel_path)

    if len(companies) < 1:
        raise ValueError("panel must contain at least one company")

    run_id = run_id or _make_run_id(spec.cli_key, k)
    run_dir = EVAL_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw").mkdir(exist_ok=True)
    (run_dir / "traces").mkdir(exist_ok=True)

    config_snapshot = {
        "architecture": spec.cli_key,
        "full_name": spec.full_name,
        "package": spec.package,
        "k": k,
        "dry_run": dry_run,
        "panel_id": panel_meta.get("panel_id"),
        "panel_path": str(panel_path) if panel_path else None,
        "phase": "phase1_scaffolding",
    }
    (run_dir / "config.snapshot.json").write_text(
        json.dumps(config_snapshot, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "panel_ref.json").write_text(
        json.dumps(panel_meta, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "status.json").write_text(
        json.dumps({"status": "running", "run_id": run_id}, indent=2) + "\n",
        encoding="utf-8",
    )

    predictions: list[dict[str, Any]] = []
    try:
        for panel_index, company in enumerate(companies):
            company_input = (
                company
                if isinstance(company, CompanyInput)
                else CompanyInput.from_mapping(company)
            )
            for repeat in range(1, k + 1):
                result = run_company(spec.cli_key, company_input, dry_run=dry_run)
                row = result.to_dict()
                row["repeat"] = repeat
                row["panel_index"] = panel_index
                predictions.append(row)
                # panel_index keeps duplicate rcids from clobbering traces.
                trace_path = (
                    run_dir
                    / "traces"
                    / f"{panel_index:03d}_{company_input.rcid}_r{repeat}.json"
                )
                trace_path.write_text(
                    json.dumps(result.traces, indent=2) + "\n",
                    encoding="utf-8",
                )
    except Exception as exc:
        (run_dir / "status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "run_id": run_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "predictions_written": len(predictions),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (run_dir / "run.log").write_text(
            f"run_id={run_id}\narchitecture={spec.cli_key}\ndry_run={dry_run}\n"
            f"status=failed\nerror={type(exc).__name__}: {exc}\n"
            f"predictions_partial={len(predictions)}\n",
            encoding="utf-8",
        )
        raise

    predictions_path = run_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as f:
        for row in predictions:
            f.write(json.dumps(row) + "\n")

    scored = {
        "architecture": spec.cli_key,
        "panel_id": panel_meta.get("panel_id"),
        "n_companies": len(companies),
        "n_predictions": len(predictions),
        "total_findings": sum(r.get("findings_count", 0) for r in predictions),
        "total_cost_usd": sum(r.get("cost_usd", 0.0) or 0.0 for r in predictions),
        "component_cost_means": _component_means(predictions),
        "phase": "phase1_scaffolding",
        "note": "Scoring is a placeholder summary. Full metrics arrive in Phase 2.",
    }
    (run_dir / "scored.json").write_text(
        json.dumps(scored, indent=2) + "\n",
        encoding="utf-8",
    )

    dashboard_html = _stub_dashboard_html(spec.full_name, spec.cli_key, run_id, scored)
    (run_dir / "dashboard.html").write_text(dashboard_html, encoding="utf-8")

    # Core artifacts already succeeded. Landing failures must not rewrite status
    # to failed, but they still surface to the caller.
    landing_error: Optional[str] = None
    try:
        ensure_landing_stub()
        update_landing_index(
            run_id=run_id,
            architecture=spec.cli_key,
            full_name=spec.full_name,
            scored=scored,
        )
    except Exception as exc:
        landing_error = f"{type(exc).__name__}: {exc}"

    status_payload: dict[str, Any] = {"status": "completed", "run_id": run_id}
    if landing_error:
        status_payload["landing_error"] = landing_error
    (run_dir / "run.log").write_text(
        f"run_id={run_id}\narchitecture={spec.cli_key}\ndry_run={dry_run}\n"
        f"companies={len(companies)}\npredictions={len(predictions)}\n"
        f"status=completed\n"
        + (f"landing_error={landing_error}\n" if landing_error else ""),
        encoding="utf-8",
    )
    (run_dir / "status.json").write_text(
        json.dumps(status_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    if landing_error:
        raise RuntimeError(f"eval run artifacts written, but landing update failed: {landing_error}")
    return run_dir


def _component_means(predictions: list[dict[str, Any]]) -> dict[str, float]:
    """Mean cost per component name, matching CostLedger (ran=True only)."""
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in predictions:
        ledger = row.get("cost_ledger") or {}
        for component in ledger.get("components") or []:
            name = component.get("name")
            if not name or not component.get("ran"):
                continue
            totals[name] = totals.get(name, 0.0) + float(component.get("cost_usd") or 0.0)
            counts[name] = counts.get(name, 0) + 1
    return {
        name: round(totals[name] / counts[name], 6)
        for name in totals
        if counts.get(name)
    }


def _stub_dashboard_html(
    full_name: str,
    cli_key: str,
    run_id: str,
    scored: dict[str, Any],
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{full_name} · {run_id}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem; max-width: 720px; color: #1a1a1a; }}
    .chip {{ display: inline-block; border: 1px solid #bbb; padding: 0.15rem 0.5rem; margin-right: 0.35rem; font-size: 0.85rem; }}
    pre {{ background: #f6f6f6; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <p class="chip">Phase 1 stub dashboard</p>
  <p class="chip">Soft reference</p>
  <p class="chip">Stage 3 judge not run</p>
  <h1>{full_name}</h1>
  <p>CLI key: <code>{cli_key}</code> · run id: <code>{run_id}</code></p>
  <p>
    Placeholder for the future tabbed dashboard (Findings / Traces / FACT-lite /
    Cost &amp; Reliability). Phase 1 only proves artifact wiring.
  </p>
  <h2>Scored summary (placeholder)</h2>
  <pre>{json.dumps(scored, indent=2)}</pre>
</body>
</html>
"""
