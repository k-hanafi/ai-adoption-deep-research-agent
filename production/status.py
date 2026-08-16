"""Print done / remaining / errors / spend / next rcids for one architecture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from production.persist import (
    is_complete_success,
    is_runnable,
    load_payload,
    prod_paths,
    sum_recorded_spend,
)


@dataclass(frozen=True)
class StatusReport:
    architecture: str
    dataset: Path
    dataset_count: int
    done: int
    remaining: int
    errors: int
    spend_usd: float
    next_rcids: list[int]
    next_limit: int

    def format(self) -> str:
        next_text = ", ".join(str(rcid) for rcid in self.next_rcids) or "(none)"
        return (
            f"architecture: {self.architecture}\n"
            f"dataset: {self.dataset} ({self.dataset_count} companies)\n"
            f"done: {self.done}\n"
            f"remaining: {self.remaining}\n"
            f"errors: {self.errors}\n"
            f"spend: ${self.spend_usd:.4f}\n"
            f"next (--limit {self.next_limit}): {next_text}\n"
        )


def collect_status(
    companies: list[dict[str, Any]],
    *,
    architecture: str,
    output_root: Path,
    dataset: Path,
    limit: int = 10,
) -> StatusReport:
    paths = prod_paths(output_root, architecture)
    done = 0
    errors = 0
    remaining_rows: list[dict[str, Any]] = []
    next_rows: list[dict[str, Any]] = []
    for row in companies:
        payload = load_payload(paths.company_json(int(row["rcid"])))
        if is_complete_success(payload):
            done += 1
            continue
        remaining_rows.append(row)
        if payload is not None and payload.get("error"):
            errors += 1
        if is_runnable(payload):
            next_rows.append(row)
    preview = max(0, int(limit))
    next_rcids = [int(row["rcid"]) for row in next_rows[:preview]]
    spend = sum_recorded_spend(paths)
    return StatusReport(
        architecture=architecture,
        dataset=dataset,
        dataset_count=len(companies),
        done=done,
        remaining=len(remaining_rows),
        errors=errors,
        spend_usd=round(spend, 6),
        next_rcids=next_rcids,
        next_limit=preview,
    )
