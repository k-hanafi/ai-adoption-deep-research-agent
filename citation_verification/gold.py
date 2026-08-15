"""Labeled gold cases and offline scoreboard for citation verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

MANIFEST_PATH = Path(__file__).resolve().parent / "gold" / "manifest.jsonl"

# Families the expanded gold set must cover (plan WS8).
REQUIRED_FAMILIES: tuple[str, ...] = (
    "support",
    "hallucination",
    "unverifiable",
    "truncation",
    "soft_404",
    "paywall",
    "pdf",
    "redirect",
    "prompt_injection",
    "partial_support",
    "synonyms",
    "use_vs_sell",
    "timeout",
    "hard_fetch",
    "image_table",
    "non_english",
    "python_hero",
    "example_poison",
    "name_after_refetch",
    "strictness",
)


def load_manifest(path: Path | None = None) -> list[dict[str, Any]]:
    """Load labeled gold rows (one JSON object per line)."""
    target = path or MANIFEST_PATH
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        row = json.loads(text)
        if not isinstance(row, dict):
            raise ValueError(f"{target}:{line_no}: each line must be a JSON object")
        rows.append(row)
    return rows


def score_row(expected: Any, got: Optional[int], *, unverifiable: bool) -> dict[str, Any]:
    """Compare one verdict to the human label using the plan scoreboard."""
    expected_norm = _normalize_expected(expected)
    got_norm: Optional[int | str]
    if unverifiable or got is None:
        got_norm = None
    else:
        got_norm = got

    if expected_norm == "inspect":
        return {
            "ok": True,
            "kind": "inspect",
            "reason": "hard host: judge if readable, null if chrome-only",
        }
    if expected_norm == "name_rule":
        if got_norm is None:
            return {"ok": True, "kind": "true_null", "reason": "name missing after refetch"}
        if got_norm == 0:
            return {"ok": True, "kind": "tn", "reason": "name present, fact unsupported"}
        return {"ok": False, "kind": "fp", "reason": "named attribution must not be 1"}
    if expected_norm == "hero_or_null":
        if got_norm == 1:
            return {"ok": True, "kind": "tp", "reason": "hero recovered"}
        if got_norm is None:
            return {"ok": True, "kind": "true_null", "reason": "incomplete extract"}
        return {"ok": False, "kind": "fn", "reason": "incomplete extract must not be 0"}
    if expected_norm is None:
        if got_norm is None:
            return {"ok": True, "kind": "true_null", "reason": "expected null"}
        if got_norm == 1:
            return {"ok": False, "kind": "fp", "reason": "emitted 1 when label is null"}
        return {"ok": False, "kind": "fn", "reason": "emitted 0 when label is null"}
    if expected_norm == 1:
        if got_norm == 1:
            return {"ok": True, "kind": "tp", "reason": "expected 1, got 1"}
        if got_norm is None:
            return {"ok": False, "kind": "false_na", "reason": "expected 1, got null"}
        return {"ok": False, "kind": "fn", "reason": "expected 1, got 0"}
    if expected_norm == 0:
        if got_norm == 0:
            return {"ok": True, "kind": "tn", "reason": "expected 0, got 0"}
        if got_norm == 1:
            return {"ok": False, "kind": "fp", "reason": "expected 0, got 1"}
        return {"ok": False, "kind": "false_na", "reason": "expected 0, got null"}
    return {"ok": False, "kind": "unknown", "reason": f"unscored expected={expected!r}"}


def _normalize_expected(expected: Any) -> Any:
    if expected is None or expected == "null":
        return None
    if expected in (0, 1, "0", "1"):
        return int(expected)
    return expected
