"""Tuning instance dashboard (Classifier Eval Suite GUI shell)."""

from __future__ import annotations

import html
import json
import math
import statistics
from pathlib import Path
from typing import Any, Optional

from evals.dashboard.theme import SUITE_CSS

_FACTOR_LABELS = {
    "baseline": "baseline",
    "max_steps": "max_steps",
    "reasoning_effort": "effort",
    "web_search_depth": "search",
}


def render_tuning_dashboard(
    *,
    title: str,
    summary: dict[str, Any],
    instance_dir: Optional[Path] = None,
) -> str:
    """Render a three-tab Stage A screen dashboard.

    Tabs mirror the taxonomy Classifier Eval Suite shell: decision checks,
    arm leaderboard + cost/yield chart, tool-headroom diagnostics.
    """
    safe_title = html.escape(title)
    arms = list(summary.get("arms") or [])
    winner_id = str(summary.get("winner_arm_id") or "")
    constraint = summary.get("constraint_usd_per_company")
    dry = bool(summary.get("dry_run", True))
    mode = "dry" if dry else "live"
    sha = str(summary.get("git_sha") or "unknown")
    panel = str(summary.get("panel_id") or "n/a")
    stage = str(summary.get("stage") or "screen")
    arch = str(summary.get("full_name") or summary.get("architecture") or "n/a")
    n_arms = len(arms)
    n_companies = int((arms[0].get("n_companies") if arms else 0) or 0)

    tool_rows = _tool_use_by_arm(instance_dir, arms) if instance_dir else []
    chart_payload = _chart_payload(arms, winner_id, constraint)
    factors = sorted({str(a.get("factor") or "other") for a in arms})

    notice = _notice_html(summary, dry=dry)
    decision_panel = _decision_panel_html(summary, arms, tool_rows)
    leaderboard = _leaderboard_html(arms, winner_id, constraint)
    tool_panel = _tool_panel_html(tool_rows)
    factor_chips = "".join(
        f'<button type="button" class="chip active" data-factor="{html.escape(f)}">'
        f"{html.escape(_FACTOR_LABELS.get(f, f))}</button>"
        for f in factors
    )
    chart_json = html.escape(json.dumps(chart_payload), quote=True)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{safe_title}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
{SUITE_CSS}
</style>
</head>
<body>
<header class="appbar">
  <div class="brand">Deep Research Eval Suite<small>Unified Adaptive Search · Stage A</small></div>
  <div class="appbar-meta" title="{html.escape(panel)}">{n_arms} arms · {html.escape(mode)} · commit {html.escape(sha)}</div>
</header>

<nav class="tabs" aria-label="Suite sections">
  <button type="button" class="tab active" data-tab="decision">Screen decision</button>
  <button type="button" class="tab" data-tab="arms">Arm screen</button>
  <button type="button" class="tab" data-tab="tools">Tool headroom</button>
</nav>

{notice}

<div class="filter-shell" id="filter-shell" hidden>
  <div class="filter-shell-inner">
    <div class="toolbar" id="factor-filter">
      <p class="toolbar-hint">Filters the arm leaderboard and the cost-yield chart.</p>
      <div class="toolbar-left">
        <span class="toolbar-label">OFAT factor</span>
        {factor_chips}
        <button type="button" class="btn-ghost" id="btn-show-all">Show all</button>
        <button type="button" class="btn-ghost" id="btn-clear">Clear</button>
      </div>
      <div class="toolbar-right">
        <span class="toolbar-count" id="filter-count"></span>
      </div>
    </div>
  </div>
</div>

