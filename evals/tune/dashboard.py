"""Tuning instance dashboard (dark Classifier-eval visual language)."""

from __future__ import annotations

import html
import json
from typing import Any

from evals.dashboard.theme import DARK_CSS


def render_tuning_dashboard(*, title: str, summary: dict[str, Any]) -> str:
    safe_title = html.escape(title)
    arch = html.escape(str(summary.get("architecture") or "n/a"))
    stage = html.escape(str(summary.get("stage") or ""))
    panel = html.escape(str(summary.get("panel_id") or ""))
    mode = "dry" if summary.get("dry_run", True) else "live"
    sha = html.escape(str(summary.get("git_sha") or "unknown"))
    constraint = summary.get("constraint_usd_per_company")
    winner = summary.get("winner") or {}
    winner_id = html.escape(str(summary.get("winner_arm_id") or "none"))
    winner_label = html.escape(str(winner.get("label") or "none under constraint"))

    banner = (
        "<div class='banner'><strong>Dry run.</strong> Proxies only "
        "(cost priors + soft march references). Not for decisions.</div>"
        if summary.get("dry_run", True)
        else "<div class='banner'>Live run (metered usage).</div>"
    )

    rows: list[str] = []
    for arm in summary.get("arms") or []:
        knobs = arm.get("knobs") or {}
        knobs_txt = html.escape(
            f"steps={knobs.get('max_steps')}, "
            f"effort={knobs.get('reasoning_effort')}, "
            f"search={knobs.get('web_search_depth')}"
        )
        feasible = "Y" if arm.get("feasible") else "N"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(arm.get('arm_id')))}</code></td>"
            f"<td>{html.escape(str(arm.get('label')))}<span class='meta'>{knobs_txt}</span></td>"
            f"<td>{html.escape(str(arm.get('mean_cost_usd')))}</td>"
            f"<td>{html.escape(str(arm.get('mean_findings')))}</td>"
            f"<td>{feasible}</td>"
            "</tr>"
        )
    table_body = "\n".join(rows) if rows else "<tr><td colspan='5'>No arms</td></tr>"
    payload = html.escape(json.dumps(summary, indent=2))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <style>{DARK_CSS}</style>
</head>
<body>
  <div class="wrap">
    <p class="chip">Tuning · Stage A</p>
    <div class="header-row">
      <h1>{safe_title}</h1>
    </div>
    <p class="subtitle">{arch} · stage {stage} · panel {panel} · {mode} · commit {sha}</p>
    {banner}
    <p class="lede">
      Constraint: mean $/company ≤ <strong>${html.escape(str(constraint))}</strong>.
      Maximize mean findings among feasible arms.
    </p>
    <div class="banner">
      Winner under constraint: <strong>{winner_id}</strong>
      <span class="meta">{winner_label}</span>
    </div>
    <section class="section">
      <h2>Arms</h2>
      <table>
        <thead>
          <tr>
            <th>Arm</th><th>Change</th><th>Mean $/co</th><th>Mean findings</th><th>Feasible</th>
          </tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
    </section>
    <section class="section">
      <h2>summary.json</h2>
      <pre>{payload}</pre>
    </section>
    <p class="footer"><a href="../../index.html">Back to archive</a></p>
  </div>
</body>
</html>
"""
