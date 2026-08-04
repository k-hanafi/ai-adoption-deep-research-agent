"""SGS channel ids and March-informed priors (plan §3.2)."""

from __future__ import annotations

CHANNEL_IDS = ("jobs", "owned", "third_party")

# Default prior: owned > jobs > third_party (March company-level presence).
DEFAULT_CHANNEL_PRIOR = {
    "owned": 1.0,
    "jobs": 0.8,
    "third_party": 0.6,
}

DEFAULT_SCOUT_PRESET = "fast"
DEFAULT_DIG_PRESET = "medium"
DEFAULT_RESCUE_DIG_PRESET = "low"
