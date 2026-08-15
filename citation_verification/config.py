"""Config knobs for Stage 3 citation verification (design freeze 2026-08-14).

Snippet cap lock (2026-08-15): 32,000 characters *after* chrome-strip.
Stage 2 has no MAX_SNIPPET_CHARS. Its page budget is web_search
max_tokens_per_page in unified_adaptive_search/agent_call.py,
parallel_channel_search/agent_call.py, and signal_gated_search/agent_call.py:

    low 1,000 / medium (bake-off) 2,000 / high 4,000 tokens per page.

High ≈ 16,000 characters. This package keeps 32,000 after strip (2× that).
"""

from __future__ import annotations

# OpenAI judge. Same family as Stage 2 researchers; 10x cheaper than Terra.
# Keep Responses + logprobs here (Perplexity Luna has no usable logprobs).
JUDGE_MODEL: str = "gpt-5.6-luna"
JUDGE_REASONING_EFFORT: str = "none"
JUDGE_TOP_LOGPROBS: int = 5
JUDGE_MAX_OUTPUT_TOKENS: int = 400
LOGPROB_INCLUDE: tuple[str, ...] = ("message.output_text.logprobs",)

# OpenAI short-context sync rates ($ / 1M tokens) for gpt-5.6-luna.
# Used when Responses usage has tokens but no dollar total_cost field.
JUDGE_INPUT_USD_PER_MTOK: float = 0.20
JUDGE_CACHED_INPUT_USD_PER_MTOK: float = 0.02
JUDGE_OUTPUT_USD_PER_MTOK: float = 1.20

# Decision field in the judge JSON schema (0 = hallucination, 1 = verified).
DECISION_KEY: str = "verification"

# Claim text is Stage 2 evidence_description only.
CLAIM_FIELD: str = "evidence_description"

# Snippet guards. Cap applies after chrome-strip, not before.
MIN_SNIPPET_CHARS: int = 40
MAX_SNIPPET_CHARS: int = 32_000

# Overlapping claim windows (Ctrl+F, not banner-down).
CHUNK_CHARS: int = 2_500
CHUNK_OVERLAP: int = 500

# Taxonomy-style censor bound for opposing digit mass.
MAX_CENSORED_INTERVAL_WIDTH: float = 0.05
MASKED_SENTINEL_LOGPROB: float = -100.0

# Perplexity fetch wrapper. Tight max_steps so Luna cannot wander.
FETCH_MODEL: str = "openai/gpt-5.6-luna"
FETCH_MAX_STEPS: int = 2
FETCH_TIMEOUT_SEC: float = 180.0
# Gold e2e: empty fetch_url_results can flake on a URL that just succeeded.
FETCH_EMPTY_RETRIES: int = 1

# Backup fetch (paid Tavily Extract, then raw httpx, browser last).
TAVILY_EXTRACT_URL: str = "https://api.tavily.com/extract"
TAVILY_EXTRACT_DEPTH: str = "advanced"
HTTPX_TIMEOUT_SEC: float = 30.0

# Reason codes (package null, not model 0).
ERROR_SNIPPET_MISSING_ANCHORS: str = "snippet_missing_claim_anchors"
ERROR_DOCUMENT_MISMATCH: str = "fetch_document_mismatch"
ERROR_URL_ROW_MISMATCH: str = "fetch_url_row_mismatch"
ERROR_NO_PAGE_CONTENT: str = "fetch_url returned no page content"
ERROR_SOFT_404: str = "soft_404"

FETCH_SOURCE_PERPLEXITY: str = "perplexity_fetch_url"
FETCH_SOURCE_TAVILY: str = "tavily_extract"
FETCH_SOURCE_HTTPX: str = "httpx"
FETCH_SOURCE_BROWSER: str = "browser"
