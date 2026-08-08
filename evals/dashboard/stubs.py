"""Stub dashboards for archive categories not fully wired yet."""

from __future__ import annotations

import html
import json
from typing import Any

from evals.dashboard.theme import SUITE_CSS
from evals.paths import KIND_LABELS


_STUB_COPY = {
    "tuning": (
        "Tuning instances show Stage A/B hyperparameter arms, the "
        "~$0.10/company constraint, and a winner under that budget."
    ),
    "benchmark": (
        "Benchmark instances will compare UAS / PCS / SGS on a held-out paired "
        "panel (Phase 3 bake-off). Not wired in this MVP."
    ),
    "verification": (
        "Verification instances will run the Stage 3 citation judge. "
        "Not wired in this MVP."
    ),
}


def render_stub_dashboard(
    *,
    kind: str,
    title: str,
    summary: dict[str, Any],
) -> str:
    label = KIND_LABELS.get(kind, kind.title())
    copy = _STUB_COPY.get(kind, "Stub eval instance.")
    safe_title = html.escape(title)
    arch = summary.get("architecture") or "n/a"
    cli = summary.get("cli") or ""
    mode = "dry" if summary.get("dry_run", True) else "live"
    sha = summary.get("git_sha") or "unknown"
    payload = html.escape(json.dumps(summary, indent=2))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{safe_title}</title>
<style>
{SUITE_CSS}
</style>
</head>
<body>
<header class="appbar">
  <div class="brand">Deep Research Eval Suite<small>{html.escape(label)} stub</small></div>
  <div class="appbar-meta">{html.escape(str(arch))} · {html.escape(mode)} · commit {html.escape(str(sha))}</div>
</header>
<div class="notice dry">
  <span class="tag">Stub</span>
  <div><span class="run-headline">{safe_title}</span>
  <span class="run-meta">{html.escape(copy)}</span></div>
</div>
<main class="content">
  <div class="tab-lead">
    <h2>{safe_title}</h2>
    <p>CLI: <code>{html.escape(cli)}</code></p>
  </div>
  <div class="card">
    <div class="card-title">summary.json</div>
    <pre style="font-family:var(--mono);font-size:12px;white-space:pre-wrap;color:var(--text2)">{payload}</pre>
  </div>
  <footer class="page-footer"><a href="../../index.html">Back to archive</a></footer>
</main>
</body>
</html>
"""
