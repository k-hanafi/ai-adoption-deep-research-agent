"""Paid cost smokes to size UAS knob ranges before the full Stage A matrix.

Runs a small mixed company sample across OFAT highs + an API-max corner.
Writes a summary under evals/runs/_cost_diagnose_<stamp>/ for evidence-based
range locking (target: richest configs can approach ~$0.10/company).
"""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from contracts.types import CompanyInput
from evals.architectures import run_company
from evals.paths import EVAL_RUNS_DIR, MARCH_STAGE2_JSONL, TUNING_PANEL_PATH
from evals.panel import load_panel


@dataclass(frozen=True)
class SmokeConfig:
    config_id: str
    label: str
    max_steps: int
    reasoning_effort: str
    web_search_depth: str

    def runner_kwargs(self) -> dict[str, Any]:
        return {
            "model": "openai/gpt-5.6-luna",
            "max_steps": self.max_steps,
            "reasoning_effort": self.reasoning_effort,
            "web_search_depth": self.web_search_depth,
        }


# Sparse ladder: baseline, each axis high/API-max, plus full corner.
SMOKE_CONFIGS: list[SmokeConfig] = [
    SmokeConfig("baseline", "Baseline (10 / medium / search low)", 10, "medium", "low"),
    SmokeConfig("steps_50", "max_steps=50", 50, "medium", "low"),
    SmokeConfig("steps_100", "max_steps=100 (API max)", 100, "medium", "low"),
    SmokeConfig("effort_xhigh", "reasoning.effort=xhigh", 10, "xhigh", "low"),
    SmokeConfig("effort_max", "reasoning.effort=max", 10, "max", "low"),
    SmokeConfig("search_medium", "search package=medium", 10, "medium", "medium"),
    SmokeConfig("search_high", "search package=high", 10, "medium", "high"),
    SmokeConfig(
        "api_max_corner",
        "API max corner (steps 100 / effort max / search high)",
        100,
        "max",
        "high",
    ),
]


def _company_from_panel_row(row: dict[str, Any]) -> CompanyInput:
    return CompanyInput.from_mapping(row)


def default_smoke_companies(
    *,
    march_jsonl: Path = MARCH_STAGE2_JSONL,
    panel_path: Path = TUNING_PANEL_PATH,
) -> list[CompanyInput]:
    """1 high + 1 medium + 1 low from tuning panel, plus 2 March zero-finding firms."""
    march_jsonl = Path(march_jsonl)
    if not march_jsonl.is_file():
        raise FileNotFoundError(
            f"March Stage 2 JSONL not found: {march_jsonl} "
            "(expected under the repo outputs/ tree)"
        )
    panel = load_panel(panel_path)
    by_stratum: dict[str, list[dict[str, Any]]] = {"high": [], "medium": [], "low": []}
    for row in panel.get("companies") or []:
        s = row.get("stratum")
        if s in by_stratum:
            by_stratum[s].append(row)

    picked: list[dict[str, Any]] = []
    for s in ("high", "medium", "low"):
        if not by_stratum[s]:
            raise ValueError(f"tuning panel missing stratum {s!r}")
        # Prefer Jam in high when present.
        if s == "high":
            jam = next((r for r in by_stratum[s] if int(r["rcid"]) == 610194), None)
            picked.append(jam or by_stratum[s][0])
        else:
            picked.append(by_stratum[s][0])

    panel_ids = {int(r["rcid"]) for r in (panel.get("companies") or [])}
    zeros: list[dict[str, Any]] = []
    with march_jsonl.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if int(r.get("findings_count") or 0) != 0:
                continue
            rcid = int(r["rcid"])
            if rcid in panel_ids:
                continue
            if not r.get("homepage_url"):
                continue
            # Prefer P4/P5 when priority is present.
            pri = r.get("priority")
            try:
                pri_i = int(pri) if pri is not None else 0
            except (TypeError, ValueError):
                pri_i = 0
            zeros.append(
                {
                    "rcid": rcid,
                    "name": r.get("company_name") or r.get("name") or f"rcid_{rcid}",
                    "homepage_url": r.get("homepage_url"),
                    "short_description": r.get("short_description"),
                    "research_priority_score": pri_i,
                    "online_presence_score": int(r.get("online_presence_score") or 0),
                    "stratum": "none",
                    "_pri": pri_i,
                }
            )
    zeros.sort(key=lambda z: (-z["_pri"], z["rcid"]))
    if len(zeros) < 2:
        raise ValueError("need at least 2 March zero-finding companies with URLs")
    for z in zeros[:2]:
        z.pop("_pri", None)
        picked.append(z)

    return [_company_from_panel_row(r) for r in picked]


