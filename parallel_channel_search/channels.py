"""PCS channel ids and equal-depth defaults (plan §3.1).

Domain filters are deferred: leave filter lists empty for v1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


CHANNEL_IDS = ("jobs", "owned", "third_party")

# Legacy preset label (scaffolding). Prefer explicit knobs below for prod/benchmark.
DEFAULT_EQUAL_DEPTH_PRESET = "low"

# Provisional equal-depth lock from Tuning #14 (see .cursor/plans/pcs-param-lock.md).
# Projected ≈$0.023/channel × 3 ≈ $0.069/company (≤ ~$0.10).
DEFAULT_MODEL = "openai/gpt-5.6-luna"
DEFAULT_MAX_STEPS = 50
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_WEB_SEARCH_DEPTH = "medium"


@dataclass
class ChannelConfig:
    channel_id: str
    enabled: bool = True
    preset: str = DEFAULT_EQUAL_DEPTH_PRESET
    model: str = DEFAULT_MODEL
    max_steps: int = DEFAULT_MAX_STEPS
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH
    search_domain_filter: list[str] = field(default_factory=list)
    instruction_hint: str = ""


def default_channel_configs(
    preset: str = DEFAULT_EQUAL_DEPTH_PRESET,
    enabled_channels: Optional[tuple[str, ...]] = None,
    *,
    model: str = DEFAULT_MODEL,
    max_steps: int = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> list[ChannelConfig]:
    # None means all channels. An explicit empty tuple means none enabled.
    if enabled_channels is None:
        enabled = set(CHANNEL_IDS)
    else:
        enabled = {str(channel).strip().lower() for channel in enabled_channels}
    hints = {
        "jobs": "Search job postings and careers pages for specific GenAI tool requirements.",
        "owned": "Search company-owned media (site, blog, docs) for internal GenAI tool use.",
        "third_party": "Search news, podcasts, and third-party coverage for internal GenAI adoption.",
    }
    return [
        ChannelConfig(
            channel_id=cid,
            enabled=cid in enabled,
            preset=preset,
            model=model,
            max_steps=max_steps,
            reasoning_effort=reasoning_effort,
            web_search_depth=web_search_depth,
            search_domain_filter=[],
            instruction_hint=hints[cid],
        )
        for cid in CHANNEL_IDS
    ]
