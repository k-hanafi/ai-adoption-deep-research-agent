"""Second-fetch path: Tavily Extract, then raw httpx, browser last. No Jina."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import httpx

from citation_verification import config
from citation_verification.fetch import FetchResult
from citation_verification.text import cap_snippet

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def execute_backup_chain(
    url: str,
    *,
    query: Optional[Sequence[str]] = None,
) -> FetchResult:
    """Try Tavily Extract, then httpx, then optional browser. Sum costs."""
    attempts = 0
    cost = 0.0
    last = _empty_result(url, "backup fetch produced no page", attempts=0)

    tavily = execute_tavily_extract(url, query=query)
    attempts += max(1, tavily.attempts)
    cost += tavily.cost_usd
    if tavily.ok:
        return _with_cost_attempts(tavily, cost=cost, attempts=attempts)
    last = tavily

    raw = execute_httpx_fetch(url)
    attempts += max(1, raw.attempts)
    cost += raw.cost_usd
    if raw.ok:
        return _with_cost_attempts(raw, cost=cost, attempts=attempts)
    last = raw

    browser = execute_browser_fetch(url)
    attempts += max(1, browser.attempts)
    cost += browser.cost_usd
    if browser.ok:
        return _with_cost_attempts(browser, cost=cost, attempts=attempts)
    if last.error:
        return _with_cost_attempts(last, cost=cost, attempts=attempts)
    return _with_cost_attempts(browser, cost=cost, attempts=attempts)


def execute_tavily_extract(
    url: str,
    *,
    query: Optional[Sequence[str]] = None,
    api_key: Optional[str] = None,
) -> FetchResult:
    """URL-in, clean text-out. Paid backup only. Not Tavily Search."""
    key = api_key or _tavily_api_key()
    if not key:
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error="tavily api key missing",
            source=config.FETCH_SOURCE_TAVILY,
        )
    payload: dict[str, Any] = {
        "urls": [url],
        "extract_depth": config.TAVILY_EXTRACT_DEPTH,
        "format": "text",
    }
    if query:
        joined = " ".join(item.strip() for item in query if item.strip())
        if joined:
            payload["query"] = joined
            payload["chunks_per_source"] = 5
    try:
        with httpx.Client(timeout=config.HTTPX_TIMEOUT_SEC) as client:
            response = client.post(
                config.TAVILY_EXTRACT_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except Exception as exc:  # noqa: BLE001 - backup must not raise into judge
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error=f"tavily extract failed: {exc}",
            source=config.FETCH_SOURCE_TAVILY,
        )
    return _parse_tavily_extract(body, requested_url=url)


def execute_httpx_fetch(url: str) -> FetchResult:
    """Raw GET for static HTML. Fails on JS walls and many PDFs."""
    try:
        with httpx.Client(
            timeout=config.HTTPX_TIMEOUT_SEC,
            follow_redirects=True,
        ) as client:
            response = client.get(url, headers={"User-Agent": "citation-verification/1.0"})
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            final_url = str(response.url)
            if "pdf" in content_type or final_url.lower().endswith(".pdf"):
                return FetchResult(
                    url=final_url,
                    title="",
                    snippet="",
                    cost_usd=0.0,
                    error="pdf extract unavailable",
                    source=config.FETCH_SOURCE_HTTPX,
                )
            text = _html_to_text(response.text)
    except Exception as exc:  # noqa: BLE001 - backup must not raise into judge
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error=f"httpx fetch failed: {exc}",
            source=config.FETCH_SOURCE_HTTPX,
        )
    snippet, truncated = cap_snippet(text)
    if len(snippet) < config.MIN_SNIPPET_CHARS:
        return FetchResult(
            url=final_url,
            title=_title_from_text(snippet),
            snippet=snippet,
            cost_usd=0.0,
            error=(
                f"snippet too short ({len(snippet)} chars; "
                f"min {config.MIN_SNIPPET_CHARS})"
            ),
            source=config.FETCH_SOURCE_HTTPX,
            truncated=truncated,
        )
    return FetchResult(
        url=final_url,
        title=_title_from_text(snippet),
        snippet=snippet,
        cost_usd=0.0,
        error=None,
        source=config.FETCH_SOURCE_HTTPX,
        truncated=truncated,
    )


def execute_browser_fetch(url: str) -> FetchResult:
    """Optional last resort. Off unless CITATION_VERIFICATION_BROWSER=1."""
    if os.environ.get("CITATION_VERIFICATION_BROWSER") != "1":
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error="browser fetch not enabled",
            source=config.FETCH_SOURCE_BROWSER,
        )
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error="playwright not installed",
            source=config.FETCH_SOURCE_BROWSER,
        )
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            title = page.title()
            html = page.content()
            browser.close()
    except Exception as exc:  # noqa: BLE001 - last resort must not raise
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error=f"browser fetch failed: {exc}",
            source=config.FETCH_SOURCE_BROWSER,
        )
    snippet, truncated = cap_snippet(_html_to_text(html))
    if len(snippet) < config.MIN_SNIPPET_CHARS:
        return FetchResult(
            url=url,
            title=title,
            snippet=snippet,
            cost_usd=0.0,
            error=(
                f"snippet too short ({len(snippet)} chars; "
                f"min {config.MIN_SNIPPET_CHARS})"
            ),
            source=config.FETCH_SOURCE_BROWSER,
            truncated=truncated,
        )
    return FetchResult(
        url=url,
        title=title,
        snippet=snippet,
        cost_usd=0.0,
        error=None,
        source=config.FETCH_SOURCE_BROWSER,
        truncated=truncated,
    )


def _parse_tavily_extract(body: Mapping[str, Any] | Any, *, requested_url: str) -> FetchResult:
    payload = body if isinstance(body, dict) else {}
    rows = payload.get("results") or []
    if not rows:
        failed = payload.get("failed_results") or []
        detail = ""
        if failed and isinstance(failed[0], dict):
            detail = str(failed[0].get("error") or failed[0].get("url") or "")
        return FetchResult(
            url=requested_url,
            title="",
            snippet="",
            cost_usd=_tavily_cost(payload),
            raw=payload,
            error=f"tavily extract empty{': ' + detail if detail else ''}",
            source=config.FETCH_SOURCE_TAVILY,
        )
    row = rows[0] if isinstance(rows[0], dict) else {}
    raw_text = str(row.get("raw_content") or row.get("content") or "").strip()
    title = str(row.get("title") or "").strip() or _title_from_text(raw_text)
    final_url = str(row.get("url") or requested_url).strip()
    snippet, truncated = cap_snippet(raw_text)
    if len(snippet) < config.MIN_SNIPPET_CHARS:
        return FetchResult(
            url=final_url,
            title=title,
            snippet=snippet,
            cost_usd=_tavily_cost(payload),
            raw=payload,
            error=(
                f"snippet too short ({len(snippet)} chars; "
                f"min {config.MIN_SNIPPET_CHARS})"
            ),
            source=config.FETCH_SOURCE_TAVILY,
            truncated=truncated,
        )
    return FetchResult(
        url=final_url,
        title=title,
        snippet=snippet,
        cost_usd=_tavily_cost(payload),
        raw=payload,
        error=None,
        source=config.FETCH_SOURCE_TAVILY,
        truncated=truncated,
    )


def _tavily_cost(payload: dict[str, Any]) -> float:
    usage = payload.get("usage") or {}
    if isinstance(usage, dict) and usage.get("total_cost") is not None:
        return float(usage["total_cost"])
    cost = payload.get("cost")
    if isinstance(cost, (int, float)):
        return float(cost)
    return 0.0


def _tavily_api_key() -> str:
    env = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if env:
        return env
    path = PROJECT_ROOT / "credentials" / "tavily_api_key.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _html_to_text(html: str) -> str:
    cleaned = _SCRIPT_STYLE.sub(" ", html or "")
    cleaned = _TAG.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _title_from_text(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def _empty_result(url: str, error: str, *, attempts: int) -> FetchResult:
    return FetchResult(
        url=url,
        title="",
        snippet="",
        cost_usd=0.0,
        error=error,
        source=config.FETCH_SOURCE_TAVILY,
        attempts=attempts,
    )


def _with_cost_attempts(result: FetchResult, *, cost: float, attempts: int) -> FetchResult:
    return FetchResult(
        url=result.url,
        title=result.title,
        snippet=result.snippet,
        cost_usd=round(cost, 6),
        raw=result.raw,
        error=result.error,
        source=result.source,
        attempts=attempts,
        truncated=result.truncated,
    )
