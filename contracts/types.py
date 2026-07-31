"""Shared Finding, company input, and component cost ledger types.

Finding fields match Stage 2 production JSON (`AI_tool_used`, `source_url`, etc.)
so March outputs and new architecture results stay comparable.

Cost ledger shape follows plan §3.4: every architecture emits `components[]`
with `name`, `preset`, `cost_usd`, plus `total_usd`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class CompanyInput:
    """Minimal company record passed into architecture runners."""

    rcid: int
    name: str
    homepage_url: Optional[str] = None
    short_description: Optional[str] = None
    research_priority_score: int = 0
    online_presence_score: int = 0
    category_list: Optional[str] = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> CompanyInput:
        name = data.get("name")
        if name is None:
            raise ValueError("company name is required and cannot be null")
        return cls(
            rcid=int(data["rcid"]),
            name=str(name),
            homepage_url=data.get("homepage_url"),
            short_description=data.get("short_description"),
            research_priority_score=_int_or_default(
                data.get("research_priority_score"), 0
            ),
            online_presence_score=_int_or_default(
                data.get("online_presence_score"), 0
            ),
            category_list=data.get("category_list"),
        )


def _int_or_default(value: Any, default: int) -> int:
    """Coerce mapping ints. JSON null / missing become default."""
    if value is None:
        return default
    return int(value)


@dataclass
class Finding:
    """One GenAI-adoption evidence row (Stage 2 compatible field names)."""

    finding_id: int
    AI_tool_used: str
    use_case: str
    business_function: str
    evidence_description: str
    source_url: str
    source_type: str
    channel: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostComponent:
    """One billed (or skipped) Agent API sub-call in a company run."""

    name: str
    preset: str
    cost_usd: float
    channel: Optional[str] = None
    ran: bool = True
    skipped_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostLedger:
    """Per-company component cost breakdown required of every architecture."""

    components: list[CostComponent] = field(default_factory=list)
    total_usd: float = 0.0
    counterfactuals: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "total_usd": self.total_usd,
            "counterfactuals": list(self.counterfactuals),
        }

    @staticmethod
    def from_components(
        components: list[CostComponent],
        counterfactuals: Optional[list[dict[str, Any]]] = None,
    ) -> CostLedger:
        total = sum(c.cost_usd for c in components if c.ran)
        return CostLedger(
            components=components,
            total_usd=round(total, 6),
            counterfactuals=list(counterfactuals or []),
        )


@dataclass
class ArchitectureResult:
    """Normalized public return type for `architecture.run(company)`."""

    rcid: int
    company_name: str
    architecture: str
    findings: list[Finding] = field(default_factory=list)
    cost_ledger: CostLedger = field(default_factory=CostLedger)
    genai_adoption_found: bool = False
    no_finding_reason: Optional[str] = None
    no_finding_analysis: Optional[str] = None
    traces: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    stub: bool = False
    dry_run: bool = False
    preset: Optional[str] = None
    model_used: Optional[str] = None
    duration_seconds: float = 0.0

    @property
    def findings_count(self) -> int:
        return len(self.findings)

    @property
    def cost_usd(self) -> float:
        return self.cost_ledger.total_usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "rcid": self.rcid,
            "company_name": self.company_name,
            "architecture": self.architecture,
            "findings": [f.to_dict() for f in self.findings],
            "findings_count": self.findings_count,
            "cost_ledger": self.cost_ledger.to_dict(),
            "cost_usd": self.cost_usd,
            "genai_adoption_found": self.genai_adoption_found,
            "no_finding_reason": self.no_finding_reason,
            "no_finding_analysis": self.no_finding_analysis,
            "traces": self.traces,
            "error": self.error,
            "stub": self.stub,
            "dry_run": self.dry_run,
            "preset": self.preset,
            "model_used": self.model_used,
            "duration_seconds": self.duration_seconds,
        }
