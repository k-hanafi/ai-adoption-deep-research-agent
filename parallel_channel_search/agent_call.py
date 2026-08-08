"""Agent API request builder for one PCS channel call.

Builds explicit kwargs (model, max_steps, reasoning, tools) instead of a
dynamic `preset` name. Matches the UAS request shape so the bake-off compares
architectures, not API packaging.

Dry-run uses `build_request_kwargs` only (no Perplexity SDK import).
Live `execute_agent_call` lands in a later PR.
"""

from __future__ import annotations

from typing import Any, Optional

from contracts.types import CompanyInput
from parallel_channel_search.channels import (
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
)
from parallel_channel_search.prompting import RESPONSE_SCHEMA, build_channel_prompt

# Same ladder as UAS: low/medium/high → rising search package size.
# Kept local so PCS does not import UAS internals.
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


def build_request_kwargs(
    company: CompanyInput,
    channel_id: str,
    *,
    model: str = DEFAULT_MODEL,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> dict[str, Any]:
    """Build explicit kwargs for one PCS channel Agent API call (no preset)."""
    depth = (web_search_depth or DEFAULT_WEB_SEARCH_DEPTH).strip().lower()
    if depth not in _WEB_SEARCH_DEPTH:
        known = ", ".join(sorted(_WEB_SEARCH_DEPTH))
        raise ValueError(f"Unknown web_search_depth {web_search_depth!r}. Choose: {known}")

    kwargs: dict[str, Any] = {
        "model": model,
        "input": build_channel_prompt(company, channel_id),
        "response_format": RESPONSE_SCHEMA,
        "reasoning": {"effort": reasoning_effort},
        "tools": [
            {
                "type": "web_search",
                **_WEB_SEARCH_DEPTH[depth],
            },
            {"type": "fetch_url"},
        ],
    }
    # Match UAS / March: omit falsy max_steps (including 0).
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs


def request_snapshot(request_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Compact dry-run / trace view of one channel request (no full prompt text)."""
    return {
        "model": request_kwargs.get("model"),
        "max_steps": request_kwargs.get("max_steps"),
        "reasoning": request_kwargs.get("reasoning"),
        "tools": request_kwargs.get("tools"),
        "has_response_format": "response_format" in request_kwargs,
        "input_chars": len(request_kwargs.get("input") or ""),
        "has_preset": "preset" in request_kwargs,
    }
