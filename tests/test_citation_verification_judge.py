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
    assert "lenient" in prompt.lower()
    assert "paraphrase" in prompt.lower()
    assert "sells or markets" in prompt
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
    # 200 in * $0.20/M + 80 out * $1.20/M
    assert result.cost_usd == pytest.approx(0.00004 + 0.000096)
    assert result.model == config.JUDGE_MODEL


def test_parse_judge_prefers_explicit_total_cost() -> None:
    payload = {
        "model": config.JUDGE_MODEL,
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
        "model": config.JUDGE_MODEL,
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
    # 100*$0.20/M + 50*$1.20/M = 0.00002 + 0.00006
    assert caught.value.cost_usd == pytest.approx(0.00008)


def test_execute_judge_retries_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from citation_verification.judge import execute_judge
    from citation_verification.limits import reset_limiters

    reset_limiters()
    monkeypatch.setattr("citation_verification.limits.time.sleep", lambda _s: None)
    monkeypatch.setattr(
        "citation_verification.judge.require_openai_api_key",
        lambda _key=None: "sk-test",
    )
    payload = json.loads(
        (FIXTURES / "citation_judge_ok.json").read_text(encoding="utf-8")
    )
    calls = {"n": 0}

    class _Resp:
        def __init__(self, status_code: int, body: dict | None = None) -> None:
            self.status_code = status_code
            self.headers = {"retry-after": "0.1"}
            self._body = body or {}
            self.request = httpx.Request("POST", "https://api.openai.com/v1/responses")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "Client error '429 Too Many Requests'",
                    request=self.request,
                    response=httpx.Response(self.status_code, request=self.request),
                )

        def json(self) -> dict:
            return self._body

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> _Resp:
            calls["n"] += 1
            if calls["n"] == 1:
                return _Resp(429)
            return _Resp(200, payload)

    monkeypatch.setattr("httpx.Client", _Client)
    result = execute_judge(
        claim="Uses Copilot for PR review",
        source_url="https://example.com/careers",
        snippet="Our engineers use GitHub Copilot when reviewing pull requests.",
    )
    assert calls["n"] == 2
    assert result.verification == 1