<main class="content">
  <section class="panel active" id="panel-decision">
    <div class="tab-lead">
      <h2>Which knobs should production freeze?</h2>
      <p>{html.escape(arch)} Stage A one-factor screen on the held-out tuning panel.
      Maximize mean findings subject to mean $/company ≤ ${html.escape(str(constraint))}.
      Panel: <code>{html.escape(panel)}</code> · {n_companies} companies · stage <code>{html.escape(stage)}</code>.</p>
    </div>
    {decision_panel}
  </section>

  <section class="panel" id="panel-arms">
    <div class="tab-lead">
      <h2>How do the arms trade cost for findings?</h2>
      <p>Each row is one OFAT arm against the same panel. Feasible means mean
      cost stays under the per-company ceiling. The auto-winner is the feasible
      arm with the highest mean findings.</p>
    </div>
    {leaderboard}
    <div class="card">
      <div class="card-title">Cost against mean findings</div>
      <div class="card-desc">Each point is one arm. The dashed line is the
      ${html.escape(str(constraint))}/company constraint. Points to the right
      of the line are infeasible for the freeze.</div>
      <div id="chart-pareto" class="chart" data-constraint="{html.escape(str(constraint))}" data-payload="{chart_json}"></div>
    </div>
  </section>

  <section class="panel" id="panel-tools">
    <div class="tab-lead">
      <h2>Does extra headroom get used?</h2>
      <p>Tool counts come from live traces (<code>search_web</code> +
      <code>fetch_url</code> ≈ <code>tool_output_items</code>). If raising a
      ceiling does not move these distributions, do not ship the higher max.</p>
    </div>
    {tool_panel}
  </section>

  <footer class="page-footer">
    <a href="../../index.html">Back to archive</a>
    &middot; {safe_title}
    &middot; regenerate with <code>python -m evals refresh-dashboard PATH</code>.
  </footer>
</main>
<script>
{ _SUITE_JS }
</script>
</body>
</html>
"""


def _notice_html(summary: dict[str, Any], *, dry: bool) -> str:
    winner = summary.get("winner") or {}
    winner_id = str(summary.get("winner_arm_id") or "none")
    winner_label = str(winner.get("label") or "none under constraint")
    created = str(summary.get("created_at") or "")
    cli = str(summary.get("cli") or "")
    if dry:
        cls = "notice dry"
        tag = "Dry run"
        body = (
            "<div><span class='run-headline'>Proxies only (cost priors + soft "
            "March references). Not for freeze decisions.</span>"
            f"<span class='run-meta'>{html.escape(cli)}</span></div>"
        )
    else:
        cls = "notice scored"
        tag = "Live metered"
        body = (
            f"<div><span class='run-headline'>Winner under constraint: "
            f"{html.escape(winner_id)} · {html.escape(winner_label)}</span>"
            f"<span class='run-meta'>{html.escape(created)} · {html.escape(cli)}</span></div>"
        )
    return (
        f'<div class="{cls}" id="run-instance">'
        f'<span class="tag">{tag}</span>{body}</div>'
    )


def _decision_panel_html(
    summary: dict[str, Any],
    arms: list[dict[str, Any]],
    tool_rows: list[dict[str, Any]],
) -> str:
    constraint = summary.get("constraint_usd_per_company")
    winner = summary.get("winner") or {}
    winner_id = str(summary.get("winner_arm_id") or "none")
    feasible = [a for a in arms if a.get("feasible")]
    best = max(arms, key=lambda a: float(a.get("mean_findings") or 0), default=None)

    winner_cost = winner.get("mean_cost_usd")
    winner_findings = winner.get("mean_findings")
    winner_block = f"""
<div class="check" id="check-winner">
  <div class="check-head"><h3>Winner under the per-company ceiling</h3></div>
  <div class="check-body">
    <p class="check-meaning">Among arms whose mean $/company stays at or below
    the Stage A constraint, pick the highest mean findings. This is the freeze
    candidate the archive recorded automatically.</p>
    <div class="check-stats">
      <div class="stat"><span class="stat-label">Winner arm</span>
        <span class="stat-value">{html.escape(winner_id)}</span></div>
      <div class="stat"><span class="stat-label">Mean $/co</span>
        <span class="stat-value">{_fmt_money(winner_cost)}</span></div>
      <div class="stat"><span class="stat-label">Mean findings</span>
        <span class="stat-value">{_fmt_num(winner_findings)}</span></div>
      <div class="stat"><span class="stat-label">Feasible arms</span>
        <span class="stat-value">{len(feasible)} / {len(arms)}</span></div>
    </div>
    <p class="check-footnote">Constraint: mean $/company ≤ ${_fmt_money(constraint)}.
    Label: {html.escape(str(winner.get("label") or "n/a"))}.</p>
  </div>
</div>
"""

    # Factor readouts
    by_factor: dict[str, list[dict[str, Any]]] = {}
    for a in arms:
        by_factor.setdefault(str(a.get("factor") or "other"), []).append(a)

    rows = []
    for factor, group in by_factor.items():
        costs = [float(a.get("mean_cost_usd") or 0) for a in group]
        finds = [float(a.get("mean_findings") or 0) for a in group]
        spread_f = max(finds) - min(finds) if finds else 0
        spread_c = max(costs) - min(costs) if costs else 0
        moves = "moves yield" if spread_f >= 0.25 else "flat on yield"
        status = "pass" if spread_f >= 0.25 else "pending"
        rows.append(
            "<tr>"
            f"<td class='mono'>{html.escape(_FACTOR_LABELS.get(factor, factor))}</td>"
            f"<td><span class='mini-status {status}'>{moves}</span></td>"
            f"<td class='num'>{_fmt_num(spread_f)}</td>"
            f"<td class='num'>{_fmt_money(spread_c)}</td>"
            f"<td class='num'>{len(group)}</td>"
            "</tr>"
        )

    factor_block = f"""
