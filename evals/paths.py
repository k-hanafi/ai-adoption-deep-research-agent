"""Filesystem paths for the eval harness."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALS_PACKAGE_DIR = Path(__file__).resolve().parent
PANEL_DIR = EVALS_PACKAGE_DIR / "panel"
CONFIGS_DIR = EVALS_PACKAGE_DIR / "configs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EVAL_RUNS_DIR = OUTPUTS_DIR / "evals" / "runs"
PRESENTATION_DIR = PROJECT_ROOT / "presentation"
EVAL_INSTANCES_DIR = PRESENTATION_DIR / "eval_instances"
LANDING_INDEX_PATH = EVAL_INSTANCES_DIR / "index.html"

# Tiny fixture used until Anchor Panel v1 membership is frozen.
FIXTURE_PANEL_PATH = PANEL_DIR / "fixture_panel.json"
