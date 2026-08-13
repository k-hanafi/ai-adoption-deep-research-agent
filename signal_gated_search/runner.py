"""Public SGS entrypoint: `run(company) -> ArchitectureResult`.

Phase 1 stub: emits scout/dig/rescue component cost ledger rows even when
components did not run, so Cost-tab wiring and professor what-ifs have a shape.
"""

from __future__ import annotations

from typing import Any, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from signal_gated_search.channels import (
    CHANNEL_IDS,
    DEFAULT_DIG_PRESET,
    DEFAULT_RESCUE_DIG_PRESET,
    DEFAULT_SCOUT_PRESET,
)
from signal_gated_search.gate import GateDecision

ARCHITECTURE_NAME = "Signal Gated Search"
ARCHITECTURE_CLI_KEY = "signal-gated-search"


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    scout_preset: str = DEFAULT_SCOUT_PRESET,
    dig_preset: str = DEFAULT_DIG_PRESET,
    rescue_dig_preset: str = DEFAULT_RESCUE_DIG_PRESET,
    rescue_enabled: bool = True,
) -> ArchitectureResult:
    """Run SGS for one company.

    Phase 1: stub only. No scout/dig Agent API calls.
    """
    if not dry_run:
        raise NotImplementedError(
            "Signal Gated Search live Agent API calls are Phase 2. "
            "Use dry_run=True for scaffolding."
        )

    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )

    # STUB: ledger lists every component the live design can emit.
    components = [
        CostComponent(
            name=f"scout_{channel}",
            preset=scout_preset,
            cost_usd=0.0,
            channel=channel,
            ran=False,
            skipped_reason="phase1_stub_no_api",
        )
        for channel in CHANNEL_IDS
    ]
    components.append(
        CostComponent(
            name="dig_1",
            preset=dig_preset,
            cost_usd=0.0,
            ran=False,
            skipped_reason="phase1_stub_no_api",
        )
    )
    components.append(
        CostComponent(
            name="dig_rescue",
            preset=rescue_dig_preset,
            cost_usd=0.0,
            ran=False,
            skipped_reason=(
                "phase1_stub_no_api" if rescue_enabled else "rescue_disabled"
            ),
        )
    )
    ledger = CostLedger.from_components(
        components,
        counterfactuals=[
            {
                "name": "always_dig_2_medium",
                "estimated_extra_usd": None,
                "note": (
                    "Phase 1 placeholder: if second dig always ran at medium when "
                    "≥2 signals (professor what-if)."
                ),
            },
            {
                "name": "rescue_off",
                "estimated_extra_usd": None,
                "note": "Phase 1 placeholder: estimated savings if rescue dig is off.",
            },
        ],
    )

    gate = GateDecision(
        stop_at_scouts=True,
        rationale="phase1_stub_no_scout_signals",
    )

    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=[],
        cost_ledger=ledger,
        genai_adoption_found=False,
        no_finding_reason="phase1_stub",
        no_finding_analysis=(
            "Signal Gated Search stub: 3× fast presence scouts → "
            "dig-all signaled at effort ladder (1=max, 2=high, 3=medium). "
            "No Perplexity Agent API call was made."
        ),
        traces={
            "strategy": "signal_gated_search",
            "phase": "stub",
            "gate": gate.to_dict(),
            "scout_preset": scout_preset,
            "dig_effort_by_count": {"1": "max", "2": "high", "3": "medium"},
            "rescue_enabled": False,
        },
        stub=True,
        dry_run=True,
        preset=dig_preset,
    )
