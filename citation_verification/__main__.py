"""CLI: python -m citation_verification [--dry-run|--live] --findings path.jsonl

Optional one-off debug: --url URL --claim TEXT
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from citation_verification.runner import LiveNotWiredError, verify_finding, verify_findings


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stage 3 citation verification "
            "(dry-run default; --live reserved for paid fetch+judge)"
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
        help="Paid fetch+judge (not wired in skeleton commit)",
    )
    parser.add_argument(
        "--findings",
        type=Path,
        help="JSONL of findings (needs evidence_description + source_url)",
    )
    parser.add_argument("--url", default=None, help="One-off debug source URL")
    parser.add_argument("--claim", default=None, help="One-off debug claim text")
    args = parser.parse_args(argv)

    dry_run = not args.live

    try:
        if args.findings is not None:
            rows = _load_jsonl(args.findings)
            if not rows:
                raise SystemExit(f"{args.findings}: no findings rows")
            result = verify_findings(rows, dry_run=dry_run)
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
            print(json.dumps(verdict.to_dict(), indent=2))
            return 0

        raise SystemExit("provide --findings PATH.jsonl or both --url and --claim")
    except LiveNotWiredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
