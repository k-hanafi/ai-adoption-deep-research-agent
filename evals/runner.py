"""Thin adapter: run_panel(architecture, panel) -> run_dir."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional, Union

from contracts.types import CompanyInput
from evals.architectures import resolve_architecture, run_company
from evals.dashboard.landing import ensure_landing_stub, update_landing_index
from evals.panel import load_panel, load_panel_companies
from evals.paths import EVAL_RUNS_DIR, FIXTURE_PANEL_PATH


def _make_run_id(cli_key: str, k: int) -> str:
    return f"{date.today().isoformat()}_{cli_key}_k{k}"


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
    spec = resolve_architecture(architecture)
    if isinstance(panel, list):
        companies = panel
        panel_meta = {"panel_id": "inline", "reference_kind": "soft"}
        panel_path = None
    else:
        panel_path = Path(panel) if panel else FIXTURE_PANEL_PATH
        panel_meta = load_panel(panel_path)
        companies = load_panel_companies(panel_path)

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

    predictions: list[dict[str, Any]] = []
    for company in companies:
        for repeat in range(1, k + 1):
            result = run_company(spec.cli_key, company, dry_run=dry_run)
            row = result.to_dict()
            row["repeat"] = repeat
            predictions.append(row)
            trace_path = run_dir / "traces" / f"{company.rcid}_r{repeat}.json"
            trace_path.write_text(
                json.dumps(result.traces, indent=2) + "\n",
                encoding="utf-8",
            )

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
    (run_dir / "run.log").write_text(
        f"run_id={run_id}\narchitecture={spec.cli_key}\ndry_run={dry_run}\n"
        f"companies={len(companies)}\npredictions={len(predictions)}\n",
        encoding="utf-8",
    )

    ensure_landing_stub()
    update_landing_index(
        run_id=run_id,
        architecture=spec.cli_key,
        full_name=spec.full_name,
        scored=scored,
    )
    return run_dir


def _component_means(predictions: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in predictions:
        ledger = row.get("cost_ledger") or {}
        for component in ledger.get("components") or []:
            name = component.get("name")
            if not name:
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
