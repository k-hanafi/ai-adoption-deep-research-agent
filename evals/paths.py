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
TUNING_CONFIGS_DIR = CONFIGS_DIR / "tuning"

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
