"""Architecture registry: kebab-case CLI keys → importable packages."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Callable

from contracts.types import ArchitectureResult, CompanyInput


@dataclass(frozen=True)
class ArchitectureSpec:
    cli_key: str
    full_name: str
    package: str
    short_alias: str


ARCHITECTURES: dict[str, ArchitectureSpec] = {
    "parallel-channel-search": ArchitectureSpec(
        cli_key="parallel-channel-search",
        full_name="Parallel Channel Search",
        package="parallel_channel_search",
        short_alias="pcs",
    ),
    "signal-gated-search": ArchitectureSpec(
        cli_key="signal-gated-search",
        full_name="Signal Gated Search",
        package="signal_gated_search",
        short_alias="sgs",
    ),
    "unified-adaptive-search": ArchitectureSpec(
        cli_key="unified-adaptive-search",
        full_name="Unified Adaptive Search",
        package="unified_adaptive_search",
        short_alias="uas",
    ),
}

ALIASES: dict[str, str] = {
    spec.short_alias: spec.cli_key for spec in ARCHITECTURES.values()
}


def resolve_architecture(key: str) -> ArchitectureSpec:
    normalized = key.strip().lower()
    if normalized in ALIASES:
        normalized = ALIASES[normalized]
    if normalized not in ARCHITECTURES:
        known = ", ".join(sorted(ARCHITECTURES) + sorted(ALIASES))
        raise ValueError(f"Unknown architecture {key!r}. Choose one of: {known}")
    return ARCHITECTURES[normalized]


def load_runner(cli_key: str) -> Callable[..., ArchitectureResult]:
    spec = resolve_architecture(cli_key)
    module = import_module(f"{spec.package}.runner")
    run_fn = getattr(module, "run")
    return run_fn


def run_company(
    architecture: str,
    company: CompanyInput | dict[str, Any],
    **kwargs: Any,
) -> ArchitectureResult:
    run_fn = load_runner(architecture)
    return run_fn(company, **kwargs)
