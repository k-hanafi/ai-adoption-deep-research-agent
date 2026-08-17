"""Page-cache sidecar: scrape once, judge again without refetching."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from citation_verification.fetch import FetchResult
from citation_verification.judge import JudgeResult
from production.__main__ import main
from production.pages import (
    append_page_record,
    fetch_from_record,
    load_pages_by_url,
    page_cache_reusable,
    record_from_fetch,
)
from production.persist import VERIFIED_COLUMNS, prod_paths
from production.verify import run_verify

FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def _one_finding(path: Path, *, url: str = "https://co1.example/careers") -> Path:
    return _deduped_csv(
        path,
        [
            {
                "rcid": 1,
                "company_name": "Co1",
                "finding_id": 1,
                "evidence_description": "Uses Copilot for PR review",
                "source_url": url,
            }
        ],
    )


def _judge_ok() -> JudgeResult:
    raw = json.loads(
        (FIXTURES / "citation_verification_one.json").read_text(encoding="utf-8")
    )
    raw = dict(raw)
    raw["model"] = "gpt-5.6-luna"
    raw["usage"] = {"cost": {"total_cost": 0.002}}
    return JudgeResult(
        verification=1,
        confidence_1_5=4,
        verification_reasoning="Snippet mentions Copilot for PR review.",
        verification_critique="Could be aspirational copy.",
        cost_usd=0.002,
        model="gpt-5.6-luna",
        raw=raw,
    )


def _page(url: str) -> FetchResult:
    return FetchResult(
        url=url,
        title="Careers",
        snippet="Our engineers use GitHub Copilot when reviewing pull requests every day.",
        cost_usd=0.0003,
        source="perplexity",
        attempts=1,
        truncated=False,
    )


def _install_live(monkeypatch: pytest.MonkeyPatch, *, fetch=None, judge=None) -> dict:
    from citation_verification import runner as runner_mod

    state = {"fetch": 0, "judge": 0}

    def _fetch(url: str, **_kwargs: object) -> FetchResult:
        state["fetch"] += 1
        if fetch is not None:
            return fetch(url)
        return _page(url)

    def _judge(**_kwargs: object) -> JudgeResult:
        state["judge"] += 1
        if judge is not None:
            return judge()
        return _judge_ok()

    monkeypatch.setattr(runner_mod, "execute_fetch", _fetch)
    monkeypatch.setattr(
        runner_mod,
        "execute_backup_chain",
        lambda url, **_: FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error="backup unused",
        ),
    )
    monkeypatch.setattr(runner_mod, "execute_judge", _judge)
    return state


def test_pages_jsonl_last_write_per_url_wins(tmp_path: Path) -> None:
    path = tmp_path / "pages.jsonl"
    first = record_from_fetch(
        "https://co1.example/a",
        FetchResult(
            url="https://co1.example/a",
            title="Old",
            snippet="old text " * 10,
            cost_usd=0.01,
            error="429 rate limit",
        ),
        fetch_cost=0.01,
        fetch_attempts=2,
        fetched_at="2026-08-17T00:00:00+00:00",
    )
    second = record_from_fetch(
        "https://co1.example/a",
        _page("https://co1.example/a"),
        fetch_cost=0.0003,
        fetch_attempts=1,
        fetched_at="2026-08-17T01:00:00+00:00",
    )
    append_page_record(path, first)
    append_page_record(path, second)
    loaded = load_pages_by_url(path)
    assert set(loaded) == {"https://co1.example/a"}
    assert loaded["https://co1.example/a"]["snippet"].startswith("Our engineers")
    assert loaded["https://co1.example/a"]["fetch_ok"] is True
    assert page_cache_reusable(first) is False
    assert page_cache_reusable(second) is True
    replay = fetch_from_record(second)
    assert replay.ok is True
    assert replay.cost_usd == 0.0


def test_live_verify_writes_page_cache_before_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "prod"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv")
    state = _install_live(monkeypatch)
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        limit=1,
        concurrency=1,
    )
    assert state["fetch"] >= 1
    assert state["judge"] >= 1
    paths = prod_paths(output_root, "sgs")
    pages = load_pages_by_url(paths.pages_jsonl)
    record = pages["https://co1.example/careers"]
    assert "GitHub Copilot" in record["snippet"]
    assert record["fetch_ok"] is True
    assert record["fetched_title"] == "Careers"
    assert record["fetch_source"]
    assert record["fetched_at"]
    with paths.findings_verified_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(VERIFIED_COLUMNS)
        row = list(reader)[0]
    assert "evidence_snippet" not in (reader.fieldnames or [])
    assert "snippet" not in row
    assert row["verification"] == "1"


def test_second_verify_judges_from_disk_when_fetch_explodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "prod"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv")
    _install_live(monkeypatch)
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        limit=1,
        concurrency=1,
    )

    from citation_verification import runner as runner_mod

    def _boom(url: str, **_kwargs: object) -> FetchResult:
        raise AssertionError(f"fetch must not run on cache hit: {url}")

    judge_calls = {"n": 0}

    def _judge(**_kwargs: object) -> JudgeResult:
        judge_calls["n"] += 1
        return _judge_ok()

    monkeypatch.setattr(runner_mod, "execute_fetch", _boom)
    monkeypatch.setattr(runner_mod, "execute_backup_chain", _boom)
    monkeypatch.setattr(runner_mod, "execute_judge", _judge)
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        from_cache=True,
        limit=1,
        concurrency=1,
    )
    assert judge_calls["n"] >= 1
    paths = prod_paths(output_root, "sgs")
    rows = [
        json.loads(line)
        for line in paths.findings_verified_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    replay = rows[-1]
    assert replay["verification"] == 1
    assert float(replay["verification_cost_usd"]) == pytest.approx(0.002)
    with paths.findings_verified_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(VERIFIED_COLUMNS)


def test_from_cache_skips_urls_without_a_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "prod"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv")
    from citation_verification import runner as runner_mod

    def _boom(url: str, **_kwargs: object) -> FetchResult:
        raise AssertionError(f"fetch must not run: {url}")

    monkeypatch.setattr(runner_mod, "execute_fetch", _boom)
    monkeypatch.setattr(runner_mod, "execute_backup_chain", _boom)
    monkeypatch.setattr(
        runner_mod,
        "execute_judge",
        lambda **_: (_ for _ in ()).throw(AssertionError("judge must not run")),
    )
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        from_cache=True,
        limit=1,
        concurrency=1,
    )
    paths = prod_paths(output_root, "sgs")
    assert not paths.findings_verified_jsonl.exists() or (
        not paths.findings_verified_jsonl.read_text(encoding="utf-8").strip()
    )


def test_retryable_page_cache_is_not_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "prod"
    url = "https://co1.example/careers"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv", url=url)
    paths = prod_paths(output_root, "sgs")
    append_page_record(
        paths.pages_jsonl,
        record_from_fetch(
            url,
            FetchResult(
                url=url,
                title="",
                snippet="",
                cost_usd=0.01,
                error="429 rate limit",
            ),
            fetch_cost=0.01,
            fetch_attempts=3,
        ),
    )
    state = _install_live(monkeypatch)
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        limit=1,
        concurrency=1,
    )
    assert state["fetch"] >= 1
    pages = load_pages_by_url(paths.pages_jsonl)
    assert pages[url]["fetch_ok"] is True
    assert "Copilot" in pages[url]["snippet"]


def test_from_cache_requires_live(tmp_path: Path) -> None:
    _one_finding(tmp_path / "prod" / "sgs" / "findings_deduplicated.csv")
    with pytest.raises(SystemExit, match="--from-cache requires --live"):
        main(
            [
                "verify",
                "--architecture",
                "sgs",
                "--output-root",
                str(tmp_path / "prod"),
                "--from-cache",
                "--limit",
                "1",
            ]
        )


def test_failed_fetch_is_still_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "prod"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv")
    from citation_verification import runner as runner_mod

    monkeypatch.setattr(
        runner_mod,
        "execute_fetch",
        lambda url, **_: FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0001,
            error="snippet too short (0 chars; min 40)",
        ),
    )
    monkeypatch.setattr(
        runner_mod,
        "execute_backup_chain",
        lambda url, **_: FetchResult(
            url=url,
            title="",
            snippet="",
            cost_usd=0.0,
            error="snippet too short (0 chars; min 40)",
        ),
    )
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=False,
        limit=1,
        concurrency=1,
    )
    pages = load_pages_by_url(prod_paths(output_root, "sgs").pages_jsonl)
    record = pages["https://co1.example/careers"]
    assert record["fetch_ok"] is False
    assert "snippet too short" in record["error"]


def test_dry_run_does_not_write_pages(tmp_path: Path) -> None:
    output_root = tmp_path / "prod"
    _one_finding(output_root / "sgs" / "findings_deduplicated.csv")
    run_verify(
        architecture="sgs",
        output_root=output_root,
        dry_run=True,
        limit=1,
        concurrency=1,
    )
    paths = prod_paths(output_root, "sgs")
    assert not paths.pages_jsonl.exists()
    with paths.findings_verified_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(VERIFIED_COLUMNS)
