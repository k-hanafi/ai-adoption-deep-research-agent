"""Public SGS entrypoint: `run(company) -> ArchitectureResult`.

Dry-run composes three presence-scout Agent API snapshots, runs the gate on
injected or empty scout JSON, then composes 0–3 cold dig snapshots. Live
fan-out is the next PR.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
)
from signal_gated_search.agent_call import (
    build_dig_request_kwargs,
    build_scout_request_kwargs,
    request_snapshot,
)
from signal_gated_search.channels import (
    CHANNEL_IDS,
    DEFAULT_DIG_MAX_STEPS,
    DEFAULT_DIG_MODEL,
    DEFAULT_DIG_WEB_SEARCH_DEPTH,
    DEFAULT_SCOUT_PRESET,
    DIG_EFFORT_BY_COUNT,
    dig_config_label,
)
from signal_gated_search.gate import GateDecision, decide_gate

ARCHITECTURE_NAME = "Signal Gated Search"
ARCHITECTURE_CLI_KEY = "signal-gated-search"


def _as_company(company: Union[CompanyInput, dict[str, Any]]) -> CompanyInput:
    if isinstance(company, CompanyInput):
        return company
    return CompanyInput.from_mapping(company)


def _empty_scout_rows() -> list[dict[str, Any]]:
    """Dry-run stand-in when no scout JSON is injected: no room lights up."""
    return [
        {
            "channel": channel,
            "evidence_bin": "none",
            "urls": [],
            "snippets": [],
            "rationale": "dry_run_no_api",
        }
        for channel in CHANNEL_IDS
    ]


def _scout_snapshots(company: CompanyInput) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {}
    for channel in CHANNEL_IDS:
        kwargs = build_scout_request_kwargs(company, channel)
        snapshots[channel] = request_snapshot(kwargs)
    return snapshots


def _dig_snapshots(
    company: CompanyInput,
    gate: GateDecision,
) -> dict[str, dict[str, Any]]:
    if gate.stop_at_scouts or not gate.reasoning_effort:
        return {}
    snapshots: dict[str, dict[str, Any]] = {}
    for channel in gate.dig_channels:
        kwargs = build_dig_request_kwargs(
            company,
            channel,
            model=DEFAULT_DIG_MODEL,
            max_steps=DEFAULT_DIG_MAX_STEPS,
            reasoning_effort=gate.reasoning_effort,
            web_search_depth=DEFAULT_DIG_WEB_SEARCH_DEPTH,
        )
        snapshots[channel] = request_snapshot(kwargs)
    return snapshots


def _dry_components(gate: GateDecision) -> list[CostComponent]:
    components = [
        CostComponent(
            name=f"scout_{channel}",
            preset=DEFAULT_SCOUT_PRESET,
            cost_usd=0.0,
            channel=channel,
            ran=False,
            skipped_reason="dry_run_no_api",
        )
        for channel in CHANNEL_IDS
    ]
    if gate.stop_at_scouts:
        return components
    dig_label = dig_config_label(gate.reasoning_effort or "")
    for channel in gate.dig_channels:
        components.append(
            CostComponent(
                name=f"dig_{channel}",
                preset=dig_label,
                cost_usd=0.0,
                channel=channel,
                ran=False,
                skipped_reason="dry_run_no_api",
            )
        )
    return components


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    scout_outputs: Optional[list[dict[str, Any]]] = None,
) -> ArchitectureResult:
    """Run SGS for one company.

    Dry-run builds scout (and gated dig) request snapshots. Pass scout_outputs
    to simulate a gate decision without calling the Agent API. Live mode is
    not wired yet.
    """
    if not dry_run:
        raise NotImplementedError(
            "Signal Gated Search live Agent API calls are the next PR. "
            "Use dry_run=True to inspect scout/dig request snapshots."
        )

    company_input = _as_company(company)
    scout_snapshots = _scout_snapshots(company_input)
    gate = decide_gate(scout_outputs if scout_outputs is not None else _empty_scout_rows())
    dig_snapshots = _dig_snapshots(company_input, gate)
    effort = gate.reasoning_effort
    n_digs = gate.dig_count
    analysis = (
        "Signal Gated Search dry-run: 3 presence-scout request(s)"
        + (
            f" then {n_digs} cold dig(s) at effort={effort}."
            if n_digs
            else " then 0 digs (no channel above signal threshold)."
        )
        + " No Perplexity Agent API call was made."
    )
    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=[],
        cost_ledger=CostLedger.from_components(_dry_components(gate)),
        genai_adoption_found=False,
        no_finding_reason="dry_run",
        no_finding_analysis=analysis,
        traces={
            "strategy": "signal_gated_search",
            "phase": "dry_run",
            "gate": gate.to_dict(),
            "scout_preset": DEFAULT_SCOUT_PRESET,
            "dig_effort_by_count": {str(k): v for k, v in DIG_EFFORT_BY_COUNT.items()},
            "rescue_enabled": False,
            "cold_start": True,
            "channels": list(CHANNEL_IDS),
            "request_snapshots": {
                "scouts": scout_snapshots,
                "digs": dig_snapshots,
            },
            "prompt_lineage": "prompts/signal_gated_search/",
        },
        stub=True,
        dry_run=True,
        preset=effort,
        model_used=DEFAULT_DIG_MODEL if n_digs else None,
    )
