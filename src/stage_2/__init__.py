"""Stage 2: Deep research via Perplexity Agent API.

Migration note (Phase 1 scaffolding):
- New eval-facing home for the status-quo single-call shape is
  `unified_adaptive_search` (CLI: unified-adaptive-search).
- March batch production remains on
  `python -m src.stage_2.production_agent_runner`.
- Prefer `python -m evals …` for architecture experiments going forward.
"""

# Compatibility re-export for the new public runner contract.
from unified_adaptive_search.runner import run as unified_adaptive_search_run

__all__ = ["unified_adaptive_search_run"]
