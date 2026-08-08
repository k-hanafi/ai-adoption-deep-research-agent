"""CLI for the eval product: run-* modes, cost-preview, open-dashboard."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from evals.archive import create_stub_instance
from evals.architectures import ARCHITECTURES, ALIASES, resolve_architecture
from evals.cost_preview import preview_cost, preview_matrix
from evals.dashboard.landing import ensure_landing_stub
from evals.tune import run_tuning
from evals.tune.cost_diagnose import run_cost_diagnose


def _architecture_help() -> str:
    keys = ", ".join(sorted(ARCHITECTURES))
    aliases = ", ".join(f"{a}->{k}" for a, k in sorted(ALIASES.items()))
    return f"Architecture CLI key ({keys}) or alias ({aliases})"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals",
        description=(
            "Eval harness for Parallel Channel Search, Signal Gated Search, "
            "and Unified Adaptive Search."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tune_p = sub.add_parser(
        "run-tuning",
        help="Run a tuning stage and archive a Tuning instance dashboard.",
    )
    tune_p.add_argument("architecture", help=_architecture_help())
    tune_p.add_argument(
        "--stage",
        choices=("screen", "factorial"),
        default="screen",
        help="Tuning stage (default: screen)",
    )
    tune_p.add_argument(
        "--panel",
        type=Path,
        default=None,
        help="Optional tuning panel JSON (default: evals/panel/tuning_panel.json)",
    )
    tune_p.add_argument(
        "--live",
        action="store_true",
        help="Paid UAS matrix (metered Agent API; requires key; dry is default)",
    )

    bench_p = sub.add_parser(
        "run-benchmarks",
        help="Archive a benchmark instance (stub until Phase 3 bake-off).",
    )
    bench_p.add_argument("architecture", help=_architecture_help())
    bench_p.add_argument(
        "--live",
        action="store_true",
        help="Mark instance as live (paid path not wired yet)",
    )

    ver_p = sub.add_parser(
        "run-verification",
        help="Archive a verification instance (stub until Stage 3 judge).",
    )
    ver_p.add_argument(
        "architecture",
        nargs="?",
        default=None,
        help="Optional architecture key/alias for metadata",
    )
    ver_p.add_argument(
        "--live",
        action="store_true",
        help="Mark instance as live (paid path not wired yet)",
    )

    diag_p = sub.add_parser(
        "cost-diagnose",
        help=(
            "Small paid (or dry) knob smokes to size Stage A ranges "
            "before a full tuning matrix."
        ),
    )
    diag_p.add_argument(
        "--live",
        action="store_true",
        help="Paid Agent API smokes (default is dry)",
    )

    cost_p = sub.add_parser(
        "cost-preview",
        help="Estimate spend before a paid run (no API calls).",
    )
    cost_p.add_argument("architecture", help=_architecture_help())
    cost_p.add_argument(
        "--k",
        type=int,
        default=1,
        help="Repeat count (default 1, must be >= 1)",
    )
    cost_p.add_argument(
        "--n",
        type=int,
        default=None,
        help="Override company count (default: panel size, must be >= 1)",
    )
    cost_p.add_argument(
        "--panel",
        type=Path,
        default=None,
        help="Optional panel JSON path for company count",
    )
    cost_p.add_argument(
        "--matrix",
        choices=("screen",),
        default=None,
        help="Preview a tuning matrix instead of a single architecture prior",
    )

    dash_p = sub.add_parser(
        "open-dashboard",
        help="Open the categorized landing index of prior eval instances.",
    )
    dash_p.add_argument(
        "--no-open",
        action="store_true",
        help="Print the path only (do not launch a browser)",
    )

    return parser


def _cli_summary(argv: list[str] | None) -> str:
    if argv is None:
        argv = sys.argv[1:]
    return "python -m evals " + " ".join(str(a) for a in argv)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cli = _cli_summary(argv)

    if args.command == "run-tuning":
        try:
            instance_dir = run_tuning(
                args.architecture,
                stage=args.stage,
                dry_run=not args.live,
                panel=args.panel,
                cli=cli,
            )
        except NotImplementedError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Wrote tuning instance to: {instance_dir}")
        print(f"Dashboard: {instance_dir / 'dashboard.html'}")
        return 0

    if args.command == "run-benchmarks":
        spec = resolve_architecture(args.architecture)
        instance_dir = create_stub_instance(
            kind="benchmark",
            cli=cli,
            architecture=spec.cli_key,
            full_name=spec.full_name,
            dry_run=not args.live,
            notes="Stub. Paired bake-off not wired.",
        )
        print(f"Wrote benchmark instance to: {instance_dir}")
        print(f"Dashboard: {instance_dir / 'dashboard.html'}")
        return 0

    if args.command == "run-verification":
        architecture = None
        full_name = None
        if args.architecture:
            spec = resolve_architecture(args.architecture)
            architecture = spec.cli_key
            full_name = spec.full_name
        instance_dir = create_stub_instance(
            kind="verification",
            cli=cli,
            architecture=architecture,
            full_name=full_name,
            dry_run=not args.live,
            notes="Stub. Stage 3 judge not wired.",
        )
        print(f"Wrote verification instance to: {instance_dir}")
        print(f"Dashboard: {instance_dir / 'dashboard.html'}")
        return 0

    if args.command == "cost-diagnose":
        if args.live:
            print(
                "Live cost-diagnose: paid UAS smokes across knob highs + "
                "API-max corner. Approve spend before large follows.",
                file=sys.stderr,
            )
        out_dir = run_cost_diagnose(dry_run=not args.live)
        print(f"Wrote cost-diagnose bundle to: {out_dir}")
        print(f"Summary: {out_dir / 'summary.csv'}")
        return 0

    if args.command == "cost-preview":
        if args.k < 1:
            parser.error("--k must be >= 1")
        if args.n is not None and args.n < 1:
            parser.error("--n must be >= 1")
        if args.matrix:
            preview = preview_matrix(
                args.architecture,
                matrix=args.matrix,
                k=args.k,
                n_companies=args.n,
                panel=args.panel,
            )
        else:
            preview = preview_cost(
                args.architecture,
                k=args.k,
                n_companies=args.n,
                panel=args.panel,
            )
        print(json.dumps(preview.to_dict(), indent=2))
        return 0

    if args.command == "open-dashboard":
        path = ensure_landing_stub()
        print(f"Landing index: {path}")
        if not args.no_open:
            webbrowser.open(path.resolve().as_uri())
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
