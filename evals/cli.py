"""CLI for the locked eval product trio."""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from evals.architectures import ARCHITECTURES, ALIASES
from evals.cost_preview import preview_cost
from evals.dashboard.landing import ensure_landing_stub
from evals.runner import run_panel


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

    run_p = sub.add_parser(
        "run-evals",
        help="Run one architecture against the panel (Phase 1: dry/stub).",
    )
    run_p.add_argument("architecture", help=_architecture_help())
    run_p.add_argument(
        "--k",
        type=int,
        default=1,
        help="Repeat count (default 1, must be >= 1)",
    )
    run_p.add_argument(
        "--panel",
        type=Path,
        default=None,
        help="Optional panel JSON path (default: fixture panel)",
    )
    run_p.add_argument(
        "--live",
        action="store_true",
        help=(
            "Attempt live API mode "
            "(Phase 1 architectures raise NotImplementedError)"
        ),
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
        help="Optional panel JSON path for company count (default: fixture panel)",
    )

    dash_p = sub.add_parser(
        "open-dashboard",
        help="Open the landing index of prior eval instances.",
    )
    dash_p.add_argument(
        "--no-open",
        action="store_true",
        help="Print the path only (do not launch a browser)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-evals":
        if args.k < 1:
            parser.error("--k must be >= 1")
        run_dir = run_panel(
            args.architecture,
            panel=args.panel,
            k=args.k,
            dry_run=not args.live,
        )
        print(f"Wrote eval run bundle to: {run_dir}")
        print(f"Dashboard: {run_dir / 'dashboard.html'}")
        return 0

    if args.command == "cost-preview":
        if args.k < 1:
            parser.error("--k must be >= 1")
        if args.n is not None and args.n < 1:
            parser.error("--n must be >= 1")
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
