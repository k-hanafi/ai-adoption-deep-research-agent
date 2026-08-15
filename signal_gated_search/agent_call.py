"""SGS Agent API request builders and live scout/dig calls.

Scout calls use stock `preset=low`. Dig calls use explicit Luna knobs like PCS.
Digs reuse the PCS live executor (same findings schema). Scouts parse presence JSON.
Snapshots reuse the PCS helper so dry traces share one shape.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from contracts.types import CompanyInput
from parallel_channel_search.agent_call import (
    execute_agent_call,
    request_snapshot,
)
from signal_gated_search.channels import (
    DEFAULT_DIG_MAX_STEPS,
    DEFAULT_DIG_MODEL,
    DEFAULT_DIG_WEB_SEARCH_DEPTH,
    DEFAULT_SCOUT_MAX_STEPS,
    DEFAULT_SCOUT_PRESET,
)
from signal_gated_search.prompting import (
    DIG_RESPONSE_SCHEMA,
    SCOUT_RESPONSE_SCHEMA,
    build_dig_prompt,
    build_scout_prompt,
)

DEFAULT_TIMEOUT = 300.0

# Same ladder as PCS. Digs freeze search=medium; kept for explicit kwargs.
_WEB_SEARCH_DEPTH: dict[str, dict[str, Any]] = {
    "low": {
        "search_context_size": "medium",
        "max_tokens": 2000,
        "max_tokens_per_page": 1000,
        "max_results": 10,
    },
    "medium": {
        "search_context_size": "high",
        "max_tokens": 4000,
        "max_tokens_per_page": 2000,
        "max_results": 20,
    },
    "high": {
        "search_context_size": "high",
        "max_tokens": 8000,
        "max_tokens_per_page": 4000,
        "max_results": 50,
    },
}


def build_scout_request_kwargs(
    company: CompanyInput,
    channel_id: str,
    *,
    preset: str = DEFAULT_SCOUT_PRESET,
    max_steps: Optional[int] = DEFAULT_SCOUT_MAX_STEPS,
) -> dict[str, Any]:
    """Build kwargs for one presence-scout Agent API call."""
    kwargs: dict[str, Any] = {
        "preset": preset,
        "input": build_scout_prompt(company, channel_id),
        "response_format": SCOUT_RESPONSE_SCHEMA,
        "tools": [{"type": "web_search"}],
    }
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs


def build_dig_request_kwargs(
    company: CompanyInput,
    channel_id: str,
    *,
    model: str = DEFAULT_DIG_MODEL,
    max_steps: Optional[int] = DEFAULT_DIG_MAX_STEPS,
    reasoning_effort: str,
    web_search_depth: str = DEFAULT_DIG_WEB_SEARCH_DEPTH,
) -> dict[str, Any]:
    """Build kwargs for one cold-start dig Agent API call (no scout URLs)."""
    depth = (web_search_depth or DEFAULT_DIG_WEB_SEARCH_DEPTH).strip().lower()
    if depth not in _WEB_SEARCH_DEPTH:
        known = ", ".join(sorted(_WEB_SEARCH_DEPTH))
        raise ValueError(f"Unknown web_search_depth {web_search_depth!r}. Choose: {known}")

    kwargs: dict[str, Any] = {
        "model": model,
        "input": build_dig_prompt(company, channel_id),
        "response_format": DIG_RESPONSE_SCHEMA,
        "reasoning": {"effort": reasoning_effort},
        "tools": [
            {"type": "web_search", **_WEB_SEARCH_DEPTH[depth]},
            {"type": "fetch_url"},
        ],
    }
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs


def require_api_key(api_key: Optional[str] = None) -> str:
    """Resolve Perplexity key from arg, credentials file, or env. Refuse if missing."""
    if api_key:
        return api_key
    from src.config import APIKeys

    key = APIKeys().perplexity
    if not key:
        raise RuntimeError(
            "Perplexity API key required for live Signal Gated Search. "
            "Set credentials/perplexity_api_key.txt or PERPLEXITY_API_KEY. "
            "Use dry_run=True to build request snapshots without calling the API."
        )
    return key


def execute_dig_call(
    request_kwargs: dict[str, Any],
    *,
    channel_id: str,
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """One sync dig call. Reuses PCS parse/metering (same findings schema)."""
    return execute_agent_call(
        request_kwargs,
        channel_id=channel_id,
        api_key=api_key,
        timeout=timeout,
    )


def _extract_text_fallback(output: list) -> str:
    """Walk output items for text when `output_text` is empty (PCS/UAS pattern)."""
    texts: list[str] = []
    for item in output or []:
        for part in getattr(item, "content", None) or []:
            text = getattr(part, "text", None)
            if text:
                texts.append(text)
    return "".join(texts)


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _usage_meta(response: Any, *, channel_id: str) -> dict[str, Any]:
    cost_usd = 0.0
    input_tokens = None
    output_tokens = None
    total_tokens = None
    if getattr(response, "usage", None):
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = response.usage.total_tokens
        if response.usage.cost and response.usage.cost.total_cost is not None:
            cost_usd = float(response.usage.cost.total_cost)
    return {
        "channel_id": channel_id,
        "response_id": getattr(response, "id", None),
        "model_used": getattr(response, "model", None),
        "response_status": getattr(response, "status", None),
        "cost_usd": cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "evidence_bin": "none",
        "urls": [],
        "snippets": [],
        "rationale": "",
        "error": None,
        "transport_error": False,
        "raw_content_preview": None,
    }


def execute_scout_call(
    request_kwargs: dict[str, Any],
    *,
    channel_id: str,
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """One sync presence-scout call. Returns bin/urls plus usage."""
    from perplexity import Perplexity

    key = require_api_key(api_key)
    client = Perplexity(api_key=key, max_retries=0)
    create_kwargs = dict(request_kwargs)
    create_kwargs["timeout"] = timeout
    response = client.responses.create(**create_kwargs)
    meta = _usage_meta(response, channel_id=channel_id)

    if getattr(response, "status", None) == "failed":
        err = getattr(response, "error", None)
        detail = f"{err.type}: {err.message}" if err else "unknown"
        meta["error"] = f"Agent API response failed: {detail}"
        return meta

    content = (getattr(response, "output_text", None) or "").strip()
    if not content:
        content = _extract_text_fallback(list(getattr(response, "output", None) or [])).strip()
    if not content:
        meta["error"] = (
            f"Empty Agent API scout response (model={meta['model_used']}, "
            f"status={meta['response_status']})"
        )
        return meta

    meta["raw_content_preview"] = content[:500]
    try:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = json.loads(_extract_json_object(content))
        if not isinstance(parsed, dict):
            meta["error"] = (
                f"JSON root must be an object, got {type(parsed).__name__}"
            )
            return meta
        meta["evidence_bin"] = str(parsed.get("evidence_bin") or "none")
        urls = parsed.get("urls") or []
        snippets = parsed.get("snippets") or []
        meta["urls"] = [str(u) for u in urls] if isinstance(urls, list) else []
        meta["snippets"] = (
            [str(s) for s in snippets] if isinstance(snippets, list) else []
        )
        meta["rationale"] = str(parsed.get("rationale") or "")
    except json.JSONDecodeError as exc:
        meta["error"] = f"JSON parse error: {exc}"
    except Exception as exc:
        meta["error"] = f"Response parse error: {type(exc).__name__}: {exc}"
    return meta


__all__ = [
    "DEFAULT_TIMEOUT",
    "build_dig_request_kwargs",
    "build_scout_request_kwargs",
    "execute_dig_call",
    "execute_scout_call",
    "request_snapshot",
    "require_api_key",
]
