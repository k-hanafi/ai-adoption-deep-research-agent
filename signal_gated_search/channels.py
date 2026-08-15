"""SGS channel ids and frozen scout/dig defaults."""

from __future__ import annotations

CHANNEL_IDS = ("jobs", "owned", "third_party")

# Presence bins the scout prompt allows. Code maps bin → confidence → signal.
EVIDENCE_BINS = ("none", "weak", "moderate", "strong")
BIN_CONFIDENCE = {
    "none": 0.0,
    "weak": 0.35,
    "moderate": 0.65,
    "strong": 0.90,
}

DEFAULT_SIGNAL_THRESHOLD = 0.5
DEFAULT_SCOUT_PRESET = "low"
DEFAULT_SCOUT_MAX_STEPS = 2

DEFAULT_DIG_MODEL = "openai/gpt-5.6-luna"
DEFAULT_DIG_MAX_STEPS = 50
DEFAULT_DIG_WEB_SEARCH_DEPTH = "medium"
DEFAULT_DIG_EFFORT = "high"
# Count still decides how many rooms to dig. Every dig uses the same effort.
DIG_EFFORT_BY_COUNT = {
    1: DEFAULT_DIG_EFFORT,
    2: DEFAULT_DIG_EFFORT,
    3: DEFAULT_DIG_EFFORT,
}


def dig_config_label(reasoning_effort: str) -> str:
    """Stable ledger label for one dig (explicit knobs, not a stock preset)."""
    model_tag = DEFAULT_DIG_MODEL.rsplit("/", 1)[-1].replace(".", "_")
    return (
        f"{model_tag}_steps{DEFAULT_DIG_MAX_STEPS}_"
        f"{reasoning_effort}_search_{DEFAULT_DIG_WEB_SEARCH_DEPTH}"
    )

# Unused for dig selection (dig-all signaled). Kept for traces / Top-1 ablation.
DEFAULT_CHANNEL_PRIOR = {
    "owned": 1.0,
    "jobs": 0.8,
    "third_party": 0.6,
}

# Legacy stub-runner labels (not bake-off defaults).
DEFAULT_DIG_PRESET = "medium"
DEFAULT_RESCUE_DIG_PRESET = "low"
