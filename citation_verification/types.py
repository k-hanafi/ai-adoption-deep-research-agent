"""Result types for Stage 3 citation verification.

Field order: finding identity + URL, then core verification, then ops/cost.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping, Optional

from contracts.types import CostComponent, CostLedger

from citation_verification import config

VerificationValue = Literal[0, 1]

# Extra finding columns copied into outputs when the input row has them.
FINDING_PASSTHROUGH_FIELDS: tuple[str, ...] = (
    "company_name",
    "rcid",
    "channel",
    "AI_tool_used",
    "use_case",
    "business_function",
    "source_type",
    "architecture",
)


@dataclass
class VerdictResult:
    """One finding after Stage 3 (or an unverifiable / dry stub)."""

    finding_id: Optional[int] = None
    source_url: str = ""
    claim: str = ""
    evidence_description: str = ""

    company_name: Optional[str] = None
    rcid: Optional[int] = None
    channel: Optional[str] = None
    AI_tool_used: Optional[str] = None
    use_case: Optional[str] = None
    business_function: Optional[str] = None
    source_type: Optional[str] = None
    architecture: Optional[str] = None

    # Core product fields (first).
    verification: Optional[VerificationValue] = None
    log_probs_conf: Optional[float] = None
    confidence_1_5: Optional[int] = None
    verification_reasoning: Optional[str] = None
    verification_critique: Optional[str] = None

    # Ops / cost fields (trailing).
    fetch_ok: bool = False
    fetched_url: Optional[str] = None
    fetched_title: Optional[str] = None
    fetch_source: Optional[str] = None
    fetch_attempts: Optional[int] = None
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


def finding_passthrough(row: Mapping[str, Any]) -> dict[str, Any]:
    """Copy optional finding fields from an input row (skip missing/blank)."""
    out: dict[str, Any] = {}
    for key in FINDING_PASSTHROUGH_FIELDS:
        if key not in row or row[key] is None:
            continue
        raw = row[key]
        if key == "rcid":
            try:
                out[key] = int(raw)
            except (TypeError, ValueError):
                continue
            continue
        text = str(raw).strip()
        if text:
            out[key] = text
    return out


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
    **passthrough: Any,
) -> VerdictResult:
    """Package-side unverifiable (fetch/claim/judge unusable). Not model verification=0."""
    extra = {
        key: passthrough[key]
        for key in FINDING_PASSTHROUGH_FIELDS
        if key in passthrough
    }
    return VerdictResult(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        evidence_description=claim,
        verification=None,
        fetch_ok=False,
        model_judge=None,
        error=reason,
        dry_run=dry_run,
        unverifiable=True,
        **extra,
    )


def dry_stub_result(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
    **passthrough: Any,
) -> VerdictResult:
    """Dry-run placeholder: inputs look usable; live fetch/judge not executed."""
    extra = {
        key: passthrough[key]
        for key in FINDING_PASSTHROUGH_FIELDS
        if key in passthrough
    }
    return VerdictResult(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        evidence_description=claim,
        verification=None,
        fetch_ok=False,
        model_judge=None,
        cost_usd=0.0,
        error="dry_run_no_api",
        dry_run=True,
        unverifiable=False,
        **extra,
    )


def ledger_from_verdicts(results: list[VerdictResult]) -> CostLedger:
    """Sum per-finding costs into a simple two-component ledger."""
    fetch_total = round(sum(r.cost_fetch_usd for r in results), 6)
    judge_total = round(sum(r.cost_judge_usd for r in results), 6)
    components = [
        CostComponent(name="fetch_url", preset="perplexity_fetch", cost_usd=fetch_total),
        CostComponent(name="openai_judge", preset=config.JUDGE_MODEL, cost_usd=judge_total),
    ]
    return CostLedger.from_components(components)
