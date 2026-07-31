"""Standalone eval harness for the three Stage 2 architecture packages.

Locked CLI product trio:
  python -m evals run-evals <architecture>
  python -m evals cost-preview <architecture>
  python -m evals open-dashboard
"""

from evals.runner import run_panel

__all__ = ["run_panel"]
