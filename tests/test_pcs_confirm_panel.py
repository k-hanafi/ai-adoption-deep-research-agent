"""PCS confirm panel: 20 cos, strata, no overlap with tuning or hill-climb."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.panel import load_panel, load_panel_companies
from evals.panel.build_pcs_confirm_panel_v1 import SEED, build
from evals.paths import (
    HILLCLIMB_PANEL_PATH,
    PCS_CONFIRM_PANEL_PATH,
    TUNING_PANEL_PATH,
)

EXPECTED_STRATA = {"high": 5, "medium": 5, "low": 5, "none": 5}


def test_pcs_confirm_panel_membership() -> None:
    panel = load_panel(PCS_CONFIRM_PANEL_PATH)
    assert panel["panel_id"] == "pcs_confirm_v1_march_20"
    assert panel["source"]["selection_seed"] == SEED
    companies = panel["companies"]
    assert len(companies) == 20

    rcids = [int(c["rcid"]) for c in companies]
    assert len(set(rcids)) == 20

    counts = Counter(c["stratum"] for c in companies)
    assert dict(counts) == EXPECTED_STRATA

    blocked: set[int] = set()
    for path in (TUNING_PANEL_PATH, HILLCLIMB_PANEL_PATH):
        blocked.update(
            int(c["rcid"])
            for c in json.loads(Path(path).read_text(encoding="utf-8"))["companies"]
        )
    overlap = set(rcids) & blocked
    assert not overlap, f"confirm IDs in blocked panels: {sorted(overlap)}"
    assert 610194 not in rcids

    for company in companies:
        hp = (company.get("homepage_url") or "").strip().lower()
        assert hp.startswith("https://"), company["rcid"]
        n = int(company["march_reference"]["findings_count"])
        stratum = company["stratum"]
        if stratum == "none":
            assert n == 0
        elif stratum == "low":
            assert n == 1
        elif stratum == "medium":
            assert n == 2
        else:
            assert stratum == "high" and n >= 3
        assert company.get("confirm_role")

    loaded = load_panel_companies(PCS_CONFIRM_PANEL_PATH)
    assert [c.rcid for c in loaded] == rcids


def test_pcs_confirm_builder_is_deterministic() -> None:
    first = [int(c["rcid"]) for c in build()["companies"]]
    second = [int(c["rcid"]) for c in build()["companies"]]
    on_disk = [
        int(c["rcid"])
        for c in json.loads(PCS_CONFIRM_PANEL_PATH.read_text(encoding="utf-8"))[
            "companies"
        ]
    ]
    assert first == second == on_disk
