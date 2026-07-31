"""Landing index of prior eval instances (open-dashboard target)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.paths import EVAL_INSTANCES_DIR, LANDING_INDEX_PATH


def _catalog_path() -> Path:
    return EVAL_INSTANCES_DIR / "catalog.json"


def _load_catalog() -> list[dict[str, Any]]:
    catalog_path = _catalog_path()
    if not catalog_path.exists():
        return []
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Corrupt eval catalog at {catalog_path}: {exc}. "
            "Fix or remove catalog.json before updating the landing index."
        ) from exc
    if not isinstance(data, list):
        raise ValueError(
            f"Corrupt eval catalog at {catalog_path}: expected a JSON list."
        )
    return data


def ensure_landing_stub() -> Path:
    EVAL_INSTANCES_DIR.mkdir(parents=True, exist_ok=True)
    if not LANDING_INDEX_PATH.exists():
        # Rebuild from catalog when only index.html was deleted.
        LANDING_INDEX_PATH.write_text(
            _render_index(_load_catalog()),
            encoding="utf-8",
        )
    return LANDING_INDEX_PATH


def update_landing_index(
    *,
    run_id: str,
    architecture: str,
    full_name: str,
    scored: dict[str, Any],
) -> Path:
    ensure_landing_stub()
    catalog = _load_catalog()

    entry = {
        "run_id": run_id,
        "architecture": architecture,
        "full_name": full_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_cost_usd": scored.get("total_cost_usd"),
        "total_findings": scored.get("total_findings"),
        "n_companies": scored.get("n_companies"),
        "dashboard_relpath": f"../../outputs/evals/runs/{run_id}/dashboard.html",
        "phase": scored.get("phase"),
    }
    catalog = [row for row in catalog if row.get("run_id") != run_id]
    catalog.insert(0, entry)
    _catalog_path().write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    LANDING_INDEX_PATH.write_text(_render_index(catalog), encoding="utf-8")
    return LANDING_INDEX_PATH


def _render_index(catalog: list[dict[str, Any]]) -> str:
    if not catalog:
        rows_html = (
            "<tr><td colspan='5'>No eval instances yet. "
            "Run <code>python -m evals run-evals &lt;architecture&gt;</code>.</td></tr>"
        )
    else:
        parts: list[str] = []
        for row in catalog:
            href = row.get("dashboard_relpath", "#")
            parts.append(
                "<tr>"
                f"<td><a href='{href}'>{row.get('run_id')}</a></td>"
                f"<td>{row.get('full_name')} (<code>{row.get('architecture')}</code>)</td>"
                f"<td>{row.get('n_companies')}</td>"
                f"<td>{row.get('total_findings')}</td>"
                f"<td>{row.get('total_cost_usd')}</td>"
                "</tr>"
            )
        rows_html = "\n".join(parts)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Eval instances</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem; max-width: 900px; color: #1a1a1a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #ddd; text-align: left; padding: 0.5rem; vertical-align: top; }}
    .chip {{ display: inline-block; border: 1px solid #bbb; padding: 0.15rem 0.5rem; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <p class="chip">Phase 1 landing stub</p>
  <h1>Eval instances</h1>
  <p>
    Landing index for prior <code>run-evals</code> dashboard instances.
    Full tabbed Cost / Findings / Traces dashboards ship in Phase 2.
  </p>
  <table>
    <thead>
      <tr>
        <th>Run id</th>
        <th>Architecture</th>
        <th>Companies</th>
        <th>Findings</th>
        <th>Spend (USD)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>
"""
