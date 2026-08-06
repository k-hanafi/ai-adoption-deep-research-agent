"""Agent API request builder + live call for UAS (single call per company).

UAS freezes explicit kwargs (model, max_steps, reasoning, tools) instead of
passing a dynamic `preset` name. Docs note: these defaults match today's
`medium` family on Luna, with March-style max_steps=10 for the baseline arm.

Dry-run builds the kwargs snapshot without importing the Perplexity SDK.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from contracts.types import CompanyInput, Finding
from unified_adaptive_search.prompting import RESPONSE_SCHEMA, build_company_prompt

logger = logging.getLogger("unified_adaptive_search.agent_call")

# Pin to Luna unless an override is provided. Matches current medium engine.
DEFAULT_MODEL = "openai/gpt-5.6-luna"
# March production used 10; stock medium docs default is 15 (see from_preset_defaults).
DEFAULT_MAX_STEPS = 10
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_WEB_SEARCH_DEPTH = "medium"
DEFAULT_TIMEOUT = 300.0

# Ledger label for CostComponent.preset (schema field). Not an API preset kwarg.
LEDGER_CONFIG_LABEL = "luna"

# Map depth labels to web_search tool options.
# Named API sizes are low/medium/high only. beyond_high is our stretch past
# named high via explicit max_tokens (docs: explicit budgets override size).
_WEB_SEARCH_DEPTH: dict[str, dict[str, Any]] = {
    "medium": {
        "search_context_size": "medium",
        "max_tokens": 2000,
    },
    "high": {
        "search_context_size": "high",
        "max_tokens": 4000,
    },
    # Only max_tokens differs from high (OFAT: do not also set max_tokens_per_page).
    "beyond_high": {
        "search_context_size": "high",
        "max_tokens": 8000,
    },
}


def from_preset_defaults(name: str = "medium") -> dict[str, Any]:
    """Expand a known preset name into explicit call fields (no `preset` key).

    Convenience for docs / migration only. Eval and tuning arms should pass
    explicit knobs directly, not sweep `preset=...`.
    """
    key = (name or "").strip().lower()
    if key == "medium":
        # Current docs freeze for medium: Luna + steps 15 + effort medium +
        # web_search + fetch_url. UAS baseline arms still use max_steps=10.
        return {
            "model": DEFAULT_MODEL,
            "max_steps": 15,
            "reasoning_effort": "medium",
            "web_search_depth": "medium",
        }
    if key == "low":
        return {
            "model": DEFAULT_MODEL,
            "max_steps": 5,
            "reasoning_effort": "minimal",
            "web_search_depth": "medium",
        }
    raise ValueError(
        f"Unknown preset defaults {name!r}. "
        "Supported helpers: medium, low. Prefer passing explicit knobs."
    )


def build_request_kwargs(
    company: CompanyInput,
    *,
    model: str = DEFAULT_MODEL,
    max_steps: Optional[int] = DEFAULT_MAX_STEPS,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    web_search_depth: str = DEFAULT_WEB_SEARCH_DEPTH,
) -> dict[str, Any]:
    """Build explicit kwargs for one UAS Agent API call (no top-level preset)."""
    depth = (web_search_depth or DEFAULT_WEB_SEARCH_DEPTH).strip().lower()
    if depth not in _WEB_SEARCH_DEPTH:
        known = ", ".join(sorted(_WEB_SEARCH_DEPTH))
        raise ValueError(f"Unknown web_search_depth {web_search_depth!r}. Choose: {known}")

    kwargs: dict[str, Any] = {
        "model": model,
        "input": build_company_prompt(company),
        "response_format": RESPONSE_SCHEMA,
        "reasoning": {"effort": reasoning_effort},
        # Without preset, list tools explicitly (medium-family: search + fetch).
        "tools": [
            {
                "type": "web_search",
                **_WEB_SEARCH_DEPTH[depth],
            },
            {"type": "fetch_url"},
        ],
    }
    # Match March production: omit falsy max_steps (including 0).
    if max_steps:
        kwargs["max_steps"] = max_steps
    return kwargs


def _extract_text_fallback(output: list) -> str:
    """Walk MessageOutputItem content parts for text (production_agent_runner pattern)."""
    # Lazy import: dry-run never loads the Perplexity SDK.
    from perplexity.types.output_item import MessageOutputItem

    texts: list[str] = []
    for item in output:
        if isinstance(item, MessageOutputItem):
            for part in getattr(item, "content", None) or []:
                text = getattr(part, "text", None)
                if text:
                    texts.append(text)
    return "".join(texts)


def _extract_json_from_text(text: str) -> str:
    """Find the outermost JSON object in text using brace-depth counting."""
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _parse_findings(raw_findings: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(raw_findings, list):
        return findings
    for idx, row in enumerate(raw_findings):
        if not isinstance(row, dict):
            continue
        try:
            findings.append(
                Finding(
                    finding_id=int(row.get("finding_id") or idx + 1),
                    AI_tool_used=str(row.get("AI_tool_used") or ""),
                    use_case=str(row.get("use_case") or ""),
                    business_function=str(row.get("business_function") or ""),
                    evidence_description=str(row.get("evidence_description") or ""),
                    source_url=str(row.get("source_url") or ""),
                    source_type=str(row.get("source_type") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return findings


def require_api_key(api_key: Optional[str] = None) -> str:
    """Resolve Perplexity key from arg, credentials file, or env. Refuse if missing."""
    if api_key:
        return api_key
    # Lazy import so dry-run never depends on src.config side effects.
    from src.config import APIKeys

    key = APIKeys().perplexity
    if not key:
        raise RuntimeError(
            "Perplexity API key required for live Unified Adaptive Search. "
            "Set credentials/perplexity_api_key.txt or PERPLEXITY_API_KEY. "
            "Use dry_run=True to build a request snapshot without calling the API."
        )
    return key


def execute_agent_call(
    request_kwargs: dict[str, Any],
    *,
    api_key: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """One sync Agent API call. Returns parsed payload + usage metadata.

    Reuses the production parse / usage patterns (sync client, like preset tests).
    """
    from perplexity import Perplexity
    from perplexity.types.output_item import SearchResultsOutputItem

    key = require_api_key(api_key)
    client = Perplexity(api_key=key, max_retries=0)
    create_kwargs = dict(request_kwargs)
    create_kwargs["timeout"] = timeout

    response = client.responses.create(**create_kwargs)

    cost_usd = 0.0
    input_tokens = None
    output_tokens = None
    total_tokens = None
    if response.usage:
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = response.usage.total_tokens
        if response.usage.cost and response.usage.cost.total_cost is not None:
            cost_usd = float(response.usage.cost.total_cost)

    citations: list[str] = []
    for item in response.output or []:
        if isinstance(item, SearchResultsOutputItem):
            for sr in item.results or []:
                if getattr(sr, "url", None):
                    citations.append(sr.url)

    # Build meta before failure/empty checks so metered usage is never dropped.
    meta = {
        "response_id": response.id,
        "model_used": response.model,
        "response_status": response.status,
        "cost_usd": cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "citations": citations,
        "raw_content_preview": None,
        "genai_adoption_found": False,
        "findings": [],
        "no_finding_reason": None,
        "no_finding_analysis": None,
        "error": None,
    }

    if response.status == "failed":
        err = response.error
        detail = f"{err.type}: {err.message}" if err else "unknown"
        meta["error"] = f"Agent API response failed: {detail}"
        return meta

    content = (response.output_text or "").strip()
    if not content:
        content = _extract_text_fallback(list(response.output or [])).strip()
    if not content:
        output_types = [type(item).__name__ for item in (response.output or [])]
        meta["error"] = (
            f"Empty Agent API response (model={response.model}, "
            f"status={response.status}, output_types={output_types})"
        )
        return meta

    meta["raw_content_preview"] = content[:500]
    try:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = json.loads(_extract_json_from_text(content))
    except json.JSONDecodeError as exc:
        meta["error"] = f"JSON parse error: {exc}"
        return meta

    meta["findings"] = _parse_findings(parsed.get("findings"))
    meta["genai_adoption_found"] = bool(parsed.get("genai_adoption_found", False))
    meta["no_finding_reason"] = parsed.get("no_finding_reason")
    meta["no_finding_analysis"] = parsed.get("no_finding_analysis")
    return meta
