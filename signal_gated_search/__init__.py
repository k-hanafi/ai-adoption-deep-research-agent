"""Signal Gated Search (SGS): presence scouts, then gated digs.

CLI key: signal-gated-search (alias: sgs)
Dry-run composes scout/dig request snapshots. Live fans out scouts, then gated digs.
"""

from signal_gated_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
