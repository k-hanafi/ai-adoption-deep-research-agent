"""SGS Agent API request builders (no live call in this module).

Scout calls use stock `preset=fast`. Dig calls use explicit Luna knobs like PCS.
Snapshots reuse the PCS helper so dry traces share one shape.
"""

from __future__ import annotations

from typing import Any, Optional

from contracts.types import CompanyInput
from parallel_channel_search.agent_call import request_snapshot
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

# Same ladder as PCS/UAS. Digs freeze search=low; kept for explicit kwargs.
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


__all__ = [
    "build_dig_request_kwargs",
    "build_scout_request_kwargs",
    "request_snapshot",
]
