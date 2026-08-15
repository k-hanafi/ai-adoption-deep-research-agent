"""Offline tests for backup fetch parse and browser skip."""

from __future__ import annotations

from citation_verification import config
from citation_verification.backup_fetch import (
    execute_browser_fetch,
    execute_backup_chain,
    _html_to_text,
    _parse_tavily_extract,
)


def test_tavily_extract_parse_keeps_iana_text() -> None:
    payload = {
        "results": [
            {
                "url": "https://example.com/",
                "title": "Example Domain",
                "raw_content": (
                    "This domain is for use in illustrative examples in documents. "
                    "You may use this domain in literature without prior coordination."
                ),
            }
        ]
    }
    result = _parse_tavily_extract(payload, requested_url="https://example.com/")
    assert result.ok is True
    assert result.source == config.FETCH_SOURCE_TAVILY
    assert "illustrative examples" in result.snippet
    assert result.title == "Example Domain"


def test_tavily_extract_empty_is_not_ok() -> None:
    result = _parse_tavily_extract(
        {"results": [], "failed_results": [{"error": "timeout"}]},
        requested_url="https://example.com/x",
    )
    assert result.ok is False
    assert "tavily extract empty" in (result.error or "")


def test_html_to_text_drops_script() -> None:
    html = "<html><script>alert(1)</script><p>Hello Copilot users</p></html>"
    text = _html_to_text(html)
    assert "Copilot" in text
    assert "alert" not in text


def test_browser_skipped_unless_enabled(monkeypatch) -> None:
    monkeypatch.delenv("CITATION_VERIFICATION_BROWSER", raising=False)
    result = execute_browser_fetch("https://example.com/")
    assert result.ok is False
    assert result.source == config.FETCH_SOURCE_BROWSER
    assert "not enabled" in (result.error or "")


def test_backup_chain_uses_httpx_when_tavily_empty(monkeypatch) -> None:
    from citation_verification.fetch import FetchResult

    monkeypatch.setattr(
        "citation_verification.backup_fetch.execute_tavily_extract",
        lambda url, **_: FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.001,
            error="tavily extract empty",
            source=config.FETCH_SOURCE_TAVILY,
        ),
    )
    monkeypatch.setattr(
        "citation_verification.backup_fetch.execute_httpx_fetch",
        lambda url: FetchResult(
            url=url,
            title="Example Domain",
            snippet=(
                "This domain is for use in illustrative examples in documents. "
                "You may use this domain in literature without prior coordination."
            ),
            cost_usd=0.0,
            source=config.FETCH_SOURCE_HTTPX,
        ),
    )
    result = execute_backup_chain("https://example.com/")
    assert result.ok is True
    assert result.source == config.FETCH_SOURCE_HTTPX
    assert result.cost_usd == 0.001
    assert result.attempts >= 2
