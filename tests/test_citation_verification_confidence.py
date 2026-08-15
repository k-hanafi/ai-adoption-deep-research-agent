"""Offline tests for verification logprob extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citation_verification.confidence import (
    BinaryConfidenceUnavailable,
    extract_binary_confidence,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_extract_verification_one() -> None:
    conf = extract_binary_confidence(_load("citation_verification_one.json"))
    assert conf.verification == 1
    assert conf.log_probs_conf == pytest.approx(0.97, rel=1e-6)
    assert conf.censored is False
    assert conf.margin == pytest.approx(abs(2 * conf.p_one - 1))


def test_extract_verification_zero() -> None:
    conf = extract_binary_confidence(_load("citation_verification_zero.json"))
    assert conf.verification == 0
    assert conf.log_probs_conf == pytest.approx(0.97, rel=1e-6)


def test_extract_censored_within_bound() -> None:
    conf = extract_binary_confidence(_load("citation_verification_censored.json"))
    assert conf.verification == 1
    assert conf.censored is True
    assert conf.interval_width <= 0.05
