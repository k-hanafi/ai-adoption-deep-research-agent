"""Public verify API: dry stub or live fetch → judge → confidence."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Union

from contracts.types import Finding

from citation_verification import config
from citation_verification.backup_fetch import execute_backup_chain
from citation_verification.confidence import (
    BinaryConfidenceUnavailable,
    LogprobExtractionError,
    extract_binary_confidence,
)
from citation_verification.fetch import FetchResult, execute_fetch
from citation_verification.judge import JudgeParseError, JudgeResult, execute_judge
from citation_verification.text import (
    cap_snippet,
    claim_on_topic,
    combine_chunk_verdicts,
    documents_disagree,
    extract_anchors,
    looks_document_mismatch,
    missing_anchors,
    page_looks_complete,
    select_windows,
)
from citation_verification.types import (
    FINDING_PASSTHROUGH_FIELDS,
    VerdictResult,
    VerifyResult,
    dry_stub_result,
    finding_passthrough,
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


def _identity(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    extra = {
        key: context[key]
        for key in FINDING_PASSTHROUGH_FIELDS
        if key in context
    }
    return {
        "finding_id": finding_id,
        "source_url": source_url,
        "claim": claim,
        "evidence_description": claim,
        **extra,
    }


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
    context = finding_passthrough(row)

    reason = _unusable_reason(claim, source_url)
    if reason is not None:
        return unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=reason,
            dry_run=dry_run,
            **context,
        )

    if dry_run:
        return dry_stub_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            **context,
        )

    return _verify_live(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        context=context,
    )


def _verify_live(
    *,
    finding_id: Optional[int],
    source_url: str,
    claim: str,
    context: Mapping[str, Any],
) -> VerdictResult:
    identity = _identity(
        finding_id=finding_id,
        source_url=source_url,
        claim=claim,
        context=context,
    )
    try:
        page, fetch_cost, fetch_attempts = _resolve_page(source_url)
    except Exception as exc:  # noqa: BLE001 - surface any fetch transport failure
        return unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=f"fetch failed: {exc}",
            dry_run=False,
            **context,
        )

    if not page.ok:
        result = unverifiable_result(
            finding_id=finding_id,
            source_url=source_url,
            claim=claim,
            reason=page.error or "fetch failed",
            dry_run=False,
            **context,
        )
        result.evidence_snippet = page.snippet or None
        result.fetched_url = page.url or None
        result.fetched_title = page.title or None
        result.fetch_source = page.source
        result.fetch_attempts = fetch_attempts
        result.cost_fetch_usd = float(fetch_cost)
        result.cost_usd = float(fetch_cost)
        return result

    anchors = extract_anchors(claim)
    missing = missing_anchors(page.snippet, anchors)
    if missing:
        page, fetch_cost, fetch_attempts = _recover_missing_anchors(
            source_url,
            claim,
            page=page,
            missing=missing,
            fetch_cost=fetch_cost,
            fetch_attempts=fetch_attempts,
        )
        if not page.ok:
            return _unreadable(
                identity,
                page=page,
                reason=page.error or config.ERROR_SNIPPET_MISSING_ANCHORS,
                fetch_cost=fetch_cost,
                fetch_attempts=fetch_attempts,
            )
        missing = missing_anchors(page.snippet, anchors)

    on_topic = claim_on_topic(source_url, page.title, anchors)
    complete = page_looks_complete(page.snippet, truncated=page.truncated)
    if missing and on_topic:
        return _unreadable(
            identity,
            page=page,
            reason=config.ERROR_SNIPPET_MISSING_ANCHORS,
            fetch_cost=fetch_cost,
            fetch_attempts=fetch_attempts,
        )

    windows = select_windows(page.snippet, claim)
    if not windows:
        return _unreadable(
            identity,
            page=page,
            reason=config.ERROR_SNIPPET_MISSING_ANCHORS,
            fetch_cost=fetch_cost,
            fetch_attempts=fetch_attempts,
        )

    judged_rows: list[JudgeResult] = []
    judge_cost = 0.0
    last_error: Optional[VerdictResult] = None
    for window in windows:
        judged, error_row = _judge_window(
            identity,
            page=page,
            claim=claim,
            source_url=source_url,
            snippet=window,
            fetch_cost=fetch_cost,
            fetch_attempts=fetch_attempts,
            prior_judge_cost=judge_cost,
        )
        if error_row is not None:
            last_error = error_row
            judge_cost = error_row.cost_judge_usd
            continue
        assert judged is not None
        judged_rows.append(judged)
        judge_cost += float(judged.cost_usd)

    if not judged_rows:
        if last_error is not None:
            return last_error
        return _unreadable(
            identity,
            page=page,
            reason="judge produced no usable window",
            fetch_cost=fetch_cost,
            fetch_attempts=fetch_attempts,
        )

    combined, combine_error = combine_chunk_verdicts(
        [row.verification for row in judged_rows],
        anchors_present=not missing,
        page_complete=complete,
        on_topic=on_topic,
    )
    winner = next(
        (row for row in judged_rows if row.verification == combined),
        judged_rows[0],
    )
    if combined is None:
        return VerdictResult(
            **identity,
            fetch_ok=True,
            fetched_url=page.url or None,
            fetched_title=page.title or None,
            fetch_source=page.source,
            fetch_attempts=fetch_attempts,
            evidence_snippet=page.snippet,
            model_judge=winner.model,
            cost_fetch_usd=float(fetch_cost),
            cost_judge_usd=round(judge_cost, 6),
            cost_usd=round(float(fetch_cost) + judge_cost, 6),
            error=combine_error or config.ERROR_SNIPPET_MISSING_ANCHORS,
            dry_run=False,
            unverifiable=True,
        )

    return _attach_confidence(
        identity,
        page=page,
        judged=winner,
        verification=combined,
        fetch_cost=fetch_cost,
        judge_cost=judge_cost,
        fetch_attempts=fetch_attempts,
    )


def _resolve_page(source_url: str) -> tuple[FetchResult, float, int]:
    primary = execute_fetch(source_url)
    fetch_cost = float(primary.cost_usd)
    fetch_attempts = max(1, primary.attempts)
    poisoned = primary.ok and looks_document_mismatch(
        source_url, primary.title, primary.snippet
    )
    if primary.ok and not poisoned:
        return primary, fetch_cost, fetch_attempts

    # Full-page extract. Claim-chunk query is only for targeted refetch.
    backup = execute_backup_chain(source_url)
    fetch_cost += float(backup.cost_usd)
    fetch_attempts += max(1, backup.attempts)
    if primary.ok and backup.ok and documents_disagree(
        primary.title, primary.snippet, backup.title, backup.snippet
    ):
        if looks_document_mismatch(source_url, primary.title, primary.snippet) and (
            not looks_document_mismatch(source_url, backup.title, backup.snippet)
        ):
            return backup, fetch_cost, fetch_attempts
        mismatch = FetchResult(
            url=source_url,
            title=backup.title or primary.title,
            snippet="",
            cost_usd=fetch_cost,
            error=config.ERROR_DOCUMENT_MISMATCH,
            source=backup.source,
            attempts=fetch_attempts,
        )
        return mismatch, fetch_cost, fetch_attempts
    if backup.ok:
        return backup, fetch_cost, fetch_attempts
    if poisoned:
        mismatch = FetchResult(
            url=source_url,
            title=primary.title,
            snippet=primary.snippet,
            cost_usd=fetch_cost,
            error=config.ERROR_DOCUMENT_MISMATCH,
            source=primary.source,
            attempts=fetch_attempts,
            truncated=primary.truncated,
        )
        return mismatch, fetch_cost, fetch_attempts
    return primary, fetch_cost, fetch_attempts


def _recover_missing_anchors(
    source_url: str,
    claim: str,
    *,
    page: FetchResult,
    missing: Sequence[str],
    fetch_cost: float,
    fetch_attempts: int,
) -> tuple[FetchResult, float, int]:
    targeted = execute_fetch(source_url, extract_for=list(missing))
    fetch_cost += float(targeted.cost_usd)
    fetch_attempts += max(1, targeted.attempts)
    if targeted.ok and not missing_anchors(targeted.snippet, missing):
        return _merge_page(page, targeted), fetch_cost, fetch_attempts

    backup = execute_backup_chain(source_url, query=list(missing))
    fetch_cost += float(backup.cost_usd)
    fetch_attempts += max(1, backup.attempts)
    if backup.ok and not missing_anchors(backup.snippet, missing):
        return _merge_page(page, backup), fetch_cost, fetch_attempts
    if targeted.ok:
        return _merge_page(page, targeted), fetch_cost, fetch_attempts
    if backup.ok:
        return _merge_page(page, backup), fetch_cost, fetch_attempts
    return page, fetch_cost, fetch_attempts


def _merge_page(original: FetchResult, recovered: FetchResult) -> FetchResult:
    """Keep both extracts. Recovered text goes first so the 32k cap cannot drop it."""
    left = (original.snippet or "").strip()
    right = (recovered.snippet or "").strip()
    if not left:
        combined = right
    elif not right or right in left:
        combined = left
    elif left in right:
        combined = right
    else:
        combined = f"{right}\n\n{left}"
    snippet, truncated = cap_snippet(combined)
    return FetchResult(
        url=recovered.url or original.url,
        title=recovered.title or original.title,
        snippet=snippet,
        cost_usd=recovered.cost_usd,
        raw=recovered.raw,
        error=None,
        source=recovered.source,
        attempts=recovered.attempts,
        truncated=truncated or original.truncated,
    )


def _judge_window(
    identity: Mapping[str, Any],
    *,
    page: FetchResult,
    claim: str,
    source_url: str,
    snippet: str,
    fetch_cost: float,
    fetch_attempts: int,
    prior_judge_cost: float,
) -> tuple[Optional[JudgeResult], Optional[VerdictResult]]:
    try:
        judged = execute_judge(
            claim=claim,
            source_url=source_url,
            snippet=snippet,
        )
    except JudgeParseError as exc:
        cost_judge = prior_judge_cost + float(exc.cost_usd)
        return None, VerdictResult(
            **identity,
            fetch_ok=True,
            fetched_url=page.url or None,
            fetched_title=page.title or None,
            fetch_source=page.source,
            fetch_attempts=fetch_attempts,
            evidence_snippet=page.snippet,
            model_judge=config.JUDGE_MODEL,
            cost_fetch_usd=float(fetch_cost),
            cost_judge_usd=round(cost_judge, 6),
            cost_usd=round(float(fetch_cost) + cost_judge, 6),
            error=f"judge parse failed: {exc}",
            dry_run=False,
            unverifiable=True,
        )
    except Exception as exc:  # noqa: BLE001 - surface transport / HTTP errors
        return None, VerdictResult(
            **identity,
            fetch_ok=True,
            fetched_url=page.url or None,
            fetched_title=page.title or None,
            fetch_source=page.source,
            fetch_attempts=fetch_attempts,
            evidence_snippet=page.snippet,
            model_judge=config.JUDGE_MODEL,
            cost_fetch_usd=float(fetch_cost),
            cost_usd=float(fetch_cost),
            cost_judge_usd=round(prior_judge_cost, 6),
            error=f"judge failed: {exc}",
            dry_run=False,
            unverifiable=True,
        )
    return judged, None


def _attach_confidence(
    identity: Mapping[str, Any],
    *,
    page: FetchResult,
    judged: JudgeResult,
    verification: int,
    fetch_cost: float,
    judge_cost: float,
    fetch_attempts: int,
) -> VerdictResult:
    cost_usd = round(float(fetch_cost) + float(judge_cost), 6)
    try:
        conf = extract_binary_confidence(judged.raw)
    except (LogprobExtractionError, BinaryConfidenceUnavailable) as exc:
        return VerdictResult(
            **identity,
            verification=None,
            confidence_1_5=judged.confidence_1_5,
            verification_reasoning=judged.verification_reasoning,
            verification_critique=judged.verification_critique,
            fetch_ok=True,
            fetched_url=page.url or None,
            fetched_title=page.title or None,
            fetch_source=page.source,
            fetch_attempts=fetch_attempts,
            evidence_snippet=page.snippet,
            model_judge=judged.model,
            cost_usd=cost_usd,
            cost_fetch_usd=float(fetch_cost),
            cost_judge_usd=round(float(judge_cost), 6),
            error=f"logprob confidence unavailable: {exc}",
            dry_run=False,
            unverifiable=True,
        )

    if conf.verification != judged.verification:
        return VerdictResult(
            **identity,
            verification=None,
            log_probs_conf=conf.log_probs_conf,
            confidence_1_5=judged.confidence_1_5,
            verification_reasoning=judged.verification_reasoning,
            verification_critique=judged.verification_critique,
            fetch_ok=True,
            fetched_url=page.url or None,
            fetched_title=page.title or None,
            fetch_source=page.source,
            fetch_attempts=fetch_attempts,
            evidence_snippet=page.snippet,
            censored=conf.censored,
            margin=conf.margin,
            model_judge=judged.model,
            cost_usd=cost_usd,
            cost_fetch_usd=float(fetch_cost),
            cost_judge_usd=round(float(judge_cost), 6),
            error=(
                "logprob verification token "
                f"{conf.verification} != JSON verification {judged.verification}"
            ),
            dry_run=False,
            unverifiable=True,
        )

    return VerdictResult(
        **identity,
        verification=verification,  # type: ignore[arg-type]
        log_probs_conf=conf.log_probs_conf,
        confidence_1_5=judged.confidence_1_5,
        verification_reasoning=judged.verification_reasoning,
        verification_critique=judged.verification_critique,
        fetch_ok=True,
        fetched_url=page.url or None,
        fetched_title=page.title or None,
        fetch_source=page.source,
        fetch_attempts=fetch_attempts,
        evidence_snippet=page.snippet,
        censored=conf.censored,
        margin=conf.margin,
        model_judge=judged.model,
        cost_usd=cost_usd,
        cost_fetch_usd=float(fetch_cost),
        cost_judge_usd=round(float(judge_cost), 6),
        error=None,
        dry_run=False,
        unverifiable=False,
    )


def _unreadable(
    identity: Mapping[str, Any],
    *,
    page: FetchResult,
    reason: str,
    fetch_cost: float,
    fetch_attempts: int,
) -> VerdictResult:
    return VerdictResult(
        **identity,
        fetch_ok=bool(page.snippet),
        fetched_url=page.url or None,
        fetched_title=page.title or None,
        fetch_source=page.source,
        fetch_attempts=fetch_attempts,
        evidence_snippet=page.snippet or None,
        cost_fetch_usd=float(fetch_cost),
        cost_usd=float(fetch_cost),
        error=reason,
        dry_run=False,
        unverifiable=True,
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
