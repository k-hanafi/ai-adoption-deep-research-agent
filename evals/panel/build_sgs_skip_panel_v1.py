"""Build sgs_skip_panel.json: 50 unused March none/low companies.

Seeded sample. Soft March refs only. Disjoint from tuning-50, hill-climb 20,
and the PCS confirm 20. Not a bake-off panel. Measures whether SGS existence
scouts skip rooms on companies March already scored none or low.
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
CONFIRM_PATH = PANEL_DIR / "pcs_confirm_panel.json"
OUT_PATH = PANEL_DIR / "sgs_skip_panel.json"

SEED = 20260815
EXPECTED_STRATA = {"none": 40, "low": 10}


def _blocked_ids() -> set[int]:
    blocked: set[int] = set()
    for path in (TUNING_PATH, HILLCLIMB_PATH, CONFIRM_PATH):
        blocked.update(
            int(c["rcid"])
            for c in json.loads(path.read_text(encoding="utf-8")).get("companies")
            or []
        )
    return blocked


def _load_pools() -> dict[str, list[dict[str, Any]]]:
    blocked = _blocked_ids()
    pools: dict[str, list[dict[str, Any]]] = {"low": [], "none": []}
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
            if built["stratum"] not in pools:
                continue
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
            row["skip_role"] = role
            chosen.append(row)
            used.add(int(row["rcid"]))
    return chosen


def build() -> dict[str, Any]:
    rng = random.Random(SEED)
    pools = _load_pools()

    companies: list[dict[str, Any]] = []
    companies.extend(
        _pick_labeled(
            rng,
            pools["none"],
            [("march_none", lambda _c: True, 40)],
        )
    )
    companies.extend(
        _pick_labeled(
            rng,
            pools["low"],
            [
                ("march_jobs_only", lambda c: _channels(c) == ["jobs"], 3),
                ("march_owned_only", lambda c: _channels(c) == ["owned"], 3),
                (
                    "march_third_party_only",
                    lambda c: _channels(c) == ["third_party"],
                    2,
                ),
                ("march_stratum_fill", lambda _c: True, 2),
            ],
        )
    )

    if len({int(c["rcid"]) for c in companies}) != 50:
        raise RuntimeError("skip panel must have 50 unique rcids")

    counts = Counter(c["stratum"] for c in companies)
    if dict(counts) != EXPECTED_STRATA:
        raise RuntimeError(f"strata {dict(counts)} != {EXPECTED_STRATA}")

    blocked = _blocked_ids()
    overlap = sorted({int(c["rcid"]) for c in companies} & blocked)
    if overlap:
        raise RuntimeError(f"skip IDs overlap blocked panels: {overlap}")

    order = {"low": 0, "none": 1}
    companies.sort(
        key=lambda c: (
            order[c["stratum"]],
            -int(c["march_reference"]["findings_count"]),
            int(c["rcid"]),
        )
    )

    return {
        "panel_id": "sgs_skip_v1_march_50",
        "reference_kind": "soft",
        "note": (
            "SGS skip-rate panel. Fifty unused March Stage 2 companies: "
            "40 none + 10 low. Seeded sample "
            f"(seed={SEED}) with a March-channel mix inside low. Soft "
            "march_reference only. Disjoint from tuning_panel_v2, "
            "hillclimb_pcs_v1_march_20, and pcs_confirm_v1_march_20. Not a "
            "bake-off panel. Bake-off still needs a later disjoint set. This "
            "panel measures whether existence scouts skip rooms on March "
            "none/low companies."
        ),
        "source": {
            "march_run": "outputs/stage2/production_results.jsonl",
            "selection_axis": "march_none_low_plus_low_channel_mix",
            "selection_seed": SEED,
            "population": (
                "Stage 2 companies excluding tuning_panel_v2, "
                "hillclimb_pcs_v1_march_20, and pcs_confirm_v1_march_20"
            ),
            "strata_cutpoints": {
                "none": {"min_findings_count": 0, "max_findings_count": 0},
                "low": {"min_findings_count": 1, "max_findings_count": 1},
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
            f"{company['skip_role']:24} "
            f"march={company['march_reference']['findings_count']} "
            f"ch={company['march_reference']['channels']}"
        )


if __name__ == "__main__":
    main()
