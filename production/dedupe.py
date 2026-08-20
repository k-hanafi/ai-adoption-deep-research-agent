"""Derived syndication squash for production findings.csv.

``python -m production dedupe`` writes ``findings_deduplicated.csv``.
It does not change ``findings.csv`` or what ``run`` writes. No LLM.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from parallel_channel_search.merge import normalize_source_url
from production.persist import RESEARCH_COLUMNS, csv_cell, prod_paths

USE_SIMILAR = 0.70
TOOL_SIMILAR = 0.70
EVIDENCE_SIMILAR = 0.45

_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "for",
        "in",
        "on",
        "with",
        "including",
        "via",
        "through",
    }
)
_NAMED_TOOLS = frozenset(
    {
        "chatgpt",
        "gpt",
        "claude",
        "copilot",
        "cursor",
        "codex",
        "gemini",
        "perplexity",
        "grok",
        "llama",
        "midjourney",
    }
)
_PRIMARY_JOB_HOSTS = frozenset(
    {
        "linkedin.com",
        "wellfound.com",
        "angel.co",
        "jobs.ashbyhq.com",
        "ats.rippling.com",
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.smartrecruiters.com",
    }
)


@dataclass(frozen=True)
class DedupeResult:
    rows: list[dict[str, Any]]
    in_findings: int
    out_findings: int
    dropped: int


def _tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower())
    return {part for part in cleaned.split() if part and part not in _STOP}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _named_tools(tool: str) -> set[str]:
    return _tokens(tool) & _NAMED_TOOLS


def distinct_named_tools(left: str, right: str) -> bool:
    """True when two labels name different products (ChatGPT vs Copilot)."""
    named_left = _named_tools(left)
    named_right = _named_tools(right)
    if not named_left or not named_right:
        return False
    if named_left <= named_right or named_right <= named_left:
        return False
    return True


def similar_tool(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if a == b:
        return True
    if a and b and (a in b or b in a):
        return True
    if a.startswith("unspecified") and b.startswith("unspecified"):
        return True
    named_left = _named_tools(a)
    named_right = _named_tools(b)
    if named_left and named_right and (
        named_left <= named_right or named_right <= named_left
    ):
        return True
    return _jaccard(_tokens(a), _tokens(b)) >= TOOL_SIMILAR


def similar_use(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if a == b:
        return True
    return _jaccard(_tokens(a), _tokens(b)) >= USE_SIMILAR


def similar_evidence(left: str, right: str) -> bool:
    return _jaccard(_tokens(left), _tokens(right)) >= EVIDENCE_SIMILAR


def _host(url: str) -> str:
    host = urlsplit(normalize_source_url(url)).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def is_primary_job_url(url: str) -> bool:
    """Company job posting on a first-party board, not an aggregator copy."""
    raw = normalize_source_url(url)
    if not raw:
        return False
    parts = urlsplit(raw)
    host = _host(raw)
    path = (parts.path or "").lower()
    if host == "linkedin.com":
        return "/jobs/" in path
    return host in _PRIMARY_JOB_HOSTS


def distinct_role_postings(left_url: str, right_url: str) -> bool:
    """Different primary job URLs stay (Cloaked iOS vs Android)."""
    if normalize_source_url(left_url) == normalize_source_url(right_url):
        return False
    return is_primary_job_url(left_url) and is_primary_job_url(right_url)


def has_finding(row: dict[str, Any]) -> bool:
    url = str(row.get("source_url") or "").strip()
    claim = str(row.get("evidence_description") or "").strip()
    return bool(url and claim)


def is_duplicate(kept: dict[str, Any], candidate: dict[str, Any]) -> bool:
    if distinct_named_tools(
        str(kept.get("AI_tool_used") or ""),
        str(candidate.get("AI_tool_used") or ""),
    ):
        return False
    if not similar_tool(
        str(kept.get("AI_tool_used") or ""),
        str(candidate.get("AI_tool_used") or ""),
    ):
        return False
    if not similar_use(str(kept.get("use_case") or ""), str(candidate.get("use_case") or "")):
        return False

    kept_url = normalize_source_url(str(kept.get("source_url") or ""))
    cand_url = normalize_source_url(str(candidate.get("source_url") or ""))
    if kept_url == cand_url:
        return True
    if distinct_role_postings(
        str(kept.get("source_url") or ""),
        str(candidate.get("source_url") or ""),
    ):
        return False
    return similar_evidence(
        str(kept.get("evidence_description") or ""),
        str(candidate.get("evidence_description") or ""),
    )


def squash_rows(rows: Iterable[dict[str, Any]]) -> DedupeResult:
    """First row in file order wins. Blank company rows always pass through."""
    kept_by_rcid: dict[str, list[dict[str, Any]]] = {}
    out: list[dict[str, Any]] = []
    in_findings = 0
    dropped = 0

    for raw in rows:
        row = dict(raw)
        if not has_finding(row):
            out.append(row)
            continue
        in_findings += 1
        rcid = str(row.get("rcid") or "")
        prior = kept_by_rcid.setdefault(rcid, [])
        if any(is_duplicate(kept, row) for kept in prior):
            dropped += 1
            continue
        prior.append(row)
        out.append(row)

    counts = {rcid: len(group) for rcid, group in kept_by_rcid.items()}
    for row in out:
        if has_finding(row):
            row["findings_count"] = counts.get(str(row.get("rcid") or ""), 1)

    return DedupeResult(
        rows=out,
        in_findings=in_findings,
        out_findings=in_findings - dropped,
        dropped=dropped,
    )


def read_findings_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_deduplicated_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(RESEARCH_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_cell(row.get(key)) for key in RESEARCH_COLUMNS})


def run_dedupe(*, architecture: str, output_root: Path) -> DedupeResult:
    paths = prod_paths(output_root, architecture)
    source = paths.findings_csv
    if not source.exists():
        raise FileNotFoundError(f"no findings to dedupe: expected {source}")
    rows = read_findings_csv(source)
    if not rows:
        raise ValueError(f"{source}: no rows to dedupe")
    result = squash_rows(rows)
    write_deduplicated_csv(paths.findings_deduplicated_csv, result.rows)
    print(
        f"DEDUPE arch={architecture} in={result.in_findings} "
        f"out={result.out_findings} dropped={result.dropped} "
        f"wrote={paths.findings_deduplicated_csv}",
        flush=True,
    )
    return result
