"""Dry-run tests for citation_verification skeleton."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citation_verification.runner import verify_finding, verify_findings
from citation_verification.types import VerdictResult
from citation_verification import __main__ as cli


def test_empty_url_is_unverifiable_not_hallucination() -> None:
    result = verify_finding(
        {
            "finding_id": 1,
            "source_url": "",
            "evidence_description": "Uses Copilot for PR review",
        },
        dry_run=True,
    )
    assert result.unverifiable is True
    assert result.verification is None
    assert result.fetch_ok is False
    assert "source_url" in (result.error or "")


def test_missing_claim_is_unverifiable() -> None:
    result = verify_finding(
        {
            "finding_id": 2,
            "source_url": "https://example.com/blog",
            "evidence_description": "  ",
        },
        dry_run=True,
    )
    assert result.unverifiable is True
    assert result.verification is None
    assert "evidence_description" in (result.error or "")


def test_dry_stub_for_usable_inputs() -> None:
    result = verify_finding(
        {
            "finding_id": 3,
            "source_url": "https://example.com/careers",
            "evidence_description": "Company uses ChatGPT in support workflows",
        },
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.unverifiable is False
    assert result.verification is None
    assert result.error == "dry_run_no_api"
    assert result.cost_usd == 0.0


def test_live_fetch_fail_is_unverifiable(monkeypatch: pytest.MonkeyPatch) -> None:
    from citation_verification.fetch import FetchResult
    from citation_verification import runner as runner_mod

    def _fake_fetch(url: str, **_kwargs: object) -> FetchResult:
        return FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0001,
            error="snippet too short (0 chars; min 40)",
        )

    monkeypatch.setattr(runner_mod, "execute_fetch", _fake_fetch)
    result = verify_finding(
        {
            "finding_id": 4,
            "source_url": "https://example.com/x",
            "evidence_description": "Uses Claude for coding",
        },
        dry_run=False,
    )
    assert result.unverifiable is True
    assert result.verification is None
    assert result.fetch_ok is False
    assert result.cost_fetch_usd == pytest.approx(0.0001)
    assert result.model_judge is None
    assert "snippet too short" in (result.error or "")


def test_live_happy_path_wires_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from citation_verification.fetch import FetchResult
    from citation_verification.judge import JudgeResult
    from citation_verification import runner as runner_mod

    fixtures = Path(__file__).resolve().parent / "fixtures"
    raw = json.loads(
        (fixtures / "citation_verification_one.json").read_text(encoding="utf-8")
    )
    # Attach full judge JSON fields while keeping logprob tokens for "1".
    raw = dict(raw)
    raw["model"] = "gpt-5.6-terra"
    raw["usage"] = {"cost": {"total_cost": 0.002}}

    def _fake_fetch(url: str, **_kwargs: object) -> FetchResult:
        return FetchResult(
            url=url,
            title="Careers",
            snippet="Our engineers use GitHub Copilot when reviewing pull requests every day.",
            cost_usd=0.0003,
        )

    def _fake_judge(**_kwargs: object) -> JudgeResult:
        return JudgeResult(
            verification=1,
            confidence_1_5=4,
            verification_reasoning="Snippet mentions Copilot for PR review.",
            verification_critique="Could be aspirational copy.",
            cost_usd=0.002,
            model="gpt-5.6-terra",
            raw=raw,
        )

    monkeypatch.setattr(runner_mod, "execute_fetch", _fake_fetch)
    monkeypatch.setattr(runner_mod, "execute_judge", _fake_judge)
    result = verify_finding(
        {
            "finding_id": 5,
            "source_url": "https://example.com/careers",
            "evidence_description": "Uses Copilot for PR review",
        },
        dry_run=False,
    )
    assert result.unverifiable is False
    assert result.fetch_ok is True
    assert result.verification == 1
    assert result.log_probs_conf == pytest.approx(0.97, rel=1e-6)
    assert result.confidence_1_5 == 4
    assert result.model_judge == "gpt-5.6-terra"
    assert result.cost_usd == pytest.approx(0.0023)
    assert result.cost_fetch_usd == pytest.approx(0.0003)
    assert result.cost_judge_usd == pytest.approx(0.002)
    assert result.error is None


def test_live_judge_parse_error_keeps_judge_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from citation_verification.fetch import FetchResult
    from citation_verification.judge import JudgeParseError
    from citation_verification import runner as runner_mod

    monkeypatch.setattr(
        runner_mod,
        "execute_fetch",
        lambda url, **_: FetchResult(
            url=url,
            title="Careers",
            snippet="Engineers use GitHub Copilot for pull request review every day.",
            cost_usd=0.0003,
        ),
    )

    def _boom(**_kwargs: object) -> object:
        raise JudgeParseError("verification_reasoning is empty", cost_usd=0.0015)

    monkeypatch.setattr(runner_mod, "execute_judge", _boom)
    result = verify_finding(
        {
            "finding_id": 6,
            "source_url": "https://example.com/careers",
            "evidence_description": "Uses Copilot for PR review",
        },
        dry_run=False,
    )
    assert result.fetch_ok is True
    assert result.verification is None
    assert "judge parse failed" in (result.error or "")
    assert result.cost_fetch_usd == pytest.approx(0.0003)
    assert result.cost_judge_usd == pytest.approx(0.0015)
    assert result.cost_usd == pytest.approx(0.0018)


def test_verify_findings_batch_dry(tmp_path: Path) -> None:
    rows = [
        {
            "finding_id": 1,
            "source_url": "https://example.com/a",
            "evidence_description": "Uses Copilot",
        },
        {
            "finding_id": 2,
            "source_url": "",
            "evidence_description": "Uses Copilot",
        },
    ]
    batch = verify_findings(rows, dry_run=True)
    assert batch.dry_run is True
    assert len(batch.results) == 2
    assert batch.results[0].error == "dry_run_no_api"
    assert batch.results[1].unverifiable is True
    assert batch.total_usd == 0.0
    assert len(batch.cost_ledger.components) == 2


def test_core_fields_precede_ops_in_to_dict() -> None:
    keys = list(VerdictResult().to_dict().keys())
    core = [
        "verification",
        "log_probs_conf",
        "confidence_1_5",
        "verification_reasoning",
        "verification_critique",
    ]
    ops = ["fetch_ok", "evidence_snippet", "cost_usd", "error"]
    core_idxs = [keys.index(k) for k in core]
    ops_idxs = [keys.index(k) for k in ops]
    assert max(core_idxs) < min(ops_idxs)


def test_cli_findings_dry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "findings.jsonl"
    path.write_text(
        json.dumps(
            {
                "finding_id": 9,
                "source_url": "https://example.com/z",
                "evidence_description": "Uses Cursor for coding",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code = cli.main(["--dry-run", "--findings", str(path)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert len(payload["results"]) == 1


def test_cli_one_off_requires_both_flags() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--dry-run", "--url", "https://example.com"])
