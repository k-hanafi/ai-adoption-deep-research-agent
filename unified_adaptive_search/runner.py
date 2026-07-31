"""Public UAS entrypoint: `run(company) -> ArchitectureResult`.

Adapted from src/stage_2/production_agent_runner.py:
- one Agent API call shape per company
- Stage 2 prompt + RESPONSE_SCHEMA lineage
- component cost ledger with a single `unified_call` row

Phase 1 default is dry_run=True (no paid API). Pass dry_run=False later
when the live client path is wired for panel evals.
"""

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
) -> ArchitectureResult:
    """Run UAS for one company.

    Phase 1: dry-run / wiring path. Builds the real request kwargs snapshot
    and returns a structured placeholder result with a `unified_call` ledger.
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
    )

    if not dry_run:
        # Live Agent API path intentionally not implemented in Phase 1.
        # Production batch runs remain on src.stage_2.production_agent_runner.
        raise NotImplementedError(
            "Unified Adaptive Search live Agent API calls are Phase 2. "
            "Use dry_run=True for scaffolding, or "
            "python -m src.stage_2.production_agent_runner for March-style batch runs."
        )

    ledger = CostLedger.from_components(
        [
            CostComponent(
                name="unified_call",
                preset=preset,
                cost_usd=0.0,
                ran=False,
                skipped_reason="phase1_dry_run_no_api",
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
        no_finding_reason="phase1_dry_run",
        no_finding_analysis=(
            "Unified Adaptive Search Phase 1 dry-run: single "
            f"preset={preset!r} call shape (max_steps={max_steps}). "
            "Request kwargs were built from the Stage 2 prompt lineage. "
            "No Perplexity Agent API call was made."
        ),
        traces={
            "strategy": "unified_adaptive_search",
            "phase": "dry_run",
            "request_snapshot": {
                "preset": request_kwargs.get("preset"),
                "max_steps": request_kwargs.get("max_steps"),
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
