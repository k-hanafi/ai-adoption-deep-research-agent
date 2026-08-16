"""Build tuning_panel.json v2: 50 March companies with richness + none bins.

Keeps v1's 15 positives, expands high/medium/low, and adds a March
zero-findings bin. Soft references only. Held out from bake-off forever.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from evals.paths import MARCH_STAGE2_JSONL

MARCH_JSONL = MARCH_STAGE2_JSONL
OUT_PATH = Path(__file__).resolve().parent / "tuning_panel.json"

# Target: 50 total. Keep v1 15; fill to these counts.
TARGET = {"high": 12, "medium": 12, "low": 12, "none": 14}
assert sum(TARGET.values()) == 50


def _channel(source_type: str) -> str:
    s = (source_type or "").lower()
    if any(k in s for k in ("job", "career", "greenhouse", "lever", "ashby", "workday")):
        return "jobs"
    if any(
        k in s
        for k in (
            "company",
            "blog",
            "engineering",
            "press release",
            "about",
            "docs",
            "documentation",
            "changelog",
            "github",
        )
    ):
        return "owned"
    return "third_party"


def _stratum(findings_count: int) -> str:
    if findings_count <= 0:
        return "none"
    if findings_count == 1:
        return "low"
    if findings_count == 2:
        return "medium"
    return "high"


def _row_from_march(r: dict[str, Any]) -> dict[str, Any]:
    findings = r.get("findings") or []
    # Prefer explicit findings_count, including 0. Do not use `or len(findings)`
    # because 0 is falsy and would mis-bin zeros that still have a findings list.
    raw_count = r.get("findings_count")
    if raw_count is None:
        n = len(findings)
    else:
        n = int(raw_count)
    tools: list[str] = []
    channels: list[str] = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        tool = f.get("AI_tool_used")
        if tool and tool not in tools:
            tools.append(str(tool))
        ch = _channel(str(f.get("source_type") or ""))
        if ch not in channels:
            channels.append(ch)
    pri = r.get("priority")
    try:
        pri_i = int(pri) if pri is not None else 0
    except (TypeError, ValueError):
        pri_i = 0
    return {
        "rcid": int(r["rcid"]),
        "name": r.get("company_name") or r.get("name") or f"rcid_{r['rcid']}",
        "homepage_url": r.get("homepage_url"),
        "short_description": r.get("short_description"),
        "research_priority_score": pri_i,
        "online_presence_score": int(r.get("online_presence_score") or 0),
        "category_list": r.get("category_list"),
        "stratum": _stratum(n),
        "march_reference": {
            "reference_kind": "soft",
            "findings_count": n,
            "tools": tools,
            "channels": channels,
            "cost_usd": r.get("cost_usd"),
        },
    }


def build() -> dict[str, Any]:
    existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    keep = list(existing.get("companies") or [])
    keep_ids = {int(c["rcid"]) for c in keep}
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in keep:
        by_stratum[c["stratum"]].append(c)

    # Pool new candidates from March (exclude already kept).
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with MARCH_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rcid = int(r["rcid"])
            if rcid in keep_ids:
                continue
            if not r.get("homepage_url"):
                continue
            row = _row_from_march(r)
            pools[row["stratum"]].append(row)

    def sort_key(row: dict[str, Any]) -> tuple:
        ref = row["march_reference"]
        # Prefer richer highs, P4/P5, then stable rcid.
        return (
            -int(ref.get("findings_count") or 0),
            -int(row.get("research_priority_score") or 0),
            int(row["rcid"]),
        )

    for s in pools:
        pools[s].sort(key=sort_key)

    # Force Jam in high if somehow missing.
    if not any(int(c["rcid"]) == 610194 for c in by_stratum["high"]):
        raise RuntimeError("Jam (610194) missing from kept high stratum")

    companies: list[dict[str, Any]] = []
    for stratum, need in TARGET.items():
        have = list(by_stratum.get(stratum) or [])
        # Diversify secondary: alternate P5 then P4 when adding.
        added: list[dict[str, Any]] = []
        for row in pools.get(stratum) or []:
            if len(have) + len(added) >= need:
                break
            added.append(row)
        chosen = have + added
        if len(chosen) < need:
            raise RuntimeError(
                f"stratum {stratum}: only {len(chosen)} companies, need {need}"
            )
        companies.extend(chosen[:need])

    if len(companies) != 50:
        raise RuntimeError(f"expected 50 companies, got {len(companies)}")

    # Stable order: high → medium → low → none, then -findings, rcid.
    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    companies.sort(
        key=lambda c: (
            order[c["stratum"]],
            -int(c["march_reference"]["findings_count"]),
            int(c["rcid"]),
        )
    )

    return {
        "panel_id": "tuning_panel_v2_march_50_richness_plus_none",
        "reference_kind": "soft",
        "note": (
            "Held-out UAS Stage A tuning panel (v2). Fifty March Stage 2 companies: "
            "12 high + 12 medium + 12 low positives by findings richness, plus 14 "
            "March zero-finding companies (stratum=none). Soft march_reference only. "
            "Includes all v1 panel IDs. NEVER reuse these company IDs for bake-off / "
            "Phase 3 paired evals."
        ),
        "source": {
            "march_run": "evals/references/march_2026_production.jsonl",
            "selection_axis": "march_findings_count",
            "population": "Stage 2 companies (positives + zeros)",
            "population_size_positives": 1251,
            "population_size_zeros": 8221,
            "strata_cutpoints": {
                "none": {"min_findings_count": 0, "max_findings_count": 0},
                "low": {"min_findings_count": 1, "max_findings_count": 1},
                "medium": {"min_findings_count": 2, "max_findings_count": 2},
                "high": {"min_findings_count": 3, "max_findings_count": None},
            },
            "strata_targets": TARGET,
            "strata_cutpoints_note": (
                "Same richness bins as v1 for positives; added none=0. "
                "v1's 15 IDs retained; filled from March with homepage_url. "
                "Jam (rcid 610194) remains in high."
            ),
            "channel_mapping": (
                "Soft-mapped from March finding source_type strings into "
                "owned | jobs | third_party for reference only."
            ),
        },
        "companies": companies,
    }


def main() -> None:
    panel = build()
    OUT_PATH.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8")
    from collections import Counter

    counts = Counter(c["stratum"] for c in panel["companies"])
    print(f"Wrote {OUT_PATH} panel_id={panel['panel_id']} n={len(panel['companies'])}")
    print("strata:", dict(counts))


if __name__ == "__main__":
    main()
