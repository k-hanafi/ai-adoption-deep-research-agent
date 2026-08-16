"""Thin wrap of citation_verification/ onto the production spreadsheet.

Reads ``findings_deduplicated.csv`` when present, otherwise ``findings.csv``.
Renames Stage 3's ``error`` field to ``verification_error`` so it does not
clash with the research ``error`` column. Default is dry-run (no paid APIs).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Optional

from citation_verification.runner import verify_findings
from production.persist import (
    VERIFIED_COLUMNS,
    VERIFIED_EXTRA_COLUMNS,
    csv_cell,
    prod_paths,
)


def verification_source(paths) -> Path:
    if paths.findings_deduplicated_csv.exists():
        return paths.findings_deduplicated_csv
    if paths.findings_csv.exists():
        return paths.findings_csv
    raise FileNotFoundError(
        f"no findings to verify: expected {paths.findings_deduplicated_csv} "
        f"or {paths.findings_csv}"
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _has_finding(row: dict[str, Any]) -> bool:
    url = str(row.get("source_url") or "").strip()
    claim = str(row.get("evidence_description") or "").strip()
    return bool(url and claim)


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _verdict_map(verdicts) -> dict[tuple[Optional[int], Optional[int]], Any]:
    mapping: dict[tuple[Optional[int], Optional[int]], Any] = {}
    for verdict in verdicts:
        mapping[(verdict.rcid, verdict.finding_id)] = verdict
    return mapping


def _empty_verification() -> dict[str, Any]:
    return {key: "" for key in VERIFIED_EXTRA_COLUMNS}


def _from_verdict(verdict) -> dict[str, Any]:
    verification = verdict.verification
    return {
        "verification": "" if verification is None else verification,
        "unverifiable": verdict.unverifiable,
        "verification_error": verdict.error or "",
        "log_probs_conf": verdict.log_probs_conf,
        "confidence_1_5": verdict.confidence_1_5,
        "verification_reasoning": verdict.verification_reasoning,
        "verification_critique": verdict.verification_critique,
        "fetch_ok": verdict.fetch_ok,
        "fetched_url": verdict.fetched_url,
        "fetched_title": verdict.fetched_title,
        "fetch_source": verdict.fetch_source,
        "fetch_attempts": verdict.fetch_attempts,
        "model_judge": verdict.model_judge,
    }


def merge_verification_rows(
    research_rows: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> list[dict[str, Any]]:
    to_verify = [row for row in research_rows if _has_finding(row)]
    verdicts = verify_findings(to_verify, dry_run=dry_run).results if to_verify else []
    by_key = _verdict_map(verdicts)
    merged: list[dict[str, Any]] = []
    for row in research_rows:
        out = dict(row)
        if not _has_finding(row):
            out.update(_empty_verification())
            merged.append(out)
            continue
        key = (_int_or_none(row.get("rcid")), _int_or_none(row.get("finding_id")))
        verdict = by_key.get(key)
        if verdict is None:
            out.update(_empty_verification())
        else:
            out.update(_from_verdict(verdict))
        merged.append(out)
    return merged


def write_verified_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(VERIFIED_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_cell(row.get(key)) for key in VERIFIED_COLUMNS})


def run_verify(
    *,
    architecture: str,
    output_root: Path,
    dry_run: bool = True,
) -> Path:
    paths = prod_paths(output_root, architecture)
    source = verification_source(paths)
    rows = _read_csv(source)
    if not rows:
        raise ValueError(f"{source}: no rows to verify")
    merged = merge_verification_rows(rows, dry_run=dry_run)
    write_verified_csv(paths.findings_verified_csv, merged)
    print(
        f"VERIFY wrote {paths.findings_verified_csv} from {source.name} "
        f"rows={len(merged)} dry_run={dry_run}",
        flush=True,
    )
    return paths.findings_verified_csv
