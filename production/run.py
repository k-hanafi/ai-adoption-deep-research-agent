"""Live and dry-run batch loops over the P4+P5 set.

Calls the existing architecture ``run(company)`` APIs. Does not fork those
packages. Live persist is resume-safe per architecture: skip complete success,
back up 429/timeout failures, never overwrite a good ``{rcid}.json``.
"""

from __future__ import annotations

import signal
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Event, Lock
from typing import Any, Callable, Optional

import parallel_channel_search
import signal_gated_search
import unified_adaptive_search
from production.persist import (
    WriteOutcome,
    append_findings_jsonl,
    backup_retryable,
    copy_retryable_backup,
    company_record,
    disk_payload,
    is_complete_success,
    is_retryable,
    load_payload,
    prod_paths,
    rebuild_findings_csv,
    rebuild_jsonl_from_companies,
    retry_kind,
    write_company_json,
)

RUNNERS: dict[str, Callable[..., Any]] = {
    "sgs": signal_gated_search.run,
    "pcs": parallel_channel_search.run,
    "uas": unified_adaptive_search.run,
}

DEFAULT_CONCURRENCY = 4
DEFAULT_TIMEOUT_S = 600.0


def as_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        payload = result.to_dict()
        if isinstance(payload, dict):
            return payload
    if isinstance(result, dict):
        return result
    raise TypeError(f"architecture run() must return ArchitectureResult or dict, got {type(result)!r}")


def company_input(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rcid": row["rcid"],
        "name": row.get("name"),
        "homepage_url": row.get("homepage_url"),
        "short_description": row.get("short_description"),
        "research_priority_score": row.get("research_priority_score"),
        "online_presence_score": row.get("online_presence_score"),
        "category_list": row.get("category_list"),
    }


def remaining_companies(
    companies: list[dict[str, Any]],
    *,
    architecture: str,
    output_root,
) -> list[dict[str, Any]]:
    """Dataset-order companies that do not yet have a successful JSON."""
    paths = prod_paths(output_root, architecture)
    todo: list[dict[str, Any]] = []
    for row in companies:
        payload = load_payload(paths.company_json(int(row["rcid"])))
        if is_complete_success(payload):
            continue
        todo.append(row)
    return todo


def _error_payload(company: dict[str, Any], architecture: str, exc: BaseException) -> dict[str, Any]:
    return {
        "rcid": int(company["rcid"]),
        "company_name": company.get("name"),
        "architecture": architecture,
        "findings": [],
        "findings_count": 0,
        "cost_usd": 0.0,
        "cost_ledger": {"components": [], "total_usd": 0.0, "counterfactuals": []},
        "genai_adoption_found": False,
        "error": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc(),
        "dry_run": False,
        "stub": False,
    }


def _run_one(
    company: dict[str, Any],
    *,
    architecture: str,
    dry_run: bool,
    timeout: float,
) -> dict[str, Any]:
    runner = RUNNERS[architecture]
    result = runner(
        company_input(company),
        dry_run=dry_run,
        timeout=timeout,
    )
    return as_payload(result)


def _persist_live(
    company: dict[str, Any],
    payload: dict[str, Any],
    *,
    architecture: str,
    output_root,
    write_lock: Lock,
) -> WriteOutcome:
    paths = prod_paths(output_root, architecture)
    rcid = int(company["rcid"])
    disk = disk_payload(company, payload)
    with write_lock:
        outcome = write_company_json(paths.company_json(rcid), disk)
        if outcome.action == "kept_success":
            print(
                f"KEEP_SUCCESS {rcid} {company.get('name')}: "
                f"left {paths.company_json(rcid).name} in place, "
                f"wrote failure to {outcome.backup.name if outcome.backup else 'backup'}",
                flush=True,
            )
            return outcome
        record = company_record(company, disk, architecture)
        append_findings_jsonl(paths, record)
        rebuild_findings_csv(paths)
    return outcome


