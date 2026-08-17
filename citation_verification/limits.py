"""Adaptive in-flight caps for Perplexity fetch and OpenAI judge.

Think of each limiter as a door that starts partway open. Successes nudge
it wider. A 429 slams it halfway shut. Callers wait at the door instead of
all rushing the API at once.
"""

from __future__ import annotations

import time
from threading import Condition, Lock, Semaphore
from typing import Any, Optional

from citation_verification import config


def is_rate_limit_error(exc: BaseException) -> bool:
    """True for HTTP 429 / RateLimitError. Do not match cost substrings like 0.1429."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    if status == 429:
        return True
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    text = str(exc).lower()
    return (
        "rate limit" in text
        or "ratelimit" in text
        or "too many requests" in text
        or "http 429" in text
        or "'429" in text
    )


def retry_after_seconds(exc: BaseException, attempt: int) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw:
        try:
            return min(config.RATE_LIMIT_SLEEP_CAP_SEC, max(0.1, float(raw)))
        except (TypeError, ValueError):
            pass
    return min(config.RATE_LIMIT_SLEEP_CAP_SEC, 2.0 ** attempt)


class AdaptiveLimiter:
    """AIMD cap: +1 after climb_every oks, halve on 429."""

    def __init__(
        self,
        name: str,
        *,
        start: int,
        min_cap: int,
        max_cap: int,
        climb_every: int = config.LIMIT_CLIMB_EVERY,
    ) -> None:
        if min_cap < 1 or max_cap < min_cap or start < min_cap or start > max_cap:
            raise ValueError(f"bad limiter bounds for {name}")
        self.name = name
        self.min_cap = min_cap
        self.max_cap = max_cap
        self.climb_every = max(1, climb_every)
        self._cap = start
        self._in_flight = 0
        self._ok_streak = 0
        self._n_429 = 0
        self._cond = Condition()

    @property
    def cap(self) -> int:
        with self._cond:
            return self._cap

    @property
    def in_flight(self) -> int:
        with self._cond:
            return self._in_flight

    @property
    def n_429(self) -> int:
        with self._cond:
            return self._n_429

    def acquire(self) -> None:
        with self._cond:
            while self._in_flight >= self._cap:
                self._cond.wait(timeout=0.25)
            self._in_flight += 1

    def release(self) -> None:
        with self._cond:
            if self._in_flight > 0:
                self._in_flight -= 1
            self._cond.notify_all()

    def record_ok(self) -> None:
        with self._cond:
            self._ok_streak += 1
            if self._ok_streak >= self.climb_every and self._cap < self.max_cap:
                self._cap += 1
                self._ok_streak = 0
                print(f"LIMIT {self.name} climb cap={self._cap}", flush=True)
            self._cond.notify_all()

    def record_429(self) -> None:
        with self._cond:
            self._n_429 += 1
            self._ok_streak = 0
            new_cap = max(self.min_cap, self._cap // 2)
            if new_cap < self._cap:
                print(
                    f"LIMIT {self.name} 429 backoff {self._cap}->{new_cap}",
                    flush=True,
                )
            self._cap = new_cap
            self._cond.notify_all()

    def snapshot(self) -> dict[str, int]:
        with self._cond:
            return {
                "cap": self._cap,
                "in_flight": self._in_flight,
                "n_429": self._n_429,
            }


_LOCK = Lock()
_FETCH: Optional[AdaptiveLimiter] = None
_JUDGE: Optional[AdaptiveLimiter] = None
_TAVILY: Optional[AdaptiveLimiter] = None
_BROWSER: Optional[Semaphore] = None


def reset_limiters() -> None:
    """Test helper. Live runs keep process-wide limiters."""
    global _FETCH, _JUDGE, _TAVILY, _BROWSER
    with _LOCK:
        _FETCH = None
        _JUDGE = None
        _TAVILY = None
        _BROWSER = None


def fetch_limiter() -> AdaptiveLimiter:
    global _FETCH
    with _LOCK:
        if _FETCH is None:
            _FETCH = AdaptiveLimiter(
                "perplexity_fetch",
                start=config.FETCH_LIMIT_START,
                min_cap=config.FETCH_LIMIT_MIN,
                max_cap=config.FETCH_LIMIT_MAX,
            )
        return _FETCH


def judge_limiter() -> AdaptiveLimiter:
    global _JUDGE
    with _LOCK:
        if _JUDGE is None:
            _JUDGE = AdaptiveLimiter(
                "openai_judge",
                start=config.JUDGE_LIMIT_START,
                min_cap=config.JUDGE_LIMIT_MIN,
                max_cap=config.JUDGE_LIMIT_MAX,
            )
        return _JUDGE


def tavily_limiter() -> AdaptiveLimiter:
    global _TAVILY
    with _LOCK:
        if _TAVILY is None:
            _TAVILY = AdaptiveLimiter(
                "tavily_extract",
                start=config.TAVILY_LIMIT_START,
                min_cap=config.TAVILY_LIMIT_MIN,
                max_cap=config.TAVILY_LIMIT_MAX,
            )
        return _TAVILY


def browser_slots() -> Semaphore:
    global _BROWSER
    with _LOCK:
        if _BROWSER is None:
            _BROWSER = Semaphore(config.BROWSER_LIMIT)
        return _BROWSER


def call_with_429_retry(func, *, limiter: AdaptiveLimiter, retries: int | None = None):
    """Run func() under the limiter. Retry 429s with backoff; then raise."""
    attempts = max(1, int(retries if retries is not None else config.RATE_LIMIT_RETRIES) + 1)
    last: Optional[BaseException] = None
    for attempt in range(attempts):
        limiter.acquire()
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001 - classify 429 vs other
            limiter.release()
            if not is_rate_limit_error(exc) or attempt == attempts - 1:
                if is_rate_limit_error(exc):
                    limiter.record_429()
                raise
            limiter.record_429()
            last = exc
            sleep_for = retry_after_seconds(exc, attempt)
            print(
                f"LIMIT {limiter.name} 429 retry {attempt + 1}/{attempts} "
                f"sleep={sleep_for:.1f}s",
                flush=True,
            )
            time.sleep(sleep_for)
            continue
        limiter.record_ok()
        limiter.release()
        return result
    assert last is not None
    raise last


def limiter_status() -> dict[str, Any]:
    return {
        "perplexity_fetch": fetch_limiter().snapshot(),
        "openai_judge": judge_limiter().snapshot(),
        "tavily_extract": tavily_limiter().snapshot(),
    }
