"""Thin Agent API request builder for UAS (single call per company).

Dry-run path does not import or call the Perplexity SDK.
Live call wiring stays with src/stage_2/production_agent_runner.py until
paid panel runs are enabled.
"""

from __future__ import annotations

from typing import Any, Optional

from contracts.types import CompanyInput
from unified_adaptive_search.prompting import RESPONSE_SCHEMA, build_company_prompt

# Modern preset name for the March `deep-research` tier.
DEFAULT_PRESET = "medium"
DEFAULT_MAX_STEPS = 10
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_WEB_SEARCH_DEPTH = "medium"

# Map depth labels to illustrative web_search tool options (request snapshot).
_WEB_SEARCH_DEPTH: dict[str, dict[str, Any]] = {
    "medium": {
        "search_context_size": "medium",
        "max_tokens": 2000,
    },
    "high": {
        "search_context_size": "high",
        "max_tokens": 4000,
    },
}


def build_request_kwargs(
    company: CompanyInput,
    *,
    preset: str = DEFAULT_PRESET,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> dict[str, Any]:
    """Build the kwargs snapshot for one UAS Agent API call."""
    depth = (web_search_depth or DEFAULT_WEB_SEARCH_DEPTH).strip().lower()
    if depth not in _WEB_SEARCH_DEPTH:
        known = ", ".join(sorted(_WEB_SEARCH_DEPTH))
        raise ValueError(f"Unknown web_search_depth {web_search_depth!r}. Choose: {known}")

    kwargs: dict[str, Any] = {
        "preset": preset,
        "input": build_company_prompt(company),
        "response_format": RESPONSE_SCHEMA,
        "reasoning": {"effort": reasoning_effort},
        "tools": [
            {
                "type": "web_search",
                **_WEB_SEARCH_DEPTH[depth],
            }
        ],
    }
    # Match March production: omit falsy max_steps (including 0).
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs
