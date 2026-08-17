"""Offline tests for the production batch runner. No paid API calls."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from contracts.types import (
    ArchitectureResult,
    CostComponent,
    CostLedger,
    Finding,
)
from production.__main__ import main
from production.persist import (
    RESEARCH_COLUMNS,
    VERIFIED_COLUMNS,
    backup_retryable,
    is_complete_success,
    load_dataset,
    load_payload,
    prod_paths,
    rebuild_jsonl_from_companies,
    write_company_json,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _dataset(path: Path, n: int = 5) -> Path:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "rcid": i,
                "name": f"Co{i}",
                "homepage_url": f"https://co{i}.example",
                "short_description": f"desc {i}",
                "research_priority_score": 5,
            }
        )
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _finding(rcid: int) -> Finding:
    return Finding(
        finding_id=1,
        AI_tool_used="GitHub Copilot",
        use_case="code review",
        business_function="Engineering",
        evidence_description="Uses Copilot for pull requests",
        source_url=f"https://co{rcid}.example/jobs",
        source_type="careers",
        channel="jobs",
    )


def _sgs_result(
    company,
    *,
    findings: list[Finding] | None = None,
    error: str | None = None,
) -> ArchitectureResult:
    if isinstance(company, dict):
        rcid = int(company["rcid"])
        name = company["name"]
    else:
        rcid = int(company.rcid)
        name = company.name
    rows = findings if findings is not None else [_finding(rcid)]
    ledger = CostLedger.from_components(
        [
            CostComponent(name="scout_jobs", preset="low", cost_usd=0.01, channel="jobs"),
            CostComponent(name="scout_owned", preset="low", cost_usd=0.01, channel="owned"),
            CostComponent(
                name="scout_third_party",
                preset="low",
                cost_usd=0.01,
                channel="third_party",
            ),
            CostComponent(name="dig_jobs", preset="luna_high", cost_usd=0.10, channel="jobs"),
        ]
    )
    return ArchitectureResult(
        rcid=rcid,
        company_name=name,
        architecture="signal-gated-search",
        findings=rows,
        cost_ledger=ledger,
        genai_adoption_found=bool(rows),
        no_finding_reason=None if rows else "no_channel_above_signal_threshold",
        traces={
            "gate": {
                "dig_count": 1 if rows else 0,
                "dig_channels": ["jobs"] if rows else [],
                "stop_at_scouts": not bool(rows),
            },
            "scout_results": {
                "jobs": {"evidence_bin": "moderate"},
                "owned": {"evidence_bin": "none"},
                "third_party": {"evidence_bin": "none"},
            },
        },
        error=error,
        stub=False,
        dry_run=False,
        duration_seconds=1.5,
    )


def _pcs_result(company, **_kwargs) -> ArchitectureResult:
    rcid = int(company["rcid"] if isinstance(company, dict) else company.rcid)
    name = company["name"] if isinstance(company, dict) else company.name
    return ArchitectureResult(
        rcid=rcid,
        company_name=name,
        architecture="parallel-channel-search",
        findings=[_finding(rcid)],
        cost_ledger=CostLedger.from_components(
            [
                CostComponent(name="channel_jobs", preset="pcs", cost_usd=0.05, channel="jobs"),
                CostComponent(name="channel_owned", preset="pcs", cost_usd=0.05, channel="owned"),
                CostComponent(
                    name="channel_third_party",
                    preset="pcs",
                    cost_usd=0.05,
                    channel="third_party",
                ),
            ]
        ),
        genai_adoption_found=True,
        traces={"channels": ["jobs", "owned", "third_party"]},
        dry_run=False,
        duration_seconds=2.0,
    )


def _install_fake(monkeypatch, *, sgs=None, pcs=None, uas=None) -> None:
    from production import run as run_mod

    runners = dict(run_mod.RUNNERS)
    if sgs is not None:
        runners["sgs"] = sgs
    if pcs is not None:
        runners["pcs"] = pcs
    if uas is not None:
        runners["uas"] = uas
    monkeypatch.setattr(run_mod, "RUNNERS", runners)


def _cli(args: list[str]) -> int:
    return main(args)


def _capture_cli(args: list[str]) -> tuple[int, str]:
    from io import StringIO
    import sys

    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    code = 0
    try:
        code = main(args)
    except SystemExit as exc:
        code = int(exc.code) if exc.code is not None else 1
    finally:
        sys.stdout = old
    return code, buf.getvalue()


def test_live_run_requires_limit_or_all(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl")
    with pytest.raises(SystemExit, match="requires --limit N or --all"):
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(tmp_path / "prod"),
            ]
        )
    assert not (tmp_path / "prod").exists()


def test_limit_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=5)
    output_root = tmp_path / "prod"
    seen: list[int] = []

    def fake_sgs(company, *, dry_run=False, **_kwargs):
        assert dry_run is False
        rcid = int(company["rcid"])
        seen.append(rcid)
        return _sgs_result(company)

    _install_fake(monkeypatch, sgs=fake_sgs)
    common = [
        "run",
        "--architecture",
        "sgs",
        "--dataset",
        str(dataset),
        "--output-root",
        str(output_root),
        "--concurrency",
        "2",
    ]
    assert _cli([*common, "--limit", "2"]) == 0
    assert seen == [1, 2] or set(seen) == {1, 2}
    first_seen = list(seen)
    assert _cli([*common, "--limit", "2"]) == 0
    assert set(seen) == {1, 2, 3, 4}
    assert set(seen[len(first_seen) :]) == {3, 4}

    sgs_dir = output_root / "sgs"
    assert (sgs_dir / "companies" / "1.json").exists()
    assert (sgs_dir / "companies" / "3.json").exists()
    assert not (sgs_dir / "companies" / "5.json").exists()
    jsonl_rcids = [
        json.loads(line)["rcid"]
        for line in (sgs_dir / "findings.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert jsonl_rcids == [1, 2, 3, 4]


def test_architecture_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=2)
    output_root = tmp_path / "prod"
    sgs_calls: list[int] = []
    pcs_calls: list[int] = []

    def fake_sgs(company, **_kwargs):
        sgs_calls.append(int(company["rcid"]))
        return _sgs_result(company)

    def fake_pcs(company, **_kwargs):
        pcs_calls.append(int(company["rcid"]))
        return _pcs_result(company)

    _install_fake(monkeypatch, sgs=fake_sgs, pcs=fake_pcs)
    common = [
        "--dataset",
        str(dataset),
        "--output-root",
        str(output_root),
        "--limit",
        "1",
        "--concurrency",
        "1",
    ]
    assert _cli(["run", "--architecture", "sgs", *common]) == 0
    assert _cli(["run", "--architecture", "pcs", *common]) == 0
    assert sgs_calls == [1]
    assert pcs_calls == [1]
    assert (output_root / "sgs" / "companies" / "1.json").exists()
    assert (output_root / "pcs" / "companies" / "1.json").exists()
    assert _cli(["run", "--architecture", "sgs", *common]) == 0
    # PCS files must not count as SGS resume. Limit 1 skips done SGS #1 and takes #2.
    assert sgs_calls == [1, 2]
    assert pcs_calls == [1]
    assert not (output_root / "pcs" / "companies" / "2.json").exists()


def test_csv_column_order_and_sgs_cost_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    _install_fake(monkeypatch, sgs=lambda company, **_k: _sgs_result(company))
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    with (output_root / "sgs" / "findings.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(RESEARCH_COLUMNS)
        rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["rcid"] == "1"
    assert row["architecture"] == "sgs"
    assert row["AI_tool_used"] == "GitHub Copilot"
    assert row["scout_jobs"] == "moderate"
    assert row["scout_owned"] == "none"
    assert row["dig_count"] == "1"
    assert row["dig_channels"] == "jobs"
    assert float(row["scout_cost_usd"]) == pytest.approx(0.03)
    assert float(row["dig_cost_usd"]) == pytest.approx(0.10)
    payload = json.loads((output_root / "sgs" / "companies" / "1.json").read_text())
    assert "traces" in payload
    assert "no_finding_analysis" in payload
    assert "input_tokens" not in row


def test_zero_finding_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"

    def fake_sgs(company, **_kwargs):
        return _sgs_result(company, findings=[])

    _install_fake(monkeypatch, sgs=fake_sgs)
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    with (output_root / "sgs" / "findings.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["finding_id"] == ""
    assert rows[0]["AI_tool_used"] == ""
    assert rows[0]["source_url"] == ""
    assert rows[0]["findings_count"] == "0"
    assert rows[0]["genai_adoption_found"] == "false"
    assert rows[0]["no_finding_reason"] == "no_channel_above_signal_threshold"


def test_pcs_scout_columns_blank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    _install_fake(monkeypatch, pcs=_pcs_result)
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "pcs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    with (output_root / "pcs" / "findings.csv").open(encoding="utf-8", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
    assert row["scout_jobs"] == ""
    assert row["scout_cost_usd"] == "0.0"
    assert float(row["dig_cost_usd"]) == pytest.approx(0.15)
    assert row["dig_count"] == "3"


def test_dry_run_writes_no_paid_artifacts(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=2)
    output_root = tmp_path / "prod"
    assert (
        _cli(
            [
                "dry-run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "2",
            ]
        )
        == 0
    )
    assert not (output_root / "sgs" / "companies").exists()
    assert not (output_root / "sgs" / "findings.csv").exists()
    assert not (output_root / "sgs" / "findings.jsonl").exists()


def _deduped_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rcid",
        "company_name",
        "finding_id",
        "evidence_description",
        "source_url",
        "AI_tool_used",
        "channel",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return path


def test_dedupe_writes_derived_csv_and_leaves_raw(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    sgs = output_root / "sgs"
    sgs.mkdir(parents=True)
    raw = (
        "rcid,company_name,homepage_url,short_description,research_priority_score,"
        "architecture,finding_id,AI_tool_used,use_case,business_function,"
        "evidence_description,source_url,source_type,channel,genai_adoption_found,"
        "findings_count,no_finding_reason,error,duration_seconds,scout_jobs,"
        "scout_owned,scout_third_party,dig_count,dig_channels,cost_usd,"
        "scout_cost_usd,dig_cost_usd\n"
        "1,Co1,https://co1.example,desc,5,sgs,1,Claude Code,"
        "AI-assisted software development,Engineering,"
        "The Head of Engineering posting names Claude Code,"
        "https://www.linkedin.com/jobs/view/head-of-engineering,jobs,jobs,true,2,"
        ",,1,none,none,none,1,jobs,0.1,0.02,0.08\n"
        "1,Co1,https://co1.example,desc,5,sgs,2,Claude Code,"
        "AI-assisted software development,Engineering,"
        "A third-party mirror of the Head of Engineering posting names Claude Code,"
        "https://jobright.ai/jobs/info/abc123,jobs,third_party,true,2,"
        ",,1,none,none,none,1,jobs,0.1,0.02,0.08\n"
    )
    findings = sgs / "findings.csv"
    findings.write_text(raw, encoding="utf-8")
    code, out = _capture_cli(
        [
            "dedupe",
            "--architecture",
            "sgs",
            "--dataset",
            str(_dataset(tmp_path / "companies.jsonl", n=1)),
            "--output-root",
            str(output_root),
        ]
    )
    assert code == 0
    assert "dropped=1" in out
    derived = sgs / "findings_deduplicated.csv"
    assert derived.exists()
    assert findings.read_text(encoding="utf-8") == raw
    with derived.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["finding_id"] == "1"
    assert rows[0]["source_url"].startswith("https://www.linkedin.com/")
    assert rows[0]["findings_count"] == "1"


def test_verify_uses_deduplicated_csv_and_renames_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    _install_fake(monkeypatch, sgs=lambda company, **_k: _sgs_result(company))
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    findings = output_root / "sgs" / "findings.csv"
    deduped = output_root / "sgs" / "findings_deduplicated.csv"
    deduped.write_text(findings.read_text(encoding="utf-8"), encoding="utf-8")
    assert (
        _cli(
            [
                "verify",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--all",
            ]
        )
        == 0
    )
    verified = output_root / "sgs" / "findings_verified.csv"
    assert verified.exists()
    with verified.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(VERIFIED_COLUMNS)
        row = list(reader)[0]
    assert "verification_error" in row
    assert row["verification_error"] == "dry_run_no_api"
    assert row["verification"] == ""
    assert row["AI_tool_used"] == "GitHub Copilot"
    assert row["error"] == ""


def test_verify_requires_deduplicated_csv(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    sgs = output_root / "sgs"
    sgs.mkdir(parents=True)
    (sgs / "findings.csv").write_text(
        "rcid,source_url,evidence_description\n1,https://raw.example,Uses Claude\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="findings_deduplicated.csv"):
        _cli(
            [
                "verify",
                "--architecture",
                "sgs",
                "--dataset",
                str(_dataset(tmp_path / "companies.jsonl", n=1)),
                "--output-root",
                str(output_root),
                "--all",
            ]
        )


def test_verify_requires_limit_or_all(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    _deduped_csv(
        output_root / "sgs" / "findings_deduplicated.csv",
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 1,
                "evidence_description": "Uses Claude",
                "source_url": "https://co1.example",
            }
        ],
    )
    with pytest.raises(SystemExit, match="--limit N or --all"):
        _cli(
            [
                "verify",
                "--architecture",
                "sgs",
                "--dataset",
                str(_dataset(tmp_path / "companies.jsonl", n=1)),
                "--output-root",
                str(output_root),
            ]
        )


def test_verify_limit_resumes_and_appends(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    _deduped_csv(
        output_root / "sgs" / "findings_deduplicated.csv",
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 1,
                "evidence_description": "Uses Claude",
                "source_url": "https://co1.example/one",
            },
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 2,
                "evidence_description": "Uses Copilot",
                "source_url": "https://co1.example/two",
            },
            {
                "rcid": 2,
                "company_name": "Co2",
                "finding_id": 1,
                "evidence_description": "Uses Cursor",
                "source_url": "https://co2.example/one",
            },
        ],
    )
    common = [
        "verify",
        "--architecture",
        "sgs",
        "--dataset",
        str(dataset),
        "--output-root",
        str(output_root),
        "--limit",
        "1",
    ]
    assert _cli(common) == 0
    verified = output_root / "sgs" / "findings_verified.csv"
    first = list(csv.DictReader(verified.open(encoding="utf-8", newline="")))
    assert len(first) == 1
    assert first[0]["finding_id"] == "1"
    assert first[0]["source_url"] == "https://co1.example/one"
    assert first[0]["verification_error"] == "dry_run_no_api"
    assert _cli(common) == 0
    second = list(csv.DictReader(verified.open(encoding="utf-8", newline="")))
    assert len(second) == 2
    assert [row["source_url"] for row in second] == [
        "https://co1.example/one",
        "https://co1.example/two",
    ]


def test_verify_status_counts_remaining(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    _deduped_csv(
        output_root / "sgs" / "findings_deduplicated.csv",
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 1,
                "evidence_description": "Uses Claude",
                "source_url": "https://co1.example/one",
            },
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 2,
                "evidence_description": "Uses Copilot",
                "source_url": "https://co1.example/two",
            },
        ],
    )
    assert (
        _cli(
            [
                "verify",
                "--architecture",
                "sgs",
                "--dataset",
                str(_dataset(tmp_path / "companies.jsonl", n=1)),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    code, text = _capture_cli(
        [
            "verify",
            "--architecture",
            "sgs",
            "--dataset",
            str(_dataset(tmp_path / "companies.jsonl", n=1)),
            "--output-root",
            str(output_root),
            "--status",
        ]
    )
    assert code == 0
    assert "verified done: 1" in text
    assert "verified remaining: 1" in text


def test_verify_requeues_429_and_does_not_repay_complete(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    sgs = output_root / "sgs"
    _deduped_csv(
        sgs / "findings_deduplicated.csv",
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 1,
                "evidence_description": "Uses Claude",
                "source_url": "https://co1.example/one",
            },
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 2,
                "evidence_description": "Uses Copilot",
                "source_url": "https://co1.example/two",
            },
        ],
    )
    (sgs / "findings_verified.jsonl").write_text(
        json.dumps(
            {
                "rcid": 1,
                "finding_id": 1,
                "source_url": "https://co1.example/one",
                "evidence_description": "Uses Claude",
                "verification": "",
                "verification_error": "429 rate limit",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        _cli(
            [
                "verify",
                "--architecture",
                "sgs",
                "--dataset",
                str(_dataset(tmp_path / "companies.jsonl", n=1)),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
            ]
        )
        == 0
    )
    rows = list(
        csv.DictReader((sgs / "findings_verified.csv").open(encoding="utf-8", newline=""))
    )
    assert len(rows) == 1
    assert rows[0]["finding_id"] == "1"
    assert rows[0]["verification_error"] == "dry_run_no_api"


def test_verify_runs_findings_in_parallel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time
    from threading import Lock

    from citation_verification.types import VerdictResult
    from production.verify import run_verify

    output_root = tmp_path / "prod"
    _deduped_csv(
        output_root / "sgs" / "findings_deduplicated.csv",
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": i,
                "evidence_description": f"Uses tool {i}",
                "source_url": f"https://co1.example/{i}",
            }
            for i in range(1, 4)
        ],
    )
    state = {"n": 0, "max": 0}
    lock = Lock()

    def _fake_verify(row, dry_run=True, **_kwargs):  # noqa: ARG001
        with lock:
            state["n"] += 1
            state["max"] = max(state["max"], state["n"])
        time.sleep(0.2)
        with lock:
            state["n"] -= 1
        return VerdictResult(
            finding_id=int(row["finding_id"]),
            source_url=str(row["source_url"]),
            verification=1,
            dry_run=True,
            error="dry_run_no_api",
        )

    monkeypatch.setattr("production.verify.verify_finding", _fake_verify)
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=True,
        limit=3,
        concurrency=3,
    )
    assert state["max"] >= 2
    rows = list(
        csv.DictReader(
            (output_root / "sgs" / "findings_verified.csv").open(
                encoding="utf-8", newline=""
            )
        )
    )
    assert len(rows) == 3


def test_verify_help_says_findings_not_companies() -> None:
    code, text = _capture_cli(["verify", "--help"])
    assert code == 0
    assert "Max findings in flight" in text
    assert "Companies in flight" not in text


def test_status_lists_next_rcids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=4)
    output_root = tmp_path / "prod"
    _install_fake(monkeypatch, sgs=lambda company, **_k: _sgs_result(company))
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "2",
            ]
        )
        == 0
    )
    report = collect_printed_status(dataset, output_root, limit=2)
    assert "done: 2" in report
    assert "remaining: 2" in report
    assert "next (--limit 2): 3, 4" in report


def collect_printed_status(dataset: Path, output_root: Path, limit: int) -> str:
    from io import StringIO
    import sys

    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        _cli(
            [
                "status",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                str(limit),
            ]
        )
    finally:
        sys.stdout = old
    return buf.getvalue()


def test_keep_success_does_not_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "1.json"
    success = {"rcid": 1, "error": None, "findings": [{"finding_id": 1}]}
    failure = {"rcid": 1, "error": "TimeoutError: late fail", "findings": []}
    write_company_json(path, success)
    outcome = write_company_json(path, failure)
    assert outcome.action == "kept_success"
    assert is_complete_success(load_payload(path))
    assert outcome.backup is not None
    assert outcome.backup.exists()
    assert json.loads(outcome.backup.read_text())["error"] == "TimeoutError: late fail"


def test_permanent_error_does_not_consume_next_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=3)
    output_root = tmp_path / "prod"
    calls: list[int] = []

    def fake_sgs(company, **_kwargs):
        rcid = int(company["rcid"])
        calls.append(rcid)
        if rcid == 1:
            return _sgs_result(company, error="ValueError: bad company record")
        return _sgs_result(company)

    _install_fake(monkeypatch, sgs=fake_sgs)
    common = [
        "run",
        "--architecture",
        "sgs",
        "--dataset",
        str(dataset),
        "--output-root",
        str(output_root),
        "--concurrency",
        "1",
    ]
    assert _cli([*common, "--limit", "1"]) == 1
    assert calls == [1]
    assert _cli([*common, "--limit", "1"]) == 0
    assert calls == [1, 2]
    report = collect_printed_status(dataset, output_root, limit=2)
    assert "errors: 1" in report
    assert "next (--limit 2): 3" in report
    assert "1" not in report.split("next (--limit 2):")[1]


def test_status_spend_includes_429_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    _install_fake(
        monkeypatch,
        sgs=lambda company, **_k: _sgs_result(company, error="RateLimitError: 429"),
    )
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
                "--concurrency",
                "1",
            ]
        )
        == 1
    )
    from production.persist import prod_paths, sum_recorded_spend

    paths = prod_paths(output_root, "sgs")
    backups = list(paths.companies.glob("1.*.429.json"))
    assert backups
    # First attempt is the sidecar. Last attempt stays canonical. Both billed.
    assert sum_recorded_spend(paths) == pytest.approx(0.26)
    report = collect_printed_status(dataset, output_root, limit=1)
    assert "spend: $0.2600" in report


def test_retryable_429_is_requeued(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    calls = {"n": 0}

    def fake_sgs(company, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _sgs_result(company, error="RateLimitError: 429")
        return _sgs_result(company)

    _install_fake(monkeypatch, sgs=fake_sgs)
    assert (
        _cli(
            [
                "run",
                "--architecture",
                "sgs",
                "--dataset",
                str(dataset),
                "--output-root",
                str(output_root),
                "--limit",
                "1",
                "--concurrency",
                "1",
            ]
        )
        == 0
    )
    assert calls["n"] == 2
    payload = json.loads((output_root / "sgs" / "companies" / "1.json").read_text())
    assert payload.get("error") in (None, "")
    backups = list((output_root / "sgs" / "companies").glob("1.*.429.json"))
    assert backups


def test_rebuild_keeps_unlinked_429_in_findings(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    paths = prod_paths(output_root, "sgs")
    paths.companies.mkdir(parents=True)
    payload = {
        "rcid": 1,
        "company_name": "Co1",
        "architecture": "sgs",
        "findings": [],
        "findings_count": 0,
        "cost_usd": 0.13,
        "error": "RateLimitError: 429",
        "homepage_url": "https://co1.example",
        "short_description": "desc 1",
        "research_priority_score": 5,
    }
    canonical = paths.company_json(1)
    canonical.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    backup_retryable(canonical, "429")
    assert not canonical.exists()
    rebuild_jsonl_from_companies(paths, load_dataset(dataset))
    lines = [
        json.loads(line)
        for line in paths.findings_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["rcid"] == 1
    assert "429" in str(lines[0].get("error"))
    with paths.findings_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["rcid"] == "1"
    assert "429" in rows[0]["error"]


def test_nothing_to_run_reports_parked_remaining(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = _dataset(tmp_path / "companies.jsonl", n=1)
    output_root = tmp_path / "prod"
    _install_fake(
        monkeypatch,
        sgs=lambda company, **_k: _sgs_result(
            company, error="ValueError: bad company record"
        ),
    )
    common = [
        "run",
        "--architecture",
        "sgs",
        "--dataset",
        str(dataset),
        "--output-root",
        str(output_root),
        "--limit",
        "1",
        "--concurrency",
        "1",
    ]
    assert _cli(common) == 1
    code, out = _capture_cli(common)
    assert code == 1
    assert "NOTHING_TO_RUN" in out
    assert "remaining=1" in out
    assert "parked=1" in out


def _git_ignores(rel_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel_path],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return result.returncode == 0


def test_prod_outputs_are_gitignored() -> None:
    assert _git_ignores("outputs/prod/sgs/companies/1247.json")
    assert _git_ignores("outputs/prod/sgs/findings.csv")
    assert _git_ignores("outputs/prod/pcs/findings.jsonl")