<div class="check" id="check-factors">
  <div class="check-head"><h3>Which OFAT factors moved the needle?</h3></div>
  <div class="check-body">
    <p class="check-meaning">Spread is max − min mean findings (and mean cost)
    within each factor family. Flat factors should not get oversized production
    ceilings &quot;just in case.&quot;</p>
    <table class="mini">
      <thead><tr><th>Factor</th><th>Read</th><th>Findings spread</th><th>Cost spread</th><th>Arms</th></tr></thead>
      <tbody>{''.join(rows) if rows else '<tr><td colspan="5">No arms</td></tr>'}</tbody>
    </table>
  </div>
</div>
"""

    # Headroom recommendation from tool rows (steps family)
    steps_tools = [
        r for r in tool_rows if r.get("factor") in ("baseline", "max_steps")
    ]
    if steps_tools:
        p95s = [r["tools_p95"] for r in steps_tools if r.get("tools_p95") is not None]
        maxima = [r["tools_max"] for r in steps_tools if r.get("tools_max") is not None]
        rec = int(math.ceil(max(p95s) + 3)) if p95s else None
        observed_max = max(maxima) if maxima else None
        headroom_status = "pass" if rec else "pending"
        headroom_body = f"""
    <div class="check-stats">
      <div class="stat"><span class="stat-label">Suggested max_steps</span>
        <span class="stat-value">{rec if rec is not None else "n/a"}</span></div>
      <div class="stat"><span class="stat-label">Observed p95 tools</span>
        <span class="stat-value">{_fmt_num(max(p95s) if p95s else None)}</span></div>
      <div class="stat"><span class="stat-label">Observed max tools</span>
        <span class="stat-value">{observed_max if observed_max is not None else "n/a"}</span></div>
    </div>
    <p class="check-footnote">At medium effort, tool use stayed ~flat when the
    steps ceiling rose from 10 → 100. Suggestion is p95 + small slack, not the
    API maximum. Re-check if you freeze a high effort setting (those runs pile
    up near ~30 tools).</p>
"""
    else:
        headroom_status = "pending"
        headroom_body = (
            "<p class='check-footnote'>Tool traces were not available in this "
            "instance bundle when the dashboard was rendered.</p>"
        )

    headroom_block = f"""
<div class="check" id="check-headroom">
  <div class="check-head">
    <h3>Steps ceiling to ship
      <span class="mini-status {headroom_status}" style="margin-left:10px">{headroom_status}</span>
    </h3>
  </div>
  <div class="check-body">
    <p class="check-meaning">Use measured tool-loop usage, not the OFAT arm
    label, to pick production <code>max_steps</code>.</p>
    {headroom_body}
  </div>
</div>
"""

    best_note = ""
    if best and str(best.get("arm_id")) != winner_id:
        best_note = f"""
<div class="check">
  <div class="check-head"><h3>Highest findings overall</h3></div>
  <div class="check-body">
    <p class="check-meaning"><code>{html.escape(str(best.get('arm_id')))}</code>
    led on mean findings ({_fmt_num(best.get('mean_findings'))}) at
    ${_fmt_money(best.get('mean_cost_usd'))}/co
    {"(also the winner)." if best.get("feasible") else "(outside the ceiling, so not auto-selected)."}
    </p>
  </div>
