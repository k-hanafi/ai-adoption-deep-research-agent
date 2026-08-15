"""Result types for Stage 3 citation verification.

Field order: core verification fields first, then ops/cost for observability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from contracts.types import CostComponent, CostLedger

VerificationValue = Literal[0, 1]


@dataclass
class VerdictResult:
    """One finding after Stage 3 (or an unverifiable / dry stub)."""

    finding_id: Optional[int] = None
    source_url: str = ""
    claim: str = ""

    # Core product fields (first).
    verification: Optional[VerificationValue] = None
    log_probs_conf: Optional[float] = None
    confidence_1_5: Optional[int] = None
    verification_reasoning: Optional[str] = None
    verification_critique: Optional[str] = None

    # Ops / cost fields (trailing).
    fetch_ok: bool = False
    evidence_snippet: Optional[str] = None
    censored: Optional[bool] = None
    margin: Optional[float] = None
    model_judge: Optional[str] = None
    cost_usd: float = 0.0
    cost_fetch_usd: float = 0.0
    cost_judge_usd: float = 0.0
    error: Optional[str] = None

    # Run metadata.
    dry_run: bool = False
    unverifiable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifyResult:
    """Batch Stage 3 output over many findings."""

    results: list[VerdictResult] = field(default_factory=list)
    cost_ledger: CostLedger = field(default_factory=CostLedger)
    dry_run: bool = False
    error: Optional[str] = None

    @property
    def total_usd(self) -> float:
        return float(self.cost_ledger.total_usd)

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "cost_ledger": self.cost_ledger.to_dict(),
            "dry_run": self.dry_run,
            "error": self.error,
            "total_usd": self.total_usd,
        }


def unverifiable_result(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
    reason: str,
    dry_run: bool = False,
) -> VerdictResult:
    """Package-side unverifiable (fetch/claim unusable). Not model verification=0."""
    return VerdictResult(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        verification=None,
        fetch_ok=False,
        error=reason,
        dry_run=dry_run,
        unverifiable=True,
    )


def dry_stub_result(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
) -> VerdictResult:
    """Dry-run placeholder: inputs look usable; live fetch/judge not executed."""
    return VerdictResult(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        verification=None,
        fetch_ok=False,
        model_judge=None,
        cost_usd=0.0,
        error="dry_run_no_api",
        dry_run=True,
        unverifiable=False,
    )


def ledger_from_verdicts(results: list[VerdictResult]) -> CostLedger:
    """Sum per-finding costs into a simple two-component ledger."""
    fetch_total = round(sum(r.cost_fetch_usd for r in results), 6)
    judge_total = round(sum(r.cost_judge_usd for r in results), 6)
    components = [
        CostComponent(name="fetch_url", preset="perplexity_fetch", cost_usd=fetch_total),
        CostComponent(name="openai_judge", preset="gpt-5.6-terra", cost_usd=judge_total),
    ]
    return CostLedger.from_components(components)
