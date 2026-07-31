"""Signal Gated Search (SGS): cheap scouts, then ranked top-1 dig (+ rescue).

CLI key: signal-gated-search (alias: sgs)
Phase 1: stub runner with locked design skeleton and component cost ledger.
"""

from signal_gated_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
