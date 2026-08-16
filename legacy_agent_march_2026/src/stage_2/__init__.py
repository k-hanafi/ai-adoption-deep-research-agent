"""Stage 2: Deep research via Perplexity Agent API.

Migration note (Phase 1 scaffolding):
- New eval-facing home for the status-quo single-call shape is
  `unified_adaptive_search` (CLI: unified-adaptive-search).
- March batch production remains on
  `python -m src.stage_2.production_agent_runner`.
- Prefer `python -m evals …` for architecture experiments going forward.
"""

from __future__ import annotations

from typing import Any

__all__ = ["unified_adaptive_search_run"]


def __getattr__(name: str) -> Any:
    # Lazy re-export so `python -m src.stage_2.production_agent_runner`
    # does not import the new packages unless callers ask for the shim.
    if name == "unified_adaptive_search_run":
        from unified_adaptive_search.runner import run as unified_adaptive_search_run

        return unified_adaptive_search_run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
