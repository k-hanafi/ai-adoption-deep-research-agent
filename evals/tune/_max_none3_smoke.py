"""Max-knob smoke on 3 March-zero (stratum=none) companies, skipping 4D Sight."""
from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contracts.types import CompanyInput
from evals.architectures import run_company
from evals.panel import load_panel
from evals.paths import EVAL_RUNS_DIR, TUNING_PANEL_PATH
from unified_adaptive_search.agent_call import require_api_key

KNOBS = {
    "model": "openai/gpt-5.6-luna",
    "max_steps": 100,
    "reasoning_effort": "max",
    "web_search_depth": "high",
}
TIMEOUT = 600.0
PICK_RCIDS = [6631, 8898, 9799]  # Entendre Finance, Transcarent, EdgeMode

def main() -> None:
    require_api_key()
    panel = load_panel(TUNING_PANEL_PATH)
    by_rcid = {int(r["rcid"]): r for r in panel.get("companies") or []}
    picked = []
    for rcid in PICK_RCIDS:
        row = by_rcid[rcid]
        assert row.get("stratum") == "none", row
        picked.append(row)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = EVAL_RUNS_DIR / f"_max_none3_smoke_{stamp}_{uuid.uuid4().hex[:6]}"
    out.mkdir(parents=True, exist_ok=True)

    meta = {
        "kind": "max_none3_smoke",
        "knobs": KNOBS,
        "timeout_seconds": TIMEOUT,
        "note": "3 March-zero companies at max knobs; excludes 4D Sight (prior 400).",
        "companies": [
            {
                "rcid": r["rcid"],
                "name": r["name"],
                "stratum": r["stratum"],
                "march_findings": (r.get("march_reference") or {}).get("findings_count"),
            }
            for r in picked
        ],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("OUT", out, flush=True)
    print("KNOBS", KNOBS, flush=True)

    rows = []
    for row in picked:
        company = CompanyInput.from_mapping(row)
        print(f"START none rcid={company.rcid} {company.name}", flush=True)
        result = run_company(
            "unified-adaptive-search",
            company,
            dry_run=False,
            timeout=TIMEOUT,
            **KNOBS,
        )
        payload = result.to_dict()
        tu = (payload.get("traces") or {}).get("tool_use") or {}
        details = tu.get("tool_calls_details") or {}
        counts = tu.get("output_item_counts") or {}
        rec = {
            "stratum": row["stratum"],
            "rcid": company.rcid,
            "company_name": company.name,
            "march_findings": (row.get("march_reference") or {}).get("findings_count"),
            "max_steps_ceiling": KNOBS["max_steps"],
            "reasoning_effort": KNOBS["reasoning_effort"],
            "web_search_depth": KNOBS["web_search_depth"],
            "cost_usd": payload.get("cost_usd"),
            "findings_count": payload.get("findings_count")
            or len(payload.get("findings") or []),
            "duration_seconds": payload.get("duration_seconds"),
            "error": payload.get("error"),
            "search_web_invocations": details.get("search_web", details.get("web_search")),
            "fetch_url_invocations": details.get("fetch_url"),
            "tool_calls_cost_usd": tu.get("tool_calls_cost_usd"),
            "search_result_urls": tu.get("search_result_urls"),
            "tool_output_items": tu.get("tool_output_items"),
            "search_results_items": counts.get("search_results"),
            "fetch_url_results_items": counts.get("fetch_url_results"),
            "message_items": counts.get("message"),
            "input_tokens": (payload.get("traces") or {}).get("input_tokens"),
            "output_tokens": (payload.get("traces") or {}).get("output_tokens"),
            "response_status": (payload.get("traces") or {}).get("response_status"),
            "phase": (payload.get("traces") or {}).get("phase"),
            "tool_use": tu,
        }
        rows.append(rec)
        with (out / "calls.jsonl").open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(
            f"DONE  {company.name} cost={rec['cost_usd']} findings={rec['findings_count']} "
            f"search_web={rec['search_web_invocations']} fetch={rec['fetch_url_invocations']} "
            f"tools={rec['tool_output_items']} dur={rec['duration_seconds']} err={rec['error']}",
            flush=True,
        )

    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    summary = {
        "n": len(rows),
        "mean_cost_usd": round(sum(costs) / len(costs), 4) if costs else None,
        "min_cost_usd": round(min(costs), 4) if costs else None,
        "max_cost_usd": round(max(costs), 4) if costs else None,
        "mean_findings": round(
            sum(int(r["findings_count"] or 0) for r in rows) / len(rows), 4
        ),
        "n_errors": sum(1 for r in rows if r.get("error")),
        "mean_search_web": round(
            sum(int(r["search_web_invocations"] or 0) for r in rows) / len(rows), 2
        ),
        "mean_fetch_url": round(
            sum(int(r["fetch_url_invocations"] or 0) for r in rows) / len(rows), 2
        ),
        "mean_tool_output_items": round(
            sum(int(r["tool_output_items"] or 0) for r in rows) / len(rows), 2
        ),
        "knobs": KNOBS,
        "rows": [{k: v for k, v in r.items() if k != "tool_use"} for r in rows],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (out / "summary.csv").open("w", newline="") as f:
        cols = [k for k in rows[0] if k != "tool_use"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("SUMMARY", json.dumps({k: summary[k] for k in summary if k != "rows"}, indent=2), flush=True)
    print("OUT", out, flush=True)

if __name__ == "__main__":
    main()