def _prepare_todo(
    companies: list[dict[str, Any]],
    *,
    architecture: str,
    output_root,
    limit: Optional[int],
) -> tuple[list[dict[str, Any]], int]:
    paths = prod_paths(output_root, architecture)
    todo: list[dict[str, Any]] = []
    skipped = 0
    for row in companies:
        rcid = int(row["rcid"])
        result_path = paths.company_json(rcid)
        if result_path.exists():
            existing = load_payload(result_path)
            if is_complete_success(existing):
                skipped += 1
                print(
                    f"SKIP {rcid} {row.get('name')}: {result_path.name} already complete",
                    flush=True,
                )
                continue
            kind = retry_kind((existing or {}).get("error"))
            backup = backup_retryable(result_path, kind)
            print(
                f"REQUEUE {rcid} {row.get('name')}: failed {result_path.name} "
                f"backed up to {backup.name}",
                flush=True,
            )
        todo.append(row)
        if limit is not None and len(todo) >= limit:
            break
    return todo, skipped


def _execute_batch(
    todo: list[dict[str, Any]],
    *,
    architecture: str,
    output_root,
    workers: int,
    timeout: float,
    write_lock: Lock,
    stop_event: Event,
    unlink_on_retry: bool,
) -> tuple[int, int, list[dict[str, Any]]]:
    failed = 0
    ran = 0
    need_retry: list[dict[str, Any]] = []
    if not todo:
        return failed, ran, need_retry

    pending = deque(todo)
    in_flight: dict[Any, dict[str, Any]] = {}
    worker_count = max(1, min(workers, len(todo)))

    def _submit(pool: ThreadPoolExecutor, company: dict[str, Any]) -> None:
        future = pool.submit(
            _run_one,
            company,
            architecture=architecture,
            dry_run=False,
            timeout=timeout,
        )
        in_flight[future] = company

    def _finish(future: Any, company: dict[str, Any]) -> None:
        nonlocal failed, ran
        rcid = int(company["rcid"])
        paths = prod_paths(output_root, architecture)
        result_path = paths.company_json(rcid)
        try:
            payload = future.result()
        except Exception as exc:
            payload = _error_payload(company, architecture, exc)
            print(f"FAIL {rcid} {company.get('name')}: {payload['error']}", flush=True)
        outcome = _persist_live(
            company,
            payload,
            architecture=architecture,
            output_root=output_root,
            write_lock=write_lock,
        )
        ran += 1
        err = payload.get("error")
        if outcome.action == "kept_success":
            print(
                f"COMPANY_DONE {rcid} {company.get('name')} kept_success err={err!r}",
                flush=True,
            )
            return
        if is_retryable(err) and outcome.path == result_path:
            kind = retry_kind(err)
            if unlink_on_retry:
                backup = backup_retryable(result_path, kind)
            else:
                backup = copy_retryable_backup(result_path, kind)
            need_retry.append(company)
            label = "RATE_LIMIT" if kind == "429" else "TIMEOUT"
            print(
                f"{label} {rcid} {company.get('name')} backed up to {backup.name}",
                flush=True,
            )
        elif err:
            failed += 1
        print(
            f"COMPANY_DONE {rcid} {company.get('name')} "
            f"cost={payload.get('cost_usd')} findings={payload.get('findings_count')} "
            f"dur={payload.get('duration_seconds')}s err={err!r}",
            flush=True,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        while pending and len(in_flight) < worker_count and not stop_event.is_set():
            _submit(pool, pending.popleft())
        while in_flight:
            try:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED, timeout=1.0)
            except KeyboardInterrupt:
                stop_event.set()
                print(
                    "Stop requested. Finishing in-flight companies, starting no new ones.",
                    flush=True,
                )
                done = set()
            for future in done:
                company = in_flight.pop(future)
                _finish(future, company)
            while pending and len(in_flight) < worker_count and not stop_event.is_set():
                _submit(pool, pending.popleft())
    return failed, ran, need_retry


