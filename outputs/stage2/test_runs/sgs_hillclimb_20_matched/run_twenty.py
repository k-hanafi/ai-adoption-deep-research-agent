"""Paid SGS vs PCS-high compare on the hill-climb 20.

Package defaults: scout_preset=low, digs Luna steps=50 / search=medium /
effort=high, current extract prompts (PCS locks imported). Does not overwrite
sgs_hillclimb_20_high/ (old fast scouts + shallow digs).

Compare target: outputs/stage2/test_runs/pcs_hillclimb_20_high/
(same 20, same dig leash, same extract teaching). The intended difference is
SGS presence scouts that can skip rooms that do not exist.

Resume-safe. 4 companies in flight. 429s backed up and retried sequentially.

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/sgs_hillclimb_20_matched/run_twenty.py
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

from evals.paths import HILLCLIMB_PANEL_PATH
from signal_gated_search.channels import (
    DEFAULT_DIG_MAX_STEPS,
    DEFAULT_DIG_WEB_SEARCH_DEPTH,
    DEFAULT_SCOUT_PRESET,
)
from signal_gated_search.runner import run

OUT_DIR = Path(__file__).resolve().parent
DIG_EFFORT = "high"
SCOUT_PRESET = DEFAULT_SCOUT_PRESET
TIMEOUT_S = 600.0
WORKERS = 4


def _load_companies() -> list[dict]:
    panel = json.loads(HILLCLIMB_PANEL_PATH.read_text(encoding="utf-8"))
    companies = panel.get("companies") or []
    if len(companies) != 20:
        raise RuntimeError(f"expected 20 hill-climb companies, got {len(companies)}")
    return companies


def _is_429(error: str | None) -> bool:
    text = (error or "").lower()
    return "429" in text or "rate limit" in text or "ratelimit" in text


def _load_payload(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_complete_success(payload: dict | None) -> bool:
    return bool(payload) and not payload.get("error")


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
        "scout_preset": traces.get("scout_preset") or SCOUT_PRESET,
        "dig_effort": DIG_EFFORT,
        "dig_max_steps": DEFAULT_DIG_MAX_STEPS,
        "dig_web_search_depth": DEFAULT_DIG_WEB_SEARCH_DEPTH,
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
        scout_preset=SCOUT_PRESET,
    )
    payload = result.to_dict()
    return payload, _compact(payload, meta)


def _write_result(result_path: Path, payload: dict, compact: dict, write_lock: Lock) -> Path:
    existing = _load_payload(result_path) if result_path.exists() else None
    if _is_complete_success(existing) and compact.get("error"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = result_path.with_name(f"{result_path.stem}.{stamp}.failed.json")
        backup.write_text(json.dumps(payload, indent=2) + "\n")
        print(
            f"KEEP_SUCCESS {compact.get('rcid')} {compact.get('name')}: "
            f"left {result_path.name} in place, wrote failure to {backup.name}",
            flush=True,
        )
        return backup
    result_path.write_text(json.dumps(payload, indent=2) + "\n")
    summary_path = OUT_DIR / "summary.jsonl"
    with write_lock:
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(compact) + "\n")
    return result_path


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
            written = _write_result(result_path, payload, compact, write_lock)
            ran += 1
            err = compact.get("error")
            if _is_429(err) and written == result_path:
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
                f"bins={compact.get('scout_bins')} "
                f"dur={compact.get('duration_seconds')}s "
                f"err={err!r}",
                flush=True,
            )
    return failed, ran, need_retry


def main() -> int:
    if SCOUT_PRESET != "low":
        raise RuntimeError(f"expected package scout_preset=low, got {SCOUT_PRESET!r}")
    if DEFAULT_DIG_MAX_STEPS != 50 or DEFAULT_DIG_WEB_SEARCH_DEPTH != "medium":
        raise RuntimeError(
            f"expected PCS-matched digs 50/medium, got "
            f"{DEFAULT_DIG_MAX_STEPS}/{DEFAULT_DIG_WEB_SEARCH_DEPTH}"
        )
    companies = _load_companies()
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
            err = (existing or {}).get("error")
            kind = "429" if _is_429(err) else "failed"
            backup = result_path.with_name(
                f"{result_path.stem}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.{kind}.json"
            )
            shutil.move(str(result_path), str(backup))
            print(
                f"REQUEUE {rcid} {meta['name']}: failed {result_path.name} "
                f"backed up to {backup.name}",
                flush=True,
            )
        todo.append(meta)
        print(
            f"QUEUE {rcid} {meta['name']} stratum={meta.get('stratum')} "
            f"scout={SCOUT_PRESET} digs=50/medium/{DIG_EFFORT}",
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
        f"PANEL_DONE live=True arch=sgs scout={SCOUT_PRESET} "
        f"digs=50/medium/{DIG_EFFORT} ran={ran} skipped={skipped} failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
