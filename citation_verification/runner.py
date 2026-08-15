"""Public verify API (dry-run first; live fetch/judge land in later commits)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Union

from contracts.types import Finding

from citation_verification import config
from citation_verification.types import (
    VerdictResult,
    VerifyResult,
    dry_stub_result,
    ledger_from_verdicts,
    unverifiable_result,
)

FindingLike = Union[Finding, Mapping[str, Any]]


class LiveNotWiredError(RuntimeError):
    """Raised when --live is requested before fetch/judge commits land."""


def _as_mapping(finding: FindingLike) -> Mapping[str, Any]:
    if isinstance(finding, Finding):
        return finding.to_dict()
    return finding


def _claim_text(row: Mapping[str, Any]) -> str:
    raw = row.get(config.CLAIM_FIELD)
    if raw is None:
        return ""
    return str(raw).strip()


def _source_url(row: Mapping[str, Any]) -> str:
    raw = row.get("source_url")
    if raw is None:
        return ""
    return str(raw).strip()


def _finding_id(row: Mapping[str, Any]) -> Optional[int]:
    raw = row.get("finding_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _unusable_reason(claim: str, source_url: str) -> Optional[str]:
    if not claim:
        return f"missing claim field {config.CLAIM_FIELD!r}"
    if not source_url:
        return "missing source_url"
    return None


def verify_finding(
    finding: FindingLike,
    *,
    dry_run: bool = True,
) -> VerdictResult:
    """Verify one finding. Dry-run default; live raises until later commits wire APIs."""
    row = _as_mapping(finding)
    claim = _claim_text(row)
    source_url = _source_url(row)
    finding_id = _finding_id(row)

    reason = _unusable_reason(claim, source_url)
    if reason is not None:
        return unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=reason,
            dry_run=dry_run,
        )

    if dry_run:
        return dry_stub_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
        )

    raise LiveNotWiredError(
        "Live citation verification is not wired yet "
        "(fetch + judge land in later commits on this PR)."
    )


def verify_findings(
    findings: Sequence[FindingLike],
    *,
    dry_run: bool = True,
) -> VerifyResult:
    """Verify many findings. Stops live batch if any call is not wired."""
    results: list[VerdictResult] = []
    for finding in findings:
        results.append(verify_finding(finding, dry_run=dry_run))
    return VerifyResult(
        results=results,
        cost_ledger=ledger_from_verdicts(results),
        dry_run=dry_run,
    )
