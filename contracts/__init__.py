"""Shared result contracts for architecture packages and the eval harness.

Keeps Finding fields and the component cost ledger aligned across
Parallel Channel Search, Signal Gated Search, and Unified Adaptive Search.
"""

from contracts.types import (
    ArchitectureResult,
    CompanyInput,
    CostComponent,
    CostLedger,
    Finding,
)

__all__ = [
    "ArchitectureResult",
    "CompanyInput",
    "CostComponent",
    "CostLedger",
    "Finding",
]
