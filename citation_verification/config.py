"""Config knobs for Stage 3 citation verification (design freeze 2026-08-14)."""

from __future__ import annotations

# OpenAI judge (different model from Stage 2 Luna researchers).
JUDGE_MODEL: str = "gpt-5.6-terra"
JUDGE_REASONING_EFFORT: str = "none"
JUDGE_TOP_LOGPROBS: int = 5
LOGPROB_INCLUDE: tuple[str, ...] = ("message.output_text.logprobs",)

# Decision field in the judge JSON schema (0 = hallucination, 1 = verified).
DECISION_KEY: str = "verification"

# Claim text is Stage 2 evidence_description only.
CLAIM_FIELD: str = "evidence_description"

# Snippet guards (tune after smoke).
MIN_SNIPPET_CHARS: int = 40
MAX_SNIPPET_CHARS: int = 12_000

# Taxonomy-style censor bound for opposing digit mass.
MAX_CENSORED_INTERVAL_WIDTH: float = 0.05
MASKED_SENTINEL_LOGPROB: float = -100.0

# Perplexity fetch wrapper (cheapest path that can run fetch_url; finalize in commit 2).
FETCH_MODEL: str = "openai/gpt-5.6-luna"
FETCH_MAX_STEPS: int = 5
