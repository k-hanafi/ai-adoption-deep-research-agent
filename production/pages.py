"""Sidecar page cache for Stage 3: scrape once, judge many times.

``pages.jsonl`` holds the extract (and fetch failures). Last write per
source URL wins. The operator CSV stays stamp-sized; 32k-char pages
never go there.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from citation_verification.fetch import FetchResult, is_flaky_fetch_error
from production.persist import is_retryable

PAGE_RECORD_FIELDS: tuple[str, ...] = (
    "source_url",
    "fetched_url",
    "fetched_title",
    "fetch_source",
    "snippet",
    "truncated",
    "fetch_ok",
    "error",
    "cost_usd",
    "attempts",
    "fetched_at",
)


def page_cache_key(url: str) -> str:
    return (url or "").strip()


def page_cache_reusable(record: Optional[Mapping[str, Any]]) -> bool:
    """429/timeout and flaky empty extracts must not block a refetch."""
    if not record:
        return False
    error = str(record.get("error") or "")
    return not is_retryable(error) and not is_flaky_fetch_error(error)


def record_from_fetch(
    source_url: str,
    page: FetchResult,
    *,
    fetch_cost: float,
    fetch_attempts: int,
    fetched_at: Optional[str] = None,
) -> dict[str, Any]:
    stamp = fetched_at or datetime.now(timezone.utc).isoformat()
    return {
        "source_url": page_cache_key(source_url),
        "fetched_url": (page.url or source_url or "").strip(),
        "fetched_title": page.title or "",
        "fetch_source": page.source or "",
        "snippet": page.snippet or "",
        "truncated": bool(page.truncated),
        "fetch_ok": bool(page.ok),
        "error": page.error or "",
        "cost_usd": float(fetch_cost),
        "attempts": max(1, int(fetch_attempts)),
        "fetched_at": stamp,
    }


def fetch_from_record(record: Mapping[str, Any]) -> FetchResult:
    error = str(record.get("error") or "").strip() or None
    try:
        attempts = int(record.get("attempts") or 1)
    except (TypeError, ValueError):
        attempts = 1
    return FetchResult(
        url=str(record.get("fetched_url") or record.get("source_url") or ""),
        title=str(record.get("fetched_title") or ""),
        snippet=str(record.get("snippet") or ""),
        cost_usd=0.0,
        error=error,
        source=str(record.get("fetch_source") or ""),
        attempts=max(1, attempts),
        truncated=bool(record.get("truncated")),
    )


def load_pages_by_url(path: Path) -> dict[str, dict[str, Any]]:
    """Last write per source_url wins."""
    if not path.exists():
        return {}
    by_url: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        key = page_cache_key(str(record.get("source_url") or ""))
        if not key:
            continue
        by_url[key] = record
    return by_url


def append_page_record(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: record.get(key, "") for key in PAGE_RECORD_FIELDS}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