</div>
"""

    return winner_block + factor_block + headroom_block + best_note


def _leaderboard_html(
    arms: list[dict[str, Any]],
    winner_id: str,
    constraint: Any,
) -> str:
    if not arms:
        return '<div class="empty">No arms in this tuning instance.</div>'
    max_findings = max(float(a.get("mean_findings") or 0) for a in arms) or 1.0
    # Rank by findings desc, cost asc tie-break
    ranked = sorted(
        enumerate(arms, start=1),
        key=lambda iv: (
            -float(iv[1].get("mean_findings") or 0),
            float(iv[1].get("mean_cost_usd") or 0),
        ),
    )
    body = []
    for rank, (_orig_i, arm) in enumerate(ranked, start=1):
        arm_id = str(arm.get("arm_id") or "")
        knobs = arm.get("knobs") or {}
        findings = float(arm.get("mean_findings") or 0)
        cost = arm.get("mean_cost_usd")
        pct = max(0.0, min(100.0, 100.0 * findings / max_findings))
        is_winner = arm_id == winner_id
        feasible = bool(arm.get("feasible"))
        row_cls = "winner-row" if is_winner else ""
        badges = []
        if is_winner:
            badges.append('<span class="badge winner">winner</span>')
        if not feasible:
            badges.append('<span class="badge fail">over budget</span>')
        else:
            badges.append('<span class="badge pass">feasible</span>')
        badge_html = "".join(badges)
        factor = str(arm.get("factor") or "")
        body.append(
            f"<tr class='{row_cls}' data-factor='{html.escape(factor)}' data-arm='{html.escape(arm_id)}'>"
            f"<td class='num'>{rank}</td>"
            f"<td><div class='name-cell'>{html.escape(str(arm.get('label') or arm_id))}{badge_html}</div>"
            f"<div class='sub-cell mono'>{html.escape(arm_id)} · "
            f"steps={html.escape(str(knobs.get('max_steps')))} · "
            f"effort={html.escape(str(knobs.get('reasoning_effort')))} · "
            f"search={html.escape(str(knobs.get('web_search_depth')))}</div></td>"
            f"<td class='num'><div class='score-cell'>"
            f"<span class='score-val'>{_fmt_num(findings)}</span>"
            f"<span class='score-bar'><span style='width:{pct:.1f}%'></span></span>"
            f"</div></td>"
            f"<td class='num mono'>{_fmt_money(cost)}</td>"
            f"<td class='num mono'>{html.escape(str(arm.get('n_companies') or ''))}</td>"
            f"<td class='mono'>{html.escape(_FACTOR_LABELS.get(factor, factor))}</td>"
            "</tr>"
        )
    return f"""
<div class="table-wrap">
  <table class="grid" id="leaderboard">
    <thead>
      <tr>
        <th>#</th>
        <th>Configuration</th>
        <th class="num">Mean findings</th>
        <th class="num" title="Constraint ≤ ${_fmt_money(constraint)}">Mean $/co</th>
        <th class="num">n</th>
        <th>Factor</th>
      </tr>
    </thead>
    <tbody id="leaderboard-body">
      {''.join(body)}
    </tbody>
  </table>
</div>
"""


def _tool_panel_html(tool_rows: list[dict[str, Any]]) -> str:
    if not tool_rows:
        return (
            '<div class="empty">No per-arm traces found under '
            "<code>arms/*/traces</code> for this instance.</div>"
        )
    rows = []
    for r in tool_rows:
        hit = r.get("hit_ceiling_pct")
        hit_s = f"{hit:.0f}%" if hit is not None else "n/a"
        rows.append(
            "<tr>"
            f"<td class='mono'>{html.escape(str(r['arm_id']))}</td>"
            f"<td>{html.escape(str(r['label']))}</td>"
            f"<td class='num'>{r.get('ceiling') if r.get('ceiling') is not None else '—'}</td>"
            f"<td class='num'>{r['n_ok']}/{r['n_total']}</td>"
            f"<td class='num'>{_fmt_num(r.get('tools_mean'))}</td>"
            f"<td class='num'>{_fmt_num(r.get('tools_p50'))}</td>"
            f"<td class='num'>{_fmt_num(r.get('tools_p95'))}</td>"
            f"<td class='num'>{r.get('tools_max') if r.get('tools_max') is not None else '—'}</td>"
            f"<td class='num'>{_fmt_num(r.get('search_mean'))}</td>"
            f"<td class='num'>{_fmt_num(r.get('urls_per_search'))}</td>"
            f"<td class='num'>{hit_s}</td>"
            "</tr>"
        )
    return f"""
<div class="table-wrap">
  <table class="grid">
    <thead>
      <tr>
        <th>Arm</th>
        <th>Label</th>
        <th class="num">Ceiling</th>
        <th class="num">Completed</th>
        <th class="num">Tools mean</th>
        <th class="num">Tools p50</th>
        <th class="num">Tools p95</th>
        <th class="num">Tools max</th>
        <th class="num">search_web mean</th>
        <th class="num">URLs / search</th>
        <th class="num">≥ ceiling</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</div>
