"""CLI: python -m production {run,dry-run,status,dedupe,verify}.

Live run requires --limit N or --all so a full 9,420-company job cannot start
by accident. Default architecture is SGS. Resume is per architecture.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from production.dedupe import run_dedupe
from production.persist import ARCH_KEYS, DEFAULT_DATASET, DEFAULT_OUTPUT_ROOT, load_dataset
from production.run import DEFAULT_CONCURRENCY, run_dry, run_live
from production.status import collect_status
from production.verify import DEFAULT_VERIFY_CONCURRENCY, collect_verify_status, run_verify


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--architecture",
        choices=ARCH_KEYS,
        default="sgs",
        help="Search architecture (default: sgs)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Company JSONL (default: crunchbase_data/stage2_input_dataset_p4_p5.jsonl)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root for per-architecture folders (default: outputs/prod)",
    )


def _add_limit(parser: argparse.ArgumentParser, *, required_note: bool) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Next N remaining companies" + (" (required for live unless --all)" if required_note else ""),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every remaining company in the dataset",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m production",
        description=(
            "Production batch runner. run writes raw findings. "
            "dedupe writes findings_deduplicated.csv. "
            "verify writes findings_verified.csv."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Live paid batch (requires --limit N or --all)")
    _add_common(run_p)
    _add_limit(run_p, required_note=True)
    run_p.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Companies in flight (default: {DEFAULT_CONCURRENCY})",
    )

    dry_p = sub.add_parser("dry-run", help="Call architecture dry-run and write no files")
    _add_common(dry_p)
    _add_limit(dry_p, required_note=True)

    status_p = sub.add_parser("status", help="Print done / remaining / errors / spend / next rcids")
    _add_common(status_p)
    status_p.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many next rcids to preview (default: 10)",
    )

    dedupe_p = sub.add_parser("dedupe", help="Write findings_deduplicated.csv from findings.csv")
    _add_common(dedupe_p)

    verify_p = sub.add_parser(
        "verify",
        help="Verify findings_deduplicated.csv (requires --limit N or --all, or --status)",
    )
    _add_common(verify_p)
    _add_limit(verify_p, required_note=True)
    verify_p.add_argument(
        "--live",
        action="store_true",
        help="Paid fetch+judge (default is dry-run, no APIs)",
    )
    verify_p.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_VERIFY_CONCURRENCY,
        help=(
            f"Max findings in flight (default: {DEFAULT_VERIFY_CONCURRENCY}). "
            "Per-API caps adapt under this pool."
        ),
    )
    verify_p.add_argument(
        "--status",
        action="store_true",
        help="Print verify done / remaining / spend and exit",
    )
    verify_p.add_argument(
        "--from-cache",
        action="store_true",
        dest="from_cache",
        help=(
            "Judge saved pages only (no Perplexity/Tavily). "
            "Re-runs Luna on cached URLs, including complete stamps. "
            "Requires --live. Findings with no page are skipped."
        ),
    )
    return parser


def _require_limit_or_all(args: argparse.Namespace) -> None:
    if args.limit is not None and args.all:
        raise SystemExit("use --limit N or --all, not both")
    if args.limit is None and not args.all:
        raise SystemExit(
            f"{args.command} requires --limit N or --all. "
            "Refusing to start the full dataset by accident."
        )
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")


def _load(args: argparse.Namespace) -> list[dict]:
    try:
        return load_dataset(args.dataset)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "dedupe":
        try:
            run_dedupe(
                architecture=args.architecture,
                output_root=args.output_root,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        return 0

    if args.command == "verify":
        if args.status:
            try:
                report = collect_verify_status(
                    architecture=args.architecture,
                    output_root=args.output_root,
                )
            except (FileNotFoundError, ValueError) as exc:
                raise SystemExit(str(exc)) from exc
            print(report.format(), end="")
            return 0
        _require_limit_or_all(args)
        if args.concurrency < 1:
            raise SystemExit("--concurrency must be >= 1")
        if args.from_cache and not args.live:
            raise SystemExit("--from-cache requires --live (Luna still runs on the saved page)")
        try:
            run_verify(
                architecture=args.architecture,
                output_root=args.output_root,
                dry_run=not args.live,
                limit=None if args.all else args.limit,
                concurrency=args.concurrency,
                from_cache=args.from_cache,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        return 0

    companies = _load(args)
    if args.command == "status":
        report = collect_status(
            companies,
            architecture=args.architecture,
            output_root=args.output_root,
            dataset=args.dataset,
            limit=args.limit,
        )
        print(report.format(), end="")
        return 0

    if args.command == "dry-run":
        _require_limit_or_all(args)
        return run_dry(
            companies,
            architecture=args.architecture,
            output_root=args.output_root,
            limit=None if args.all else args.limit,
        )

    if args.command == "run":
        _require_limit_or_all(args)
        if args.concurrency < 1:
            raise SystemExit("--concurrency must be >= 1")
        return run_live(
            companies,
            architecture=args.architecture,
            output_root=args.output_root,
            limit=None if args.all else args.limit,
            concurrency=args.concurrency,
        )

    raise SystemExit(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
