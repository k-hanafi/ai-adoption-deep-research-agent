"""Gate: presence bins → signal → effort ladder."""

from __future__ import annotations

import pytest

from signal_gated_search.gate import decide_gate, normalize_scout_output


def _scout(channel: str, bin_name: str, urls: list[str] | None = None) -> dict:
    return {
        "channel": channel,
        "evidence_bin": bin_name,
        "urls": urls if urls is not None else (["https://example.com"] if bin_name in {"moderate", "strong"} else []),
        "snippets": [],
        "rationale": "test",
    }


def test_normalize_maps_bin_to_confidence_and_signal() -> None:
    none = normalize_scout_output(_scout("jobs", "none", []), assigned_channel="jobs")
    weak = normalize_scout_output(_scout("jobs", "weak", []), assigned_channel="jobs")
    moderate = normalize_scout_output(_scout("jobs", "moderate"), assigned_channel="jobs")
    strong = normalize_scout_output(_scout("jobs", "strong"), assigned_channel="jobs")
    assert none == {
        **none,
        "confidence": 0.0,
        "signal": False,
        "evidence_bin": "none",
    }
    assert weak["confidence"] == 0.35
    assert weak["signal"] is False
    assert moderate["confidence"] == 0.65
    assert moderate["signal"] is True
    assert strong["confidence"] == 0.90
    assert strong["signal"] is True


def test_moderate_without_url_downgrades_to_none() -> None:
    row = normalize_scout_output(
        _scout("owned", "moderate", []),
        assigned_channel="owned",
    )
    assert row["evidence_bin"] == "none"
    assert row["signal"] is False
    assert row["downgraded"] == "missing_url"


def test_strong_without_url_downgrades_to_none() -> None:
    row = normalize_scout_output(
        {"evidence_bin": "strong", "urls": ["  "]},
        assigned_channel="third_party",
    )
    assert row["evidence_bin"] == "none"
    assert row["signal"] is False


def test_code_ignores_model_confidence_and_signal_fields() -> None:
    row = normalize_scout_output(
        {
            "channel": "jobs",
            "evidence_bin": "weak",
            "confidence": 0.99,
            "signal": True,
            "urls": ["https://jobs.example.com"],
        },
        assigned_channel="jobs",
    )
    assert row["confidence"] == 0.35
    assert row["signal"] is False


def test_assigned_channel_wins_over_scout_channel_field() -> None:
    row = normalize_scout_output(
        _scout("owned", "moderate"),
        assigned_channel="jobs",
    )
    assert row["channel"] == "jobs"


def test_gate_n0_stops() -> None:
    decision = decide_gate(
        [
            _scout("jobs", "none", []),
            _scout("owned", "weak", []),
            _scout("third_party", "none", []),
        ]
    )
    assert decision.stop_at_scouts is True
    assert decision.dig_count == 0
    assert decision.dig_channels == []
    assert decision.reasoning_effort is None
    assert decision.rationale == "no_channel_above_signal_threshold"


def test_gate_n1_max() -> None:
    decision = decide_gate(
        [
            _scout("jobs", "none", []),
            _scout("owned", "moderate"),
            _scout("third_party", "weak", []),
        ]
    )
    assert decision.stop_at_scouts is False
    assert decision.dig_channels == ["owned"]
    assert decision.dig_count == 1
    assert decision.reasoning_effort == "max"


def test_gate_n2_high_stable_channel_order() -> None:
    decision = decide_gate(
        [
            _scout("third_party", "strong"),
            _scout("jobs", "moderate"),
            _scout("owned", "none", []),
        ]
    )
    assert decision.dig_channels == ["jobs", "third_party"]
    assert decision.dig_count == 2
    assert decision.reasoning_effort == "high"


def test_gate_n3_medium() -> None:
    decision = decide_gate(
        [
            _scout("jobs", "moderate"),
            _scout("owned", "strong"),
            _scout("third_party", "moderate"),
        ]
    )
    assert decision.dig_channels == ["jobs", "owned", "third_party"]
    assert decision.dig_count == 3
    assert decision.reasoning_effort == "medium"


def test_unknown_bin_is_none() -> None:
    row = normalize_scout_output(
        {"evidence_bin": "maybe", "urls": ["https://x.example"]},
        assigned_channel="jobs",
    )
    assert row["evidence_bin"] == "none"
    assert row["signal"] is False


def test_unknown_channel_raises() -> None:
    with pytest.raises(ValueError, match="Unknown SGS channel"):
        normalize_scout_output(_scout("jobs", "none", []), assigned_channel="careers")


def test_gate_accepts_channel_id_field() -> None:
    decision = decide_gate(
        [
            {
                "channel_id": "jobs",
                "evidence_bin": "moderate",
                "urls": ["https://boards.greenhouse.io/example"],
            },
            {"channel_id": "owned", "evidence_bin": "none", "urls": []},
        ]
    )
    assert decision.dig_channels == ["jobs"]
    assert decision.reasoning_effort == "max"


def test_gate_skips_unknown_channel_instead_of_aborting() -> None:
    decision = decide_gate(
        [
            {"channel": "careers", "evidence_bin": "strong", "urls": ["https://x"]},
            _scout("owned", "moderate"),
        ]
    )
    assert decision.dig_channels == ["owned"]
    assert decision.dig_count == 1
