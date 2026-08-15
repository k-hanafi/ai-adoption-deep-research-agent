"""Dry-run tests for citation_verification skeleton."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from citation_verification.runner import LiveNotWiredError, verify_finding, verify_findings
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


def test_live_raises_not_wired() -> None:
    with pytest.raises(LiveNotWiredError):
        verify_finding(
            {
                "finding_id": 4,
                "source_url": "https://example.com/x",
                "evidence_description": "Uses Claude for coding",
            },
            dry_run=False,
        )


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
