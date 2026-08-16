"""Public UAS entrypoint: `run(company) -> ArchitectureResult`."""

from __future__ import annotations

import time
from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from unified_adaptive_search.agent_call import (
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_TIMEOUT,
    DEFAULT_WEB_SEARCH_DEPTH,
    LEDGER_CONFIG_LABEL,
    build_request_kwargs,
    execute_agent_call,
    require_api_key,
)

ARCHITECTURE_NAME = "Unified Adaptive Search"
ARCHITECTURE_CLI_KEY = "unified-adaptive-search"


def _request_snapshot(request_kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": request_kwargs.get("model"),
        "max_steps": request_kwargs.get("max_steps"),
        "reasoning": request_kwargs.get("reasoning"),
        "tools": request_kwargs.get("tools"),
        "has_response_format": "response_format" in request_kwargs,
        "input_chars": len(request_kwargs.get("input") or ""),
        "has_preset": "preset" in request_kwargs,
    }


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    model: str = DEFAULT_MODEL,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
    timeout: float = DEFAULT_TIMEOUT,
    api_key: Optional[str] = None,
) -> ArchitectureResult:
    """Run UAS for one company.

    Dry-run builds an explicit request kwargs snapshot (model, steps, effort,
    tools) and returns a structured placeholder with a `unified_call` ledger.
    Live mode makes one Perplexity Agent API call and meters cost from usage.
    """
    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )
    request_kwargs = build_request_kwargs(
        company_input,
        model=model,
        max_steps=max_steps,
        reasoning_effort=reasoning_effort,
        web_search_depth=web_search_depth,
    )
    snapshot = _request_snapshot(request_kwargs)

    if dry_run:
        ledger = CostLedger.from_components(
            [
                CostComponent(
                    name="unified_call",
                    preset=LEDGER_CONFIG_LABEL,
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
                "Unified Adaptive Search dry-run: single explicit "
                f"model={model!r} call "
                f"(max_steps={max_steps}, reasoning.effort={reasoning_effort!r}, "
                f"web_search_depth={web_search_depth!r}). "
                "No Perplexity Agent API call was made."
            ),
            traces={
                "strategy": "unified_adaptive_search",
                "phase": "dry_run",
                "request_snapshot": snapshot,
                "prompt_lineage": "prompts/stage_2_perplexity_prompt.txt",
                "source_patterns": "legacy_agent_march_2026/src/stage_2/production_agent_runner.py",
            },
            stub=True,
            dry_run=True,
            preset=None,
            model_used=model,
        )

    # Config errors fail fast (do not write N empty panel rows).
    require_api_key(api_key)

    start = time.monotonic()
    try:
        payload = execute_agent_call(
            request_kwargs,
            api_key=api_key,
            timeout=timeout,
        )
    except Exception as exc:
        # Failures before a metered response (transport, hard API fail).
        duration = round(time.monotonic() - start, 2)
        ledger = CostLedger.from_components(
            [
                CostComponent(
                    name="unified_call",
                    preset=LEDGER_CONFIG_LABEL,
                    cost_usd=0.0,
                    ran=False,
                    skipped_reason="api_error",
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
            traces={
                "strategy": "unified_adaptive_search",
                "phase": "live_error",
                "request_snapshot": snapshot,
                "prompt_lineage": "prompts/stage_2_perplexity_prompt.txt",
                "source_patterns": "legacy_agent_march_2026/src/stage_2/production_agent_runner.py",
            },
            error=f"{type(exc).__name__}: {exc}",
            stub=False,
            dry_run=False,
            preset=None,
            model_used=model,
            duration_seconds=duration,
        )

    duration = round(time.monotonic() - start, 2)
    cost_usd = float(payload.get("cost_usd") or 0.0)
    # Metered responses count even when content parse fails (matches March runner).
    ledger = CostLedger.from_components(
        [
            CostComponent(
                name="unified_call",
                preset=LEDGER_CONFIG_LABEL,
                cost_usd=cost_usd,
                ran=True,
            )
        ]
    )
    findings = payload.get("findings") or []
    parse_error = payload.get("error")
    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=list(findings),
        cost_ledger=ledger,
        genai_adoption_found=bool(payload.get("genai_adoption_found")),
        no_finding_reason=payload.get("no_finding_reason"),
        no_finding_analysis=payload.get("no_finding_analysis"),
        traces={
            "strategy": "unified_adaptive_search",
            "phase": "live_error" if parse_error else "live",
            "request_snapshot": snapshot,
            "response_id": payload.get("response_id"),
            "response_status": payload.get("response_status"),
            "input_tokens": payload.get("input_tokens"),
            "output_tokens": payload.get("output_tokens"),
            "total_tokens": payload.get("total_tokens"),
            "citations": payload.get("citations") or [],
            # Actual tool use vs request caps (see agent_call._tool_use_from_response).
            "tool_use": payload.get("tool_use") or {},
            "raw_content_preview": payload.get("raw_content_preview"),
            "prompt_lineage": "prompts/stage_2_perplexity_prompt.txt",
            "source_patterns": "legacy_agent_march_2026/src/stage_2/production_agent_runner.py",
        },
        error=parse_error,
        stub=False,
        dry_run=False,
        preset=None,
        model_used=payload.get("model_used") or model,
        duration_seconds=duration,
    )
