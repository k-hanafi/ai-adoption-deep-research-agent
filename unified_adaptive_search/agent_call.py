"""Thin Agent API request builder for UAS (single call per company).

Phase 1 dry-run path does not import or call the Perplexity SDK.
Live call wiring stays with src/stage_2/production_agent_runner.py until
Phase 2 pays for panel runs.
"""

from __future__ import annotations

from typing import Any, Optional

from contracts.types import CompanyInput
from unified_adaptive_search.prompting import RESPONSE_SCHEMA, build_company_prompt

# Modern preset name for the March `deep-research` tier (plan §0 / §3.3).
DEFAULT_PRESET = "medium"
DEFAULT_MAX_STEPS = 10


def build_request_kwargs(
    company: CompanyInput,
    *,
    preset: str = DEFAULT_PRESET,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
) -> dict[str, Any]:
    """Build the kwargs snapshot for one UAS Agent API call."""
    kwargs: dict[str, Any] = {
        "preset": preset,
        "input": build_company_prompt(company),
        "response_format": RESPONSE_SCHEMA,
    }
    # Match March production: omit falsy max_steps (including 0).
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs
