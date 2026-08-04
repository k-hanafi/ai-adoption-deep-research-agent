"""Unified Adaptive Search (UAS): single medium-depth Agent API call per company.

CLI key: unified-adaptive-search (alias: uas)
"Adaptive" means hyperparameters / prompt / search config, not channel fan-out.

Phase 1: public runner adapted from src/stage_2/production_agent_runner.py
patterns, with dry-run default for harness wiring (no paid API required).
"""

from unified_adaptive_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
