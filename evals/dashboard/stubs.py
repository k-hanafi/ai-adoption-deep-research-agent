"""Stub dashboards for archive categories not fully wired yet."""

from __future__ import annotations

import html
import json
from typing import Any

from evals.dashboard.theme import DARK_CSS
from evals.paths import KIND_LABELS


_STUB_COPY = {
    "tuning": (
        "Tuning instances will show Stage A/B hyperparameter arms, the "
        "~$0.10/company constraint, and a winner under that budget. "
        "This stub only proves archive wiring. Real Stage A screen lands in the next PR."
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
    meta = (
        f"{html.escape(str(arch))} · {html.escape(mode)} · "
        f"commit {html.escape(str(sha))}"
    )
    body = html.escape(copy)
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
    <p class="chip">{html.escape(label)} stub</p>
    <div class="header-row">
      <h1>{safe_title}</h1>
    </div>
    <p class="subtitle">{meta}</p>
    <div class="banner">{body}</div>
    <p class="meta">CLI: <code>{html.escape(cli)}</code></p>
    <h2 class="section" style="margin-top:1.5rem">summary.json</h2>
    <pre>{payload}</pre>
    <p class="footer"><a href="../../index.html">Back to archive</a></p>
  </div>
</body>
</html>
"""
