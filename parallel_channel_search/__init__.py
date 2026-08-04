"""Parallel Channel Search (PCS): equal-depth channel specialists, then merge.

CLI key: parallel-channel-search (alias: pcs)
Phase 1: stub runner with locked design skeleton (3 channels × preset `low`).
"""

from parallel_channel_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
