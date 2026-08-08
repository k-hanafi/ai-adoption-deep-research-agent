"""Deterministic merge / dedupe for PCS channel findings."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit

from contracts.types import Finding


def normalize_source_url(url: str) -> str:
    """Normalize a source URL for cross-channel dedupe.

    Lowercases scheme/host, strips whitespace and fragments, and drops a trailing
    slash on non-root paths. Query strings are kept (different query can be a
    different evidence page).
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def _dedupe_key(finding: Finding) -> tuple[str, str]:
    tool = (finding.AI_tool_used or "").strip().lower()
    url = normalize_source_url(finding.source_url or "")
    return (tool, url)


def merge_findings(channel_findings: list[Finding]) -> list[Finding]:
    """Union channel findings and drop duplicates by normalized (tool, url).

    First occurrence wins (callers should pass channels in stable order:
    jobs → owned → third_party). Provenance `channel` on the kept finding is
    preserved. `finding_id` is renumbered 1..N on copies.
    """
    seen: set[tuple[str, str]] = set()
    merged: list[Finding] = []
    for finding in channel_findings:
        key = _dedupe_key(finding)
        # Empty tool+url rows still pass once; later empties collapse together.
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return [replace(finding, finding_id=i) for i, finding in enumerate(merged, start=1)]
