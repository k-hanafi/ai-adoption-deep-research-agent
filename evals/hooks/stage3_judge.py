"""Stage 3 citation judge hook (stub only, plan STATUS)."""

from __future__ import annotations

from typing import Any


def judge_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Placeholder for a future citation-support judge.

    Phase 1 leaves the schema hook only. Do not call paid judges here.
    """
    return {
        "supported": None,
        "verdict": "not_run",
        "reason": "Stage 3 citation judge is not implemented in Phase 1.",
        "finding_id": finding.get("finding_id"),
    }
