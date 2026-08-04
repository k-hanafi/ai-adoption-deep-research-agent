"""Anchor Panel loaders (fixture until v1 membership is frozen)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.types import CompanyInput
from evals.paths import FIXTURE_PANEL_PATH


def load_panel(panel_path: Path | None = None) -> dict[str, Any]:
    path = panel_path or FIXTURE_PANEL_PATH
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_panel_companies(panel_path: Path | None = None) -> list[CompanyInput]:
    panel = load_panel(panel_path)
    # JSON null for "companies" makes dict.get return None, not the default.
    companies = panel.get("companies") or []
    if not isinstance(companies, list):
        raise ValueError(
            f"Panel companies must be a list, got {type(companies).__name__}"
        )
    return [CompanyInput.from_mapping(row) for row in companies]
