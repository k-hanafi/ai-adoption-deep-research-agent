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

# Pin to Luna unless an override is provided. Bake-off lock: effort xhigh.
DEFAULT_MODEL = "openai/gpt-5.6-luna"
# March production used 10; stock medium docs default is 15 (see from_preset_defaults).
DEFAULT_MAX_STEPS = 10
DEFAULT_REASONING_EFFORT = "xhigh"
# Our ladder (not a Perplexity enum): low/medium/high → rising max_tokens.
DEFAULT_WEB_SEARCH_DEPTH = "low"
DEFAULT_TIMEOUT = 300.0

# Ledger label for CostComponent.preset (schema field). Not an API preset kwarg.
LEDGER_CONFIG_LABEL = "luna"

# UAS web_search_depth → coordinated web_search tool package (our ladder).
# Each step raises size, token budgets, and result breadth together so
# "search=high" means a richer search package, not only max_tokens.
_WEB_SEARCH_DEPTH: dict[str, dict[str, Any]] = {
    "low": {
        "search_context_size": "medium",
        "max_tokens": 2000,
        "max_tokens_per_page": 1000,
        "max_results": 10,
    },
    "medium": {
        "search_context_size": "high",
        "max_tokens": 4000,
        "max_tokens_per_page": 2000,
        "max_results": 20,
    },
    "high": {
        "search_context_size": "high",
        "max_tokens": 8000,
        "max_tokens_per_page": 4000,
        "max_results": 50,
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
            "web_search_depth": "low",
        }
    if key == "low":
        return {
            "model": DEFAULT_MODEL,
            "max_steps": 5,
            "reasoning_effort": "minimal",
            "web_search_depth": "low",
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


def _tool_use_from_response(response: Any) -> dict[str, Any]:
    """Extract actual tool/search utilization from an Agent API response.

    - tool_calls_details: metered invocations per tool (web_search, fetch_url, …)
    - output_item_counts: how many search/fetch/message blocks appear in output
      (soft proxy for research-loop activity; API has no steps_used field)
    - search_result_urls: URLs collected from search_results items
    """
    from perplexity.types.output_item import (
        FetchURLResultsOutputItem,
        MessageOutputItem,
        SearchResultsOutputItem,
    )

    tool_calls_details: dict[str, int] = {}
    tool_calls_cost_usd = None
    if getattr(response, "usage", None):
        usage = response.usage
        raw_details = getattr(usage, "tool_calls_details", None) or {}
        for name, detail in raw_details.items():
            inv = getattr(detail, "invocation", None)
            if inv is None and isinstance(detail, dict):
                inv = detail.get("invocation")
            if inv is not None:
                tool_calls_details[str(name)] = int(inv)
        cost = getattr(usage, "cost", None)
        if cost is not None and getattr(cost, "tool_calls_cost", None) is not None:
            tool_calls_cost_usd = float(cost.tool_calls_cost)

    output_item_counts = {
        "search_results": 0,
        "fetch_url_results": 0,
        "message": 0,
        "other": 0,
    }
    citations: list[str] = []
    for item in response.output or []:
        if isinstance(item, SearchResultsOutputItem):
            output_item_counts["search_results"] += 1
            for sr in item.results or []:
                if getattr(sr, "url", None):
                    citations.append(sr.url)
        elif isinstance(item, FetchURLResultsOutputItem):
            output_item_counts["fetch_url_results"] += 1
        elif isinstance(item, MessageOutputItem):
            output_item_counts["message"] += 1
        else:
            output_item_counts["other"] += 1

    return {
        "tool_calls_details": tool_calls_details,
        "tool_calls_cost_usd": tool_calls_cost_usd,
        "output_item_counts": output_item_counts,
        "search_result_urls": len(citations),
        "citations": citations,
        # Soft loop proxy: tool output blocks (not an official steps_used).
        "tool_output_items": (
            output_item_counts["search_results"]
            + output_item_counts["fetch_url_results"]
        ),
    }


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

    tool_use = _tool_use_from_response(response)

    # Build meta before failure/empty checks so metered usage is never dropped.
    meta = {
        "response_id": response.id,
        "model_used": response.model,
        "response_status": response.status,
        "cost_usd": cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "citations": tool_use["citations"],
        "tool_use": {
            "tool_calls_details": tool_use["tool_calls_details"],
            "tool_calls_cost_usd": tool_use["tool_calls_cost_usd"],
            "output_item_counts": tool_use["output_item_counts"],
            "search_result_urls": tool_use["search_result_urls"],
            "tool_output_items": tool_use["tool_output_items"],
            "max_steps_ceiling": request_kwargs.get("max_steps"),
        },
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
