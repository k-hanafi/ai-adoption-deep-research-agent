"""OpenAI Responses judge: request build, parse, and live call."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional

from citation_verification import config
from citation_verification.schema import judge_text_format

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JUDGE_PROMPT = (
    PROJECT_ROOT / "prompts" / "citation_verification" / "judge.txt"
)
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class JudgeParseError(ValueError):
    """Judge response JSON or fields are unusable."""

    def __init__(self, message: str, *, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = float(cost_usd)


@dataclass(frozen=True)
class JudgeResult:
    """Parsed model fields plus raw response and metered cost when present."""

    verification: int
    confidence_1_5: int
    verification_reasoning: str
    verification_critique: str
    cost_usd: float
    model: str
    raw: dict[str, Any]


@lru_cache(maxsize=4)
def load_judge_prompt(path: str | None = None) -> str:
    """Load the judge system instructions from prompts/."""
    prompt_path = Path(path) if path else DEFAULT_JUDGE_PROMPT
    return prompt_path.read_text(encoding="utf-8").strip()


def format_judge_input(*, claim: str, source_url: str, snippet: str) -> str:
    """Build the user message for one claim/snippet pair."""
    return (
        "CLAIM:\n"
        f"{claim.strip()}\n\n"
        "SOURCE_URL:\n"
        f"{source_url.strip()}\n\n"
        "PAGE_SNIPPET:\n"
        f"{snippet.strip()}\n"
    )


def build_judge_request(
    *,
    claim: str,
    source_url: str,
    snippet: str,
    model: str = config.JUDGE_MODEL,
    max_output_tokens: int = config.JUDGE_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    """Build Responses API kwargs for the Terra logprob judge."""
    return {
        "model": model,
        "instructions": load_judge_prompt(),
        "input": format_judge_input(
            claim=claim, source_url=source_url, snippet=snippet
        ),
        "max_output_tokens": max_output_tokens,
        "store": False,
        "text": judge_text_format(),
        "reasoning": {"effort": config.JUDGE_REASONING_EFFORT},
        "top_logprobs": config.JUDGE_TOP_LOGPROBS,
        "include": list(config.LOGPROB_INCLUDE),
    }


def parse_judge_response(response: Mapping[str, Any] | Any) -> JudgeResult:
    """Parse model JSON fields and cost from a Responses payload."""
    payload = _as_mapping(response)
    cost_usd = _total_cost_usd(payload)
    try:
        text = _output_text(payload)
    except JudgeParseError as exc:
        raise JudgeParseError(str(exc), cost_usd=cost_usd) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise JudgeParseError(
            f"judge output is not JSON: {exc}", cost_usd=cost_usd
        ) from exc
    if not isinstance(data, dict):
        raise JudgeParseError(
            "judge output JSON must be an object", cost_usd=cost_usd
        )

    verification = data.get("verification")
    if verification not in (0, 1):
        raise JudgeParseError(
            f"verification must be 0 or 1, got {verification!r}",
            cost_usd=cost_usd,
        )
    confidence = data.get("confidence_1_5")
    try:
        confidence_i = int(confidence)
    except (TypeError, ValueError) as exc:
        raise JudgeParseError(
            f"confidence_1_5 must be an int 1-5, got {confidence!r}",
            cost_usd=cost_usd,
        ) from exc
    if confidence_i < 1 or confidence_i > 5:
        raise JudgeParseError(
            f"confidence_1_5 must be an int 1-5, got {confidence_i!r}",
            cost_usd=cost_usd,
        )

    reasoning = str(data.get("verification_reasoning") or "").strip()
    critique = str(data.get("verification_critique") or "").strip()
    if not reasoning:
        raise JudgeParseError(
            "verification_reasoning is empty", cost_usd=cost_usd
        )
    if not critique:
        raise JudgeParseError(
            "verification_critique is empty", cost_usd=cost_usd
        )

    model = str(payload.get("model") or config.JUDGE_MODEL)
    return JudgeResult(
        verification=int(verification),
        confidence_1_5=confidence_i,
        verification_reasoning=reasoning,
        verification_critique=critique,
        cost_usd=cost_usd,
        model=model,
        raw=dict(payload) if isinstance(payload, dict) else dict(payload),
    )


def execute_judge(
    *,
    claim: str,
    source_url: str,
    snippet: str,
    api_key: Optional[str] = None,
    timeout: float = 120.0,
) -> JudgeResult:
    """Live OpenAI Responses call for one claim/snippet."""
    import httpx

    key = require_openai_api_key(api_key)
    kwargs = build_judge_request(
        claim=claim, source_url=source_url, snippet=snippet
    )
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=kwargs,
        )
        response.raise_for_status()
        payload = response.json()
    return parse_judge_response(payload)


def require_openai_api_key(api_key: Optional[str] = None) -> str:
    """Resolve OpenAI key from arg, credentials file, or env."""
    if api_key:
        return api_key
    from src.config import APIKeys

    key = APIKeys().openai
    if not key:
        raise RuntimeError(
            "OpenAI API key required for live citation judge. "
            "Set credentials/openai_api_key.txt or OPENAI_API_KEY. "
            "Use dry_run=True to skip paid APIs."
        )
    return key


def _as_mapping(response: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return {
        "output": getattr(response, "output", None),
        "usage": getattr(response, "usage", None),
        "model": getattr(response, "model", None),
    }


def _output_text(payload: Mapping[str, Any]) -> str:
    for item in payload.get("output") or []:
        item_map = item if isinstance(item, Mapping) else _as_mapping(item)
        if item_map.get("type") != "message":
            continue
        for content in item_map.get("content") or []:
            content_map = (
                content if isinstance(content, Mapping) else _as_mapping(content)
            )
            if content_map.get("type") == "output_text":
                text = content_map.get("text")
                if text is not None:
                    return str(text)
    raise JudgeParseError("response has no message/output_text content")


def _total_cost_usd(payload: Mapping[str, Any]) -> float:
    """Prefer provider dollar total; else estimate from Terra token rates."""
    usage = payload.get("usage") or {}
    if not isinstance(usage, Mapping):
        cost = getattr(usage, "cost", None)
        if cost is not None and getattr(cost, "total_cost", None) is not None:
            return float(cost.total_cost)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        details = getattr(usage, "input_tokens_details", None)
        cached = 0
        if details is not None:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        return _estimate_terra_cost_usd(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached,
        )

    cost = usage.get("cost") or {}
    if isinstance(cost, Mapping) and cost.get("total_cost") is not None:
        return float(cost["total_cost"])

    details = usage.get("input_tokens_details") or {}
    cached = 0
    if isinstance(details, Mapping):
        cached = int(details.get("cached_tokens") or 0)
    return _estimate_terra_cost_usd(
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        cached_input_tokens=cached,
    )


def _estimate_terra_cost_usd(
    *,
    input_tokens: Any,
    output_tokens: Any,
    cached_input_tokens: int = 0,
) -> float:
    try:
        total_in = int(input_tokens or 0)
    except (TypeError, ValueError):
        total_in = 0
    try:
        total_out = int(output_tokens or 0)
    except (TypeError, ValueError):
        total_out = 0
    cached = max(0, int(cached_input_tokens or 0))
    billable_in = max(0, total_in - cached)
    usd = (
        billable_in / 1_000_000.0 * config.JUDGE_INPUT_USD_PER_MTOK
        + cached / 1_000_000.0 * config.JUDGE_CACHED_INPUT_USD_PER_MTOK
        + total_out / 1_000_000.0 * config.JUDGE_OUTPUT_USD_PER_MTOK
    )
    return round(usd, 6)
