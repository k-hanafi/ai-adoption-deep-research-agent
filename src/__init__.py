"""
Deep Research AI Agent

Cost-optimized pipeline for discovering GenAI adoption evidence
across 44k+ startups from Crunchbase.

Architecture:
    Stage 1: Presence filter (website check + Tavily + GPT-5 nano priority score)
    Stage 2: Perplexity deep-research agent on priority 4–5 companies
"""

__version__ = "0.1.0"
