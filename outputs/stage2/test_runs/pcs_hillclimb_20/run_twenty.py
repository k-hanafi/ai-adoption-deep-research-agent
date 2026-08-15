"""Paid PCS hill-climb: 20 companies from hillclimb_panel.json.

Sequential, resume-safe (skips a company if its result JSON already exists).
Writes one full result JSON per company plus a compact summary JSONL.

Usage:
  PYTHONPATH=. python3 outputs/stage2/test_runs/pcs_hillclimb_20/run_twenty.py
  PYTHONPATH=. python3 outputs/stage2/test_runs/pcs_hillclimb_20/run_twenty.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from evals.paths import HILLCLIMB_PANEL_PATH
from parallel_channel_search.runner import run

OUT_DIR = Path(__file__).resolve().parent


def _load_companies() -> list[dict]:
    panel = json.loads(HILLCLIMB_PANEL_PATH.read_text(encoding="utf-8"))
    companies = panel.get("companies") or []
    if len(companies) != 20:
        raise RuntimeError(f"expected 20 hill-climb companies, got {len(companies)}")
    return companies


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    channel_results = traces.get("channel_results") or {}
    ledger = result.get("cost_ledger") or {}
    findings = result.get("findings") or []
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "stratum": meta.get("stratum"),
        "hillclimb_role": meta.get("hillclimb_role"),
        "march_findings": (meta.get("march_reference") or {}).get("findings_count"),
        "march_channels": (meta.get("march_reference") or {}).get("channels") or [],
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


def main() -> int:
    parser = argparse.ArgumentParser(description="PCS hill-climb 20-company run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compose three channel requests per company; no paid API calls",
    )
    parser.add_argument(
        "--only",
        type=int,
        nargs="+",
        default=None,
        help="Retry only these rcids (still resume-safe if the JSON exists)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-channel Agent API timeout in seconds (default: package 300)",
    )
    args = parser.parse_args()
    live = not args.dry_run

    companies = _load_companies()
    if args.only:
        want = set(args.only)
        companies = [c for c in companies if int(c["rcid"]) in want]
        missing = want - {int(c["rcid"]) for c in companies}
        if missing:
            raise SystemExit(f"rcids not in hill-climb panel: {sorted(missing)}")
    summary_path = OUT_DIR / ("summary_dry.jsonl" if args.dry_run else "summary.jsonl")
    failed = 0
    ran = 0
    skipped = 0
    for meta in companies:
        rcid = int(meta["rcid"])
        suffix = ".dry.json" if args.dry_run else ".json"
        result_path = OUT_DIR / f"{rcid}{suffix}"
        if result_path.exists():
            skipped += 1
            print(
                f"SKIP {rcid} {meta['name']}: {result_path.name} already exists",
                flush=True,
            )
            print(f"COMPANY_DONE {rcid} skip", flush=True)
            continue
        print(
            f"START {rcid} {meta['name']} stratum={meta.get('stratum')} "
            f"march_n={(meta.get('march_reference') or {}).get('findings_count')} "
            f"live={live}",
            flush=True,
        )
        try:
            run_kwargs = {
                "dry_run": not live,
            }
            if args.timeout is not None:
                run_kwargs["timeout"] = args.timeout
            result = run(
                {
                    "rcid": meta["rcid"],
                    "name": meta["name"],
                    "homepage_url": meta.get("homepage_url"),
                    "short_description": meta.get("short_description"),
                },
                **run_kwargs,
            )
            payload = result.to_dict()
            compact = _compact(payload, meta)
        except Exception as exc:
            failed += 1
            payload = {
                "rcid": rcid,
                "company_name": meta["name"],
                "architecture": "parallel-channel-search",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "dry_run": not live,
            }
            compact = _compact(payload, meta, error=payload["error"])
            print(f"FAIL {rcid} {meta['name']}: {payload['error']}", flush=True)
        result_path.write_text(json.dumps(payload, indent=2) + "\n")
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(compact) + "\n")
        ran += 1
        print(
            f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
            f"findings={compact.get('findings_count')} "
            f"ch={compact.get('finding_channels')} "
            f"dur={compact.get('duration_seconds')}s "
            f"err={compact.get('error')!r}",
            flush=True,
        )
    print(
        f"PANEL_DONE live={live} ran={ran} skipped={skipped} failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
