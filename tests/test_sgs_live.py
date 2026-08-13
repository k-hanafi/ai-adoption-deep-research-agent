"""SGS live fan-out: mocked scouts then gated digs (no paid API)."""

from __future__ import annotations

from contracts.types import CompanyInput, Finding
from signal_gated_search.channels import CHANNEL_IDS, dig_config_label
from signal_gated_search.runner import run

COMPANY = CompanyInput(
    rcid=610194,
    name="Jam",
    homepage_url="https://jam.dev",
    short_description="A test company",
)


def _scout_payload(
    channel: str,
    bin_name: str,
    *,
    urls: list[str] | None = None,
    cost_usd: float = 0.001,
    transport_error: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "channel_id": channel,
        "evidence_bin": bin_name,
        "urls": urls if urls is not None else (
            [f"https://example.com/{channel}"] if bin_name in {"moderate", "strong"} else []
        ),
        "snippets": ["room exists"] if bin_name in {"moderate", "strong"} else [],
        "rationale": "test",
        "cost_usd": 0.0 if transport_error else cost_usd,
        "transport_error": transport_error,
        "error": error,
        "response_id": None if transport_error else f"scout-{channel}",
    }


def _finding(channel: str, tool: str, url: str) -> Finding:
    return Finding(
        finding_id=1,
        AI_tool_used=tool,
        use_case="coding",
        business_function="engineering",
        evidence_description="internal use",
        source_url=url,
        source_type="job_posting" if channel == "jobs" else "owned_site",
        channel=channel,
    )


def _dig_payload(
    channel: str,
    findings: list[Finding] | None = None,
    *,
    cost_usd: float = 0.02,
    transport_error: bool = False,
    error: str | None = None,
) -> dict:
    return {
        "channel_id": channel,
        "findings": findings or [],
        "cost_usd": 0.0 if transport_error else cost_usd,
        "transport_error": transport_error,
        "error": error,
        "genai_adoption_found": bool(findings),
        "response_id": None if transport_error else f"dig-{channel}",
    }


def test_live_n0_does_not_call_digs(monkeypatch) -> None:
    dig_calls: list[str] = []

    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _scout_payload(channel_id, "none")

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        dig_calls.append(channel_id)
        return _dig_payload(channel_id)

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert dig_calls == []
    assert result.dry_run is False
    assert result.stub is False
    assert result.traces["gate"]["stop_at_scouts"] is True
    assert result.traces["request_snapshots"]["digs"] == {}
    assert [c.name for c in result.cost_ledger.components] == [
        "scout_jobs",
        "scout_owned",
        "scout_third_party",
    ]
    assert result.no_finding_reason == "no_channel_above_signal_threshold"
    assert result.cost_ledger.total_usd == 0.003


def test_live_n1_digs_jobs_at_max_and_merges(monkeypatch) -> None:
    dig_efforts: list[str] = []

    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        if channel_id == "jobs":
            return _scout_payload(channel_id, "moderate")
        return _scout_payload(channel_id, "none")

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        effort = (request_kwargs.get("reasoning") or {}).get("effort")
        dig_efforts.append(effort)
        assert "https://example.com/jobs" not in (request_kwargs.get("input") or "")
        return _dig_payload(
            channel_id,
            [_finding(channel_id, "GitHub Copilot", "https://jam.dev/careers")],
        )

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert dig_efforts == ["max"]
    assert result.traces["gate"]["dig_channels"] == ["jobs"]
    assert result.genai_adoption_found is True
    assert len(result.findings) == 1
    assert result.findings[0].AI_tool_used == "GitHub Copilot"
    assert result.findings[0].channel == "jobs"
    names = [c.name for c in result.cost_ledger.components]
    assert names == [
        "scout_jobs",
        "scout_owned",
        "scout_third_party",
        "dig_jobs",
    ]
    assert result.cost_ledger.components[-1].preset == dig_config_label("max")
    assert result.cost_ledger.total_usd == 0.023


def test_live_n3_digs_at_medium_and_dedupes(monkeypatch) -> None:
    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _scout_payload(channel_id, "strong")

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        effort = (request_kwargs.get("reasoning") or {}).get("effort")
        assert effort == "medium"
        url = "https://jam.dev/blog/copilot"
        return _dig_payload(channel_id, [_finding(channel_id, "GitHub Copilot", url)])

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert result.traces["gate"]["dig_count"] == 3
    assert list(result.traces["request_snapshots"]["digs"]) == list(CHANNEL_IDS)
    # Same (tool, url) across rooms collapses to the first (jobs).
    assert len(result.findings) == 1
    assert result.findings[0].channel == "jobs"


