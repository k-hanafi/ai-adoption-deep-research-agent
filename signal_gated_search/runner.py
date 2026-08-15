"""Public SGS entrypoint: `run(company) -> ArchitectureResult`.

Dry-run composes three presence-scout snapshots, runs the gate, then 0–3
cold dig snapshots. Live fans out scouts, gates, then fans out digs and
merges findings with the PCS (tool, url) dedupe.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional, Union

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
    Finding,
)
from parallel_channel_search.merge import merge_findings
from signal_gated_search.agent_call import (
    DEFAULT_TIMEOUT,
    build_dig_request_kwargs,
    build_scout_request_kwargs,
    execute_dig_call,
    execute_scout_call,
    request_snapshot,
    require_api_key,
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


def _scout_requests(
    company: CompanyInput,
    *,
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> dict[str, dict[str, Any]]:
    return {
        channel: build_scout_request_kwargs(company, channel, preset=scout_preset)
        for channel in CHANNEL_IDS
    }


def _snapshots(requests: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {cid: request_snapshot(kwargs) for cid, kwargs in requests.items()}


def _dig_requests(company: CompanyInput, gate: GateDecision) -> dict[str, dict[str, Any]]:
    if gate.stop_at_scouts or not gate.reasoning_effort:
        return {}
    return {
        channel: build_dig_request_kwargs(
            company,
            channel,
            model=DEFAULT_DIG_MODEL,
            max_steps=DEFAULT_DIG_MAX_STEPS,
            reasoning_effort=gate.reasoning_effort,
            web_search_depth=DEFAULT_DIG_WEB_SEARCH_DEPTH,
        )
        for channel in gate.dig_channels
    }


def _dry_components(
    gate: GateDecision,
    *,
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> list[CostComponent]:
    components = [
        CostComponent(
            name=f"scout_{channel}",
            preset=scout_preset,
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


def _base_traces(
    *,
    phase: str,
    gate: GateDecision,
    scout_snapshots: dict[str, dict[str, Any]],
    dig_snapshots: dict[str, dict[str, Any]],
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> dict[str, Any]:
    return {
        "strategy": "signal_gated_search",
        "phase": phase,
        "gate": gate.to_dict(),
        "scout_preset": scout_preset,
        "dig_effort_by_count": {str(k): v for k, v in DIG_EFFORT_BY_COUNT.items()},
        "rescue_enabled": False,
        "cold_start": True,
        "channels": list(CHANNEL_IDS),
        "request_snapshots": {
            "scouts": scout_snapshots,
            "digs": dig_snapshots,
        },
        "prompt_lineage": "prompts/signal_gated_search/",
    }


def _run_one_scout(
    channel_id: str,
    request_kwargs: dict[str, Any],
    *,
    api_key: Optional[str],
    timeout: float,
) -> dict[str, Any]:
    try:
        return execute_scout_call(
            request_kwargs,
            channel_id=channel_id,
            api_key=api_key,
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "channel_id": channel_id,
            "evidence_bin": "none",
            "urls": [],
            "snippets": [],
            "rationale": "",
            "cost_usd": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
            "transport_error": True,
        }


def _run_one_dig(
    channel_id: str,
    request_kwargs: dict[str, Any],
    *,
    api_key: Optional[str],
    timeout: float,
) -> dict[str, Any]:
    try:
        return execute_dig_call(
            request_kwargs,
            channel_id=channel_id,
            api_key=api_key,
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "channel_id": channel_id,
            "response_id": None,
            "cost_usd": 0.0,
            "findings": [],
            "error": f"{type(exc).__name__}: {exc}",
            "transport_error": True,
        }


def _fanout(
    runner,
    requests: dict[str, dict[str, Any]],
    *,
    api_key: Optional[str],
    timeout: float,
) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    workers = max(1, len(requests))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                runner,
                channel_id,
                kwargs,
                api_key=api_key,
                timeout=timeout,
            ): channel_id
            for channel_id, kwargs in requests.items()
        }
        for future in as_completed(futures):
            payloads[futures[future]] = future.result()
    return payloads


def _scout_row_from_payload(channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "assigned_channel": channel_id,
        "channel_id": channel_id,
        "channel": channel_id,
        "evidence_bin": payload.get("evidence_bin") or "none",
        "urls": payload.get("urls") or [],
        "snippets": payload.get("snippets") or [],
        "rationale": payload.get("rationale") or "",
    }


def _component_from_payload(
    *,
    name: str,
    preset: str,
    channel: str,
    payload: dict[str, Any],
) -> CostComponent:
    transport_error = bool(payload.get("transport_error"))
    cost_usd = float(payload.get("cost_usd") or 0.0)
    ran = not transport_error
    return CostComponent(
        name=name,
        preset=preset,
        cost_usd=cost_usd if ran else 0.0,
        channel=channel,
        ran=ran,
        skipped_reason="api_error" if transport_error else None,
    )


def _payload_trace(payload: dict[str, Any], *, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    row = {
        "response_id": payload.get("response_id"),
        "response_status": payload.get("response_status"),
        "model_used": payload.get("model_used"),
        "cost_usd": float(payload.get("cost_usd") or 0.0),
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "error": payload.get("error"),
        "transport_error": bool(payload.get("transport_error")),
    }
    if extra:
        row.update(extra)
    return row


def _aggregate_no_finding_reason(dig_payloads: dict[str, dict[str, Any]]) -> Optional[str]:
    reasons = {
        str((payload or {}).get("no_finding_reason") or "").strip().lower()
        for payload in dig_payloads.values()
    }
    reasons.discard("")
    if "has_presence_no_evidence" in reasons:
        return "has_presence_no_evidence"
    if "limited_online_presence" in reasons:
        return "limited_online_presence"
    return None


def _run_dry(
    company_input: CompanyInput,
    scout_snapshots: dict[str, dict[str, Any]],
    scout_outputs: Optional[list[dict[str, Any]]],
    *,
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> ArchitectureResult:
    gate = decide_gate(
        scout_outputs if scout_outputs is not None else _empty_scout_rows()
    )
    dig_snapshots = _snapshots(_dig_requests(company_input, gate))
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
        cost_ledger=CostLedger.from_components(
            _dry_components(gate, scout_preset=scout_preset)
        ),
        genai_adoption_found=False,
        no_finding_reason="dry_run",
        no_finding_analysis=analysis,
        traces=_base_traces(
            phase="dry_run",
            gate=gate,
            scout_snapshots=scout_snapshots,
            dig_snapshots=dig_snapshots,
            scout_preset=scout_preset,
        ),
        stub=True,
        dry_run=True,
        preset=effort,
        model_used=DEFAULT_DIG_MODEL if n_digs else None,
    )


def _run_live(
    company_input: CompanyInput,
    scout_requests: dict[str, dict[str, Any]],
    scout_snapshots: dict[str, dict[str, Any]],
    *,
    timeout: float,
    api_key: Optional[str],
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> ArchitectureResult:
    require_api_key(api_key)
    start = time.monotonic()
    scout_payloads = _fanout(
        _run_one_scout,
        scout_requests,
        api_key=api_key,
        timeout=timeout,
    )
    scout_rows = [
        _scout_row_from_payload(channel, scout_payloads.get(channel) or {})
        for channel in CHANNEL_IDS
    ]
    gate = decide_gate(scout_rows)
    dig_requests = _dig_requests(company_input, gate)
    dig_snapshots = _snapshots(dig_requests)
    dig_payloads: dict[str, dict[str, Any]] = {}
    if dig_requests:
        dig_payloads = _fanout(
            _run_one_dig,
            dig_requests,
            api_key=api_key,
            timeout=timeout,
        )
    duration = round(time.monotonic() - start, 2)

    components: list[CostComponent] = []
    for channel in CHANNEL_IDS:
        components.append(
            _component_from_payload(
                name=f"scout_{channel}",
                preset=scout_preset,
                channel=channel,
                payload=scout_payloads.get(channel) or {},
            )
        )
    dig_label = dig_config_label(gate.reasoning_effort or "")
    channel_findings: list[Finding] = []
    errors: list[str] = []
    no_finding_bits: list[str] = []
    for channel in gate.dig_channels:
        payload = dig_payloads.get(channel) or {}
        components.append(
            _component_from_payload(
                name=f"dig_{channel}",
                preset=dig_label,
                channel=channel,
                payload=payload,
            )
        )
        channel_findings.extend(list(payload.get("findings") or []))
        err = payload.get("error")
        if err:
            errors.append(f"dig_{channel}: {err}")
        reason = payload.get("no_finding_reason")
        analysis = payload.get("no_finding_analysis")
        if reason or analysis:
            no_finding_bits.append(
                f"[{channel}] reason={reason!r} analysis={analysis!r}"
            )
    for channel, payload in scout_payloads.items():
        err = payload.get("error")
        if err:
            errors.append(f"scout_{channel}: {err}")

    findings = merge_findings(channel_findings)
    adoption_found = bool(findings)
    phase = "live_error" if errors else "live"
    if findings:
        no_finding_reason = None
        no_finding_analysis = None
    elif gate.stop_at_scouts:
        scout_failed = any(
            (scout_payloads.get(channel) or {}).get("transport_error")
            or (scout_payloads.get(channel) or {}).get("error")
            for channel in CHANNEL_IDS
        )
        if scout_failed:
            no_finding_reason = "scout_errors"
            no_finding_analysis = (
                "Signal Gated Search live: one or more presence scouts failed, "
                "so the gate did not see a complete screen. No dig was made."
            )
        else:
            no_finding_reason = "no_channel_above_signal_threshold"
            no_finding_analysis = (
                "Signal Gated Search live: no channel cleared the presence gate. "
                "No dig was made."
            )
    else:
        no_finding_reason = _aggregate_no_finding_reason(dig_payloads)
        no_finding_analysis = (
            "Signal Gated Search live: no merged findings. "
            + (" ".join(no_finding_bits) if no_finding_bits else "No dig analysis.")
        )

    traces = _base_traces(
        phase=phase,
        gate=gate,
        scout_snapshots=scout_snapshots,
        dig_snapshots=dig_snapshots,
        scout_preset=scout_preset,
    )
    traces["scout_results"] = {
        channel: _payload_trace(
            scout_payloads.get(channel) or {},
            extra={
                "evidence_bin": (scout_payloads.get(channel) or {}).get("evidence_bin"),
                "url_count": len((scout_payloads.get(channel) or {}).get("urls") or []),
            },
        )
        for channel in CHANNEL_IDS
    }
    traces["dig_results"] = {
        channel: _payload_trace(
            dig_payloads.get(channel) or {},
            extra={
                "finding_count": len((dig_payloads.get(channel) or {}).get("findings") or []),
                "genai_adoption_found": bool(
                    (dig_payloads.get(channel) or {}).get("genai_adoption_found")
                ),
            },
        )
        for channel in gate.dig_channels
    }

    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=findings,
        cost_ledger=CostLedger.from_components(components),
        genai_adoption_found=adoption_found,
        no_finding_reason=no_finding_reason,
        no_finding_analysis=no_finding_analysis,
        traces=traces,
        error="; ".join(errors) if errors else None,
        stub=False,
        dry_run=False,
        preset=gate.reasoning_effort,
        model_used=DEFAULT_DIG_MODEL if gate.dig_count else None,
        duration_seconds=duration,
    )


def run(
    company: Union[CompanyInput, dict[str, Any]],
    *,
    dry_run: bool = True,
    scout_outputs: Optional[list[dict[str, Any]]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    api_key: Optional[str] = None,
    scout_preset: str = DEFAULT_SCOUT_PRESET,
) -> ArchitectureResult:
    """Run SGS for one company.

    Dry-run builds scout (and gated dig) request snapshots. Pass scout_outputs
    to simulate a gate decision without calling the Agent API. Live mode fans
    out three scouts, then 0–3 cold digs at the gated effort.

    scout_preset overrides the stock scout Agent API preset in-memory only.
    Package default stays DEFAULT_SCOUT_PRESET (low).
    """
    company_input = _as_company(company)
    scout_requests = _scout_requests(company_input, scout_preset=scout_preset)
    scout_snapshots = _snapshots(scout_requests)
    if dry_run:
        return _run_dry(
            company_input,
            scout_snapshots,
            scout_outputs,
            scout_preset=scout_preset,
        )
    return _run_live(
        company_input,
        scout_requests,
        scout_snapshots,
        timeout=timeout,
        api_key=api_key,
        scout_preset=scout_preset,
    )
