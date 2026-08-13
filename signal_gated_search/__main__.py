"""Optional one-company CLI outside the eval harness."""

from __future__ import annotations

import argparse
import json

from signal_gated_search.runner import ARCHITECTURE_NAME, run


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            f"{ARCHITECTURE_NAME} "
            "(dry-run default. Pass --live for paid scout then gated dig calls)"
        )
    )
    parser.add_argument("--rcid", type=int, default=0)
    parser.add_argument("--name", default="Stub Company")
    parser.add_argument("--homepage-url", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Make paid Agent API calls: 3 presence scouts, then 0 to 3 cold digs "
            "(requires Perplexity API key)"
        ),
    )
    args = parser.parse_args()

    result = run(
        {
            "rcid": args.rcid,
            "name": args.name,
            "homepage_url": args.homepage_url,
            "short_description": args.description,
        },
        dry_run=not args.live,
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