<div class="card">
  <div class="card-title">How to read this table</div>
  <div class="card-desc">
    <code>Tools</code> is <code>tool_output_items</code> (almost always
    search_web + fetch_url calls). It is a soft proxy, not the Agent API's
    official step counter, which is why some runs show more tools than the
    logged <code>max_steps</code> ceiling. Prefer p95 + slack over shipping
    unused 50/100 ceilings when the distribution is flat.
  </div>
</div>
"""


def _chart_payload(
    arms: list[dict[str, Any]],
    winner_id: str,
    constraint: Any,
) -> dict[str, Any]:
    points = []
    for a in arms:
        points.append(
            {
                "arm_id": a.get("arm_id"),
                "label": a.get("label"),
                "factor": a.get("factor"),
                "cost": a.get("mean_cost_usd"),
                "findings": a.get("mean_findings"),
                "feasible": bool(a.get("feasible")),
                "winner": str(a.get("arm_id")) == winner_id,
            }
        )
    try:
        cval: Any = float(constraint) if constraint is not None else None
    except (TypeError, ValueError):
        cval = None
    return {"points": points, "constraint": cval}


def _tool_use_by_arm(
    instance_dir: Path,
    arms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for arm in arms:
        arm_id = str(arm.get("arm_id") or "")
        rel = arm.get("arm_artifact_dir") or f"arms/{arm_id}"
        traces_dir = instance_dir / rel / "traces"
        if not traces_dir.is_dir():
            traces_dir = instance_dir / "arms" / arm_id / "traces"
        tools: list[float] = []
        searches: list[float] = []
        url_ratios: list[float] = []
        ceiling = None
        n_total = 0
        n_ok = 0
        hit = 0
        if traces_dir.is_dir():
            for path in sorted(traces_dir.glob("*.json")):
                n_total += 1
                try:
                    t = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                tu = t.get("tool_use") or {}
                details = tu.get("tool_calls_details") or {}
                if not details:
                    continue
                n_ok += 1
                toi = tu.get("tool_output_items")
                # Agent usage may label the tool search_web or web_search.
                sw = float(
                    details.get("search_web")
                    or details.get("web_search")
                    or 0
                )
                urls = float(tu.get("search_result_urls") or 0)
                if toi is not None:
                    tools.append(float(toi))
                searches.append(sw)
                if sw > 0:
                    url_ratios.append(urls / sw)
                ceiling = tu.get("max_steps_ceiling", ceiling)
                if ceiling is not None and toi is not None and float(toi) >= float(ceiling):
                    hit += 1
        out.append(
            {
                "arm_id": arm_id,
                "label": arm.get("label"),
                "factor": arm.get("factor"),
                "ceiling": ceiling if ceiling is not None else (arm.get("knobs") or {}).get("max_steps"),
                "n_total": n_total,
                "n_ok": n_ok,
                "tools_mean": _mean(tools),
                "tools_p50": _pct(tools, 50),
                "tools_p95": _pct(tools, 95),
                "tools_max": int(max(tools)) if tools else None,
                "search_mean": _mean(searches),
                "urls_per_search": _mean(url_ratios),
                "hit_ceiling_pct": (100.0 * hit / n_ok) if n_ok else None,
            }
        )
    return out


def _mean(vals: list[float]) -> Optional[float]:
    return statistics.mean(vals) if vals else None


def _pct(vals: list[float], p: float) -> Optional[float]:
    if not vals:
        return None
    xs = sorted(vals)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[f]
    return xs[f] * (c - k) + xs[c] * (k - f)


def _fmt_money(v: Any) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):.4f}".rstrip("0").rstrip(".") if float(v) < 1 else f"{float(v):.2f}"
    except (TypeError, ValueError):
        return html.escape(str(v))


def _fmt_num(v: Any) -> str:
    if v is None:
        return "n/a"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}"


_SUITE_JS = r"""
(function () {
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const panels = {
    decision: document.getElementById('panel-decision'),
    arms: document.getElementById('panel-arms'),
    tools: document.getElementById('panel-tools'),
  };
  const filterShell = document.getElementById('filter-shell');
  const chips = () => Array.from(document.querySelectorAll('#factor-filter .chip[data-factor]'));
  const rows = () => Array.from(document.querySelectorAll('#leaderboard-body tr[data-factor]'));
  const countEl = document.getElementById('filter-count');

  function activeFactors() {
    return new Set(chips().filter(c => c.classList.contains('active')).map(c => c.dataset.factor));
  }

  function applyFilter() {
    const active = activeFactors();
    let shown = 0;
    rows().forEach(tr => {
      const ok = active.has(tr.dataset.factor);
      tr.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    });
    if (countEl) countEl.textContent = shown + ' / ' + rows().length + ' arms';
    drawChart();
  }

  function showTab(name) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    Object.entries(panels).forEach(([k, el]) => {
      if (el) el.classList.toggle('active', k === name);
    });
    if (filterShell) filterShell.hidden = name !== 'arms';
    if (name === 'arms') {
      applyFilter();
      drawChart();
    }
  }

  tabs.forEach(t => t.addEventListener('click', () => showTab(t.dataset.tab)));
  chips().forEach(c => c.addEventListener('click', () => {
    c.classList.toggle('active');
    applyFilter();
  }));
  const showAll = document.getElementById('btn-show-all');
  const clear = document.getElementById('btn-clear');
  if (showAll) showAll.addEventListener('click', () => { chips().forEach(c => c.classList.add('active')); applyFilter(); });
  if (clear) clear.addEventListener('click', () => { chips().forEach(c => c.classList.remove('active')); applyFilter(); });

  const plotTheme = {
    paper_bgcolor: '#111111',
    plot_bgcolor: '#111111',
    font: { color: '#a8abb0', family: 'Segoe UI, sans-serif', size: 12 },
    margin: { t: 24, r: 24, b: 48, l: 56 },
    xaxis: { gridcolor: '#2a2a2a', zerolinecolor: '#333', title: 'Mean $/company' },
    yaxis: { gridcolor: '#2a2a2a', zerolinecolor: '#333', title: 'Mean findings' },
  };

  function drawChart() {
    const host = document.getElementById('chart-pareto');
    if (!host || typeof Plotly === 'undefined') return;
    let payload = {};
    try { payload = JSON.parse(host.getAttribute('data-payload') || '{}'); } catch (e) { payload = {}; }
    const active = activeFactors();
    const pts = (payload.points || []).filter(p => active.has(String(p.factor)));
    const feasible = pts.filter(p => p.feasible);
    const infeas = pts.filter(p => !p.feasible);
    const winners = pts.filter(p => p.winner);
    const traces = [];
    if (feasible.length) {
      traces.push({
        type: 'scatter', mode: 'markers+text', name: 'Feasible',
        x: feasible.map(p => p.cost), y: feasible.map(p => p.findings),
        text: feasible.map(p => p.winner ? '★' : ''),
        textposition: 'top center',
        customdata: feasible.map(p => p.label),
        hovertemplate: '%{customdata}<br>$%{x:.4f} · %{y:.2f} findings<extra></extra>',
        marker: { size: 11, color: '#5b8fc4' },
      });
    }
    if (infeas.length) {
      traces.push({
        type: 'scatter', mode: 'markers', name: 'Over budget',
        x: infeas.map(p => p.cost), y: infeas.map(p => p.findings),
        customdata: infeas.map(p => p.label),
        hovertemplate: '%{customdata}<br>$%{x:.4f} · %{y:.2f} findings<extra></extra>',
        marker: { size: 11, color: '#f85149', symbol: 'x' },
      });
    }
    if (winners.length) {
      traces.push({
        type: 'scatter', mode: 'markers', name: 'Winner',
        x: winners.map(p => p.cost), y: winners.map(p => p.findings),
        customdata: winners.map(p => p.label),
        hovertemplate: 'Winner · %{customdata}<extra></extra>',
        marker: { size: 16, color: '#c9944f', symbol: 'star' },
      });
    }
    let cval = Number(host.dataset.constraint);
    if (!Number.isFinite(cval) && payload.constraint != null) {
      cval = Number(payload.constraint);
    }

    Plotly.newPlot(host, traces, Object.assign({}, plotTheme, {
      showlegend: true,
      legend: { orientation: 'h', y: 1.12 },
      shapes: Number.isFinite(cval) ? [{
        type: 'line', x0: cval, x1: cval, y0: 0, y1: 1, yref: 'paper',
        line: { color: '#7a7e85', width: 1, dash: 'dash' },
      }] : [],
      annotations: Number.isFinite(cval) ? [{
        x: cval, y: 1, yref: 'paper', text: 'ceiling', showarrow: false,
        xanchor: 'left', font: { size: 11, color: '#7a7e85' },
      }] : [],
    }), { displayModeBar: false, responsive: true });
  }

  showTab('decision');
})();
"""
