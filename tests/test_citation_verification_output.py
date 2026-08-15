"""Offline tests for citation_verification JSONL/CSV human-review outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from citation_verification import __main__ as cli
from citation_verification.types import VerdictResult, unverifiable_result


def _sample_rows() -> list[VerdictResult]:
    judged = VerdictResult(
        finding_id=1,
        source_url="https://example.com/careers",
        claim="Uses Copilot for PR review",
        evidence_description="Uses Copilot for PR review",
        company_name="Acme",
        rcid=42,
        channel="jobs",
        AI_tool_used="GitHub Copilot",
        use_case="PR review",
        business_function="Engineering",
        source_type="careers",
        architecture="uas",
        verification=0,
        unverifiable=False,
        fetch_ok=True,
        model_judge="gpt-5.6-luna",
    )
    failed = unverifiable_result(
        finding_id=2,
        source_url="https://example.com/missing",
        claim="Uses Claude for coding",
        reason="fetch_url returned no page content",
        company_name="Acme",
        rcid=42,
        channel="owned",
        AI_tool_used="Claude",
        use_case="coding",
        business_function="Engineering",
        source_type="blog",
        architecture="uas",
    )
    return [judged, failed]


def test_jsonl_and_csv_keep_url_and_finding_fields(tmp_path: Path) -> None:
    rows = _sample_rows()
    jsonl_path = tmp_path / "verdicts.jsonl"
    csv_path = tmp_path / "verdicts.csv"
    cli.write_verdicts_jsonl(jsonl_path, rows)
    cli.write_verdicts_csv(csv_path, rows)

    json_rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(json_rows) == 2
    assert json_rows[0]["source_url"] == "https://example.com/careers"
    assert json_rows[0]["verification"] == 0
    assert json_rows[0]["company_name"] == "Acme"
    assert json_rows[0]["AI_tool_used"] == "GitHub Copilot"
    assert json_rows[0]["evidence_description"] == "Uses Copilot for PR review"
    assert json_rows[1]["source_url"] == "https://example.com/missing"
    assert json_rows[1]["verification"] is None
    assert json_rows[1]["unverifiable"] is True
    assert json_rows[1]["error"] == "fetch_url returned no page content"
    assert json_rows[1]["channel"] == "owned"

    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["source_url"] == "https://example.com/careers"
    assert csv_rows[0]["verification"] == "0"
    assert csv_rows[0]["company_name"] == "Acme"
    assert csv_rows[0]["architecture"] == "uas"
    assert csv_rows[1]["source_url"] == "https://example.com/missing"
    assert csv_rows[1]["verification"] == ""
    assert csv_rows[1]["unverifiable"] == "true"
    assert csv_rows[1]["evidence_description"] == "Uses Claude for coding"
    assert csv_rows[1]["AI_tool_used"] == "Claude"


def test_cli_writes_output_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    findings = tmp_path / "findings.jsonl"
    findings.write_text(
        json.dumps(
            {
                "finding_id": 9,
                "source_url": "https://example.com/z",
                "evidence_description": "Uses Cursor for coding",
                "company_name": "Zed Inc",
                "rcid": 7,
                "channel": "owned",
            }
        )
        + "\n"
        + json.dumps(
            {
                "finding_id": 10,
                "source_url": "",
                "evidence_description": "Uses Copilot",
                "company_name": "Zed Inc",
                "rcid": 7,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    jsonl_path = tmp_path / "out" / "verdicts.jsonl"
    csv_path = tmp_path / "out" / "verdicts.csv"
    code = cli.main(
        [
            "--dry-run",
            "--findings",
            str(findings),
            "--output-jsonl",
            str(jsonl_path),
            "--output-csv",
            str(csv_path),
        ]
    )
    assert code == 0
    capsys.readouterr()
    json_rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert json_rows[0]["source_url"] == "https://example.com/z"
    assert json_rows[0]["company_name"] == "Zed Inc"
    assert json_rows[0]["verification"] is None
    assert json_rows[1]["unverifiable"] is True
    assert json_rows[1]["source_url"] == ""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert csv_rows[0]["source_url"] == "https://example.com/z"
    assert csv_rows[0]["evidence_description"] == "Uses Cursor for coding"
    assert csv_rows[1]["verification"] == ""
    assert csv_rows[1]["error"]
