"""Public verify API: dry stub or live fetch → judge → confidence."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Union

from contracts.types import Finding

from citation_verification import config
from citation_verification.confidence import (
    BinaryConfidenceUnavailable,
    LogprobExtractionError,
    extract_binary_confidence,
)
from citation_verification.fetch import execute_fetch
from citation_verification.judge import JudgeParseError, execute_judge
from citation_verification.types import (
    VerdictResult,
    VerifyResult,
    dry_stub_result,
    ledger_from_verdicts,
    unverifiable_result,
)

FindingLike = Union[Finding, Mapping[str, Any]]


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
    """Verify one finding. Dry-run skips APIs; live runs fetch → judge → confidence."""
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

    return _verify_live(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
    )


def _verify_live(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
) -> VerdictResult:
    try:
        fetched = execute_fetch(source_url)
    except Exception as exc:  # noqa: BLE001 - surface any fetch transport failure
        return unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=f"fetch failed: {exc}",
            dry_run=False,
        )

    if not fetched.ok:
        result = unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=fetched.error or "fetch failed",
            dry_run=False,
        )
        result.evidence_snippet = fetched.snippet or None
        result.cost_fetch_usd = float(fetched.cost_usd)
        result.cost_usd = float(fetched.cost_usd)
        return result

    try:
        judged = execute_judge(
            claim=claim,
            source_url=source_url,
            snippet=fetched.snippet,
        )
    except JudgeParseError as exc:
        cost_judge = float(exc.cost_usd)
        cost_fetch = float(fetched.cost_usd)
        return VerdictResult(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            fetch_ok=True,
            evidence_snippet=fetched.snippet,
            model_judge=config.JUDGE_MODEL,
            cost_fetch_usd=cost_fetch,
            cost_judge_usd=cost_judge,
            cost_usd=round(cost_fetch + cost_judge, 6),
            error=f"judge parse failed: {exc}",
            dry_run=False,
            unverifiable=False,
        )
    except Exception as exc:  # noqa: BLE001 - surface transport / HTTP errors
        return VerdictResult(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            fetch_ok=True,
            evidence_snippet=fetched.snippet,
            model_judge=config.JUDGE_MODEL,
            cost_fetch_usd=float(fetched.cost_usd),
            cost_usd=float(fetched.cost_usd),
            error=f"judge failed: {exc}",
            dry_run=False,
            unverifiable=False,
        )

    conf_error: Optional[str] = None
    log_probs_conf: Optional[float] = None
    censored: Optional[bool] = None
    margin: Optional[float] = None
    verification = judged.verification
    try:
        conf = extract_binary_confidence(judged.raw)
        verification = conf.verification
        log_probs_conf = conf.log_probs_conf
        censored = conf.censored
        margin = conf.margin
        if conf.verification != judged.verification:
            conf_error = (
                "logprob verification token "
                f"{conf.verification} != JSON verification {judged.verification}"
            )
    except (LogprobExtractionError, BinaryConfidenceUnavailable) as exc:
        conf_error = f"logprob confidence unavailable: {exc}"

    cost_fetch = float(fetched.cost_usd)
    cost_judge = float(judged.cost_usd)
    return VerdictResult(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        verification=verification,  # type: ignore[arg-type]
        log_probs_conf=log_probs_conf,
        confidence_1_5=judged.confidence_1_5,
        verification_reasoning=judged.verification_reasoning,
        verification_critique=judged.verification_critique,
        fetch_ok=True,
        evidence_snippet=fetched.snippet,
        censored=censored,
        margin=margin,
        model_judge=judged.model,
        cost_usd=round(cost_fetch + cost_judge, 6),
        cost_fetch_usd=cost_fetch,
        cost_judge_usd=cost_judge,
        error=conf_error,
        dry_run=False,
        unverifiable=False,
    )


def verify_findings(
    findings: Sequence[FindingLike],
    *,
    dry_run: bool = True,
) -> VerifyResult:
    """Verify many findings; each row is independent."""
    results: list[VerdictResult] = []
    for finding in findings:
        results.append(verify_finding(finding, dry_run=dry_run))
    return VerifyResult(
        results=results,
        cost_ledger=ledger_from_verdicts(results),
        dry_run=dry_run,
    )
