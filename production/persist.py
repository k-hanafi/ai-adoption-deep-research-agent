"""On-disk layout, Excel schema, and keep-success writes for production runs.

``companies/{rcid}.json`` is the full architecture payload (plus a few company
fields so Excel can be rebuilt without re-reading the dataset). Tokens, traces,
and ``no_finding_analysis`` stay in that JSON. ``findings.csv`` is the operator
spreadsheet, rebuilt from ``findings.jsonl`` after each company.
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

ARCH_KEYS = ("sgs", "pcs", "uas")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = PROJECT_ROOT / "crunchbase_data" / "stage2_input_dataset_p4_p5.jsonl"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "prod"

RESEARCH_COLUMNS: tuple[str, ...] = (
    "rcid",
    "company_name",
    "homepage_url",
    "short_description",
    "research_priority_score",
    "architecture",
    "finding_id",
    "AI_tool_used",
    "use_case",
    "business_function",
    "evidence_description",
    "source_url",
    "source_type",
    "channel",
    "genai_adoption_found",
    "findings_count",
    "no_finding_reason",
    "error",
    "duration_seconds",
    "scout_jobs",
    "scout_owned",
    "scout_third_party",
    "dig_count",
    "dig_channels",
    "cost_usd",
    "scout_cost_usd",
    "dig_cost_usd",
)

FINDING_COLUMNS: tuple[str, ...] = (
    "finding_id",
    "AI_tool_used",
    "use_case",
    "business_function",
    "evidence_description",
    "source_url",
    "source_type",
    "channel",
)

VERIFIED_EXTRA_COLUMNS: tuple[str, ...] = (
    "verification",
    "unverifiable",
    "verification_error",
    "log_probs_conf",
    "confidence_1_5",
    "verification_reasoning",
    "verification_critique",
    "fetch_ok",
    "fetched_url",
    "fetched_title",
    "fetch_source",
    "fetch_attempts",
    "model_judge",
)

VERIFIED_COLUMNS: tuple[str, ...] = RESEARCH_COLUMNS + VERIFIED_EXTRA_COLUMNS


@dataclass(frozen=True)
class ProdPaths:
    """Per-architecture directory under ``outputs/prod/{arch}/``."""

    root: Path
    architecture: str

    @property
    def companies(self) -> Path:
        return self.root / "companies"

    @property
    def findings_jsonl(self) -> Path:
        return self.root / "findings.jsonl"

    @property
    def findings_csv(self) -> Path:
        return self.root / "findings.csv"

    @property
    def findings_deduplicated_csv(self) -> Path:
        return self.root / "findings_deduplicated.csv"

    @property
    def findings_verified_csv(self) -> Path:
        return self.root / "findings_verified.csv"

    def company_json(self, rcid: int) -> Path:
        return self.companies / f"{int(rcid)}.json"


@dataclass(frozen=True)
class WriteOutcome:
    path: Path
    action: str
    backup: Optional[Path] = None


def prod_paths(output_root: Path, architecture: str) -> ProdPaths:
    if architecture not in ARCH_KEYS:
        raise ValueError(f"unknown architecture {architecture!r}")
    return ProdPaths(root=output_root / architecture, architecture=architecture)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    """Load the P4+P5 JSONL (one company object per line), preserving order."""
    if not path.exists():
        raise FileNotFoundError(f"dataset not found: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: each line must be a JSON object")
        if row.get("rcid") is None:
            raise ValueError(f"{path}:{line_no}: company rcid is required")
        rows.append(row)
    return rows


def load_payload(path: Path) -> Optional[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def is_complete_success(payload: Optional[dict[str, Any]]) -> bool:
    return bool(payload) and not payload.get("error")


def is_429(error: Optional[str]) -> bool:
    text = (error or "").lower()
    return "429" in text or "rate limit" in text or "ratelimit" in text


def is_timeout(error: Optional[str]) -> bool:
    return "timeout" in (error or "").lower()


def is_retryable(error: Optional[str]) -> bool:
    return is_429(error) or is_timeout(error)


def is_parked_error(payload: Optional[dict[str, Any]]) -> bool:
    """True for a canonical failure that should not consume the next --limit batch."""
    if not payload or is_complete_success(payload):
        return False
    error = payload.get("error")
    if not error:
        return False
    return not is_retryable(error)


def is_runnable(payload: Optional[dict[str, Any]]) -> bool:
    """Companies live --limit N will take: no success file, or a 429/timeout."""
    if is_complete_success(payload):
        return False
    return not is_parked_error(payload)


def sum_recorded_spend(paths: ProdPaths) -> float:
    """Sum cost_usd from canonical JSON and sidecar backups (429/timeout/failed)."""
    if not paths.companies.exists():
        return 0.0
    total = 0.0
    for path in paths.companies.glob("*.json"):
        payload = load_payload(path)
        if payload is None:
            continue
        total += float(payload.get("cost_usd") or 0.0)
    return total


def sidecar_paths(paths: ProdPaths, rcid: int) -> list[Path]:
    """Backups named ``{rcid}.{stamp}.{kind}.json``, not the canonical file."""
    if not paths.companies.exists():
        return []
    return sorted(
        paths.companies.glob(f"{int(rcid)}.*.json"),
        key=lambda path: path.stat().st_mtime,
    )


def latest_sidecar_payload(paths: ProdPaths, rcid: int) -> Optional[dict[str, Any]]:
    sidecars = sidecar_paths(paths, rcid)
    if not sidecars:
        return None
    return load_payload(sidecars[-1])


def load_result_payload(paths: ProdPaths, rcid: int) -> Optional[dict[str, Any]]:
    """Canonical JSON if present, else the newest sidecar (429/timeout after unlink)."""
    payload = load_payload(paths.company_json(rcid))
    if payload is not None:
        return payload
    return latest_sidecar_payload(paths, rcid)


def count_outstanding(
    companies: list[dict[str, Any]],
    paths: ProdPaths,
) -> tuple[int, int]:
    """Return (remaining, parked). Remaining is every company without a success JSON."""
    remaining = 0
    parked = 0
    for row in companies:
        payload = load_payload(paths.company_json(int(row["rcid"])))
        if is_complete_success(payload):
            continue
        remaining += 1
        if is_parked_error(payload):
            parked += 1
    return remaining, parked


def retry_kind(error: Optional[str]) -> str:
    if is_429(error):
        return "429"
    if is_timeout(error):
        return "timeout"
    return "failed"


def csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _components(payload: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = payload.get("cost_ledger") or {}
    rows = ledger.get("components") or []
    return [row for row in rows if isinstance(row, dict)]


def split_costs(architecture: str, payload: dict[str, Any]) -> tuple[float, float, float]:
    """Return (total, scout, dig). PCS and UAS put all spend in dig."""
    total = float(payload.get("cost_usd") or (payload.get("cost_ledger") or {}).get("total_usd") or 0.0)
    if architecture == "sgs":
        scout = sum(
            float(row.get("cost_usd") or 0.0)
            for row in _components(payload)
            if str(row.get("name") or "").startswith("scout_")
        )
        dig = sum(
            float(row.get("cost_usd") or 0.0)
            for row in _components(payload)
            if str(row.get("name") or "").startswith("dig_")
        )
        return total, scout, dig
    return total, 0.0, total


def scout_bins(architecture: str, payload: dict[str, Any]) -> tuple[str, str, str]:
    if architecture != "sgs":
        return "", "", ""
    results = (payload.get("traces") or {}).get("scout_results") or {}
    jobs = (results.get("jobs") or {}).get("evidence_bin") or ""
    owned = (results.get("owned") or {}).get("evidence_bin") or ""
    third = (results.get("third_party") or {}).get("evidence_bin") or ""
    return str(jobs), str(owned), str(third)


def dig_fields(architecture: str, payload: dict[str, Any]) -> tuple[Any, str]:
    traces = payload.get("traces") or {}
    if architecture == "pcs":
        channels = traces.get("channels") or ["jobs", "owned", "third_party"]
        return 3, ",".join(str(c) for c in channels)
    if architecture == "uas":
        return "", ""
    gate = traces.get("gate") or {}
    count = gate.get("dig_count")
    if count is None:
        count = 0
    channels = gate.get("dig_channels") or []
    return count, ",".join(str(c) for c in channels)


def company_record(
    company: dict[str, Any],
    payload: dict[str, Any],
    architecture: str,
) -> dict[str, Any]:
    """One JSONL line: company fields plus the spreadsheet-facing result."""
    total, scout_cost, dig_cost = split_costs(architecture, payload)
    jobs, owned, third = scout_bins(architecture, payload)
    dig_count, dig_channels = dig_fields(architecture, payload)
    findings = payload.get("findings") or []
    return {
        "rcid": int(payload.get("rcid") if payload.get("rcid") is not None else company["rcid"]),
        "company_name": payload.get("company_name") or company.get("name") or "",
        "homepage_url": company.get("homepage_url") or payload.get("homepage_url") or "",
        "short_description": company.get("short_description")
        or payload.get("short_description")
        or "",
        "research_priority_score": company.get("research_priority_score")
        if company.get("research_priority_score") is not None
        else payload.get("research_priority_score") or 0,
        "architecture": architecture,
        "findings": findings,
        "findings_count": payload.get("findings_count")
        if payload.get("findings_count") is not None
        else len(findings),
        "genai_adoption_found": payload.get("genai_adoption_found"),
        "no_finding_reason": payload.get("no_finding_reason"),
        "error": payload.get("error"),
        "duration_seconds": payload.get("duration_seconds"),
        "scout_jobs": jobs,
        "scout_owned": owned,
        "scout_third_party": third,
        "dig_count": dig_count,
        "dig_channels": dig_channels,
        "cost_usd": total,
        "scout_cost_usd": scout_cost,
        "dig_cost_usd": dig_cost,
    }


def disk_payload(company: dict[str, Any], result_dict: dict[str, Any]) -> dict[str, Any]:
    """ArchitectureResult dict plus company fields needed to rebuild Excel."""
    return {
        **result_dict,
        "homepage_url": company.get("homepage_url"),
        "short_description": company.get("short_description"),
        "research_priority_score": company.get("research_priority_score"),
    }


def csv_rows_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    """One spreadsheet row per finding. Zero findings still emit one blank row."""
    findings = record.get("findings") or []
    base = {key: record.get(key) for key in RESEARCH_COLUMNS if key not in FINDING_COLUMNS}
    if not findings:
        row = {key: "" for key in RESEARCH_COLUMNS}
        row.update(base)
        return [row]
    rows: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            finding = {
                key: getattr(finding, key, "")
                for key in FINDING_COLUMNS
            }
        row = {key: "" for key in RESEARCH_COLUMNS}
        row.update(base)
        for key in FINDING_COLUMNS:
            row[key] = finding.get(key)
        rows.append(row)
    return rows


def records_from_jsonl(path: Path) -> list[dict[str, Any]]:
    """Last write per rcid wins (resume can append a replacement line)."""
    if not path.exists():
        return []
    by_rcid: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        record = json.loads(text)
        if not isinstance(record, dict) or record.get("rcid") is None:
            continue
        rcid = int(record["rcid"])
        if rcid not in by_rcid:
            order.append(rcid)
        by_rcid[rcid] = record
    return [by_rcid[rcid] for rcid in order]


def write_findings_csv(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(RESEARCH_COLUMNS),
            extrasaction="ignore",
        )
        writer.writeheader()
        for record in records:
            for row in csv_rows_from_record(record):
                writer.writerow({key: csv_cell(row.get(key)) for key in RESEARCH_COLUMNS})


def rebuild_findings_csv(paths: ProdPaths) -> None:
    write_findings_csv(paths.findings_csv, records_from_jsonl(paths.findings_jsonl))


def append_findings_jsonl(paths: ProdPaths, record: dict[str, Any]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    with paths.findings_jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def rebuild_jsonl_from_companies(
    paths: ProdPaths,
    companies: list[dict[str, Any]],
) -> None:
    """Rewrite findings.jsonl in dataset order from company JSON or newest sidecar."""
    by_rcid = {int(row["rcid"]): row for row in companies}
    records: list[dict[str, Any]] = []
    if paths.companies.exists():
        for company in companies:
            rcid = int(company["rcid"])
            payload = load_result_payload(paths, rcid)
            if payload is None:
                continue
            records.append(company_record(by_rcid[rcid], payload, paths.architecture))
    paths.root.mkdir(parents=True, exist_ok=True)
    with paths.findings_jsonl.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_findings_csv(paths.findings_csv, records)


def write_company_json(path: Path, payload: dict[str, Any]) -> WriteOutcome:
    """Write ``{rcid}.json``. Never replace a successful file with a later failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_payload(path) if path.exists() else None
    if is_complete_success(existing) and payload.get("error"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.stem}.{stamp}.failed.json")
        backup.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return WriteOutcome(path=path, action="kept_success", backup=backup)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return WriteOutcome(path=path, action="wrote")


def _backup_name(path: Path, kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.stem}.{stamp}.{kind}.json")
    if backup.exists():
        backup = path.with_name(f"{path.stem}.{stamp}.{kind}b.json")
    return backup


def copy_retryable_backup(path: Path, kind: str) -> Path:
    """Copy a failed canonical JSON aside and leave the original in place."""
    backup = _backup_name(path, kind)
    shutil.copy2(path, backup)
    return backup


def backup_retryable(path: Path, kind: str) -> Path:
    """Copy a failed canonical JSON aside and remove it so the company can rerun."""
    backup = copy_retryable_backup(path, kind)
    path.unlink()
    return backup
