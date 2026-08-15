"""Paid SGS smoke: same 5 companies as sgs_smoke_5co, scout_preset=low.

Digs stay package-default high. Measurement only; does not change SGS defaults.
Writes one result JSON per company plus a compact summary JSONL.
Skips a company if its result file already exists (resume-safe).
Sequential (1 company at a time). 429s are backed up to *.429.json and retried.

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/sgs_smoke_5co_low_scouts/run_smoke.py
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from signal_gated_search.runner import run

OUT_DIR = Path(__file__).resolve().parent
SCOUT_PRESET = "low"
TIMEOUT_S = 600.0
# Scouts then digs, each up to TIMEOUT_S. Hard-kill if a company exceeds this.
COMPANY_HARD_TIMEOUT_S = 1320.0
RETRY_WAIT_S = 45.0

COMPANIES = [
    {
        "rcid": 97943259,
        "name": "Easy Fill AI",
        "homepage_url": "https://easyfill.ai",
        "short_description": "AI Based SaaS Data Collection and Analysis Tool",
        "march_stratum": "none",
        "march_findings": 0,
    },
    {
        "rcid": 1314132,
        "name": "CoverTree",
        "homepage_url": "https://covertree.com",
        "short_description": (
            "CoverTree is an InsurTech company that specializes in "
            "manufactured home insurance solutions."
        ),
        "march_stratum": "low",
        "march_findings": 1,
    },
    {
        "rcid": 103497,
        "name": "Statsig",
        "homepage_url": "https://www.statsig.com",
        "short_description": (
            "Statsig provides tools for A/B testing, feature management, "
            "and product analytics to help teams optimize product development."
        ),
        "march_stratum": "medium",
        "march_findings": 2,
    },
    {
        "rcid": 26492430,
        "name": "Tern Travel",
        "homepage_url": "https://www.tern.travel/",
        "short_description": (
            "Tern Travel builds an integrated platform that connects the "
            "travel advisor to travelers and suppliers."
        ),
        "march_stratum": "high",
        "march_findings": 6,
    },
    {
        "rcid": 610194,
        "name": "Jam",
        "homepage_url": "https://jam.dev/",
        "short_description": "1-click bug reports developers love. Try for free at jam.dev",
        "march_stratum": "high",
        "march_findings": 8,
        "tuning_holdout": True,
    },
]


def _is_429(error: str | None) -> bool:
    text = (error or "").lower()
    return "429" in text or "rate limit" in text or "ratelimit" in text


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    gate = traces.get("gate") or {}
    scout_results = traces.get("scout_results") or {}
    ledger = result.get("cost_ledger") or {}
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "march_stratum": meta["march_stratum"],
        "march_findings": meta["march_findings"],
        "scout_preset": SCOUT_PRESET,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": result.get("dry_run"),
        "stub": result.get("stub"),
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
            {
                f.get("channel")
                for f in result.get("findings") or []
                if f.get("channel")
            }
        ),
    }


def _backup_429(result_path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = result_path.with_name(f"{result_path.stem}.{stamp}.429.json")
    if backup.exists():
        backup = result_path.with_name(f"{result_path.stem}.{stamp}.429b.json")
    shutil.copy2(result_path, backup)
    result_path.unlink()
    return backup


def _run_one(meta: dict) -> tuple[dict, dict]:
    result = run(
        {
            "rcid": meta["rcid"],
            "name": meta["name"],
            "homepage_url": meta["homepage_url"],
            "short_description": meta["short_description"],
        },
        dry_run=False,
        scout_preset=SCOUT_PRESET,
        timeout=TIMEOUT_S,
    )
    payload = result.to_dict()
    return payload, _compact(payload, meta)


def _write_result(result_path: Path, payload: dict, compact: dict) -> None:
    result_path.write_text(json.dumps(payload, indent=2) + "\n")
    summary_path = OUT_DIR / "summary.jsonl"
    with summary_path.open("a") as handle:
        handle.write(json.dumps(compact) + "\n")


def _execute_one(meta: dict) -> tuple[dict, dict]:
    rcid = meta["rcid"]
    try:
        return _run_one(meta)
    except Exception as exc:
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
        return payload, compact


def _process_target(meta: dict, conn) -> None:
    try:
        payload, compact = _execute_one(meta)
        conn.send(("ok", payload, compact))
    except Exception as exc:
        conn.send(("err", f"{type(exc).__name__}: {exc}", traceback.format_exc()))
    finally:
        conn.close()


def _execute_one_hard_timeout(meta: dict) -> tuple[dict, dict]:
    """Run one company in a child process so a hung API call can be killed."""
    parent, child = mp.Pipe(duplex=False)
    proc = mp.Process(target=_process_target, args=(meta, child))
    proc.start()
    child.close()
    proc.join(COMPANY_HARD_TIMEOUT_S)
    if proc.is_alive():
        proc.terminate()
        proc.join(10)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
        payload = {
            "rcid": meta["rcid"],
            "company_name": meta["name"],
            "architecture": "signal-gated-search",
            "error": (
                f"TimeoutError: company exceeded {COMPANY_HARD_TIMEOUT_S:.0f}s "
                f"hard cap (API timeout={TIMEOUT_S:.0f}s)"
            ),
            "dry_run": False,
        }
        compact = _compact(payload, meta, error=payload["error"])
        print(f"HARD_TIMEOUT {meta['rcid']} {meta['name']}: {payload['error']}", flush=True)
        return payload, compact
    if parent.poll():
        kind, *rest = parent.recv()
        if kind == "ok":
            return rest[0], rest[1]
        payload = {
            "rcid": meta["rcid"],
            "company_name": meta["name"],
            "architecture": "signal-gated-search",
            "error": rest[0],
            "traceback": rest[1] if len(rest) > 1 else None,
            "dry_run": False,
        }
        return payload, _compact(payload, meta, error=payload["error"])
    payload = {
        "rcid": meta["rcid"],
        "company_name": meta["name"],
        "architecture": "signal-gated-search",
        "error": f"RuntimeError: child exited with code {proc.exitcode} and no result",
        "dry_run": False,
    }
    return payload, _compact(payload, meta, error=payload["error"])


def main() -> int:
    summary_path = OUT_DIR / "summary.jsonl"
    failed = 0
    for meta in COMPANIES:
        rcid = meta["rcid"]
        result_path = OUT_DIR / f"{rcid}.json"
        if result_path.exists():
            print(f"SKIP {rcid} {meta['name']}: {result_path.name} already exists", flush=True)
            print(f"COMPANY_DONE {rcid} skip", flush=True)
            continue
        print(
            f"START {rcid} {meta['name']} stratum={meta['march_stratum']} "
            f"march_n={meta['march_findings']} scout_preset={SCOUT_PRESET}",
            flush=True,
        )
        payload, compact = _execute_one_hard_timeout(meta)
        _write_result(result_path, payload, compact)
        err = compact.get("error")
        retryable = _is_429(err) or (err or "").startswith("TimeoutError")
        if retryable:
            backup = _backup_429(result_path)
            label = "RATE_LIMIT" if _is_429(err) else "TIMEOUT"
            print(
                f"{label} {rcid} {meta['name']} backed up to {backup.name}; "
                f"waiting {RETRY_WAIT_S:.0f}s then retry",
                flush=True,
            )
            time.sleep(RETRY_WAIT_S)
            payload, compact = _execute_one_hard_timeout(meta)
            _write_result(result_path, payload, compact)
            err = compact.get("error")
            if _is_429(err) or (err or "").startswith("TimeoutError"):
                still = result_path.with_name(
                    f"{result_path.stem}."
                    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.429.json"
                )
                shutil.copy2(result_path, still)
                print(
                    f"STILL_FAIL {rcid} {meta['name']} kept {result_path.name} "
                    f"and copied {still.name}",
                    flush=True,
                )
                failed += 1
        elif err:
            failed += 1
        print(
            f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
            f"findings={compact.get('findings_count')} "
            f"digs={compact['gate'].get('dig_count')} "
            f"effort={compact['gate'].get('reasoning_effort')} "
            f"rooms={compact['gate'].get('dig_channels')} "
            f"dur={compact.get('duration_seconds')}s "
            f"err={err!r}",
            flush=True,
        )
    print(f"SMOKE_DONE failed={failed} scout_preset={SCOUT_PRESET}", flush=True)
    if summary_path.exists():
        print(f"SUMMARY {summary_path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
