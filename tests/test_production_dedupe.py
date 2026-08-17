"""Offline tests for production syndication squash. No paid API calls."""

from __future__ import annotations

from production.dedupe import is_duplicate, squash_rows
from production.persist import RESEARCH_COLUMNS


def _row(**overrides: object) -> dict[str, object]:
    row = {key: "" for key in RESEARCH_COLUMNS}
    row.update(
        {
            "rcid": "1",
            "company_name": "Co1",
            "finding_id": "1",
            "AI_tool_used": "Claude Code",
            "use_case": "AI-assisted software development",
            "evidence_description": "The Head of Engineering posting names Claude Code.",
            "source_url": "https://www.linkedin.com/jobs/view/head-of-engineering",
            "findings_count": "2",
        }
    )
    row.update(overrides)
    return row


def test_jobright_mirror_squashes_linkedin() -> None:
    first = _row(finding_id="1")
    copy = _row(
        finding_id="2",
        source_url="https://jobright.ai/jobs/info/abc123",
        evidence_description=(
            "A third-party mirror of the Head of Engineering posting names Claude Code."
        ),
        channel="third_party",
    )
    result = squash_rows([first, copy])
    assert result.dropped == 1
    assert [row["finding_id"] for row in result.rows] == ["1"]
    assert result.rows[0]["findings_count"] == 1


def test_cloaked_role_postings_stay() -> None:
    ios = _row(
        finding_id="1",
        AI_tool_used="Cursor, Claude, Codex",
        use_case="Daily AI-assisted software engineering and coding",
        source_url="https://wellfound.com/jobs/4180506-senior-ios-engineer",
        evidence_description=(
            "The Senior iOS Engineer posting requires daily use of Cursor, Claude, and Codex."
        ),
    )
    android = _row(
        finding_id="2",
        AI_tool_used="Cursor, Claude, Codex",
        use_case="Daily AI-assisted software engineering and coding",
        source_url="https://wellfound.com/jobs/4359684-senior-android-engineer",
        evidence_description=(
            "The Senior Android Engineer posting requires daily use of Cursor, Claude, and Codex."
        ),
    )
    result = squash_rows([ios, android])
    assert result.dropped == 0
    assert [row["finding_id"] for row in result.rows] == ["1", "2"]


def test_duty_split_same_url_stays() -> None:
    coding = _row(
        finding_id="1",
        use_case="AI-assisted software development",
        evidence_description="The post says engineers use ChatGPT to write code.",
    )
    marketing = _row(
        finding_id="2",
        use_case="marketing campaign copy",
        evidence_description="The same post says marketers use ChatGPT for campaign copy.",
        AI_tool_used="ChatGPT",
    )
    coding["AI_tool_used"] = "ChatGPT"
    result = squash_rows([coding, marketing])
    assert result.dropped == 0
    assert len(result.rows) == 2


def test_use_case_reword_same_url_squashes() -> None:
    first = _row(
        finding_id="1",
        use_case="competitive intelligence and analysis",
    )
    reword = _row(
        finding_id="2",
        use_case="competitive intelligence and competitive analysis",
    )
    result = squash_rows([first, reword])
    assert result.dropped == 1
    assert result.rows[0]["finding_id"] == "1"


def test_tool_alias_same_url_squashes() -> None:
    first = _row(
        finding_id="1",
        AI_tool_used="claude through cursor",
        use_case="AI-assisted software development",
    )
    alias = _row(
        finding_id="2",
        AI_tool_used="anthropic claude via cursor",
        use_case="AI-assisted software development",
    )
    result = squash_rows([first, alias])
    assert result.dropped == 1


def test_distinct_tools_same_url_stay() -> None:
    chatgpt = _row(finding_id="1", AI_tool_used="ChatGPT")
    copilot = _row(finding_id="2", AI_tool_used="GitHub Copilot")
    result = squash_rows([chatgpt, copilot])
    assert result.dropped == 0
    assert len(result.rows) == 2


def test_news_corroboration_stays() -> None:
    owned = _row(
        finding_id="1",
        AI_tool_used="Grok Bot",
        use_case="marketing campaign execution",
        source_url="https://x.ai/news/introducing-grok-bot",
        evidence_description="xAI says teams created Bots to handle marketing campaigns.",
    )
    news = _row(
        finding_id="2",
        AI_tool_used="Grok Bot",
        use_case="marketing campaign execution",
        source_url="https://venturebeat.com/orchestration/grok-bot-article",
        evidence_description=(
            "VentureBeat reports the internally developed Grok Bot prototype "
            "was used before being released to external users."
        ),
    )
    assert not is_duplicate(owned, news)
    result = squash_rows([owned, news])
    assert result.dropped == 0


def test_blank_company_row_passes_through() -> None:
    blank = {key: "" for key in RESEARCH_COLUMNS}
    blank["rcid"] = "9"
    blank["company_name"] = "EmptyCo"
    finding = _row(rcid="1")
    result = squash_rows([blank, finding])
    assert result.in_findings == 1
    assert result.dropped == 0
    assert result.rows[0]["company_name"] == "EmptyCo"
    assert result.rows[1]["finding_id"] == "1"


def test_other_company_never_matches() -> None:
    a = _row(rcid="1", finding_id="1")
    b = _row(rcid="2", finding_id="1")
    result = squash_rows([a, b])
    assert result.dropped == 0
    assert len(result.rows) == 2
