"""Paid PCS confirm: same 20 as pcs_confirm_20_high, 3× medium.

Does not overwrite the high folder. Resume-safe: skips only a complete
success JSON (no error). Failed or unreadable files are backed up and
retried. 5 companies in flight (15 channel calls). Rate limits and
timeouts are detected from the error field only, then backed up and
retried one company at a time. A later failure never overwrites a
successful company JSON.

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/pcs_confirm_20_medium/run_twenty_medium.py
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from evals.paths import PCS_CONFIRM_PANEL_PATH
from parallel_channel_search.runner import run

OUT_DIR = Path(__file__).resolve().parent
REASONING_EFFORT = "medium"
TIMEOUT_S = 600.0
# Each company fans out 3 channel calls. 5 companies => 15 in-flight.
# Confirm-high was clean at 5. Hill-climb medium v2 had real RateLimitError
# at 20-wide. Do not treat this folder's *.429.json as evidence: those
# payloads have error=null (old substring detector).
WORKERS = 5


def _load_companies() -> list[dict]:
    panel = json.loads(PCS_CONFIRM_PANEL_PATH.read_text(encoding="utf-8"))
    companies = panel.get("companies") or []
    if len(companies) != 20:
        raise RuntimeError(f"expected 20 confirm companies, got {len(companies)}")
    return companies


def _is_rate_limit(error: str | None) -> bool:
    text = (error or "").lower()
    return "429" in text or "rate limit" in text or "ratelimit" in text


def _is_timeout(error: str | None) -> bool:
    return "timeout" in (error or "").lower()


def _is_retryable(error: str | None) -> bool:
    return _is_rate_limit(error) or _is_timeout(error)


def _retry_kind(error: str | None) -> str:
    if _is_rate_limit(error):
        return "429"
    if _is_timeout(error):
        return "timeout"
    return "failed"


def _load_payload(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_complete_success(payload: dict | None) -> bool:
    return bool(payload) and not payload.get("error")


def _backup_path(result_path: Path, kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = result_path.with_name(f"{result_path.stem}.{stamp}.{kind}.json")
    if backup.exists():
        backup = result_path.with_name(f"{result_path.stem}.{stamp}.{kind}b.json")
    return backup


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    channel_results = traces.get("channel_results") or {}
    ledger = result.get("cost_ledger") or {}
    findings = result.get("findings") or []
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "stratum": meta.get("stratum"),
        "confirm_role": meta.get("confirm_role"),
        "march_findings": (meta.get("march_reference") or {}).get("findings_count"),
        "march_channels": (meta.get("march_reference") or {}).get("channels") or [],
        "reasoning_effort": REASONING_EFFORT,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": result.get("dry_run"),
        "duration_seconds": result.get("duration_seconds"),
        "cost_usd": result.get("cost_usd"),
        "findings_count": result.get("findings_count"),
        "genai_adoption_found": result.get("genai_adoption_found"),
        "model_used": result.get("model_used"),
        "error": error or result.get("error"),
        "no_finding_reason": result.get("no_finding_reason"),
        "channel_finding_counts": {
            channel: (channel_results.get(channel) or {}).get("finding_count")
            for channel in ("jobs", "owned", "third_party")
        },
        "channel_costs": {
            channel: (channel_results.get(channel) or {}).get("cost_usd")
            for channel in ("jobs", "owned", "third_party")
        },
        "ledger": [
            {
                "name": c.get("name"),
                "preset": c.get("preset"),
                "cost_usd": c.get("cost_usd"),
                "ran": c.get("ran"),
                "skipped_reason": c.get("skipped_reason"),
            }
            for c in ledger.get("components") or []
        ],
        "finding_channels": sorted(
            {f.get("channel") for f in findings if f.get("channel")}
        ),
        "finding_tools": [
            f.get("AI_tool_used") for f in findings if f.get("AI_tool_used")
        ],
    }


def _run_one(meta: dict) -> tuple[dict, dict]:
    result = run(
        {
            "rcid": meta["rcid"],
            "name": meta["name"],
            "homepage_url": meta.get("homepage_url"),
            "short_description": meta.get("short_description"),
        },
        dry_run=False,
        reasoning_effort=REASONING_EFFORT,
        timeout=TIMEOUT_S,
    )
    payload = result.to_dict()
    return payload, _compact(payload, meta)


def _write_result(result_path: Path, payload: dict, compact: dict, summary_path: Path, lock: Lock) -> Path:
    existing = _load_payload(result_path) if result_path.exists() else None
    if _is_complete_success(existing) and compact.get("error"):
        backup = _backup_path(result_path, "failed")
        backup.write_text(json.dumps(payload, indent=2) + "\n")
        print(
            f"KEEP_SUCCESS {compact.get('rcid')} {compact.get('name')}: "
            f"left {result_path.name} in place, wrote failure to {backup.name}",
            flush=True,
        )
        return backup
    result_path.write_text(json.dumps(payload, indent=2) + "\n")
    with lock:
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(compact) + "\n")
    return result_path


def main() -> int:
    companies = _load_companies()
    by_rcid = {int(c["rcid"]): c for c in companies}
    summary_path = OUT_DIR / "summary.jsonl"
    write_lock = Lock()
    todo: list[dict] = []
    skipped = 0
    for meta in companies:
        rcid = int(meta["rcid"])
        result_path = OUT_DIR / f"{rcid}.json"
        if result_path.exists():
            existing = _load_payload(result_path)
            if _is_complete_success(existing):
                skipped += 1
                print(
                    f"SKIP {rcid} {meta['name']}: {result_path.name} already complete",
                    flush=True,
                )
                print(f"COMPANY_DONE {rcid} skip", flush=True)
                continue
            kind = _retry_kind((existing or {}).get("error"))
            backup = _backup_path(result_path, kind)
            shutil.move(str(result_path), str(backup))
            print(
                f"REQUEUE {rcid} {meta['name']}: failed {result_path.name} "
                f"backed up to {backup.name}",
                flush=True,
            )
        todo.append(meta)
        print(
            f"QUEUE {rcid} {meta['name']} stratum={meta.get('stratum')} "
            f"effort={REASONING_EFFORT} workers={WORKERS}",
            flush=True,
        )

    failed = 0
    ran = 0
    retry: list[dict] = []

    def _handle(meta: dict, payload: dict, compact: dict, *, sequential: bool) -> None:
        nonlocal failed, ran
        rcid = int(meta["rcid"])
        result_path = OUT_DIR / f"{rcid}.json"
        err = compact.get("error") or payload.get("error")
        if _is_retryable(err) and not sequential:
            kind = _retry_kind(err)
            backup = _backup_path(result_path, kind)
            backup.write_text(json.dumps(payload, indent=2) + "\n")
            retry.append(meta)
            label = "RATE_LIMIT" if kind == "429" else "TIMEOUT"
            print(
                f"{label} {rcid} {meta['name']}: backed up {backup.name}; "
                "will retry sequentially",
                flush=True,
            )
            return
        if compact.get("error"):
            failed += 1
            print(f"FAIL {rcid} {meta['name']}: {compact.get('error')}", flush=True)
        _write_result(result_path, payload, compact, summary_path, write_lock)
        ran += 1
        print(
            f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
            f"findings={compact.get('findings_count')} "
            f"ch={compact.get('finding_channels')} "
            f"dur={compact.get('duration_seconds')}s "
            f"err={compact.get('error')!r}",
            flush=True,
        )

    if todo:
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(todo))) as pool:
            futures = {pool.submit(_run_one, meta): meta for meta in todo}
            for future in as_completed(futures):
                meta = futures[future]
                try:
                    payload, compact = future.result()
                except Exception as exc:
                    payload = {
                        "rcid": int(meta["rcid"]),
                        "company_name": meta["name"],
                        "architecture": "parallel-channel-search",
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "dry_run": False,
                    }
                    compact = _compact(payload, meta, error=payload["error"])
                _handle(meta, payload, compact, sequential=False)

    for meta in retry:
        rcid = int(meta["rcid"])
        print(f"RETRY {rcid} {meta['name']} sequential after retryable error", flush=True)
        try:
            payload, compact = _run_one(meta)
        except Exception as exc:
            payload = {
                "rcid": rcid,
                "company_name": meta["name"],
                "architecture": "parallel-channel-search",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "dry_run": False,
            }
            compact = _compact(payload, meta, error=payload["error"])
        _handle(by_rcid[rcid], payload, compact, sequential=True)

    print(
        f"PANEL_DONE live=True effort={REASONING_EFFORT} workers={WORKERS} "
        f"ran={ran} skipped={skipped} failed={failed} retried={len(retry)}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
