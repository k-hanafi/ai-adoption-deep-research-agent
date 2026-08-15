"""Tests for Perplexity fetch_url parsing."""

from __future__ import annotations

from pathlib import Path

from citation_verification.fetch import build_fetch_request, load_fixture, parse_fetch_response

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_build_fetch_request_targets_url() -> None:
    req = build_fetch_request("https://example.com/careers")
    assert req["tools"] == [{"type": "fetch_url", "max_urls": 1}]
    assert "https://example.com/careers" in req["input"]
    assert req["max_steps"] >= 1


def test_parse_fetch_ok_fixture() -> None:
    payload = load_fixture(str(FIXTURES / "citation_fetch_ok.json"))
    result = parse_fetch_response(payload, requested_url="https://example.com/careers")
    assert result.ok is True
    assert result.error is None
    assert "Copilot" in result.snippet
    assert result.cost_usd == 0.0003


def test_parse_fetch_empty_is_not_ok() -> None:
    payload = load_fixture(str(FIXTURES / "citation_fetch_empty.json"))
    result = parse_fetch_response(payload, requested_url="https://example.com/missing")
    assert result.ok is False
    assert result.error is not None
