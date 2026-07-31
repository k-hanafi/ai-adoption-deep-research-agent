"""Deterministic merge / dedupe placeholder for PCS channel findings."""

from __future__ import annotations

from contracts.types import Finding


def merge_findings(channel_findings: list[Finding]) -> list[Finding]:
    """Union findings and drop obvious duplicates by tool + URL + channel.

    Phase 1: identity merge with stable renumbering. Real heuristics come later.
    """
    seen: set[tuple[str, str, str]] = set()
    merged: list[Finding] = []
    for finding in channel_findings:
        key = (
            finding.AI_tool_used.strip().lower(),
            finding.source_url.strip().lower(),
            (finding.channel or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    for i, finding in enumerate(merged, start=1):
        finding.finding_id = i
    return merged
