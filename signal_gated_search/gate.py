"""Gate policy: presence bins → signal → dig-all + effort ladder.

Scouts emit evidence_bin only. Code maps bin to confidence, then signal vs
threshold. Dig effort is chosen by how many channels cleared the bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from signal_gated_search.channels import (
    BIN_CONFIDENCE,
    CHANNEL_IDS,
    DEFAULT_SIGNAL_THRESHOLD,
    DIG_EFFORT_BY_COUNT,
    EVIDENCE_BINS,
)


@dataclass
class GateDecision:
    """Whether/how SGS escalates beyond scouts."""

    stop_at_scouts: bool
    dig_channels: list[str] = field(default_factory=list)
    dig_count: int = 0
    reasoning_effort: Optional[str] = None
    rationale: str = ""
    signaled: list[dict[str, Any]] = field(default_factory=list)
    normalized: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_at_scouts": self.stop_at_scouts,
            "dig_channels": list(self.dig_channels),
            "dig_count": self.dig_count,
            "reasoning_effort": self.reasoning_effort,
            "rationale": self.rationale,
            "signaled": list(self.signaled),
            "normalized": list(self.normalized),
        }


def _urls(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return []


def _snippets(value: Any) -> list[str]:
    return _urls(value)


def normalize_scout_output(
    raw: dict[str, Any],
    *,
    assigned_channel: str,
    signal_threshold: float = DEFAULT_SIGNAL_THRESHOLD,
) -> dict[str, Any]:
    """Map one scout JSON blob to a gate row. Code owns confidence and signal."""
    channel = str(assigned_channel or "").strip().lower()
    if channel not in CHANNEL_IDS:
        known = ", ".join(CHANNEL_IDS)
        raise ValueError(f"Unknown SGS channel {assigned_channel!r}. Choose: {known}")

    bin_name = str(raw.get("evidence_bin") or "none").strip().lower()
    if bin_name not in EVIDENCE_BINS:
        bin_name = "none"

    urls = _urls(raw.get("urls"))
    downgraded = None
    if bin_name in ("moderate", "strong") and not urls:
        bin_name = "none"
        downgraded = "missing_url"

    confidence = BIN_CONFIDENCE[bin_name]
    signal = confidence >= signal_threshold
    return {
        "channel": channel,
        "evidence_bin": bin_name,
        "confidence": confidence,
        "signal": signal,
        "urls": urls,
        "snippets": _snippets(raw.get("snippets")),
        "rationale": str(raw.get("rationale") or "").strip(),
        "downgraded": downgraded,
    }


def effort_for_dig_count(dig_count: int) -> Optional[str]:
    if dig_count <= 0:
        return None
    if dig_count not in DIG_EFFORT_BY_COUNT:
        raise ValueError(
            f"dig_count must be 1, 2, or 3, got {dig_count!r}"
        )
    return DIG_EFFORT_BY_COUNT[dig_count]


def decide_gate(
    scouts: list[dict[str, Any]],
    *,
    signal_threshold: float = DEFAULT_SIGNAL_THRESHOLD,
) -> GateDecision:
    """Dig every signaled channel. Effort rises as dig count falls."""
    normalized: list[dict[str, Any]] = []
    by_channel: dict[str, dict[str, Any]] = {}
    for row in scouts:
        assigned = str(
            row.get("assigned_channel")
            or row.get("channel_id")
            or row.get("channel")
            or ""
        ).strip().lower()
        if assigned not in CHANNEL_IDS:
            continue
        parsed = normalize_scout_output(
            row,
            assigned_channel=assigned,
            signal_threshold=signal_threshold,
        )
        normalized.append(parsed)
        # First scout for a channel wins if duplicates appear.
        if parsed["channel"] not in by_channel:
            by_channel[parsed["channel"]] = parsed

    signaled = [
        by_channel[cid] for cid in CHANNEL_IDS if by_channel.get(cid, {}).get("signal")
    ]
    dig_channels = [row["channel"] for row in signaled]
    dig_count = len(dig_channels)
    if dig_count == 0:
        return GateDecision(
            stop_at_scouts=True,
            rationale="no_channel_above_signal_threshold",
            signaled=[],
            normalized=normalized,
        )

    return GateDecision(
        stop_at_scouts=False,
        dig_channels=dig_channels,
        dig_count=dig_count,
        reasoning_effort=effort_for_dig_count(dig_count),
        rationale="signal_count_effort_ladder",
        signaled=signaled,
        normalized=normalized,
    )
