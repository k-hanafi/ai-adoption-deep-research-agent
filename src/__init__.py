"""
Deep Research AI Agent

Cost-optimized pipeline for discovering GenAI adoption evidence
across 44k+ startups from Crunchbase.

Architecture:
    Stage 1: Presence filter (website check + Tavily + GPT-5 nano priority score)
    Stage 2: Live architectures live in signal_gated_search/,
    parallel_channel_search/, and unified_adaptive_search/.
    The March 2026 batch runner is frozen under legacy_agent_march_2026/.
"""

__version__ = "0.1.0"
