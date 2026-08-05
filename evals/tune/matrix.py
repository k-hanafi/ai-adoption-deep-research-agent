"""Stage A / Stage B arm definitions for UAS tuning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TuneArm:
    arm_id: str
    label: str
    factor: str
    preset: str
    max_steps: int
    reasoning_effort: str
    web_search_depth: str
    # Dry-only: scale soft-reference findings so OFAT ranking is visible.
    dry_findings_scale: float = 1.0
    # Dry-only: multiply Luna baseline prior for cost proxy.
    dry_cost_scale: float = 1.0

    def runner_kwargs(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "max_steps": self.max_steps,
            "reasoning_effort": self.reasoning_effort,
            "web_search_depth": self.web_search_depth,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Luna medium baseline near Jam smoke, scaled toward the ~$0.10 target envelope.
LUNA_BASELINE_PRIOR_USD = 0.05


def stage_a_screen_arms() -> list[TuneArm]:
    """OFAT screen: one factor moved per arm vs baseline."""
    return [
        TuneArm(
            arm_id="uas_screen_baseline",
            label="Baseline (medium / steps 10 / effort medium / search medium)",
            factor="baseline",
            preset="medium",
            max_steps=10,
            reasoning_effort="medium",
            web_search_depth="medium",
            dry_findings_scale=1.0,
            dry_cost_scale=1.0,
        ),
        TuneArm(
            arm_id="uas_screen_steps_15",
            label="max_steps=15",
            factor="max_steps",
            preset="medium",
            max_steps=15,
            reasoning_effort="medium",
            web_search_depth="medium",
            dry_findings_scale=1.25,
            dry_cost_scale=1.4,
        ),
        TuneArm(
            arm_id="uas_screen_search_high",
            label="web_search depth=high",
            factor="web_search_depth",
            preset="medium",
            max_steps=10,
            reasoning_effort="medium",
            web_search_depth="high",
            dry_findings_scale=1.15,
            dry_cost_scale=1.5,
        ),
        TuneArm(
            arm_id="uas_screen_effort_high",
            label="reasoning.effort=high",
            factor="reasoning_effort",
            preset="medium",
            max_steps=10,
            reasoning_effort="high",
            web_search_depth="medium",
            dry_findings_scale=1.1,
            dry_cost_scale=1.3,
        ),
    ]
