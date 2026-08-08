"""Public PCS entrypoint: `run(company) -> ArchitectureResult`.

Dry-run composes three equal-depth channel Agent API request snapshots and a
per-channel cost ledger (no API calls). Live fan-out lands in a later PR.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from parallel_channel_search.agent_call import build_request_kwargs, request_snapshot
from parallel_channel_search.channels import (
    DEFAULT_EQUAL_DEPTH_PRESET,
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
    default_channel_configs,
    equal_depth_config_label,
)
from parallel_channel_search.merge import merge_findings

ARCHITECTURE_NAME = "Parallel Channel Search"
ARCHITECTURE_CLI_KEY = "parallel-channel-search"


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    preset: str = DEFAULT_EQUAL_DEPTH_PRESET,
    enabled_channels: Optional[tuple[str, ...]] = None,
    model: str = DEFAULT_MODEL,
    max_steps: int = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> ArchitectureResult:
    """Run PCS for one company.

    Dry-run builds one explicit request kwargs snapshot per enabled channel and
    returns empty findings with a zeroed per-channel ledger. Live Agent API
    fan-out is not wired yet.
    """
    if not dry_run:
        raise NotImplementedError(
            "Parallel Channel Search live Agent API calls are not wired yet. "
            "Use dry_run=True to build per-channel request snapshots."
        )

    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )
    configs = [
        c
        for c in default_channel_configs(
            preset,
            enabled_channels,
            model=model,
            max_steps=max_steps,
            reasoning_effort=reasoning_effort,
            web_search_depth=web_search_depth,
        )
        if c.enabled
    ]

    knob_label = equal_depth_config_label(
        model, max_steps, reasoning_effort, web_search_depth
    )
    channel_snapshots: dict[str, dict[str, Any]] = {}
    components: list[CostComponent] = []
    for cfg in configs:
        request_kwargs = build_request_kwargs(
            company_input,
            cfg.channel_id,
            model=cfg.model,
            max_steps=cfg.max_steps,
            reasoning_effort=cfg.reasoning_effort,
            web_search_depth=cfg.web_search_depth,
        )
        channel_snapshots[cfg.channel_id] = request_snapshot(request_kwargs)
        components.append(
            CostComponent(
                name=f"channel_{cfg.channel_id}",
                preset=knob_label,
                cost_usd=0.0,
                channel=cfg.channel_id,
                ran=False,
                skipped_reason="dry_run_no_api",
            )
        )

    ledger = CostLedger.from_components(components)
    findings = merge_findings([])

    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=findings,
        cost_ledger=ledger,
        genai_adoption_found=False,
        no_finding_reason="dry_run",
        no_finding_analysis=(
            "Parallel Channel Search dry-run: "
            f"{len(configs)} equal-depth channel request(s) "
            f"({', '.join(c.channel_id for c in configs) or 'none'}) "
            f"at {knob_label}. "
            "No Perplexity Agent API call was made."
        ),
        traces={
            "strategy": "parallel_channel_search",
            "phase": "dry_run",
            "model": model,
            "max_steps": max_steps,
            "reasoning_effort": reasoning_effort,
            "web_search_depth": web_search_depth,
            "legacy_preset_arg": preset,
            "channels": [c.channel_id for c in configs],
            "domain_filters": "off_prompt_only",
            "request_snapshots": channel_snapshots,
            "prompt_lineage": "prompts/parallel_channel_search/",
        },
        stub=True,
        dry_run=True,
        # Explicit knobs are source of truth (same pattern as UAS: no stock preset).
        preset=None,
        model_used=model,
    )
