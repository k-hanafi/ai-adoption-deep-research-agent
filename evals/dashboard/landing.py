"""Categorized landing index (open-dashboard target)."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from evals.dashboard.theme import DARK_CSS
from evals.paths import EVAL_INSTANCES_DIR, KIND_LABELS, KINDS, LANDING_INDEX_PATH

_EMPTY_CLI = {
    "tuning": "python -m evals run-tuning uas --stage screen",
    "benchmark": "python -m evals run-benchmarks uas",
    "verification": "python -m evals run-verification",
}


def format_local_wall_time(when: datetime, *, joiner: str) -> str:
    """Local wall clock for archive titles / landing rows.

    Builds the stamp without strftime %-d / %-I, which raise on Windows.
    """
    hour12 = when.hour % 12 or 12
    return (
        f"{when.strftime('%b')} {when.day}, {when.year}{joiner}"
        f"{hour12}:{when.strftime('%M')} {when.strftime('%p')}"
    )


def ensure_landing_stub() -> Path:
    """Rebuild index.html from catalog (soft-load on corruption)."""
    from evals.archive import load_catalog

    catalog = load_catalog(strict=False)
    return rebuild_landing(catalog)


def rebuild_landing(catalog: dict[str, Any]) -> Path:
    EVAL_INSTANCES_DIR.mkdir(parents=True, exist_ok=True)
    LANDING_INDEX_PATH.write_text(_render_index(catalog), encoding="utf-8")
    return LANDING_INDEX_PATH


def _instances_for_kind(catalog: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in catalog.get("instances") or []
        if isinstance(row, dict) and row.get("kind") == kind
    ]
    # Newest-first by n (catalog already inserts at front; sort as safety).
    rows.sort(key=lambda r: int(r.get("n") or 0), reverse=True)
    return rows


def _render_section(kind: str, rows: list[dict[str, Any]]) -> str:
    label = KIND_LABELS[kind]
    count = len(rows)
    if not rows:
        cmd = html.escape(_EMPTY_CLI[kind])
        body = (
            f'<div class="empty">No {html.escape(label.lower())} instances yet. '
            f"Create one with <code>{cmd}</code>.</div>"
        )
    else:
        parts: list[str] = [
            "<table><thead><tr>"
            "<th>#</th><th>Eval instance</th><th>Archived</th><th>File</th>"
            "</tr></thead><tbody>"
        ]
        for row in rows:
            n = html.escape(str(row.get("n") or ""))
            title = html.escape(str(row.get("title") or f"{label} #{n}"))
            href = html.escape(str(row.get("dashboard_relpath") or "#"), quote=True)
            arch = row.get("architecture") or "n/a"
            mode = "dry" if row.get("dry_run", True) else "live"
            stub = "stub · " if row.get("stub") else ""
            sha = row.get("git_sha") or "—"
            # Use ASCII hyphen in meta if sha unknown; avoid em dash in product copy.
            if sha == "—":
                sha = "unknown"
            meta = (
                f"{stub}{html.escape(str(arch))} · {html.escape(mode)} · "
                f"commit {html.escape(str(sha))}"
            )
            archived = html.escape(_format_archived(row.get("created_at")))
            filename = html.escape(Path(str(row.get("dashboard_relpath") or "")).name)
            parts.append(
                "<tr>"
                f"<td>{n}</td>"
                f"<td class='title-cell'><a href='{href}'>{title}</a>"
                f"<span class='meta'>{meta}</span></td>"
                f"<td>{archived}</td>"
                f"<td><code>{filename}</code></td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
        body = "\n".join(parts)

    return (
        f'<section class="section" id="{html.escape(kind)}">'
        f"<h2>{html.escape(label)} · {count} archived</h2>"
        f"{body}"
        "</section>"
    )


def _format_archived(created_at: Optional[str]) -> str:
    if not created_at:
        return ""
    try:
        when = datetime.fromisoformat(created_at)
    except ValueError:
        return str(created_at)
    if when.tzinfo is not None:
        when = when.astimezone()
    return format_local_wall_time(when, joiner=", ")


def _render_index(catalog: dict[str, Any]) -> str:
    total = len(catalog.get("instances") or [])
    sections = "\n".join(
        _render_section(kind, _instances_for_kind(catalog, kind)) for kind in KINDS
    )
    rewritten = datetime.now().astimezone().strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Eval Suite · instance archive</title>
  <style>{DARK_CSS}</style>
</head>
<body>
  <div class="wrap">
    <div class="header-row">
      <div>
        <h1>Eval Suite</h1>
        <p class="subtitle">instance archive</p>
      </div>
      <p class="chip">{total} archived</p>
    </div>
    <p class="lede">
      Each row is one CLI invocation of
      <code>run-tuning</code>, <code>run-benchmarks</code>, or
      <code>run-verification</code>. Click a title to open that instance dashboard.
      Times use this machine's local timezone.
    </p>
    {sections}
    <p class="footer">Index rewritten {html.escape(rewritten)}.</p>
  </div>
</body>
</html>
"""
