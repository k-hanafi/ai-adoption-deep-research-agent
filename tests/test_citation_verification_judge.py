"""Offline tests for OpenAI judge request shape and response parse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citation_verification import config
from citation_verification.judge import (
    JudgeParseError,
    build_judge_request,
    format_judge_input,
    load_judge_prompt,
    parse_judge_response,
)
from citation_verification.schema import JUDGE_JSON_SCHEMA, JUDGE_SCHEMA_NAME

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_judge_schema_excludes_log_probs_conf() -> None:
    props = JUDGE_JSON_SCHEMA["properties"]
    assert "verification" in props
    assert "confidence_1_5" in props
    assert "verification_reasoning" in props
    assert "verification_critique" in props
    assert "log_probs_conf" not in props
    assert set(JUDGE_JSON_SCHEMA["required"]) == set(props)


def test_build_judge_request_logprob_knobs() -> None:
    req = build_judge_request(
        claim="Uses Copilot for PR review",
        source_url="https://example.com/careers",
        snippet="Our engineers use GitHub Copilot when reviewing pull requests.",
    )
    assert req["model"] == config.JUDGE_MODEL
    assert req["reasoning"] == {"effort": "none"}
    assert req["top_logprobs"] == config.JUDGE_TOP_LOGPROBS
    assert req["include"] == list(config.LOGPROB_INCLUDE)
    assert req["store"] is False
    text_fmt = req["text"]["format"]
    assert text_fmt["type"] == "json_schema"
    assert text_fmt["strict"] is True
    assert text_fmt["name"] == JUDGE_SCHEMA_NAME
    assert "log_probs_conf" not in text_fmt["schema"]["properties"]
    assert "Uses Copilot for PR review" in req["input"]
    assert "https://example.com/careers" in req["input"]
    assert "GitHub Copilot" in req["input"]
    prompt = load_judge_prompt()
    assert "verification = 1" in prompt
    assert "distinctive name" in prompt
    assert "untrusted data" in prompt.lower()
    assert req["instructions"] == prompt


def test_format_judge_input_sections() -> None:
    text = format_judge_input(
        claim="Uses Claude",
        source_url="https://example.com/x",
        snippet="We use Claude for coding.",
    )
    assert text.startswith("CLAIM:\n")
    assert "SOURCE_URL:\nhttps://example.com/x" in text
    assert "PAGE_SNIPPET:\nWe use Claude for coding." in text


def test_parse_judge_ok_fixture() -> None:
    payload = json.loads(
        (FIXTURES / "citation_judge_ok.json").read_text(encoding="utf-8")
    )
    result = parse_judge_response(payload)
    assert result.verification == 1
    assert result.confidence_1_5 == 4
    assert "Copilot" in result.verification_reasoning
    assert result.verification_critique
    # 200 in * $2/M + 80 out * $12/M
    assert result.cost_usd == pytest.approx(0.0004 + 0.00096)
    assert result.model == "gpt-5.6-terra"


def test_parse_judge_prefers_explicit_total_cost() -> None:
    payload = {
        "model": "gpt-5.6-terra",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "verification": 0,
                                "confidence_1_5": 2,
                                "verification_reasoning": "No support in snippet.",
                                "verification_critique": "Snippet is thin.",
                            }
                        ),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 1000,
            "cost": {"total_cost": 0.42},
        },
    }
    assert parse_judge_response(payload).cost_usd == pytest.approx(0.42)


def test_parse_rejects_bad_verification() -> None:
    payload = {
        "model": "gpt-5.6-terra",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "verification": 2,
                                "confidence_1_5": 3,
                                "verification_reasoning": "x",
                                "verification_critique": "y",
                            }
                        ),
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    with pytest.raises(JudgeParseError) as caught:
        parse_judge_response(payload)
    # 100*$2/M + 50*$12/M = 0.0002 + 0.0006
    assert caught.value.cost_usd == pytest.approx(0.0008)
