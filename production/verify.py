"""Batch citation verification over findings_deduplicated.csv.

Finding-level pool (not company-sequential). --limit N findings or --all,
resume complete rows, requeue 429/timeout only, append after each finding,
Ctrl+C finishes in-flight findings and starts no new ones. Per-API adaptive
caps sit under --concurrency so Perplexity and OpenAI can climb toward their
rate limits without one 30-finding company occupying a slot for half an hour.
"""

from __future__ import annotations

import csv
import signal
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any, Optional

from citation_verification import config
from citation_verification.limits import limiter_status
from citation_verification.runner import verify_finding
from production.persist import (
    VERIFIED_COLUMNS,
    append_verified_csv,
    append_verified_jsonl,
    is_verified_complete,
    is_verified_retryable,
    prod_paths,
    rebuild_verified_csv,
    records_from_verified_jsonl,
    sum_verified_spend,
    verified_finding_key,
)

DEFAULT_VERIFY_CONCURRENCY = config.VERIFY_POOL_DEFAULT


def verification_source(paths) -> Path:
    if paths.findings_deduplicated_csv.exists():
        return paths.findings_deduplicated_csv
    raise FileNotFoundError(
        f"no findings to verify: expected {paths.findings_deduplicated_csv}. "
        "Run dedupe first. Raw findings.csv is not the verify input."
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _has_finding(row: dict[str, Any]) -> bool:
    url = str(row.get("source_url") or "").strip()
    claim = str(row.get("evidence_description") or "").strip()
    return bool(url and claim)


def _from_verdict(verdict) -> dict[str, Any]:
    verification = verdict.verification
    return {
        "verification": "" if verification is None else verification,
        "unverifiable": verdict.unverifiable,
        "verification_error": verdict.error or "",
        "log_probs_conf": verdict.log_probs_conf,
        "confidence_1_5": verdict.confidence_1_5,
        "verification_reasoning": verdict.verification_reasoning,
        "verification_critique": verdict.verification_critique,
        "fetch_ok": verdict.fetch_ok,
        "fetched_url": verdict.fetched_url,
        "fetched_title": verdict.fetched_title,
        "fetch_source": verdict.fetch_source,
        "fetch_attempts": verdict.fetch_attempts,
        "model_judge": verdict.model_judge,
        "verification_cost_usd": verdict.cost_usd,
    }


def merge_row(research: dict[str, Any], verdict) -> dict[str, Any]:
    out = {key: research.get(key, "") for key in VERIFIED_COLUMNS}
    out.update(_from_verdict(verdict))
    return out


def load_verified_by_key(paths) -> dict[tuple[Optional[int], Optional[int]], dict[str, Any]]:
    return {
        verified_finding_key(row): row
        for row in records_from_verified_jsonl(paths.findings_verified_jsonl)
    }


def source_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _has_finding(row)]


def prepare_verify_todo(
    source_rows: list[dict[str, Any]],
    existing: dict[tuple[Optional[int], Optional[int]], dict[str, Any]],
    *,
    limit: Optional[int],
) -> tuple[list[dict[str, Any]], int]:
    """Return (todo, skipped_complete). Complete rows do not consume --limit."""
    todo: list[dict[str, Any]] = []
    skipped = 0
    for row in source_findings(source_rows):
        prior = existing.get(verified_finding_key(row))
        if prior is not None and is_verified_complete(prior):
            skipped += 1
            continue
        todo.append(row)
        if limit is not None and len(todo) >= limit:
            break
    return todo, skipped


def _persist_verdict(
    research: dict[str, Any],
    verdict,
    *,
    paths,
    write_lock: Lock,
) -> dict[str, Any]:
    merged = merge_row(research, verdict)
    with write_lock:
        append_verified_jsonl(paths, merged)
        append_verified_csv(paths, merged)
    return merged


def _run_finding(
    row: dict[str, Any],
    *,
    dry_run: bool,
    paths,
    write_lock: Lock,
) -> dict[str, Any]:
    rcid, fid = verified_finding_key(row)
    verdict = verify_finding(row, dry_run=dry_run)
    merged = _persist_verdict(row, verdict, paths=paths, write_lock=write_lock)
    err = merged.get("verification_error") or None
    print(
        f"FINDING_DONE rcid={rcid} finding_id={fid} "
        f"v={merged.get('verification')!r} ${merged.get('verification_cost_usd') or 0} "
        f"err={err!r}",
        flush=True,
    )
    return merged


