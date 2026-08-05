"""Unified Adaptive Search (UAS): single Luna Agent API call per company.

CLI key: unified-adaptive-search (alias: uas)
"Adaptive" means hyperparameters / prompt / search config, not channel fan-out.

Call kwargs are explicit (model, max_steps, reasoning, tools). Preset names are
not first-class config. Dry-run is the default for harness wiring.
"""

from unified_adaptive_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
