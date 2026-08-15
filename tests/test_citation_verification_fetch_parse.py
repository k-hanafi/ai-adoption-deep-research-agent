"""Tests for Perplexity fetch_url parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_execute_fetch_retries_timeout_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from citation_verification.fetch import FetchResult, execute_fetch

    calls = {"n": 0}

    def _once(url: str, **_kwargs: object) -> FetchResult:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("Request timed out.")
        return FetchResult(
            url=url,
            title="About",
            snippet="Python is a programming language used by millions of developers worldwide.",
            cost_usd=0.001,
        )

    monkeypatch.setattr(
        "citation_verification.fetch._execute_fetch_once",
        _once,
    )
    result = execute_fetch("https://www.python.org/about/")
    assert calls["n"] == 2
    assert result.ok is True
    assert "Python" in result.snippet


def test_execute_fetch_sums_retry_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from citation_verification.fetch import FetchResult, execute_fetch

    calls = {"n": 0}

    def _once(url: str, **_kwargs: object) -> FetchResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return FetchResult(
                url=url,
                title="",
                snippet="",
                cost_usd=0.001,
                error="no fetch_url_results contents",
            )
        return FetchResult(
            url=url,
            title="About",
            snippet="Python is a programming language used by millions of developers worldwide.",
            cost_usd=0.002,
        )

    monkeypatch.setattr(
        "citation_verification.fetch._execute_fetch_once",
        _once,
    )
    result = execute_fetch("https://www.python.org/about/")
    assert calls["n"] == 2
    assert result.ok is True
    assert result.attempts == 2
    assert result.cost_usd == pytest.approx(0.003)


def test_empty_fetch_error_is_retryable() -> None:
    from citation_verification.fetch import FetchResult, _is_retryable_fetch

    empty = FetchResult(
        url="https://example.com/x",
        title="",
        snippet="",
        cost_usd=0.0,
        error="no fetch_url_results contents",
    )
    wrong_page = FetchResult(
        url="https://example.com/",
        title="Instant Vehicle MOT Status Lookup",
        snippet="An annual test that checks whether your vehicle meets road safety standards.",
        cost_usd=0.001,
        error=None,
    )
    assert _is_retryable_fetch(empty) is True
    assert _is_retryable_fetch(wrong_page) is False


def test_parse_fetch_url_row_mismatch_does_not_take_contents_zero() -> None:
    payload = load_fixture(str(FIXTURES / "citation_fetch_url_mismatch.json"))
    result = parse_fetch_response(
        payload,
        requested_url="https://example.com/careers",
    )
    assert result.ok is False
    assert result.error == "fetch_url_row_mismatch"
    assert "Copilot" not in result.snippet
    assert "MOT" not in result.snippet


def test_parse_fetch_tool_error_snippet_is_not_ok() -> None:
    payload = load_fixture(str(FIXTURES / "citation_fetch_tool_error.json"))
    result = parse_fetch_response(
        payload,
        requested_url="https://this-domain-does-not-exist.invalid/page",
    )
    assert result.ok is False
    assert result.error == "fetch_url returned no page content"
    assert "no content could be retrieved" in result.snippet
