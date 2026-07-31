"""Gate policy skeleton: threshold, rank, top-1 dig, optional rescue.

Phase 1: documents decision shape only. No live scout outputs yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from signal_gated_search.channels import DEFAULT_CHANNEL_PRIOR


@dataclass
class GateDecision:
    """Record of whether/how SGS escalates beyond scouts."""

    stop_at_scouts: bool
    dig_1_channel: Optional[str] = None
    dig_1_score: Optional[float] = None
    rescue_channel: Optional[str] = None
    rescue_triggered: bool = False
    rationale: str = ""
    ranked: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_at_scouts": self.stop_at_scouts,
            "dig_1_channel": self.dig_1_channel,
            "dig_1_score": self.dig_1_score,
            "rescue_channel": self.rescue_channel,
            "rescue_triggered": self.rescue_triggered,
            "rationale": self.rationale,
            "ranked": list(self.ranked),
        }


def rank_signals(
    signals: list[dict[str, Any]],
    *,
    signal_threshold: float = 0.5,
    channel_prior: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Rank signaled channels by confidence × channel_prior."""
    prior = channel_prior or DEFAULT_CHANNEL_PRIOR
    ranked: list[dict[str, Any]] = []
    for signal in signals:
        # Require a real boolean True. Loose JSON strings like "false" must not escalate.
        if signal.get("signal") is not True:
            continue
        channel = str(signal.get("channel") or "").strip()
        if not channel:
            continue
        confidence = _as_float(signal.get("confidence"), default=0.0)
        if confidence < signal_threshold:
            continue
        score = confidence * float(prior.get(channel, 0.5))
        ranked.append({**signal, "channel": channel, "rank_score": score})
    ranked.sort(key=lambda row: row["rank_score"], reverse=True)
    return ranked


def _as_float(value: Any, *, default: float = 0.0) -> float:
    """Coerce scout numeric fields. null / missing become default."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def decide_gate(
    signals: list[dict[str, Any]],
    *,
    signal_threshold: float = 0.5,
    rescue_threshold: float = 0.7,
    rescue_enabled: bool = True,
    dig_1_had_findings: bool = False,
) -> GateDecision:
    """Apply Ranked Top-1 Dig (+ optional rescue) policy."""
    ranked = rank_signals(signals, signal_threshold=signal_threshold)
    if not ranked:
        return GateDecision(
            stop_at_scouts=True,
            rationale="no_channel_above_signal_threshold",
            ranked=[],
        )

    top = ranked[0]
    dig_1_channel = str(top["channel"])
    rescue_channel = None
    rescue_triggered = False
    if rescue_enabled and not dig_1_had_findings:
        # Rescue must target a different channel than dig_1 (locked second-channel policy).
        for candidate in ranked[1:]:
            channel = str(candidate.get("channel") or "")
            if not channel or channel == dig_1_channel:
                continue
            if _as_float(candidate.get("confidence"), default=0.0) >= rescue_threshold:
                rescue_channel = channel
                rescue_triggered = True
                break

    return GateDecision(
        stop_at_scouts=False,
        dig_1_channel=dig_1_channel,
        dig_1_score=float(top["rank_score"]),
        rescue_channel=rescue_channel,
        rescue_triggered=rescue_triggered,
        rationale="ranked_top1_dig",
        ranked=ranked,
    )
