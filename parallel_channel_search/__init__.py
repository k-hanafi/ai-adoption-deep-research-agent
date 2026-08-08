"""Parallel Channel Search (PCS): equal-depth channel specialists, then merge.

CLI key: parallel-channel-search (alias: pcs)
Dry-run builds three channel Agent API request snapshots. Live fans out in parallel.
"""

from parallel_channel_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
