"""SGS skip panel: 50 cos, 40 none / 10 low, no overlap with blocked panels."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from evals.panel import load_panel, load_panel_companies
from evals.panel.build_sgs_skip_panel_v1 import SEED, build
from evals.paths import (
    HILLCLIMB_PANEL_PATH,
    PCS_CONFIRM_PANEL_PATH,
    SGS_SKIP_PANEL_PATH,
    TUNING_PANEL_PATH,
)

EXPECTED_STRATA = {"none": 40, "low": 10}


def test_sgs_skip_panel_membership() -> None:
    panel = load_panel(SGS_SKIP_PANEL_PATH)
    assert panel["panel_id"] == "sgs_skip_v1_march_50"
    assert panel["source"]["selection_seed"] == SEED
    companies = panel["companies"]
    assert len(companies) == 50

    rcids = [int(c["rcid"]) for c in companies]
    assert len(set(rcids)) == 50

    counts = Counter(c["stratum"] for c in companies)
    assert dict(counts) == EXPECTED_STRATA

    blocked: set[int] = set()
    for path in (TUNING_PANEL_PATH, HILLCLIMB_PANEL_PATH, PCS_CONFIRM_PANEL_PATH):
        blocked.update(
            int(c["rcid"])
            for c in json.loads(Path(path).read_text(encoding="utf-8"))["companies"]
        )
    overlap = set(rcids) & blocked
    assert not overlap, f"skip IDs in blocked panels: {sorted(overlap)}"
    assert 610194 not in rcids

    for company in companies:
        hp = (company.get("homepage_url") or "").strip().lower()
        assert hp.startswith("https://"), company["rcid"]
        n = int(company["march_reference"]["findings_count"])
        stratum = company["stratum"]
        if stratum == "none":
            assert n == 0
        else:
            assert stratum == "low" and n == 1
        assert company.get("skip_role")

    loaded = load_panel_companies(SGS_SKIP_PANEL_PATH)
    assert [c.rcid for c in loaded] == rcids


def test_sgs_skip_builder_is_deterministic() -> None:
    first = [int(c["rcid"]) for c in build()["companies"]]
    second = [int(c["rcid"]) for c in build()["companies"]]
    on_disk = [
        int(c["rcid"])
        for c in json.loads(SGS_SKIP_PANEL_PATH.read_text(encoding="utf-8"))[
            "companies"
        ]
    ]
    assert first == second == on_disk