def _execute_verify(
    todo: list[dict[str, Any]],
    *,
    paths,
    workers: int,
    dry_run: bool,
    write_lock: Lock,
    stop_event: Event,
) -> tuple[int, int]:
    if not todo:
        return 0, 0
    pending = deque(todo)
    in_flight: dict[Any, dict[str, Any]] = {}
    worker_count = max(1, min(workers, len(todo)))
    ran = 0
    failed = 0

    def _submit(pool: ThreadPoolExecutor, row: dict[str, Any]) -> None:
        future = pool.submit(
            _run_finding,
            row,
            dry_run=dry_run,
            paths=paths,
            write_lock=write_lock,
        )
        in_flight[future] = row

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        while pending and len(in_flight) < worker_count and not stop_event.is_set():
            _submit(pool, pending.popleft())
        while in_flight:
            try:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED, timeout=1.0)
            except KeyboardInterrupt:
                stop_event.set()
                print(
                    "Stop requested. Finishing in-flight findings, starting no new ones.",
                    flush=True,
                )
                done = set()
            for future in done:
                row = in_flight.pop(future)
                rcid, fid = verified_finding_key(row)
                try:
                    merged = future.result()
                except Exception as exc:  # noqa: BLE001 - keep other findings running
                    print(f"FAIL rcid={rcid} finding_id={fid}: {exc}", flush=True)
                    failed += 1
                    continue
                ran += 1
                err = merged.get("verification_error") or None
                if (
                    err
                    and not is_verified_retryable(merged)
                    and merged.get("verification") in ("", None)
                ):
                    failed += 1
            while pending and len(in_flight) < worker_count and not stop_event.is_set():
                _submit(pool, pending.popleft())
    return ran, failed


@dataclass(frozen=True)
class VerifyStatus:
    architecture: str
    source: Path
    source_findings: int
    done: int
    remaining: int
    parked: int
    retryable: int
    spend_usd: float

    def format(self) -> str:
        return (
            f"architecture: {self.architecture}\n"
            f"source: {self.source} ({self.source_findings} findings)\n"
            f"verified done: {self.done}\n"
            f"verified remaining: {self.remaining}\n"
            f"verified parked: {self.parked}\n"
            f"verified retryable: {self.retryable}\n"
            f"verify spend: ${self.spend_usd:.4f}\n"
        )


def collect_verify_status(*, architecture: str, output_root: Path) -> VerifyStatus:
    paths = prod_paths(output_root, architecture)
    source = verification_source(paths)
    rows = source_findings(_read_csv(source))
    existing = load_verified_by_key(paths)
    done = 0
    parked = 0
    retryable = 0
    remaining = 0
    for row in rows:
        prior = existing.get(verified_finding_key(row))
        if prior is None:
            remaining += 1
        elif is_verified_retryable(prior):
            retryable += 1
            remaining += 1
        elif is_verified_complete(prior):
            done += 1
        else:
            parked += 1
            remaining += 1
    return VerifyStatus(
        architecture=architecture,
        source=source,
        source_findings=len(rows),
        done=done,
        remaining=remaining,
        parked=parked,
        retryable=retryable,
        spend_usd=round(sum_verified_spend(paths), 6),
    )


def run_verify(
    *,
    architecture: str,
    output_root: Path,
    dry_run: bool = True,
    limit: Optional[int] = None,
    concurrency: int = DEFAULT_VERIFY_CONCURRENCY,
    stop_event: Optional[Event] = None,
) -> Path:
    paths = prod_paths(output_root, architecture)
    source = verification_source(paths)
    rows = _read_csv(source)
    if not rows:
        raise ValueError(f"{source}: no rows to verify")
    if not source_findings(rows):
        raise ValueError(f"{source}: no findings with evidence_description + source_url")

    existing = load_verified_by_key(paths)
    todo, skipped = prepare_verify_todo(rows, existing, limit=limit)
    print(
        f"VERIFY source={source.name} todo={len(todo)} skip_complete={skipped} "
        f"dry_run={dry_run} pool={concurrency} limits={limiter_status()}",
        flush=True,
    )
    rebuild_verified_csv(paths)
    if not todo:
        print(f"VERIFY wrote {paths.findings_verified_csv} (nothing new)", flush=True)
        return paths.findings_verified_csv

    stop = stop_event or Event()
    previous = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum, frame):  # noqa: ARG001
        if not stop.is_set():
            print(
                "Stop requested. Finishing in-flight findings, starting no new ones.",
                flush=True,
            )
        stop.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    write_lock = Lock()
    try:
        ran, failed = _execute_verify(
            todo,
            paths=paths,
            workers=concurrency,
            dry_run=dry_run,
            write_lock=write_lock,
            stop_event=stop,
        )
    finally:
        signal.signal(signal.SIGINT, previous)
        rebuild_verified_csv(paths)

    print(
        f"VERIFY wrote {paths.findings_verified_csv} ran={ran} failed={failed} "
        f"dry_run={dry_run} limits={limiter_status()}",
        flush=True,
    )
    return paths.findings_verified_csv
