"""Confirm-medium runner: 429 from error field, resume skips only success."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "stage2"
    / "test_runs"
    / "pcs_confirm_20_medium"
    / "run_twenty_medium.py"
)


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location(
        "pcs_confirm_medium_runner", RUNNER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rate_limit_ignores_cost_and_url_substrings(runner) -> None:
    success = {
        "error": None,
        "cost_usd": 0.1429,
        "findings": [
            {
                "source_url": (
                    "https://www.linkedin.com/jobs/view/"
                    "founding-ml-engineer-4299954127"
                )
            }
        ],
    }
    assert runner._is_rate_limit(success.get("error")) is False
    assert runner._is_retryable(success.get("error")) is False
    assert runner._is_complete_success(success) is True


def test_rate_limit_reads_real_error_strings(runner) -> None:
    err = (
        "owned: RateLimitError: Error code: 429 - "
        "{'error': {'message': 'Request rate limit exceeded, please try again later.'}}"
    )
    assert runner._is_rate_limit(err) is True
    assert runner._is_retryable(err) is True
    assert runner._retry_kind(err) == "429"


def test_timeout_is_retryable_without_matching_429(runner) -> None:
    err = "jobs: APITimeoutError: Request timed out."
    assert runner._is_rate_limit(err) is False
    assert runner._is_timeout(err) is True
    assert runner._is_retryable(err) is True
    assert runner._retry_kind(err) == "timeout"


def test_confirm_medium_defaults_to_five_workers(runner) -> None:
    assert runner.WORKERS == 5


def test_resume_skips_only_error_free_json(runner) -> None:
    assert runner._is_complete_success({"error": None, "findings_count": 5}) is True
    assert runner._is_complete_success({"error": None}) is True
    assert runner._is_complete_success(
        {"error": "APITimeoutError: Request timed out.", "cost_usd": 0}
    ) is False
    assert runner._is_complete_success(None) is False
    assert runner._is_complete_success({}) is False
