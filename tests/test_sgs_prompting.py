"""SGS prompt compose + request kwargs (no API)."""

from __future__ import annotations

from contracts.types import CompanyInput
from parallel_channel_search.prompting import RESPONSE_SCHEMA
from signal_gated_search.agent_call import (
    build_dig_request_kwargs,
    build_scout_request_kwargs,
    request_snapshot,
)
from signal_gated_search.prompting import (
    DIG_RESPONSE_SCHEMA,
    SCOUT_RESPONSE_SCHEMA,
    build_dig_prompt,
    build_scout_prompt,
)

COMPANY = CompanyInput(
    rcid=610194,
    name="Jam",
    homepage_url="https://jam.dev",
    short_description="A test company",
)


def test_scout_prompt_is_presence_not_adoption() -> None:
    text = build_scout_prompt(COMPANY, "jobs")
    assert "Jam" in text
    assert "presence detector" in text.lower()
    assert "Set \"channel\" to \"jobs\"" in text
    assert "GitHub Copilot" not in text


def test_dig_prompt_is_pcs_extract_plus_presence_note() -> None:
    text = build_dig_prompt(COMPANY, "owned")
    assert "Jam" in text
    assert "Presence is not adoption" in text
    assert "Our AI platform helps enterprises automate workflows" in text
    assert "company-controlled" in text.lower()


def test_owned_scout_counts_official_accounts_without_homepage() -> None:
    text = build_scout_prompt(COMPANY, "owned")
    assert "HOMEPAGE IS IDENTITY, NOT A GATE" in text
    assert "Do not emit evidence_bin none solely because the homepage was not retrieved." in text
    assert "Official company accounts" in text
    assert "YouTube or Vimeo channel" in text
    assert "A live official account is enough even when the website is down" in text


def test_owned_dig_searches_official_accounts() -> None:
    text = build_dig_prompt(COMPANY, "owned")
    assert "The homepage does not have to load." in text
    assert "YouTube or Vimeo channel" in text
    assert "The company's own YouTube/LinkedIn/GitHub is owned-shaped" in text
    assert "Prefer leaving wire hosts, independent news, platform podcasts, YouTube, and vendor case studies to third_party" not in text


def test_third_party_does_not_claim_company_youtube() -> None:
    scout = build_scout_prompt(COMPANY, "third_party")
    assert "Official company LinkedIn / YouTube / GitHub / X accounts are owned" in scout
    dig = build_dig_prompt(COMPANY, "third_party")
    assert "The company's own channel is owned-shaped" in dig
    assert "Default YouTube/conference video to this room unless the page lives on the company domain" not in dig


def test_dig_schema_matches_pcs() -> None:
    assert DIG_RESPONSE_SCHEMA is RESPONSE_SCHEMA


def test_scout_schema_has_bins_not_signal() -> None:
    props = SCOUT_RESPONSE_SCHEMA["json_schema"]["schema"]["properties"]
    assert "evidence_bin" in props
    assert "signal" not in props
    assert "confidence" not in props


def test_scout_request_uses_fast_preset_no_fetch() -> None:
    kwargs = build_scout_request_kwargs(COMPANY, "third_party")
    assert kwargs["preset"] == "fast"
    assert "model" not in kwargs
    assert kwargs["response_format"] is SCOUT_RESPONSE_SCHEMA
    tools = kwargs["tools"]
    assert tools == [{"type": "web_search"}]
    snap = request_snapshot(kwargs)
    assert snap["has_preset"] is True
    assert snap["has_response_format"] is True
    assert snap["input_chars"] > 0


def test_dig_request_is_cold_start_explicit_knobs() -> None:
    kwargs = build_dig_request_kwargs(
        COMPANY, "jobs", reasoning_effort="max"
    )
    assert "preset" not in kwargs
    assert kwargs["model"] == "openai/gpt-5.6-luna"
    assert kwargs["max_steps"] == 10
    assert kwargs["reasoning"] == {"effort": "max"}
    assert kwargs["response_format"] is DIG_RESPONSE_SCHEMA
    tool_types = [t["type"] for t in kwargs["tools"]]
    assert tool_types == ["web_search", "fetch_url"]
    # Cold start: company identity in the prompt, no scout URL block.
    assert "https://jobs.example.com" not in kwargs["input"]
    assert "Jam" in kwargs["input"]


def test_unknown_channel_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown SGS channel"):
        build_scout_prompt(COMPANY, "careers")
