"""Stage A / Stage B arm definitions for UAS tuning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from unified_adaptive_search.agent_call import DEFAULT_MODEL


@dataclass(frozen=True)
class TuneArm:
    arm_id: str
    label: str
    factor: str
    model: str
    max_steps: int
    reasoning_effort: str
    web_search_depth: str
    # Dry-only: scale soft-reference findings so OFAT ranking is visible.
    dry_findings_scale: float = 1.0
    # Dry-only: multiply Luna baseline prior for cost proxy.
    dry_cost_scale: float = 1.0

    def runner_kwargs(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_steps": self.max_steps,
            "reasoning_effort": self.reasoning_effort,
            "web_search_depth": self.web_search_depth,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Conservative Luna prior for dry/cost-preview (live baseline ~$0.021).
LUNA_BASELINE_PRIOR_USD = 0.03


def stage_a_screen_arms() -> list[TuneArm]:
    """Wide OFAT screen: one factor moved per arm vs baseline.

    Locked v2:
      baseline Luna / steps 10 / effort medium / search low
      steps: 20, 30, 50
      effort: high, xhigh
      search: medium, high  (our ladder: low=2k, medium=4k, high=8k tokens)
    """
    return [
        TuneArm(
            arm_id="uas_screen_baseline",
            label="Baseline (Luna / steps 10 / effort medium / search low)",
            factor="baseline",
            model=DEFAULT_MODEL,
            max_steps=10,
            reasoning_effort="medium",
            web_search_depth="low",
            dry_findings_scale=1.0,
            dry_cost_scale=1.0,
        ),
        TuneArm(
            arm_id="uas_screen_steps_20",
            label="max_steps=20",
            factor="max_steps",
            model=DEFAULT_MODEL,
            max_steps=20,
            reasoning_effort="medium",
            web_search_depth="low",
            dry_findings_scale=1.05,
            dry_cost_scale=1.3,
        ),
        TuneArm(
            arm_id="uas_screen_steps_30",
            label="max_steps=30",
            factor="max_steps",
            model=DEFAULT_MODEL,
            max_steps=30,
            reasoning_effort="medium",
            web_search_depth="low",
            dry_findings_scale=1.1,
            dry_cost_scale=1.7,
        ),
        TuneArm(
            arm_id="uas_screen_steps_50",
            label="max_steps=50",
            factor="max_steps",
            model=DEFAULT_MODEL,
            max_steps=50,
            reasoning_effort="medium",
            web_search_depth="low",
            dry_findings_scale=1.15,
            dry_cost_scale=2.4,
        ),
        TuneArm(
            arm_id="uas_screen_effort_high",
            label="reasoning.effort=high",
            factor="reasoning_effort",
            model=DEFAULT_MODEL,
            max_steps=10,
            reasoning_effort="high",
            web_search_depth="low",
            dry_findings_scale=1.15,
            dry_cost_scale=2.0,
        ),
        TuneArm(
            arm_id="uas_screen_effort_xhigh",
            label="reasoning.effort=xhigh",
            factor="reasoning_effort",
            model=DEFAULT_MODEL,
            max_steps=10,
            reasoning_effort="xhigh",
            web_search_depth="low",
            dry_findings_scale=1.25,
            dry_cost_scale=3.5,
        ),
        TuneArm(
            arm_id="uas_screen_search_medium",
            label="web_search depth=medium (max_tokens=4000)",
            factor="web_search_depth",
            model=DEFAULT_MODEL,
            max_steps=10,
            reasoning_effort="medium",
            web_search_depth="medium",
            dry_findings_scale=1.05,
            dry_cost_scale=1.2,
        ),
        TuneArm(
            arm_id="uas_screen_search_high",
            label="web_search depth=high (max_tokens=8000)",
            factor="web_search_depth",
            model=DEFAULT_MODEL,
            max_steps=10,
            reasoning_effort="medium",
            web_search_depth="high",
            dry_findings_scale=1.1,
            dry_cost_scale=2.0,
        ),
    ]
