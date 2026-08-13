"""SGS dry orchestrator: scout snapshots → gate → 0–3 dig snapshots."""

from __future__ import annotations

import pytest

from contracts.types import CompanyInput
from evals.runner import run_panel
from signal_gated_search.agent_call import build_dig_request_kwargs
from signal_gated_search.channels import CHANNEL_IDS, dig_config_label
from signal_gated_search.runner import run

COMPANY = CompanyInput(
    rcid=610194,
    name="Jam",
    homepage_url="https://jam.dev",
    short_description="A test company",
)


def _signaled(*channels: str) -> list[dict]:
    rows = []
    signaled = set(channels)
    for channel in CHANNEL_IDS:
        if channel in signaled:
            rows.append(
                {
                    "channel": channel,
                    "evidence_bin": "moderate",
                    "urls": [f"https://example.com/{channel}"],
                    "snippets": ["room exists"],
                    "rationale": "test",
                }
            )
        else:
            rows.append(
                {
                    "channel": channel,
                    "evidence_bin": "none",
                    "urls": [],
                    "snippets": [],
                    "rationale": "test",
                }
            )
    return rows


def _component_names(result) -> list[str]:
    return [row.name for row in result.cost_ledger.components]


def test_dry_default_stops_at_scouts() -> None:
    result = run(COMPANY, dry_run=True)
    assert result.dry_run is True
    assert result.stub is True
    assert result.no_finding_reason == "dry_run"
    assert result.traces["phase"] == "dry_run"
    assert result.traces["cold_start"] is True
    assert result.traces["gate"]["stop_at_scouts"] is True
    assert result.traces["gate"]["dig_count"] == 0
    assert list(result.traces["request_snapshots"]["scouts"]) == list(CHANNEL_IDS)
    assert result.traces["request_snapshots"]["digs"] == {}
    assert _component_names(result) == [
        "scout_jobs",
        "scout_owned",
        "scout_third_party",
    ]
    assert result.cost_ledger.total_usd == 0.0
    for row in result.cost_ledger.components:
        assert row.ran is False
        assert row.skipped_reason == "dry_run_no_api"


def test_dry_n1_digs_at_max() -> None:
    result = run(COMPANY, dry_run=True, scout_outputs=_signaled("jobs"))
    gate = result.traces["gate"]
    assert gate["dig_channels"] == ["jobs"]
    assert gate["dig_count"] == 1
    assert gate["reasoning_effort"] == "max"
    assert list(result.traces["request_snapshots"]["digs"]) == ["jobs"]
    assert "dig_jobs" in _component_names(result)
    assert "dig_owned" not in _component_names(result)
    assert result.cost_ledger.components[-1].preset == dig_config_label("max")
    snap = result.traces["request_snapshots"]["digs"]["jobs"]
    assert snap["reasoning"] == {"effort": "max"}
    assert snap["has_preset"] is False


def test_dry_n2_digs_at_high() -> None:
    result = run(COMPANY, dry_run=True, scout_outputs=_signaled("jobs", "owned"))
    assert result.traces["gate"]["reasoning_effort"] == "high"
    assert result.traces["gate"]["dig_channels"] == ["jobs", "owned"]
    assert list(result.traces["request_snapshots"]["digs"]) == ["jobs", "owned"]
    assert _component_names(result)[-2:] == ["dig_jobs", "dig_owned"]


def test_dry_n3_digs_at_medium() -> None:
    result = run(
        COMPANY,
        dry_run=True,
        scout_outputs=_signaled("jobs", "owned", "third_party"),
    )
    assert result.traces["gate"]["reasoning_effort"] == "medium"
    assert list(result.traces["request_snapshots"]["digs"]) == list(CHANNEL_IDS)
    assert _component_names(result) == [
        "scout_jobs",
        "scout_owned",
        "scout_third_party",
        "dig_jobs",
        "dig_owned",
        "dig_third_party",
    ]


def test_dry_dig_input_is_cold_start() -> None:
    scout_url = "https://careers.should-not-leak.example/jobs"
    result = run(
        COMPANY,
        dry_run=True,
        scout_outputs=[
            {
                "channel": "jobs",
                "evidence_bin": "strong",
                "urls": [scout_url],
                "snippets": ["hiring page"],
                "rationale": "test",
            }
        ],
    )
    kwargs = build_dig_request_kwargs(
        COMPANY,
        "jobs",
        reasoning_effort=result.traces["gate"]["reasoning_effort"],
    )
    assert scout_url not in kwargs["input"]
    assert "Jam" in kwargs["input"]


def test_live_still_unimplemented() -> None:
    with pytest.raises(NotImplementedError, match="next PR"):
        run(COMPANY, dry_run=False)


def test_run_panel_sgs_dry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("evals.runner.EVAL_RUNS_DIR", tmp_path)
    run_dir = run_panel("sgs", dry_run=True, run_id="sgs_dry_fixture")
    predictions = (run_dir / "predictions.jsonl").read_text(encoding="utf-8").strip()
    assert predictions
    assert len(predictions.splitlines()) == 2
    traces = list((run_dir / "traces").glob("*.json"))
    assert len(traces) == 2
    status = (run_dir / "status.json").read_text(encoding="utf-8")
    assert '"status": "completed"' in status
