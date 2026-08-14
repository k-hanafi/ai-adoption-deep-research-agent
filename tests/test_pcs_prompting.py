"""PCS prompt compose: jobs boards, unnamed tools, owned walls."""

from __future__ import annotations

from contracts.types import CompanyInput
from parallel_channel_search.prompting import build_channel_prompt
from unified_adaptive_search.prompting import build_company_prompt

COMPANY = CompanyInput(
    rcid=610194,
    name="Jam",
    homepage_url="https://jam.dev",
    short_description="A test company",
)


def test_pcs_jobs_searches_external_boards_and_unnamed_ai() -> None:
    text = build_channel_prompt(COMPANY, "jobs")
    assert "Techstars" in text
    assert "YC Work at a Startup" in text
    assert "LinkedIn Jobs" in text
    assert "Do not stop after the company-owned board" in text
    assert "use AI in our content creation" in text
    assert "Do not drop a cited internal-use claim because no vendor brand appears" in text


def test_pcs_owned_searches_social_walls() -> None:
    text = build_channel_prompt(COMPANY, "owned")
    assert "/linkedin-posts" in text
    assert "Official company accounts" in text
    assert "A customer-facing bot that replaces staff work is adopt, not sell" in text


def test_uas_prompt_matches_jobs_owned_and_unnamed_rules() -> None:
    text = build_company_prompt(COMPANY)
    assert "Techstars" in text
    assert "YC Work at a Startup" in text
    assert "we use AI in our content creation" in text
    assert "One URL should emit as many findings as needed" in text
    assert "A customer-facing bot that replaces staff work is adopt, not sell" in text
