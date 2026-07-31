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
        if not signal.get("signal"):
            continue
        confidence = float(signal.get("confidence", 0.0))
        if confidence < signal_threshold:
            continue
        channel = str(signal.get("channel", ""))
        score = confidence * float(prior.get(channel, 0.5))
        ranked.append({**signal, "rank_score": score})
    ranked.sort(key=lambda row: row["rank_score"], reverse=True)
    return ranked


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
    rescue_channel = None
    rescue_triggered = False
    if (
        rescue_enabled
        and not dig_1_had_findings
        and len(ranked) >= 2
        and float(ranked[1].get("confidence", 0.0)) >= rescue_threshold
    ):
        rescue_channel = str(ranked[1]["channel"])
        rescue_triggered = True

    return GateDecision(
        stop_at_scouts=False,
        dig_1_channel=str(top["channel"]),
        dig_1_score=float(top["rank_score"]),
        rescue_channel=rescue_channel,
        rescue_triggered=rescue_triggered,
        rationale="ranked_top1_dig",
        ranked=ranked,
    )
