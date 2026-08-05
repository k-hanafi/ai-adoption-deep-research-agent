"""Architecture-aware spend estimate (manual gate, no paid API)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from evals.architectures import resolve_architecture
from evals.panel import load_panel_companies
from evals.paths import FIXTURE_PANEL_PATH, TUNING_PANEL_PATH
from evals.tune.matrix import LUNA_BASELINE_PRIOR_USD, stage_a_screen_arms

# Illustrative priors for preview math only (not billed values).
PRIOR_USD = {
    "fast": 0.02,
    "low": 0.08,
    "medium": 0.32,
    "high": 0.60,
}


@dataclass
class CostPreview:
    architecture: str
    full_name: str
    n_companies: int
    k: int
    expected_calls_per_company: float
    estimated_usd_per_company: float
    estimated_total_usd: float
    components: list[dict[str, Any]]
    notes: list[str]
    matrix: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "architecture": self.architecture,
            "full_name": self.full_name,
            "n_companies": self.n_companies,
            "k": self.k,
            "expected_calls_per_company": self.expected_calls_per_company,
            "estimated_usd_per_company": self.estimated_usd_per_company,
            "estimated_total_usd": self.estimated_total_usd,
            "components": self.components,
            "notes": self.notes,
        }
        if self.matrix is not None:
            payload["matrix"] = self.matrix
        return payload


def _resolve_n(
    *,
    n_companies: Optional[int],
    panel: Optional[Union[Path, str]],
    default_panel: Path,
) -> int:
    panel_path = Path(panel) if panel is not None else default_panel
    panel_count = len(load_panel_companies(panel_path)) if panel is not None else None
    if n_companies is None:
        n_companies = (
            panel_count
            if panel_count is not None
            else len(load_panel_companies(default_panel))
        )
    if n_companies < 1:
        raise ValueError(f"n_companies must be >= 1, got {n_companies}")
    return n_companies


def preview_cost(
    architecture: str,
    *,
    k: int = 1,
    n_companies: Optional[int] = None,
    panel: Optional[Union[Path, str]] = None,
) -> CostPreview:
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    spec = resolve_architecture(architecture)
    n_companies = _resolve_n(
        n_companies=n_companies,
        panel=panel,
        default_panel=FIXTURE_PANEL_PATH,
    )

    if spec.cli_key == "parallel-channel-search":
        components = [
            {"name": "channel_jobs", "preset": "low", "expected_usd": PRIOR_USD["low"]},
            {"name": "channel_owned", "preset": "low", "expected_usd": PRIOR_USD["low"]},
            {
                "name": "channel_third_party",
                "preset": "low",
                "expected_usd": PRIOR_USD["low"],
            },
        ]
        calls = 3.0
        notes = [
            "PCS: 3 equal-depth channel agents at low (locked v1).",
            "Domain filters deferred (not in this estimate).",
        ]
    elif spec.cli_key == "signal-gated-search":
        components = [
            {"name": "scout_jobs", "preset": "fast", "expected_usd": PRIOR_USD["fast"]},
            {"name": "scout_owned", "preset": "fast", "expected_usd": PRIOR_USD["fast"]},
            {
                "name": "scout_third_party",
                "preset": "fast",
                "expected_usd": PRIOR_USD["fast"],
            },
            {
                "name": "dig_1",
                "preset": "medium",
                "expected_usd": PRIOR_USD["medium"],
                "note": "Assumes dig fires (positives-heavy panels escalate often).",
            },
            {
                "name": "dig_rescue",
                "preset": "low",
                "expected_usd": 0.0,
                "note": "Preview assumes rescue rarely fires; treat as upper-bound risk.",
            },
        ]
        calls = 4.0
        notes = [
            "SGS: 3× fast scouts + expected top-1 medium dig (rescue optional).",
            "On HPE-heavy sets many companies stop at scouts (cheaper than this prior).",
        ]
    else:
        components = [
            {
                "name": "unified_call",
                "preset": "medium",
                "expected_usd": PRIOR_USD["medium"],
            }
        ]
        calls = 1.0
        notes = [
            "UAS: one medium call per company (status-quo control arm).",
            "Prior uses March empirical ~$0.32/company, not pricing-widget medians.",
        ]

    per_company = sum(float(c["expected_usd"]) for c in components)
    total = per_company * n_companies * k
    notes.append(
        "Preview uses fixture panel size unless --panel or --n is set."
    )
    notes.append("Estimates are planning priors, not quotes. Metered bill comes from usage.")

    return CostPreview(
        architecture=spec.cli_key,
        full_name=spec.full_name,
        n_companies=n_companies,
        k=k,
        expected_calls_per_company=calls,
        estimated_usd_per_company=round(per_company, 4),
        estimated_total_usd=round(total, 4),
        components=components,
        notes=notes,
    )


def preview_matrix(
    architecture: str,
    *,
    matrix: str = "screen",
    k: int = 1,
    n_companies: Optional[int] = None,
    panel: Optional[Union[Path, str]] = None,
) -> CostPreview:
    """Estimate spend for a tuning matrix (Stage A screen)."""
    if matrix != "screen":
        raise ValueError("Only --matrix screen is supported in this MVP")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    spec = resolve_architecture(architecture)
    if spec.cli_key != "unified-adaptive-search":
        raise ValueError("Matrix preview MVP supports UAS only")

    n_companies = _resolve_n(
        n_companies=n_companies,
        panel=panel,
        default_panel=TUNING_PANEL_PATH,
    )
    arms = stage_a_screen_arms()
    arm_rows: list[dict[str, Any]] = []
    total = 0.0
    for arm in arms:
        per = LUNA_BASELINE_PRIOR_USD * arm.dry_cost_scale
        arm_total = per * n_companies * k
        total += arm_total
        arm_rows.append(
            {
                "arm_id": arm.arm_id,
                "estimated_usd_per_company": round(per, 4),
                "estimated_total_usd": round(arm_total, 4),
                "knobs": arm.runner_kwargs(),
            }
        )

    mean_per = total / (len(arms) * n_companies * k) if arms else 0.0
    notes = [
        "Matrix preview uses Luna-ish dry cost priors (not March $0.32 medium).",
        f"Stage A screen: {len(arms)} OFAT arms × {n_companies} companies × k={k}.",
        "Approve spend before any future --live matrix.",
    ]
    return CostPreview(
        architecture=spec.cli_key,
        full_name=spec.full_name,
        n_companies=n_companies,
        k=k,
        expected_calls_per_company=1.0,
        estimated_usd_per_company=round(mean_per, 4),
        estimated_total_usd=round(total, 4),
        components=[
            {
                "name": "matrix_arms",
                "preset": "medium",
                "expected_usd": round(total, 4),
            }
        ],
        notes=notes,
        matrix={"stage": "screen", "arms": arm_rows},
    )
