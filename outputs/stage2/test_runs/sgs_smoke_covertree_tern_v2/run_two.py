"""Paid SGS re-smoke: CoverTree + Tern Travel after owned/social prompt fix."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from signal_gated_search.runner import run

OUT_DIR = Path(__file__).resolve().parent

COMPANIES = [
    {
        "rcid": 1314132,
        "name": "CoverTree",
        "homepage_url": "https://covertree.com",
        "short_description": (
            "CoverTree is an InsurTech company that specializes in "
            "manufactured home insurance solutions."
        ),
        "march_findings": 1,
    },
    {
        "rcid": 26492430,
        "name": "Tern Travel",
        "homepage_url": "https://www.tern.travel/",
        "short_description": (
            "Tern Travel builds an integrated platform that connects the "
            "travel advisor to travelers and suppliers."
        ),
        "march_findings": 6,
    },
]


def _compact(result: dict, meta: dict, error: str | None = None) -> dict:
    traces = result.get("traces") or {}
    gate = traces.get("gate") or {}
    scout_results = traces.get("scout_results") or {}
    ledger = result.get("cost_ledger") or {}
    return {
        "rcid": meta["rcid"],
        "name": meta["name"],
        "march_findings": meta["march_findings"],
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": result.get("duration_seconds"),
        "cost_usd": result.get("cost_usd"),
        "findings_count": result.get("findings_count"),
        "preset": result.get("preset"),
        "error": error or result.get("error"),
        "no_finding_reason": result.get("no_finding_reason"),
        "gate": {
            "dig_count": gate.get("dig_count"),
            "dig_channels": gate.get("dig_channels"),
            "reasoning_effort": gate.get("reasoning_effort"),
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


def main() -> int:
    summary_path = OUT_DIR / "summary.jsonl"
    failed = 0
    for meta in COMPANIES:
        rcid = meta["rcid"]
        result_path = OUT_DIR / f"{rcid}.json"
        print(
            f"START {rcid} {meta['name']} march_n={meta['march_findings']}",
            flush=True,
        )
        try:
            result = run(
                {
                    "rcid": meta["rcid"],
                    "name": meta["name"],
                    "homepage_url": meta["homepage_url"],
                    "short_description": meta["short_description"],
                },
                dry_run=False,
            )
            payload = result.to_dict()
            compact = _compact(payload, meta)
        except Exception as exc:
            failed += 1
            payload = {
                "rcid": rcid,
                "company_name": meta["name"],
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
            compact = _compact(payload, meta, error=payload["error"])
            print(f"FAIL {rcid}: {payload['error']}", flush=True)
        result_path.write_text(json.dumps(payload, indent=2) + "\n")
        with summary_path.open("a") as handle:
            handle.write(json.dumps(compact) + "\n")
        print(
            f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
            f"findings={compact.get('findings_count')} march={meta['march_findings']} "
            f"digs={compact['gate'].get('dig_count')} "
            f"channels={compact['gate'].get('dig_channels')} "
            f"effort={compact['gate'].get('reasoning_effort')} "
            f"bins={compact.get('scout_bins')} "
            f"dur={compact.get('duration_seconds')}s "
            f"err={compact.get('error')!r}",
            flush=True,
        )
    print(f"SMOKE_DONE failed={failed}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
