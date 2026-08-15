"""Perplexity Agent API fetch_url client for a known citation URL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import urlparse, urlunparse

from citation_verification import config
from citation_verification.text import cap_snippet, looks_soft_404


@dataclass(frozen=True)
class FetchResult:
    """Parsed page extract from one fetch call."""

    url: str
    title: str
    snippet: str
    cost_usd: float
    raw: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    source: str = config.FETCH_SOURCE_PERPLEXITY
    attempts: int = 1
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.snippet.strip())


def build_fetch_request(
    url: str,
    *,
    model: str = config.FETCH_MODEL,
    max_steps: int = config.FETCH_MAX_STEPS,
    extract_for: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Build Agent API kwargs that should fetch exactly one known URL."""
    cleaned = (url or "").strip()
    focus = ""
    if extract_for:
        joined = ", ".join(item.strip() for item in extract_for if item.strip())
        if joined:
            focus = (
                " Extract the section that mentions these exact strings: "
                f"{joined}."
            )
    return {
        "model": model,
        "input": (
            "Fetch and extract the main article text of this exact URL. "
            "Do not search. Do not open other URLs. Do not paraphrase. "
            "Do not invent missing sentences from memory."
            f"{focus} URL:\n{cleaned}"
        ),
        "instructions": (
            "Call fetch_url on the provided URL only, then stop. "
            "Do not search the web. Do not fetch a different URL. "
            "Do not summarize, complete, or replace the tool extract. "
            "If the tool fails, say so. Do not invent page text."
        ),
        "tools": [{"type": "fetch_url", "max_urls": 1}],
        "max_steps": max_steps,
        "reasoning": {"effort": "low"},
    }


def parse_fetch_response(response: Mapping[str, Any] | Any, *, requested_url: str) -> FetchResult:
    """Extract snippet/title from an Agent API response (dict or SDK object)."""
    payload = _as_mapping(response)
    cost_usd = _total_cost_usd(payload)
    contents = _fetch_contents(payload)
    if not contents:
        return FetchResult(
            url=requested_url,
            title="",
            snippet="",
            cost_usd=cost_usd,
            raw=payload if isinstance(payload, dict) else None,
            error="no fetch_url_results contents",
            source=config.FETCH_SOURCE_PERPLEXITY,
        )

    chosen = None
    for row in contents:
        if _urls_match(str(row.get("url") or ""), requested_url):
            chosen = row
            break
    if chosen is None:
        return FetchResult(
            url=requested_url,
            title="",
            snippet="",
            cost_usd=cost_usd,
            raw=payload if isinstance(payload, dict) else None,
            error=config.ERROR_URL_ROW_MISMATCH,
            source=config.FETCH_SOURCE_PERPLEXITY,
        )

    raw_snippet = str(chosen.get("snippet") or "").strip()
    title = str(chosen.get("title") or "").strip()
    url = str(chosen.get("url") or requested_url).strip()
    unusable = _unusable_snippet_reason(raw_snippet)
    if unusable is not None:
        return FetchResult(
            url=url,
            title=title,
            snippet=raw_snippet,
            cost_usd=cost_usd,
            raw=payload if isinstance(payload, dict) else None,
            error=unusable,
            source=config.FETCH_SOURCE_PERPLEXITY,
        )
    snippet, truncated = cap_snippet(raw_snippet)
    return FetchResult(
        url=url,
        title=title,
        snippet=snippet,
        cost_usd=cost_usd,
        raw=payload if isinstance(payload, dict) else None,
        error=None,
        source=config.FETCH_SOURCE_PERPLEXITY,
        truncated=truncated,
    )


