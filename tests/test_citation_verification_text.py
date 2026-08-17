"""Offline tests for chrome-strip, chunks, anchors, and combine rules."""

from __future__ import annotations

from citation_verification import config
from citation_verification.text import (
    cap_snippet,
    chunk_text,
    combine_chunk_verdicts,
    extract_anchors,
    looks_document_mismatch,
    looks_job_listings_rail,
    looks_thin_watch_page,
    missing_anchors,
    select_windows,
    strip_chrome,
    unread_reason,
)


def test_chrome_strip_keeps_late_claim_under_old_12k_cut() -> None:
    chrome = "div\nRelated Resources\nSubscribe to our newsletter\n"
    late = "Jagan Reddy uses AI constantly for asking questions in a chat window."
    padded = chrome + ("Related posts\n" * 200) + ("filler sidebar nav\n" * 800) + late
    assert len(padded) > 12_000
    kept, truncated = cap_snippet(padded)
    assert "Jagan Reddy" in kept
    assert "uses AI constantly" in kept
    assert not kept.startswith("div")
    assert "Related Resources" not in kept.splitlines()[0]
    assert truncated is False or len(kept) <= config.MAX_SNIPPET_CHARS


def test_cap_is_32000_after_strip_not_12000() -> None:
    body = ("Banana farmers export fruit worldwide. " * 400) + "GitHub Copilot"
    assert 12_000 < len(body) < 32_000
    kept, truncated = cap_snippet(body)
    assert truncated is False
    assert "GitHub Copilot" in kept
    assert config.MAX_SNIPPET_CHARS == 32_000


def test_chunk_late_quote_is_selected() -> None:
    head = "A" * 13_000
    quote = "The author uses AI constantly for asking questions and receiving answers."
    page = head + quote
    windows = select_windows(page, quote)
    assert any("uses AI constantly" in window for window in windows)


def test_select_windows_keeps_late_paraphrase_when_names_absent() -> None:
    claim = "Jagan Reddy uses GitHub Copilot for pull-request review."
    late = "The founder uses an AI coding assistant on every pull request."
    page = ("Welcome to the company blog. " * 400) + late
    assert "Jagan" not in page
    assert "Copilot" not in page
    windows = select_windows(page, claim)
    assert any("AI coding assistant" in window for window in windows)
    assert len(windows) > 1


def test_combine_any_one_wins() -> None:
    value, error = combine_chunk_verdicts([0, 1, 0])
    assert value == 1
    assert error is None


def test_combine_all_zero_is_zero() -> None:
    value, error = combine_chunk_verdicts([0, 0])
    assert value == 0
    assert error is None


def test_combine_empty_windows_is_null() -> None:
    value, error = combine_chunk_verdicts([])
    assert value is None
    assert error == "judge produced no usable window"


def test_extract_anchors_keeps_names_not_stopwords() -> None:
    anchors = extract_anchors(
        "RightRev founder and CEO Jagan Reddy describes using AI constantly."
    )
    joined = " ".join(anchors)
    assert "Jagan Reddy" in joined or "Jagan" in anchors
    assert "RightRev" in anchors
    assert "using" not in [item.lower() for item in anchors]


def test_missing_anchors_detects_absent_name() -> None:
    snippet = "The author uses AI constantly for asking questions."
    missing = missing_anchors(snippet, ["Jagan Reddy"])
    assert missing == ["Jagan Reddy"]


def test_chunk_overlap_covers_boundary() -> None:
    text = ("word " * 800) + "UNIQUEANCHOR " + ("tail " * 200)
    windows = chunk_text(text, size=2500, overlap=500)
    assert len(windows) >= 2
    assert any("UNIQUEANCHOR" in window for window in windows)


def test_example_mot_is_document_mismatch() -> None:
    assert looks_document_mismatch(
        "https://example.com/",
        "Instant Vehicle MOT Status Lookup",
        "An annual test that checks whether your vehicle meets road safety standards.",
    )
    assert not looks_document_mismatch(
        "https://example.com/",
        "Example Domain",
        "This domain is for use in illustrative examples in documents.",
    )


def test_strip_chrome_drops_cookie_and_skip_nav() -> None:
    text = "Skip to main content\nAccept all cookies\nWe use Copilot for pull requests every day."
    assert "Copilot" in strip_chrome(text)
    assert "Accept all cookies" not in strip_chrome(text)


def test_linkedin_listings_rail_is_unread() -> None:
    url = (
        "https://www.linkedin.com/jobs/view/"
        "sales-development-representative-at-k1x-inc-4424441175"
    )
    snippet = (
        "Similar jobs\n"
        "### Data Scientist Intern\n#### Tinder\n"
        "### ML Engineer\n#### Netflix\n"
        "People also viewed\n"
        "Get notified about new Artificial Intelligence Engineer jobs\n"
    )
    assert looks_job_listings_rail(url, snippet, company_name="K1x")
    assert unread_reason(url, "Sales Development Representative", snippet, company_name="K1x") == (
        config.ERROR_LISTINGS_RAIL
    )
    real_job = "K1x is hiring a Sales Development Representative to use Clay and Gong."
    assert not looks_job_listings_rail(url, real_job, company_name="K1x")


def test_thin_youtube_intro_is_unread() -> None:
    url = "https://www.youtube.com/watch?v=2dUAlrrSnSg"
    snippet = "How We Actually Use AI at Tern\nWelcome everyone. Related videos\nComments\n"
    assert looks_thin_watch_page(url, snippet)
    assert unread_reason(url, "How We Actually Use AI at Tern", snippet) == (
        config.ERROR_THIN_SNIPPET
    )
    transcript = "Claude turns Zoom recordings into case studies. " * 40
    assert not looks_thin_watch_page(url, transcript)
