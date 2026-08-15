"""Type helpers for citation_verification."""

from citation_verification.types import VerdictResult, ledger_from_verdicts, unverifiable_result


def test_unverifiable_does_not_set_verification_zero() -> None:
    row = unverifiable_result(
        finding_id=1,
        source_url="",
        claim="x",
        reason="missing source_url",
        company_name="Acme",
    )
    assert row.verification is None
    assert row.unverifiable is True
    assert row.model_judge is None
    assert row.evidence_description == "x"
    assert row.company_name == "Acme"


def test_ledger_sums_component_costs() -> None:
    results = [
        VerdictResult(cost_fetch_usd=0.00025, cost_judge_usd=0.001),
        VerdictResult(cost_fetch_usd=0.00025, cost_judge_usd=0.002),
    ]
    ledger = ledger_from_verdicts(results)
    assert ledger.total_usd == 0.0035
    names = [c.name for c in ledger.components]
    assert names == ["fetch_url", "openai_judge"]