def run_cost_diagnose(
    *,
    dry_run: bool = True,
    companies: Optional[list[CompanyInput]] = None,
    configs: Optional[list[SmokeConfig]] = None,
) -> Path:
    """Run smoke configs × companies; return artifact directory."""
    companies = companies or default_smoke_companies()
    configs = configs or list(SMOKE_CONFIGS)
    if not companies:
        raise ValueError("companies must be non-empty")
    if not configs:
        raise ValueError("configs must be non-empty")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = EVAL_RUNS_DIR / f"_cost_diagnose_{stamp}_{uuid.uuid4().hex[:6]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "kind": "cost_diagnose",
        "dry_run": dry_run,
        "n_companies": len(companies),
        "n_configs": len(configs),
        "n_calls_planned": len(companies) * len(configs),
        "companies": [
            {"rcid": c.rcid, "name": c.name, "homepage_url": c.homepage_url}
            for c in companies
        ],
        "configs": [
            {
                "config_id": cfg.config_id,
                "label": cfg.label,
                **cfg.runner_kwargs(),
            }
            for cfg in configs
        ],
        "target_note": (
            "Use mean $/company by config to lock Stage A ranges so the "
            "richest feasible corner can approach ~$0.10/company."
        ),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    rows: list[dict[str, Any]] = []
    for cfg in configs:
        for company in companies:
            result = run_company(
                "unified-adaptive-search",
                company,
                dry_run=dry_run,
                **cfg.runner_kwargs(),
            )
            payload = result.to_dict()
            traces = payload.get("traces") or {}
            tool_use = traces.get("tool_use") or {}
            details = tool_use.get("tool_calls_details") or {}
            counts = tool_use.get("output_item_counts") or {}
            # API meter key is search_web; tool type in request is web_search.
            search_inv = details.get("search_web", details.get("web_search"))
            row = {
                "config_id": cfg.config_id,
                "label": cfg.label,
                "rcid": company.rcid,
                "company_name": company.name,
                "max_steps": cfg.max_steps,
                "reasoning_effort": cfg.reasoning_effort,
                "web_search_depth": cfg.web_search_depth,
                "cost_usd": payload.get("cost_usd"),
                "findings_count": payload.get("findings_count")
                or len(payload.get("findings") or []),
                "error": payload.get("error"),
                "duration_seconds": payload.get("duration_seconds"),
                "dry_run": dry_run,
                "web_search_invocations": search_inv,
                "fetch_url_invocations": details.get("fetch_url"),
                "tool_calls_cost_usd": tool_use.get("tool_calls_cost_usd"),
                "search_result_urls": tool_use.get("search_result_urls"),
                "tool_output_items": tool_use.get("tool_output_items"),
                "search_results_items": counts.get("search_results"),
                "fetch_url_results_items": counts.get("fetch_url_results"),
            }
            rows.append(row)
            # Append-friendly crash trail.
            with (out_dir / "calls.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    _write_summary(out_dir, rows, dry_run=dry_run)
    return out_dir


def _write_summary(out_dir: Path, rows: list[dict[str, Any]], *, dry_run: bool) -> None:
    by_cfg: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cfg.setdefault(row["config_id"], []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for cfg_id, group in by_cfg.items():
        costs = [float(r["cost_usd"]) for r in group if r.get("cost_usd") is not None]
        findings = [int(r["findings_count"] or 0) for r in group]
        errors = sum(1 for r in group if r.get("error"))
        mean_cost = sum(costs) / len(costs) if costs else None
        summary_rows.append(
            {
                "config_id": cfg_id,
                "label": group[0]["label"],
                "max_steps": group[0]["max_steps"],
                "reasoning_effort": group[0]["reasoning_effort"],
                "web_search_depth": group[0]["web_search_depth"],
                "n": len(group),
                "n_costed": len(costs),
                "errors": errors,
                "mean_cost_usd": round(mean_cost, 4) if mean_cost is not None else None,
                "min_cost_usd": round(min(costs), 4) if costs else None,
                "max_cost_usd": round(max(costs), 4) if costs else None,
                "mean_findings": round(sum(findings) / len(findings), 4) if findings else None,
                "near_10c": bool(mean_cost is not None and mean_cost >= 0.08),
            }
        )

    summary_rows.sort(key=lambda r: (r["mean_cost_usd"] is None, r["mean_cost_usd"] or 0.0))
    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "dry_run": dry_run,
                "n_calls": len(rows),
                "configs": summary_rows,
                "decision_rule": {
                    "api_max_corner_mean_ge_0.08": "ranges tall enough; include API max in Stage A high end",
                    "api_max_corner_mean_lt_0.04": "even API max is cheap; lock high end at API max and expect UAS under 10c unless multi-call",
                    "between": "raise high end toward API max for the axis that still has headroom",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (out_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "config_id",
                "label",
                "max_steps",
                "reasoning_effort",
                "web_search_depth",
                "n",
                "n_costed",
                "errors",
                "mean_cost_usd",
                "min_cost_usd",
                "max_cost_usd",
                "mean_findings",
                "near_10c",
            ],
        )
        w.writeheader()
        w.writerows(summary_rows)

    with (out_dir / "calls.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            w.writeheader()
            w.writerows(rows)
