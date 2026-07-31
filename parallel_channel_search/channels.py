"""PCS channel ids and equal-depth defaults (plan §3.1).

Domain filters are deferred: leave filter lists empty for v1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


CHANNEL_IDS = ("jobs", "owned", "third_party")

# Locked for v1 evals: equal-depth `low` across all enabled channels.
DEFAULT_EQUAL_DEPTH_PRESET = "low"


@dataclass
class ChannelConfig:
    channel_id: str
    enabled: bool = True
    preset: str = DEFAULT_EQUAL_DEPTH_PRESET
    search_domain_filter: list[str] = field(default_factory=list)
    instruction_hint: str = ""


def default_channel_configs(
    preset: str = DEFAULT_EQUAL_DEPTH_PRESET,
    enabled_channels: Optional[tuple[str, ...]] = None,
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
            search_domain_filter=[],
            instruction_hint=hints[cid],
        )
        for cid in CHANNEL_IDS
    ]
