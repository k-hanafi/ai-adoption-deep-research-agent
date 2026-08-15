"""Paid SGS hill-climb: same 20 companies, digs forced to medium.

Measurement probe only. Does not change SGS package defaults (those stay high).
The override is local to this script: it patches DIG_EFFORT_BY_COUNT in memory
so every signaled room is dug at medium.

Resume-safe (skips a company if its result JSON already exists).
Modest concurrency (4 companies). 429s are backed up to *.429.json
and retried sequentially, then summary.jsonl is rebuilt from current JSONs.

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/sgs_hillclimb_20_medium/run_twenty_medium.py
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

import signal_gated_search.channels as sgs_channels
import signal_gated_search.gate as sgs_gate
import signal_gated_search.runner as sgs_runner
from evals.paths import HILLCLIMB_PANEL_PATH
from signal_gated_search.runner import run

OUT_DIR = Path(__file__).resolve().parent
DIG_EFFORT = "medium"  # probe override; package default remains high
TIMEOUT_S = 600.0
WORKERS = 4

# In-memory only. Package files stay DIG_EFFORT_BY_COUNT = high.
_PROBE_LADDER = {1: DIG_EFFORT, 2: DIG_EFFORT, 3: DIG_EFFORT}
sgs_channels.DIG_EFFORT_BY_COUNT = _PROBE_LADDER
sgs_gate.DIG_EFFORT_BY_COUNT = _PROBE_LADDER
sgs_runner.DIG_EFFORT_BY_COUNT = _PROBE_LADDER


def _load_companies() -> list[dict]:
    panel = json.loads(HILLCLIMB_PANEL_PATH.read_text(encoding="utf-8"))
    companies = panel.get("companies") or []
    if len(companies) != 20:
        raise RuntimeError(f"expected 20 hill-climb companies, got {len(companies)}")
    return companies


def _is_429(error: str | None) -> bool:
    text = (error or "").lower()
    return "429" in text or "rate limit" in text or "ratelimit" in text


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    gate = traces.get("gate") or {}
    scout_results = traces.get("scout_results") or {}
    ledger = result.get("cost_ledger") or {}
    findings = result.get("findings") or []
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "stratum": meta.get("stratum"),
        "hillclimb_role": meta.get("hillclimb_role"),
        "march_findings": (meta.get("march_reference") or {}).get("findings_count"),
        "march_channels": (meta.get("march_reference") or {}).get("channels") or [],
        "architecture": "signal-gated-search",
        "dig_effort": DIG_EFFORT,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": result.get("dry_run"),
        "duration_seconds": result.get("duration_seconds"),
        "cost_usd": result.get("cost_usd"),
        "findings_count": result.get("findings_count"),
        "genai_adoption_found": result.get("genai_adoption_found"),
        "preset": result.get("preset"),
        "model_used": result.get("model_used"),
        "error": error or result.get("error"),
        "no_finding_reason": result.get("no_finding_reason"),
        "gate": {
            "stop_at_scouts": gate.get("stop_at_scouts"),
            "dig_count": gate.get("dig_count"),
            "dig_channels": gate.get("dig_channels"),
            "reasoning_effort": gate.get("reasoning_effort"),
            "rationale": gate.get("rationale"),
        },
        "scout_bins": {
            channel: (scout_results.get(channel) or {}).get("evidence_bin")
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
        timeout=TIMEOUT_S,
    )
    payload = result.to_dict()
    return payload, _compact(payload, meta)


def _write_result(result_path: Path, payload: dict, compact: dict, write_lock: Lock) -> None:
    result_path.write_text(json.dumps(payload, indent=2) + "\n")
    summary_path = OUT_DIR / "summary.jsonl"
    with write_lock:
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(compact) + "\n")


def _backup_429(result_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = result_path.with_name(f"{result_path.stem}.{stamp}.429.json")
    if backup.exists():
        backup = result_path.with_name(f"{result_path.stem}.{stamp}.429b.json")
    shutil.copy2(result_path, backup)
    result_path.unlink()
    return backup


def _rebuild_summary(companies: list[dict]) -> None:
    summary_path = OUT_DIR / "summary.jsonl"
    rows: list[str] = []
    for meta in companies:
        rcid = int(meta["rcid"])
        result_path = OUT_DIR / f"{rcid}.json"
        if not result_path.exists():
            continue
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        rows.append(json.dumps(_compact(payload, meta, error=payload.get("error"))))
    summary_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def _execute_batch(
    todo: list[dict],
    *,
    workers: int,
    write_lock: Lock,
    unlink_on_429: bool,
) -> tuple[int, int, list[dict]]:
    failed = 0
    ran = 0
    need_retry: list[dict] = []
    if not todo:
        return failed, ran, need_retry
    with ThreadPoolExecutor(max_workers=min(workers, len(todo))) as pool:
        futures = {pool.submit(_run_one, meta): meta for meta in todo}
        for future in as_completed(futures):
            meta = futures[future]
            rcid = int(meta["rcid"])
            result_path = OUT_DIR / f"{rcid}.json"
            try:
                payload, compact = future.result()
            except Exception as exc:
                failed += 1
                payload = {
                    "rcid": rcid,
                    "company_name": meta["name"],
                    "architecture": "signal-gated-search",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                    "dry_run": False,
                }
                compact = _compact(payload, meta, error=payload["error"])
                print(f"FAIL {rcid} {meta['name']}: {payload['error']}", flush=True)
            _write_result(result_path, payload, compact, write_lock)
            ran += 1
            err = compact.get("error")
            if _is_429(err):
                backup = _backup_429(result_path) if unlink_on_429 else result_path
                if not unlink_on_429:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    backup = result_path.with_name(f"{result_path.stem}.{stamp}.429.json")
                    shutil.copy2(result_path, backup)
                need_retry.append(meta)
                print(
                    f"RATE_LIMIT {rcid} {meta['name']} backed up to {backup.name}",
                    flush=True,
                )
            print(
                f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
                f"findings={compact.get('findings_count')} "
                f"digs={compact['gate'].get('dig_count')} "
                f"effort={compact['gate'].get('reasoning_effort')} "
                f"ch={compact.get('finding_channels')} "
                f"dur={compact.get('duration_seconds')}s "
                f"err={err!r}",
                flush=True,
            )
    return failed, ran, need_retry


def main() -> int:
    companies = _load_companies()
    write_lock = Lock()
    todo: list[dict] = []
    skipped = 0
    for meta in companies:
        rcid = int(meta["rcid"])
        result_path = OUT_DIR / f"{rcid}.json"
        if result_path.exists():
            skipped += 1
            print(f"SKIP {rcid} {meta['name']}: {result_path.name} already exists", flush=True)
            print(f"COMPANY_DONE {rcid} skip", flush=True)
            continue
        todo.append(meta)
        print(
            f"QUEUE {rcid} {meta['name']} stratum={meta.get('stratum')} "
            f"dig_effort={DIG_EFFORT} (probe override)",
            flush=True,
        )

    failed, ran, need_retry = _execute_batch(
        todo, workers=WORKERS, write_lock=write_lock, unlink_on_429=True
    )

    if need_retry:
        print(
            f"RETRY_SEQUENTIAL n={len(need_retry)} "
            f"rcids={[int(m['rcid']) for m in need_retry]}",
            flush=True,
        )
        retry_failed, retry_ran, still_429 = _execute_batch(
            need_retry, workers=1, write_lock=write_lock, unlink_on_429=False
        )
        failed += retry_failed
        ran += retry_ran
        if still_429:
            print(
                f"STILL_429 n={len(still_429)} "
                f"rcids={[int(m['rcid']) for m in still_429]}",
                flush=True,
            )
            failed += len(still_429)

    _rebuild_summary(companies)
    print(
        f"PANEL_DONE live=True arch=sgs dig_effort={DIG_EFFORT} "
        f"ran={ran} skipped={skipped} failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