def test_live_scout_transport_error_skips_that_room(monkeypatch) -> None:
    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        if channel_id == "jobs":
            return _scout_payload(
                channel_id,
                "none",
                transport_error=True,
                error="Timeout",
            )
        return _scout_payload(channel_id, "moderate")

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _dig_payload(channel_id, [_finding(channel_id, "Copilot", f"https://x/{channel_id}")])

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert result.traces["gate"]["dig_channels"] == ["owned", "third_party"]
    assert result.traces["gate"]["reasoning_effort"] == "high"
    scout_jobs = next(c for c in result.cost_ledger.components if c.name == "scout_jobs")
    assert scout_jobs.ran is False
    assert scout_jobs.skipped_reason == "api_error"
    assert scout_jobs.cost_usd == 0.0


def test_live_dig_transport_error_keeps_sibling(monkeypatch) -> None:
    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _scout_payload(channel_id, "moderate")

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        if channel_id == "jobs":
            return _dig_payload(channel_id, transport_error=True, error="boom")
        return _dig_payload(
            channel_id,
            [_finding(channel_id, "Copilot", f"https://x/{channel_id}")],
        )

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert result.traces["gate"]["dig_count"] == 3
    dig_jobs = next(c for c in result.cost_ledger.components if c.name == "dig_jobs")
    assert dig_jobs.ran is False
    assert dig_jobs.skipped_reason == "api_error"
    assert result.genai_adoption_found is True
    assert {f.channel for f in result.findings} == {"owned", "third_party"}
    assert result.error is not None
    assert "dig_jobs" in result.error


def test_live_envelope_room_wins_over_model_channel_field(monkeypatch) -> None:
    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        payload = _scout_payload(
            channel_id,
            "moderate" if channel_id == "jobs" else "none",
        )
        # Model mislabels the room. Envelope channel_id from the fan-out must win.
        payload["channel"] = "owned" if channel_id == "jobs" else "jobs"
        return payload

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _dig_payload(channel_id, [_finding(channel_id, "Copilot", "https://x/jobs")])

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert result.traces["gate"]["dig_channels"] == ["jobs"]
    assert result.traces["gate"]["reasoning_effort"] == "max"


def test_scout_parses_json_from_output_items_when_output_text_empty(monkeypatch) -> None:
    class Part:
        text = (
            '{"channel": "jobs", "evidence_bin": "moderate", '
            '"urls": ["https://x"], "snippets": [], "rationale": "ok"}'
        )

    class Item:
        content = [Part()]

    class Resp:
        id = "r1"
        model = "m"
        status = "completed"
        output_text = ""
        output = [Item()]
        usage = None
        error = None

    class Client:
        def __init__(self, **kwargs):
            self.responses = self

        def create(self, **kwargs):
            return Resp()

    import types

    fake_mod = types.SimpleNamespace(Perplexity=Client)
    monkeypatch.setitem(__import__("sys").modules, "perplexity", fake_mod)

    from signal_gated_search.agent_call import execute_scout_call

    out = execute_scout_call({"input": "x"}, channel_id="jobs", api_key="k")
    assert out["evidence_bin"] == "moderate"
    assert out["urls"] == ["https://x"]
    assert out["error"] is None


def test_live_scout_failures_are_not_labeled_as_no_signal(monkeypatch) -> None:
    def fake_scout(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        return _scout_payload(
            channel_id,
            "none",
            transport_error=True,
            error="Timeout",
        )

    def fake_dig(request_kwargs, *, channel_id, api_key=None, timeout=300.0):
        raise AssertionError("digs must not run when every scout failed")

    monkeypatch.setattr("signal_gated_search.runner.execute_scout_call", fake_scout)
    monkeypatch.setattr("signal_gated_search.runner.execute_dig_call", fake_dig)

    result = run(COMPANY, dry_run=False, api_key="test-key")
    assert result.traces["gate"]["stop_at_scouts"] is True
    assert result.no_finding_reason == "scout_errors"
    assert result.findings == []
