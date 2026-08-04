"""Public PCS entrypoint: `run(company) -> ArchitectureResult`.

Phase 1 stub: validates wiring and emits a component cost ledger with one
row per channel agent. Does not call the Perplexity Agent API.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from parallel_channel_search.channels import (
    DEFAULT_EQUAL_DEPTH_PRESET,
    default_channel_configs,
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
) -> ArchitectureResult:
    """Run PCS for one company.

    Phase 1: stub only. Returns empty findings and a zeroed cost ledger that
    still lists the three equal-depth channel components for dashboard wiring.
    """
    if not dry_run:
        raise NotImplementedError(
            "Parallel Channel Search live Agent API calls are Phase 2. "
            "Use dry_run=True for scaffolding."
        )

    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )
    configs = [c for c in default_channel_configs(preset, enabled_channels) if c.enabled]

    # STUB: no Agent API calls. Real path fans out one call per channel, then merge.
    components = [
        CostComponent(
            name=f"channel_{cfg.channel_id}",
            preset=cfg.preset,
            cost_usd=0.0,
            channel=cfg.channel_id,
            ran=False,
            skipped_reason="phase1_stub_no_api",
        )
        for cfg in configs
    ]
    ledger = CostLedger.from_components(components)
    findings = merge_findings([])

    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=findings,
        cost_ledger=ledger,
        genai_adoption_found=False,
        no_finding_reason="phase1_stub",
        no_finding_analysis=(
            "Parallel Channel Search Phase 1 stub: "
            f"{len(configs)} equal-depth channel agent(s) "
            f"({', '.join(c.channel_id for c in configs) or 'none'}) "
            f"at preset={preset!r}. "
            "No Perplexity Agent API call was made."
        ),
        traces={
            "strategy": "parallel_channel_search",
            "phase": "stub",
            "equal_depth_preset": preset,
            "channels": [c.channel_id for c in configs],
            "domain_filters": "deferred_empty",
        },
        stub=True,
        dry_run=True,
        preset=preset,
    )
