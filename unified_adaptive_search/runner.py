"""Public UAS entrypoint: `run(company) -> ArchitectureResult`."""

from __future__ import annotations

from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from unified_adaptive_search.agent_call import (
    DEFAULT_MAX_STEPS,
    DEFAULT_PRESET,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
    build_request_kwargs,
)

ARCHITECTURE_NAME = "Unified Adaptive Search"
ARCHITECTURE_CLI_KEY = "unified-adaptive-search"


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    preset: str = DEFAULT_PRESET,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> ArchitectureResult:
    """Run UAS for one company.

    Dry-run builds the request kwargs snapshot (including effort + search depth)
    and returns a structured placeholder with a `unified_call` ledger.
    """
    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )
    request_kwargs = build_request_kwargs(
        company_input,
        preset=preset,
        max_steps=max_steps,
        reasoning_effort=reasoning_effort,
        web_search_depth=web_search_depth,
    )

    if not dry_run:
        raise NotImplementedError(
            "Unified Adaptive Search live Agent API calls are not wired yet. "
            "Use dry_run=True, or "
            "python -m src.stage_2.production_agent_runner for March-style batch runs."
        )

    ledger = CostLedger.from_components(
        [
            CostComponent(
                name="unified_call",
                preset=preset,
                cost_usd=0.0,
                ran=False,
                skipped_reason="dry_run_no_api",
            )
        ]
    )

    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=[],
        cost_ledger=ledger,
        genai_adoption_found=False,
        no_finding_reason="dry_run",
        no_finding_analysis=(
            "Unified Adaptive Search dry-run: single "
            f"preset={preset!r} call "
            f"(max_steps={max_steps}, reasoning.effort={reasoning_effort!r}, "
            f"web_search_depth={web_search_depth!r}). "
            "No Perplexity Agent API call was made."
        ),
        traces={
            "strategy": "unified_adaptive_search",
            "phase": "dry_run",
            "request_snapshot": {
                "preset": request_kwargs.get("preset"),
                "max_steps": request_kwargs.get("max_steps"),
                "reasoning": request_kwargs.get("reasoning"),
                "tools": request_kwargs.get("tools"),
                "has_response_format": "response_format" in request_kwargs,
                "input_chars": len(request_kwargs.get("input") or ""),
            },
            "prompt_lineage": "prompts/stage_2_perplexity_prompt.txt",
            "source_patterns": "src/stage_2/production_agent_runner.py",
        },
        stub=True,
        dry_run=True,
        preset=preset,
    )
