"""Public PCS entrypoint: `run(company) -> ArchitectureResult`.

Dry-run composes three equal-depth channel Agent API request snapshots and a
per-channel cost ledger (no API calls). Live mode fans out one call per
enabled channel in parallel, meters each component, then merges findings.
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
from parallel_channel_search.agent_call import (
    DEFAULT_TIMEOUT,
    build_request_kwargs,
    execute_agent_call,
    request_snapshot,
    require_api_key,
)
from parallel_channel_search.channels import (
    DEFAULT_EQUAL_DEPTH_PRESET,
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
    ChannelConfig,
    default_channel_configs,
    equal_depth_config_label,
)
from parallel_channel_search.merge import merge_findings

ARCHITECTURE_NAME = "Parallel Channel Search"
ARCHITECTURE_CLI_KEY = "parallel-channel-search"


def _enabled_configs(
    *,
    preset: str,
    enabled_channels: Optional[tuple[str, ...]],
    model: str,
    max_steps: int,
    reasoning_effort: str,
    web_search_depth: str,
) -> list[ChannelConfig]:
    return [
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


def _build_channel_requests(
    company: CompanyInput,
    configs: list[ChannelConfig],
) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for cfg in configs:
        requests[cfg.channel_id] = build_request_kwargs(
            company,
            cfg.channel_id,
            model=cfg.model,
            max_steps=cfg.max_steps,
            reasoning_effort=cfg.reasoning_effort,
            web_search_depth=cfg.web_search_depth,
        )
    return requests


def _run_one_channel(
    channel_id: str,
    request_kwargs: dict[str, Any],
    *,
    api_key: Optional[str],
    timeout: float,
) -> dict[str, Any]:
    """Execute one channel call. Transport errors become structured payloads."""
    try:
        return execute_agent_call(
            request_kwargs,
            channel_id=channel_id,
            api_key=api_key,
            timeout=timeout,
        )
    except Exception as exc:
        return {
            "channel_id": channel_id,
            "response_id": None,
            "model_used": None,
            "response_status": None,
            "cost_usd": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "citations": [],
            "tool_use": {},
            "raw_content_preview": None,
            "genai_adoption_found": False,
            "findings": [],
            "no_finding_reason": None,
            "no_finding_analysis": None,
            "error": f"{type(exc).__name__}: {exc}",
            "transport_error": True,
        }


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
    timeout: float = DEFAULT_TIMEOUT,
    api_key: Optional[str] = None,
) -> ArchitectureResult:
    """Run PCS for one company.

    Dry-run builds one explicit request kwargs snapshot per enabled channel and
    returns empty findings with a zeroed per-channel ledger. Live mode fans out
    equal-depth Agent API calls in parallel and meters each channel component.
    """
    company_input = (
        company
        if isinstance(company, CompanyInput)
        else CompanyInput.from_mapping(company)
    )
    configs = _enabled_configs(
        preset=preset,
        enabled_channels=enabled_channels,
        model=model,
        max_steps=max_steps,
        reasoning_effort=reasoning_effort,
        web_search_depth=web_search_depth,
    )
    knob_label = equal_depth_config_label(
        model, max_steps, reasoning_effort, web_search_depth
    )
    channel_requests = _build_channel_requests(company_input, configs)
    channel_snapshots = {
        cid: request_snapshot(kwargs) for cid, kwargs in channel_requests.items()
    }

    if dry_run:
        components = [
            CostComponent(
                name=f"channel_{cfg.channel_id}",
                preset=knob_label,
                cost_usd=0.0,
                channel=cfg.channel_id,
                ran=False,
                skipped_reason="dry_run_no_api",
            )
            for cfg in configs
        ]
        return ArchitectureResult(
            rcid=company_input.rcid,
            company_name=company_input.name,
            architecture=ARCHITECTURE_CLI_KEY,
            findings=merge_findings([]),
            cost_ledger=CostLedger.from_components(components),
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
            preset=None,
            model_used=model,
        )

    # Config errors fail fast before any paid channel call.
    require_api_key(api_key)

    start = time.monotonic()
    payloads_by_channel: dict[str, dict[str, Any]] = {}
    workers = max(1, len(configs))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _run_one_channel,
                cfg.channel_id,
                channel_requests[cfg.channel_id],
                api_key=api_key,
                timeout=timeout,
            ): cfg.channel_id
            for cfg in configs
        }
        for future in as_completed(futures):
            channel_id = futures[future]
            payloads_by_channel[channel_id] = future.result()

    duration = round(time.monotonic() - start, 2)

    components: list[CostComponent] = []
    channel_findings: list[Finding] = []
    channel_traces: dict[str, Any] = {}
    errors: list[str] = []
    no_finding_bits: list[str] = []

    for cfg in configs:
        payload = payloads_by_channel.get(cfg.channel_id) or {}
        transport_error = bool(payload.get("transport_error"))
        cost_usd = float(payload.get("cost_usd") or 0.0)
        # Metered responses count even when content parse fails.
        ran = not transport_error
        components.append(
            CostComponent(
                name=f"channel_{cfg.channel_id}",
                preset=knob_label,
                cost_usd=cost_usd if ran else 0.0,
                channel=cfg.channel_id,
                ran=ran,
                skipped_reason="api_error" if transport_error else None,
            )
        )
        findings = list(payload.get("findings") or [])
        channel_findings.extend(findings)
        err = payload.get("error")
        if err:
            errors.append(f"{cfg.channel_id}: {err}")
        reason = payload.get("no_finding_reason")
        analysis = payload.get("no_finding_analysis")
        if reason or analysis:
            no_finding_bits.append(
                f"[{cfg.channel_id}] reason={reason!r} analysis={analysis!r}"
            )
        channel_traces[cfg.channel_id] = {
            "response_id": payload.get("response_id"),
            "response_status": payload.get("response_status"),
            "model_used": payload.get("model_used"),
            "cost_usd": cost_usd,
            "input_tokens": payload.get("input_tokens"),
            "output_tokens": payload.get("output_tokens"),
            "total_tokens": payload.get("total_tokens"),
            "citations": payload.get("citations") or [],
            "tool_use": payload.get("tool_use") or {},
            "raw_content_preview": payload.get("raw_content_preview"),
            "genai_adoption_found": bool(payload.get("genai_adoption_found")),
            "finding_count": len(findings),
            "error": err,
        }

    findings = merge_findings(channel_findings)
    any_adoption = bool(findings) or any(
        bool((payloads_by_channel.get(c.channel_id) or {}).get("genai_adoption_found"))
        for c in configs
    )
    phase = "live_error" if errors else "live"
    return ArchitectureResult(
        rcid=company_input.rcid,
        company_name=company_input.name,
        architecture=ARCHITECTURE_CLI_KEY,
        findings=findings,
        cost_ledger=CostLedger.from_components(components),
        genai_adoption_found=any_adoption,
        no_finding_reason=None if findings else "has_presence_no_evidence",
        no_finding_analysis=(
            None
            if findings
            else (
                "Parallel Channel Search live: no merged findings. "
                + (" ".join(no_finding_bits) if no_finding_bits else "No channel analysis.")
            )
        ),
        traces={
            "strategy": "parallel_channel_search",
            "phase": phase,
            "model": model,
            "max_steps": max_steps,
            "reasoning_effort": reasoning_effort,
            "web_search_depth": web_search_depth,
            "legacy_preset_arg": preset,
            "channels": [c.channel_id for c in configs],
            "domain_filters": "off_prompt_only",
            "request_snapshots": channel_snapshots,
            "channel_results": channel_traces,
            "prompt_lineage": "prompts/parallel_channel_search/",
        },
        error="; ".join(errors) if errors else None,
        stub=False,
        dry_run=False,
        preset=None,
        model_used=model,
        duration_seconds=duration,
    )
