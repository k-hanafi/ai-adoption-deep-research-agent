"""Perplexity Agent API fetch_url client for a known citation URL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from citation_verification import config


@dataclass(frozen=True)
class FetchResult:
    """Parsed page extract from one fetch_url call."""

    url: str
    title: str
    snippet: str
    cost_usd: float
    raw: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.snippet.strip())


def build_fetch_request(
    url: str,
    *,
    model: str = config.FETCH_MODEL,
    max_steps: int = config.FETCH_MAX_STEPS,
) -> dict[str, Any]:
    """Build Agent API kwargs that should fetch exactly one known URL."""
    cleaned = (url or "").strip()
    return {
        "model": model,
        "input": (
            "Fetch and extract the main text content of this exact URL. "
            "Do not search for other pages. URL:\n"
            f"{cleaned}"
        ),
        "instructions": (
            "You must call the fetch_url tool on the provided URL and then "
            "stop. Do not invent content if the fetch fails."
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
        )

    # Prefer exact URL match; otherwise first content row.
    chosen = None
    for row in contents:
        if str(row.get("url") or "").strip() == requested_url.strip():
            chosen = row
            break
    if chosen is None:
        chosen = contents[0]

    snippet = str(chosen.get("snippet") or "").strip()
    title = str(chosen.get("title") or "").strip()
    url = str(chosen.get("url") or requested_url).strip()
    if len(snippet) < config.MIN_SNIPPET_CHARS:
        return FetchResult(
            url=url,
            title=title,
            snippet=snippet,
            cost_usd=cost_usd,
            raw=payload if isinstance(payload, dict) else None,
            error=(
                f"snippet too short ({len(snippet)} chars; "
                f"min {config.MIN_SNIPPET_CHARS})"
            ),
        )
    if len(snippet) > config.MAX_SNIPPET_CHARS:
        snippet = snippet[: config.MAX_SNIPPET_CHARS]
    return FetchResult(
        url=url,
        title=title,
        snippet=snippet,
        cost_usd=cost_usd,
        raw=payload if isinstance(payload, dict) else None,
        error=None,
    )


def execute_fetch(
    url: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 120.0,
) -> FetchResult:
    """Live Perplexity fetch_url call."""
    from perplexity import Perplexity

    from unified_adaptive_search.agent_call import require_api_key

    key = require_api_key(api_key)
    client = Perplexity(api_key=key, max_retries=0)
    kwargs = build_fetch_request(url)
    kwargs["timeout"] = timeout
    response = client.responses.create(**kwargs)
    # Prefer model_dump when available for stable parsing.
    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    else:
        payload = response
    return parse_fetch_response(payload, requested_url=url)


def _as_mapping(response: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    # Best-effort attribute bridge for tests.
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
