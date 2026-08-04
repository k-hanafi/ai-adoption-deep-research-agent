"""Architecture-aware spend estimate (manual gate, no paid API)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from evals.architectures import resolve_architecture
from evals.panel import load_panel_companies
from evals.paths import FIXTURE_PANEL_PATH

# Illustrative priors for preview math only (not billed values).
# March empirical medium ≈ $0.32/company; widget medians understate real depth.
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

    def to_dict(self) -> dict[str, Any]:
        return {
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
    panel_path = Path(panel) if panel is not None else FIXTURE_PANEL_PATH
    # Always open the panel when a path is supplied so a bad --panel fails even
    # if --n overrides the company count.
    panel_count = len(load_panel_companies(panel_path)) if panel is not None else None
    if n_companies is None:
        n_companies = (
            panel_count
            if panel_count is not None
            else len(load_panel_companies(FIXTURE_PANEL_PATH))
        )
    if n_companies < 1:
        raise ValueError(f"n_companies must be >= 1, got {n_companies}")

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
        "Phase 1 preview uses fixture panel size unless --panel or --n is set."
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
