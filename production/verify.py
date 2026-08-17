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
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Any, Optional

from citation_verification import config
from citation_verification.limits import limiter_status
from citation_verification.runner import verify_finding
from production.pages import (
    append_page_record,
    fetch_from_record,
    load_pages_by_url,
    page_cache_key,
    page_cache_reusable,
    record_from_fetch,
)
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
    from_cache: bool = False,
    pages: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return (todo, skipped_complete, skipped_no_cache).

    Default: complete rows do not consume --limit. ``from_cache`` never
    fetches. It re-judges rows that already have a reusable page (including
    complete stamps) and skips the rest without consuming --limit.
    """
    cached = pages or {}
    todo: list[dict[str, Any]] = []
    skipped = 0
    skipped_no_cache = 0
    for row in source_findings(source_rows):
        prior = existing.get(verified_finding_key(row))
        complete = prior is not None and is_verified_complete(prior)
        has_page = page_cache_reusable(
            cached.get(page_cache_key(str(row.get("source_url") or "")))
        )
        if from_cache:
            if not has_page:
                skipped_no_cache += 1
                continue
        elif complete:
            skipped += 1
            continue
        todo.append(row)
        if limit is not None and len(todo) >= limit:
            break
    return todo, skipped, skipped_no_cache


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


def _cached_page_for(row: dict[str, Any], pages: dict[str, dict[str, Any]]):
    record = pages.get(page_cache_key(str(row.get("source_url") or "")))
    if not page_cache_reusable(record):
        return None
    return fetch_from_record(record)


def _write_page(
    source_url: str,
    page,
    fetch_cost: float,
    fetch_attempts: int,
    *,
    paths,
    pages: dict[str, dict[str, Any]],
    write_lock: Lock,
) -> None:
    record = record_from_fetch(
        source_url,
        page,
        fetch_cost=fetch_cost,
        fetch_attempts=fetch_attempts,
    )
    with write_lock:
        append_page_record(paths.pages_jsonl, record)
        pages[page_cache_key(source_url)] = record


def _run_finding(
    row: dict[str, Any],
    *,
    dry_run: bool,
    from_cache: bool,
    paths,
    pages: dict[str, dict[str, Any]],
    write_lock: Lock,
) -> dict[str, Any]:
    rcid, fid = verified_finding_key(row)
    cached = None if dry_run else _cached_page_for(row, pages)

    def persist(source_url: str, page, cost: float, attempts: int) -> None:
        _write_page(
            source_url,
            page,
            cost,
            attempts,
            paths=paths,
            pages=pages,
            write_lock=write_lock,
        )
    verdict = verify_finding(
        row,
        dry_run=dry_run,
        cached_page=cached,
        persist_page=None if dry_run or cached is not None else persist,
        cache_only=from_cache,
    )
    merged = _persist_verdict(row, verdict, paths=paths, write_lock=write_lock)
    err = merged.get("verification_error") or None
    cache_state = "hit" if cached is not None else ("miss" if from_cache else "fetch")
    print(
        f"FINDING_DONE rcid={rcid} finding_id={fid} "
        f"v={merged.get('verification')!r} ${merged.get('verification_cost_usd') or 0} "
        f"cache={cache_state} err={err!r}",
        flush=True,
    )
    return merged


def _execute_verify(
    todo: list[dict[str, Any]],
    *,
    paths,
    pages: dict[str, dict[str, Any]],
    workers: int,
    dry_run: bool,
    from_cache: bool,
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
            from_cache=from_cache,
            paths=paths,
            pages=pages,
            write_lock=write_lock,
        )
        in_flight[future] = row

    last_limits = 0.0
    last_ran_mark = 0

    def _log_limits(reason: str) -> None:
        print(f"LIMITS {reason} pool={len(in_flight)} {limiter_status()}", flush=True)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        while pending and len(in_flight) < worker_count and not stop_event.is_set():
            _submit(pool, pending.popleft())
        _log_limits("wave")
        last_limits = time.monotonic()
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
            now = time.monotonic()
            if now - last_limits >= 15:
                _log_limits("tick")
                last_limits = now
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
                if ran - last_ran_mark >= 25:
                    _log_limits(f"ran={ran}")
                    last_ran_mark = ran
                    last_limits = time.monotonic()
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
    from_cache: bool = False,
    stop_event: Optional[Event] = None,
) -> Path:
    if from_cache and dry_run:
        raise ValueError("--from-cache requires --live (Luna still runs on the saved page)")
    paths = prod_paths(output_root, architecture)
    source = verification_source(paths)
    rows = _read_csv(source)
    if not rows:
        raise ValueError(f"{source}: no rows to verify")
    if not source_findings(rows):
        raise ValueError(f"{source}: no findings with evidence_description + source_url")

    existing = load_verified_by_key(paths)
    pages = load_pages_by_url(paths.pages_jsonl)
    todo, skipped, skipped_no_cache = prepare_verify_todo(
        rows,
        existing,
        limit=limit,
        from_cache=from_cache,
        pages=pages,
    )
    print(
        f"VERIFY source={source.name} todo={len(todo)} skip_complete={skipped} "
        f"skip_no_cache={skipped_no_cache} from_cache={from_cache} "
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
            pages=pages,
            workers=concurrency,
            dry_run=dry_run,
            from_cache=from_cache,
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
