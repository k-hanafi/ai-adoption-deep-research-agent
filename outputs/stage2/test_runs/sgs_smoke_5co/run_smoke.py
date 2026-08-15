"""Paid SGS smoke: 5 March companies across finding-count strata.

Writes one result JSON per company plus a compact summary JSONL.
Skips a company if its result file already exists (resume-safe).
"""

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
            f"march_n={meta['march_findings']}",
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
                "architecture": "signal-gated-search",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "dry_run": False,
            }
            compact = _compact(payload, meta, error=payload["error"])
            print(f"FAIL {rcid} {meta['name']}: {payload['error']}", flush=True)
        result_path.write_text(json.dumps(payload, indent=2) + "\n")
        with summary_path.open("a") as handle:
            handle.write(json.dumps(compact) + "\n")
        print(
            f"COMPANY_DONE {rcid} {meta['name']} cost={compact.get('cost_usd')} "
            f"findings={compact.get('findings_count')} "
            f"digs={compact['gate'].get('dig_count')} "
            f"effort={compact['gate'].get('reasoning_effort')} "
            f"dur={compact.get('duration_seconds')}s "
            f"err={compact.get('error')!r}",
            flush=True,
        )
    print(f"SMOKE_DONE failed={failed}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
