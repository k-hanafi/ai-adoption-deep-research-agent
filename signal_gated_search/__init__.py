"""Signal Gated Search (SGS): presence scouts, then gated digs.

CLI key: signal-gated-search (alias: sgs)
Live Agent API fan-out is not in this package yet. Gate + prompt compose are wired.
"""

from signal_gated_search.runner import ARCHITECTURE_CLI_KEY, ARCHITECTURE_NAME, run

__all__ = ["ARCHITECTURE_CLI_KEY", "ARCHITECTURE_NAME", "run"]