def execute_fetch(
    url: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = config.FETCH_TIMEOUT_SEC,
    retries: int = config.FETCH_EMPTY_RETRIES,
    extract_for: Optional[Sequence[str]] = None,
) -> FetchResult:
    """Live Perplexity fetch_url call. Retry once on empty or tool-error output."""
    last: Optional[FetchResult] = None
    last_exc: Optional[BaseException] = None
    attempts = max(1, int(retries) + 1)
    for attempt in range(attempts):
        try:
            result = _execute_fetch_once(
                url,
                api_key=api_key,
                timeout=timeout,
                extract_for=extract_for,
            )
        except Exception as exc:  # noqa: BLE001 - retry transport timeout, then raise
            last_exc = exc
            if attempt == attempts - 1:
                raise
            continue
        tagged = FetchResult(
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            cost_usd=result.cost_usd,
            raw=result.raw,
            error=result.error,
            source=result.source,
            attempts=attempt + 1,
            truncated=result.truncated,
        )
        if tagged.ok or not _is_retryable_fetch(tagged) or attempt == attempts - 1:
            return tagged
        last = tagged
    if last is not None:
        return last
    if last_exc is not None:
        raise last_exc
    return _execute_fetch_once(
        url, api_key=api_key, timeout=timeout, extract_for=extract_for
    )


def _execute_fetch_once(
    url: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = config.FETCH_TIMEOUT_SEC,
    extract_for: Optional[Sequence[str]] = None,
) -> FetchResult:
    from perplexity import Perplexity

    from unified_adaptive_search.agent_call import require_api_key

    key = require_api_key(api_key)
    client = Perplexity(api_key=key, max_retries=0)
    kwargs = build_fetch_request(url, extract_for=extract_for)
    kwargs["timeout"] = timeout
    response = client.responses.create(**kwargs)
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    else:
        payload = response
    return parse_fetch_response(payload, requested_url=url)


def _is_retryable_fetch(result: FetchResult) -> bool:
    """Empty or tool-error output can flake. Wrong-page content is not retryable."""
    error = (result.error or "").lower()
    return (
        "no fetch_url_results contents" in error
        or "fetch_url returned no page content" in error
        or error.startswith("snippet too short")
        or error == config.ERROR_SOFT_404
    )


def _as_mapping(response: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    output = getattr(response, "output", None)
    usage = getattr(response, "usage", None)
    return {"output": output, "usage": usage}


def _total_cost_usd(payload: Mapping[str, Any]) -> float:
    usage = payload.get("usage") or {}
    if not isinstance(usage, Mapping):
        cost = getattr(usage, "cost", None)
        if cost is not None and getattr(cost, "total_cost", None) is not None:
            return float(cost.total_cost)
        return 0.0
    cost = usage.get("cost") or {}
    if isinstance(cost, Mapping) and cost.get("total_cost") is not None:
        return float(cost["total_cost"])
    return 0.0


def _fetch_contents(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in payload.get("output") or []:
        item_map = item if isinstance(item, Mapping) else _as_mapping(item)
        item_type = item_map.get("type")
        if item_type != "fetch_url_results":
            continue
        for content in item_map.get("contents") or []:
            if isinstance(content, Mapping):
                rows.append(dict(content))
            else:
                rows.append(
                    {
                        "url": getattr(content, "url", ""),
                        "title": getattr(content, "title", ""),
                        "snippet": getattr(content, "snippet", ""),
                    }
                )
    return rows


def load_fixture(path: str) -> dict[str, Any]:
    """Load a recorded Agent API JSON fixture."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _unusable_snippet_reason(snippet: str) -> Optional[str]:
    """Return an error if the snippet is empty, too short, or a tool failure."""
    if len(snippet) < config.MIN_SNIPPET_CHARS:
        return (
            f"snippet too short ({len(snippet)} chars; "
            f"min {config.MIN_SNIPPET_CHARS})"
        )
    lowered = snippet.lower()
    if "[fetch_url:" in lowered and (
        "no content could be retrieved" in lowered
        or "dns_failed_to_resolve" in lowered
        or "do not infer values for this source" in lowered
    ):
        return config.ERROR_NO_PAGE_CONTENT
    if looks_soft_404(snippet):
        return config.ERROR_SOFT_404
    return None


def _urls_match(left: str, right: str) -> bool:
    return _normalize_url(left) == _normalize_url(right)


def _normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    path = parsed.path.rstrip("/") or "/"
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    scheme = (parsed.scheme or "https").lower()
    return urlunparse((scheme, host, path, "", parsed.query, ""))
