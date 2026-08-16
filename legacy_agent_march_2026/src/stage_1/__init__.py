"""
Stage 1: Presence Filter

Gathers general company intelligence via web search and predicts
research priority for subsequent deep research stages.

Components:
    1. website.py    — Website health checks
    2. tavily.py     — Tavily web search
    3. classifier.py — GPT-5-nano research priority classification
    4. run_tavily_pass.py / run_gpt_pass.py — Production batch runners
"""

from .website import WebsiteStatus, check_website, check_websites_batch
from .tavily import SearchSnippet, TavilySearchResult, search_tavily, build_search_query
from .classifier import PresenceAssessment, classify_company

__all__ = [
    "WebsiteStatus", "check_website", "check_websites_batch",
    "SearchSnippet", "TavilySearchResult", "search_tavily", "build_search_query",
    "PresenceAssessment", "classify_company",
]
