"""Standalone eval harness for the three Stage 2 architecture packages.

CLI product:
  python -m evals run-tuning <architecture> --stage screen
  python -m evals run-benchmarks <architecture>
  python -m evals run-verification
  python -m evals cost-preview <architecture> [--matrix screen]
  python -m evals open-dashboard
"""

from evals.runner import run_panel

__all__ = ["run_panel"]
