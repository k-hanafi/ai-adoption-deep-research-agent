"""Paid UAS hill-climb: same 20 companies, one Luna call at xhigh.

Does not overwrite PCS folders. Resume-safe (skips a company if its
result JSON already exists).

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/uas_hillclimb_20_xhigh/run_twenty.py
"""

from __future__ import annotations

import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from evals.paths import HILLCLIMB_PANEL_PATH
from unified_adaptive_search.agent_call import (
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
)
from unified_adaptive_search.runner import run

OUT_DIR = Path(__file__).resolve().parent
REASONING_EFFORT = DEFAULT_REASONING_EFFORT  # xhigh
MAX_STEPS = DEFAULT_MAX_STEPS  # 10
WEB_SEARCH_DEPTH = DEFAULT_WEB_SEARCH_DEPTH  # low
TIMEOUT_S = 600.0
WORKERS = 20


def _load_companies() -> list[dict]:
    panel = json.loads(HILLCLIMB_PANEL_PATH.read_text(encoding="utf-8"))
    companies = panel.get("companies") or []
    if len(companies) != 20:
        raise RuntimeError(f"expected 20 hill-climb companies, got {len(companies)}")
    return companies


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    ledger = result.get("cost_ledger") or {}
    findings = result.get("findings") or []
    tool_use = traces.get("tool_use") or {}
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "stratum": meta.get("stratum"),
        "hillclimb_role": meta.get("hillclimb_role"),
        "march_findings": (meta.get("march_reference") or {}).get("findings_count"),
        "march_channels": (meta.get("march_reference") or {}).get("channels") or [],
        "architecture": "unified-adaptive-search",
        "reasoning_effort": REASONING_EFFORT,
        "max_steps": MAX_STEPS,
        "web_search_depth": WEB_SEARCH_DEPTH,
        "model": DEFAULT_MODEL,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": result.get("dry_run"),
        "duration_seconds": result.get("duration_seconds"),
        "cost_usd": result.get("cost_usd"),
        "findings_count": result.get("findings_count"),
        "genai_adoption_found": result.get("genai_adoption_found"),
        "model_used": result.get("model_used"),
        "error": error or result.get("error"),
        "no_finding_reason": result.get("no_finding_reason"),
        "source_types": sorted(
            {f.get("source_type") for f in findings if f.get("source_type")}
        ),
        "finding_tools": [
            f.get("AI_tool_used") for f in findings if f.get("AI_tool_used")
        ],
        "tool_use": {
            "tool_calls_details": tool_use.get("tool_calls_details"),
            "tool_output_items": tool_use.get("tool_output_items"),
            "search_result_urls": tool_use.get("search_result_urls"),
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
        max_steps=MAX_STEPS,
        web_search_depth=WEB_SEARCH_DEPTH,
        timeout=TIMEOUT_S,
    )
    payload = result.to_dict()
    return payload, _compact(payload, meta)


def main() -> int:
    companies = _load_companies()
    summary_path = OUT_DIR / "summary.jsonl"
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
            f"effort={REASONING_EFFORT} steps={MAX_STEPS} search={WEB_SEARCH_DEPTH}",
            flush=True,
        )

    failed = 0
    ran = 0
    if todo:
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(todo))) as pool:
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
                        "architecture": "unified-adaptive-search",
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "dry_run": False,
                    }
                    compact = _compact(payload, meta, error=payload["error"])
                    print(f"FAIL {rcid} {meta['name']}: {payload['error']}", flush=True)
                result_path.write_text(json.dumps(payload, indent=2) + "\n")
                with write_lock:
                    with summary_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(compact) + "\n")
                ran += 1
                print(
                    f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
                    f"findings={compact.get('findings_count')} "
                    f"dur={compact.get('duration_seconds')}s "
                    f"err={compact.get('error')!r}",
                    flush=True,
                )

    print(
        f"PANEL_DONE live=True arch=uas effort={REASONING_EFFORT} "
        f"ran={ran} skipped={skipped} failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
