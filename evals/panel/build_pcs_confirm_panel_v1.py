"""Build pcs_confirm_panel.json: 20 unused March companies for a PCS high check.

Seeded stratified sample. Soft March refs only. Disjoint from tuning-50 and
the hill-climb 20. Not a bake-off panel (bake-off still needs a later set).
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from evals.panel.build_tuning_panel_v2 import _row_from_march, _stratum

ROOT = Path(__file__).resolve().parents[2]
MARCH_JSONL = ROOT / "outputs" / "stage2" / "production_results.jsonl"
PANEL_DIR = Path(__file__).resolve().parent
TUNING_PATH = PANEL_DIR / "tuning_panel.json"
HILLCLIMB_PATH = PANEL_DIR / "hillclimb_panel.json"
OUT_PATH = PANEL_DIR / "pcs_confirm_panel.json"

SEED = 20260814
EXPECTED_STRATA = {"high": 5, "medium": 5, "low": 5, "none": 5}


def _blocked_ids() -> set[int]:
    blocked: set[int] = set()
    for path in (TUNING_PATH, HILLCLIMB_PATH):
        blocked.update(
            int(c["rcid"])
            for c in json.loads(path.read_text(encoding="utf-8")).get("companies")
            or []
        )
    return blocked


def _load_pools() -> dict[str, list[dict[str, Any]]]:
    blocked = _blocked_ids()
    pools: dict[str, list[dict[str, Any]]] = {
        "high": [],
        "medium": [],
        "low": [],
        "none": [],
    }
    with MARCH_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rcid = int(row["rcid"])
            if rcid in blocked:
                continue
            hp = (row.get("homepage_url") or "").strip()
            if not hp.lower().startswith("https://"):
                continue
            built = _row_from_march(row)
            if built["stratum"] != _stratum(
                int(built["march_reference"]["findings_count"])
            ):
                raise RuntimeError(f"stratum mismatch for rcid {rcid}")
            pools[built["stratum"]].append(built)
    return pools


def _sample(
    rng: random.Random,
    pool: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    ordered = sorted(pool, key=lambda c: int(c["rcid"]))
    if len(ordered) < k:
        raise RuntimeError(f"pool size {len(ordered)} < {k}")
    return rng.sample(ordered, k)


def _channels(company: dict[str, Any]) -> list[str]:
    return list((company.get("march_reference") or {}).get("channels") or [])


def _pick_labeled(
    rng: random.Random,
    pool: list[dict[str, Any]],
    spec: list[tuple[str, Callable[[dict[str, Any]], bool], int]],
) -> list[dict[str, Any]]:
    used: set[int] = set()
    chosen: list[dict[str, Any]] = []
    for role, predicate, count in spec:
        bucket = [
            c
            for c in pool
            if int(c["rcid"]) not in used and predicate(c)
        ]
        for company in _sample(rng, bucket, count):
            row = dict(company)
            row["confirm_role"] = role
            chosen.append(row)
            used.add(int(row["rcid"]))
    return chosen


def build() -> dict[str, Any]:
    rng = random.Random(SEED)
    pools = _load_pools()

    companies: list[dict[str, Any]] = []
    for stratum in ("high", "medium"):
        companies.extend(
            _pick_labeled(
                rng,
                pools[stratum],
                [
                    ("march_jobs_only", lambda c: _channels(c) == ["jobs"], 1),
                    ("march_owned_only", lambda c: _channels(c) == ["owned"], 1),
                    (
                        "march_third_party_only",
                        lambda c: _channels(c) == ["third_party"],
                        1,
                    ),
                    ("march_mixed_channels", lambda c: len(_channels(c)) >= 2, 1),
                    ("march_stratum_fill", lambda _c: True, 1),
                ],
            )
        )
    companies.extend(
        _pick_labeled(
            rng,
            pools["low"],
            [
                ("march_jobs_only", lambda c: _channels(c) == ["jobs"], 2),
                ("march_owned_only", lambda c: _channels(c) == ["owned"], 2),
                (
                    "march_third_party_only",
                    lambda c: _channels(c) == ["third_party"],
                    1,
                ),
            ],
        )
    )
    companies.extend(
        _pick_labeled(
            rng,
            pools["none"],
            [("march_none", lambda _c: True, 5)],
        )
    )

    if len({int(c["rcid"]) for c in companies}) != 20:
        raise RuntimeError("confirm panel must have 20 unique rcids")

    counts = Counter(c["stratum"] for c in companies)
    if dict(counts) != EXPECTED_STRATA:
        raise RuntimeError(f"strata {dict(counts)} != {EXPECTED_STRATA}")

    blocked = _blocked_ids()
    overlap = sorted({int(c["rcid"]) for c in companies} & blocked)
    if overlap:
        raise RuntimeError(f"confirm IDs overlap blocked panels: {overlap}")

    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    companies.sort(
        key=lambda c: (
            order[c["stratum"]],
            -int(c["march_reference"]["findings_count"]),
            int(c["rcid"]),
        )
    )

    return {
        "panel_id": "pcs_confirm_v1_march_20",
        "reference_kind": "soft",
        "note": (
            "PCS high confirmation panel. Twenty unused March Stage 2 companies: "
            "5 high + 5 medium + 5 low + 5 none. Seeded sample "
            f"(seed={SEED}) with a March-channel mix inside each positive "
            "stratum. Soft march_reference only. Disjoint from tuning_panel_v2 "
            "and hillclimb_pcs_v1_march_20. Not a bake-off panel. Bake-off "
            "still needs a later disjoint set."
        ),
        "source": {
            "march_run": "outputs/stage2/production_results.jsonl",
            "selection_axis": "march_findings_count_plus_channel_mix",
            "selection_seed": SEED,
            "population": (
                "Stage 2 companies excluding tuning_panel_v2 and "
                "hillclimb_pcs_v1_march_20"
            ),
            "strata_cutpoints": {
                "none": {"min_findings_count": 0, "max_findings_count": 0},
                "low": {"min_findings_count": 1, "max_findings_count": 1},
                "medium": {"min_findings_count": 2, "max_findings_count": 2},
                "high": {"min_findings_count": 3, "max_findings_count": None},
            },
            "strata_targets": EXPECTED_STRATA,
            "channel_mapping": (
                "Soft-mapped from March finding source_type strings into "
                "owned | jobs | third_party for sampling mix only. Same helper "
                "as evals/panel/build_tuning_panel_v2.py."
            ),
        },
        "companies": companies,
    }


def main() -> None:
    panel = build()
    OUT_PATH.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8")
    counts = Counter(c["stratum"] for c in panel["companies"])
    print(f"Wrote {OUT_PATH} panel_id={panel['panel_id']} n={len(panel['companies'])}")
    print("strata:", dict(counts))
    for company in panel["companies"]:
        print(
            f"  {company['stratum']:6} {company['rcid']:10} "
            f"{company['name'][:28]:28} "
            f"{company['confirm_role']:24} "
            f"march={company['march_reference']['findings_count']} "
            f"ch={company['march_reference']['channels']}"
        )


if __name__ == "__main__":
    main()
