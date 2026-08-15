"""Build hillclimb_panel.json v1: 20 March companies for PCS (then SGS/UAS) hill-climb.

Frozen membership. Soft March refs only. Disjoint from the tuning-50 holdout.
Not a bake-off panel. Regenerate after swapping IDs in MEMBERSHIP.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals.panel.build_tuning_panel_v2 import _row_from_march, _stratum

ROOT = Path(__file__).resolve().parents[2]
MARCH_JSONL = ROOT / "outputs" / "stage2" / "production_results.jsonl"
TUNING_PATH = Path(__file__).resolve().parent / "tuning_panel.json"
OUT_PATH = Path(__file__).resolve().parent / "hillclimb_panel.json"

# (rcid, hillclimb_role). Order is documentary; output is sorted high→none.
MEMBERSHIP: list[tuple[int, str]] = [
    # high (3+)
    (26492430, "company_youtube_mapped_owned"),  # Tern Travel
    (510536, "ats_jobs_plus_company_youtube"),  # Chainguard
    (545293, "dense_owned_plus_noisy_third_party"),  # ClickHouse
    (95038033, "owned_product_plus_yc_jobs"),  # Alguna
    (977674, "ashby_jobs_plus_owned_blog"),  # Vendelux
    # medium (2)
    (103497, "owned_blog_plus_vendor_case_study"),  # Statsig
    (169806, "podcast_plus_owned_blog"),  # Unwrap.ai
    (230528, "help_center_product_ai_plus_lever_jobs"),  # Secureframe
    (6353965, "aggregator_jobs_pair"),  # SQOR
    (96807077, "owned_podcast_transcripts"),  # Blue Sky Robotics
    # low (1)
    (1314132, "jobs_aggregator_may_404"),  # CoverTree
    (726354, "clean_ashby_jobs"),  # LiveKit
    (21573684, "vendor_case_study"),  # K1x
    (95170103, "third_party_youtube_interview"),  # Momentic
    (743085, "linkedin_embedded_on_owned_site"),  # Sudozi
    # none (0)
    (97943259, "ai_product_seller"),  # Easy Fill AI
    (94779671, "ai_agents_seller_hard_negative"),  # Sully.ai
    (42877, "saas_no_genai_found"),  # RightRev
    (5396108, "non_ai_industrial"),  # Oso Electric Equipment
    (43778, "non_ai_insurance"),  # Ahoy Insurance
]

EXPECTED_STRATA = {"high": 5, "medium": 5, "low": 5, "none": 5}


def build() -> dict[str, Any]:
    want = {rcid: role for rcid, role in MEMBERSHIP}
    if len(want) != 20:
        raise RuntimeError(f"MEMBERSHIP must have 20 unique rcids, got {len(want)}")

    holdout = {
        int(c["rcid"])
        for c in json.loads(TUNING_PATH.read_text(encoding="utf-8")).get("companies")
        or []
    }
    overlap = sorted(want.keys() & holdout)
    if overlap:
        raise RuntimeError(f"hill-climb IDs overlap tuning holdout: {overlap}")

    found: dict[int, dict[str, Any]] = {}
    with MARCH_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            rcid = int(r["rcid"])
            if rcid not in want:
                continue
            row = _row_from_march(r)
            hp = (row.get("homepage_url") or "").strip()
            if not hp.lower().startswith("https://"):
                raise RuntimeError(f"rcid {rcid} homepage is not https: {hp!r}")
            row["hillclimb_role"] = want[rcid]
            found[rcid] = row

    missing = sorted(want.keys() - found.keys())
    if missing:
        raise RuntimeError(f"rcids missing from March dump: {missing}")

    companies = [found[rcid] for rcid, _ in MEMBERSHIP]
    counts = Counter(c["stratum"] for c in companies)
    if dict(counts) != EXPECTED_STRATA:
        raise RuntimeError(f"strata {dict(counts)} != {EXPECTED_STRATA}")

    for c in companies:
        expected = _stratum(int(c["march_reference"]["findings_count"]))
        if c["stratum"] != expected:
            raise RuntimeError(
                f"rcid {c['rcid']} stratum {c['stratum']} != count bin {expected}"
            )

    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    companies.sort(
        key=lambda c: (
            order[c["stratum"]],
            -int(c["march_reference"]["findings_count"]),
            int(c["rcid"]),
        )
    )

    return {
        "panel_id": "hillclimb_pcs_v1_march_20",
        "reference_kind": "soft",
        "note": (
            "PCS (then SGS/UAS) hill-climb panel. Twenty March Stage 2 companies: "
            "5 high + 5 medium + 5 low + 5 none. Soft march_reference only. "
            "Disjoint from tuning_panel_v2 (held out forever). Not a bake-off panel. "
            "Hill-climb until failure modes are exposed and fixed; bake-off only after "
            "the user is happy on this set. Channel map matches tuning v2 "
            "(jobs vs owned vs third_party from source_type)."
        ),
        "source": {
            "march_run": "outputs/stage2/production_results.jsonl",
            "selection_axis": "march_findings_count_plus_channel_failure_modes",
            "population": "Stage 2 companies excluding tuning_panel_v2 holdout",
            "strata_cutpoints": {
                "none": {"min_findings_count": 0, "max_findings_count": 0},
                "low": {"min_findings_count": 1, "max_findings_count": 1},
                "medium": {"min_findings_count": 2, "max_findings_count": 2},
                "high": {"min_findings_count": 3, "max_findings_count": None},
            },
            "strata_targets": EXPECTED_STRATA,
            "channel_mapping": (
                "Soft-mapped from March finding source_type strings into "
                "owned | jobs | third_party for reference only. Same helper as "
                "evals/panel/build_tuning_panel_v2.py."
            ),
            "known_regression_ids": [26492430, 1314132, 97943259, 103497],
        },
        "companies": companies,
    }


def main() -> None:
    panel = build()
    OUT_PATH.write_text(json.dumps(panel, indent=2) + "\n", encoding="utf-8")
    counts = Counter(c["stratum"] for c in panel["companies"])
    print(f"Wrote {OUT_PATH} panel_id={panel['panel_id']} n={len(panel['companies'])}")
    print("strata:", dict(counts))


if __name__ == "__main__":
    main()
