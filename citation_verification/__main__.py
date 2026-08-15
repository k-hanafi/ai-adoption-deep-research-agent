"""CLI: python -m citation_verification [--dry-run|--live] --findings path.jsonl

Optional one-off debug: --url URL --claim TEXT
Optional file output: --output-jsonl PATH and/or --output-csv PATH
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

from citation_verification.runner import verify_finding, verify_findings
from citation_verification.types import VerdictResult

# Human-review columns first (URL + finding), then verdict / error.
CSV_FIELDNAMES: tuple[str, ...] = (
    "finding_id",
    "source_url",
    "evidence_description",
    "claim",
    "company_name",
    "rcid",
    "channel",
    "AI_tool_used",
    "use_case",
    "business_function",
    "source_type",
    "architecture",
    "verification",
    "unverifiable",
    "error",
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
    "dry_run",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_no}: each line must be a JSON object")
        rows.append(row)
    return rows


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_verdicts_jsonl(path: Path, results: Sequence[VerdictResult]) -> None:
    """Write one verdict object per line, including finding fields and URL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")


def write_verdicts_csv(path: Path, results: Sequence[VerdictResult]) -> None:
    """Write a spreadsheet of verdicts. source_url is a plain clickable URL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(CSV_FIELDNAMES),
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in results:
            payload = row.to_dict()
            writer.writerow({key: _csv_cell(payload.get(key)) for key in CSV_FIELDNAMES})


def _write_outputs(
    results: Sequence[VerdictResult],
    *,
    jsonl_path: Path | None,
    csv_path: Path | None,
) -> None:
    if jsonl_path is not None:
        write_verdicts_jsonl(jsonl_path, results)
    if csv_path is not None:
        write_verdicts_csv(csv_path, results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 3 citation verification "
            "(dry-run default; --live runs paid fetch+judge)"
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="No paid APIs (default)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Paid Perplexity fetch_url + OpenAI Terra judge",
    )
    parser.add_argument(
        "--findings",
        type=Path,
        help="JSONL of findings (needs evidence_description + source_url)",
    )
    parser.add_argument("--url", default=None, help="One-off debug source URL")
    parser.add_argument("--claim", default=None, help="One-off debug claim text")
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        help="Write one verdict JSON object per line (finding fields + URL)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Write verdicts as CSV (source_url is a clickable URL string)",
    )
    args = parser.parse_args(argv)

    dry_run = not args.live

    if args.findings is not None:
        rows = _load_jsonl(args.findings)
        if not rows:
            raise SystemExit(f"{args.findings}: no findings rows")
        result = verify_findings(rows, dry_run=dry_run)
        _write_outputs(
            result.results,
            jsonl_path=args.output_jsonl,
            csv_path=args.output_csv,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.url is not None or args.claim is not None:
        if not args.url or not args.claim:
            raise SystemExit("one-off debug requires both --url and --claim")
        verdict = verify_finding(
            {
                "finding_id": None,
                "source_url": args.url,
                "evidence_description": args.claim,
            },
            dry_run=dry_run,
        )
        _write_outputs(
            [verdict],
            jsonl_path=args.output_jsonl,
            csv_path=args.output_csv,
        )
        print(json.dumps(verdict.to_dict(), indent=2))
        return 0

    raise SystemExit("provide --findings PATH.jsonl or both --url and --claim")


if __name__ == "__main__":
    raise SystemExit(main())