def run_live(
    companies: list[dict[str, Any]],
    *,
    architecture: str,
    output_root,
    limit: Optional[int],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT_S,
    stop_event: Optional[Event] = None,
) -> int:
    """Run the next ``limit`` remaining companies (or all remaining)."""
    if architecture not in RUNNERS:
        raise ValueError(f"unknown architecture {architecture!r}")
    paths = prod_paths(output_root, architecture)
    paths.companies.mkdir(parents=True, exist_ok=True)
    rebuild_jsonl_from_companies(paths, companies)

    stop = stop_event or Event()
    previous = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum, frame):  # noqa: ARG001
        if not stop.is_set():
            print(
                "Stop requested. Finishing in-flight companies, starting no new ones.",
                flush=True,
            )
        stop.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    write_lock = Lock()
    try:
        todo, skipped = _prepare_todo(
            companies,
            architecture=architecture,
            output_root=output_root,
            limit=limit,
        )
        if not todo:
            print(
                f"NOTHING_TO_RUN arch={architecture} skipped={skipped} remaining=0",
                flush=True,
            )
            return 0

        print(
            f"QUEUE n={len(todo)} arch={architecture} concurrency={concurrency} "
            f"rcids={[int(row['rcid']) for row in todo]}",
            flush=True,
        )
        failed, ran, need_retry = _execute_batch(
            todo,
            architecture=architecture,
            output_root=output_root,
            workers=concurrency,
            timeout=timeout,
            write_lock=write_lock,
            stop_event=stop,
            unlink_on_retry=True,
        )
        if need_retry and not stop.is_set():
            print(
                f"RETRY_SEQUENTIAL n={len(need_retry)} "
                f"rcids={[int(row['rcid']) for row in need_retry]}",
                flush=True,
            )
            retry_failed, retry_ran, still_retryable = _execute_batch(
                need_retry,
                architecture=architecture,
                output_root=output_root,
                workers=1,
                timeout=timeout,
                write_lock=write_lock,
                stop_event=stop,
                unlink_on_retry=False,
            )
            failed += retry_failed
            ran += retry_ran
            if still_retryable:
                print(
                    f"STILL_RETRYABLE n={len(still_retryable)} "
                    f"rcids={[int(row['rcid']) for row in still_retryable]}",
                    flush=True,
                )
                failed += len(still_retryable)
        elif need_retry and stop.is_set():
            print(
                f"STOP_SKIP_RETRY n={len(need_retry)} "
                f"rcids={[int(row['rcid']) for row in need_retry]}",
                flush=True,
            )

        rebuild_jsonl_from_companies(paths, companies)
        print(
            f"BATCH_DONE live=True arch={architecture} ran={ran} "
            f"skipped={skipped} failed={failed} stopped={stop.is_set()}",
            flush=True,
        )
        if stop.is_set() or failed:
            return 1
        return 0
    finally:
        signal.signal(signal.SIGINT, previous)


def run_dry(
    companies: list[dict[str, Any]],
    *,
    architecture: str,
    output_root,
    limit: Optional[int],
    timeout: float = DEFAULT_TIMEOUT_S,
) -> int:
    """Call architecture dry-run for the next remaining companies. Write nothing."""
    if architecture not in RUNNERS:
        raise ValueError(f"unknown architecture {architecture!r}")
    todo = remaining_companies(
        companies, architecture=architecture, output_root=output_root
    )
    if limit is not None:
        todo = todo[:limit]
    if not todo:
        print(f"DRY_RUN nothing remaining arch={architecture}", flush=True)
        return 0
    print(
        f"DRY_RUN n={len(todo)} arch={architecture} "
        f"rcids={[int(row['rcid']) for row in todo]} (no files written)",
        flush=True,
    )
    for row in todo:
        payload = _run_one(row, architecture=architecture, dry_run=True, timeout=timeout)
        print(
            f"DRY_RUN {int(row['rcid'])} {row.get('name')} "
            f"reason={payload.get('no_finding_reason')!r} "
            f"stub={payload.get('stub')} dry_run={payload.get('dry_run')}",
            flush=True,
        )
    return 0
