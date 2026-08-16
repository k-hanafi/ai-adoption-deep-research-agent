"""Filesystem paths for the eval harness."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALS_PACKAGE_DIR = Path(__file__).resolve().parent
PANEL_DIR = EVALS_PACKAGE_DIR / "panel"
CONFIGS_DIR = EVALS_PACKAGE_DIR / "configs"

# Standalone artifact root: archive + per-arm runs live under evals/.
EVAL_INSTANCES_DIR = EVALS_PACKAGE_DIR / "instances"
LANDING_INDEX_PATH = EVAL_INSTANCES_DIR / "index.html"
EVAL_RUNS_DIR = EVALS_PACKAGE_DIR / "runs"

# Tiny fixture used until Anchor / tuning panel membership is frozen.
FIXTURE_PANEL_PATH = PANEL_DIR / "fixture_panel.json"
TUNING_PANEL_PATH = PANEL_DIR / "tuning_panel.json"
# PCS (then SGS/UAS) hill-climb set. Disjoint from tuning-50. Not bake-off.
HILLCLIMB_PANEL_PATH = PANEL_DIR / "hillclimb_panel.json"
# PCS high confirmation set. Disjoint from tuning-50 and hill-climb 20. Not bake-off.
PCS_CONFIRM_PANEL_PATH = PANEL_DIR / "pcs_confirm_panel.json"
# SGS skip-rate set: March none/low only. Disjoint from the three panels above. Not bake-off.
SGS_SKIP_PANEL_PATH = PANEL_DIR / "sgs_skip_panel.json"
TUNING_CONFIGS_DIR = CONFIGS_DIR / "tuning"
# Frozen March Stage 2 dump for panel rebuilds (local copy, not in git).
# Do not point this at legacy_agent_march_2026/.
MARCH_STAGE2_JSONL = (
    EVALS_PACKAGE_DIR / "references" / "march_2026_production.jsonl"
)

# Mean $/company feasibility cutoff for tuning (drop arms above this).
COST_CONSTRAINT_USD = 0.105

# Hard abort for a single paid Stage A / Stage B matrix (not the unit-cost target).
MAX_USD_PER_TUNING_RUN = 50.0

KINDS = ("tuning", "benchmark", "verification")
KIND_LABELS = {
    "tuning": "Tuning",
    "benchmark": "Benchmark",
    "verification": "Verification",
}
