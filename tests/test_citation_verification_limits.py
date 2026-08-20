"""Offline tests for adaptive API limiters. No paid calls."""

from __future__ import annotations

import time

import pytest

from citation_verification import config
from citation_verification.limits import (
    AdaptiveLimiter,
    call_with_429_retry,
    fetch_limiter,
    is_rate_limit_error,
    reset_limiters,
    retry_after_seconds,
)


class _RateLimit(Exception):
    status_code = 429


class _Timeout(Exception):
    pass


def test_is_rate_limit_ignores_cost_substring() -> None:
    assert is_rate_limit_error(_RateLimit("429 Too Many Requests"))
    assert is_rate_limit_error(RuntimeError("RateLimitError: retry later"))
    assert is_rate_limit_error(RuntimeError("Client error '429 Too Many Requests'"))
    assert not is_rate_limit_error(RuntimeError("cost_usd=0.1429"))
    assert not is_rate_limit_error(TimeoutError("Request timed out."))


def test_retry_after_header_wins() -> None:
    class _Resp:
        headers = {"Retry-After": "3.5"}

    class _Exc(Exception):
        response = _Resp()

    assert retry_after_seconds(_Exc("429"), 0) == 3.5
    assert retry_after_seconds(RuntimeError("429"), 3) == 8.0


def test_aimd_climbs_then_halves() -> None:
    limiter = AdaptiveLimiter(
        "test",
        start=4,
        min_cap=2,
        max_cap=8,
        climb_every=2,
    )
    limiter.record_ok()
    assert limiter.cap == 4
    limiter.record_ok()
    assert limiter.cap == 5
    limiter.record_429()
    assert limiter.cap == 2
    assert limiter.n_429 == 1


def test_call_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_limiters()
    slept: list[float] = []
    monkeypatch.setattr(
        "citation_verification.limits.time.sleep",
        lambda seconds: slept.append(float(seconds)),
    )
    limiter = AdaptiveLimiter(
        "test",
        start=4,
        min_cap=1,
        max_cap=8,
        climb_every=99,
    )
    calls = {"n": 0}

    def _fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _RateLimit("http 429")
        return "ok"

    assert call_with_429_retry(_fn, limiter=limiter, retries=4) == "ok"
    assert calls["n"] == 3
    assert len(slept) == 2
    assert limiter.n_429 == 2
    assert limiter.in_flight == 0
    assert limiter.cap == 1


def test_call_gives_up_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("citation_verification.limits.time.sleep", lambda _s: None)
    limiter = AdaptiveLimiter("test", start=4, min_cap=1, max_cap=8, climb_every=99)

    def _fn() -> None:
        raise _RateLimit("http 429")

    with pytest.raises(_RateLimit):
        call_with_429_retry(_fn, limiter=limiter, retries=2)
    assert limiter.n_429 == 3
    assert limiter.in_flight == 0


def test_non_429_raises_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(
        "citation_verification.limits.time.sleep",
        lambda seconds: slept.append(float(seconds)),
    )
    limiter = AdaptiveLimiter("test", start=4, min_cap=1, max_cap=8, climb_every=99)

    def _fn() -> None:
        raise _Timeout("Request timed out.")

    with pytest.raises(_Timeout):
        call_with_429_retry(_fn, limiter=limiter, retries=4)
    assert slept == []
    assert limiter.n_429 == 0
    assert limiter.cap == 4


def test_fetch_doors_start_near_tier3_not_at_twelve() -> None:
    assert config.VERIFY_POOL_DEFAULT == 256
    assert config.FETCH_LIMIT_START == 200
    assert config.FETCH_LIMIT_MAX == 800
    assert config.FETCH_LIMIT_CLIMB_EVERY == 2
    assert config.JUDGE_LIMIT_START == 80
    assert config.JUDGE_LIMIT_MAX == 256
    assert config.TAVILY_LIMIT_MAX == 24
    assert config.FETCH_STARTS_PER_MIN == 900


def test_fetch_reaches_high_cap_without_9k_successes() -> None:
    """A 2k probe must be able to sit at hundreds in-flight, not climb from 12."""
    reset_limiters()
    limiter = fetch_limiter()
    assert limiter.cap == config.FETCH_LIMIT_START
    target = min(config.FETCH_LIMIT_START + 40, config.FETCH_LIMIT_MAX)
    steps = target - limiter.cap
    for _ in range(steps * config.FETCH_LIMIT_CLIMB_EVERY):
        limiter.record_ok()
    assert limiter.cap == target
    assert steps * config.FETCH_LIMIT_CLIMB_EVERY < 200
    reset_limiters()


def test_start_pacer_spaces_acquires() -> None:
    limiter = AdaptiveLimiter(
        "test",
        start=8,
        min_cap=1,
        max_cap=8,
        climb_every=99,
        pace_per_sec=40,
    )
    t0 = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.08
    for _ in range(5):
        limiter.release()


def test_acquire_counts_starts_for_rpm_logs() -> None:
    limiter = AdaptiveLimiter("test", start=2, min_cap=1, max_cap=4, climb_every=99)
    limiter.acquire()
    limiter.acquire()
    snap = limiter.snapshot()
    assert snap["n_calls"] == 2
    assert snap["in_flight"] == 2
    limiter.release()
    limiter.release()
