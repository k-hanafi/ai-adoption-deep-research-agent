"""Hill-climb panel invariants: 20 cos, strata, no tuning-holdout overlap."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.panel import load_panel, load_panel_companies
from evals.paths import HILLCLIMB_PANEL_PATH, TUNING_PANEL_PATH

EXPECTED_STRATA = {"high": 5, "medium": 5, "low": 5, "none": 5}
KNOWN_REGRESSION_IDS = {26492430, 1314132, 97943259, 103497}


def test_hillclimb_panel_membership() -> None:
    panel = load_panel(HILLCLIMB_PANEL_PATH)
    assert panel["panel_id"] == "hillclimb_pcs_v1_march_20"
    companies = panel["companies"]
    assert len(companies) == 20

    rcids = [int(c["rcid"]) for c in companies]
    assert len(set(rcids)) == 20
    assert KNOWN_REGRESSION_IDS <= set(rcids)

    counts = Counter(c["stratum"] for c in companies)
    assert dict(counts) == EXPECTED_STRATA

    holdout = {
        int(c["rcid"])
        for c in json.loads(Path(TUNING_PANEL_PATH).read_text(encoding="utf-8"))[
            "companies"
        ]
    }
    overlap = set(rcids) & holdout
    assert not overlap, f"hill-climb IDs in tuning holdout: {sorted(overlap)}"

    for c in companies:
        hp = (c.get("homepage_url") or "").strip().lower()
        assert hp.startswith("https://"), c["rcid"]
        n = int(c["march_reference"]["findings_count"])
        stratum = c["stratum"]
        if stratum == "none":
            assert n == 0
        elif stratum == "low":
            assert n == 1
        elif stratum == "medium":
            assert n == 2
        else:
            assert stratum == "high" and n >= 3

    # Loader ignores extra fields such as hillclimb_role / march_reference.
    loaded = load_panel_companies(HILLCLIMB_PANEL_PATH)
    assert [c.rcid for c in loaded] == rcids
