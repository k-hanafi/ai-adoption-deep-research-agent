"""Optional one-company CLI outside the eval harness."""

from __future__ import annotations

import argparse
import json

from unified_adaptive_search.agent_call import (
    DEFAULT_MAX_STEPS,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_WEB_SEARCH_DEPTH,
)
from unified_adaptive_search.runner import ARCHITECTURE_NAME, run


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{ARCHITECTURE_NAME} (dry-run default; pass --live for one paid call)"
    )
    parser.add_argument("--rcid", type=int, default=0)
    parser.add_argument("--name", default="Stub Company")
    parser.add_argument("--homepage-url", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--web-search-depth", default=DEFAULT_WEB_SEARCH_DEPTH)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make one paid Agent API call (requires Perplexity API key)",
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
        model=args.model,
        max_steps=args.max_steps,
        reasoning_effort=args.reasoning_effort,
        web_search_depth=args.web_search_depth,
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
