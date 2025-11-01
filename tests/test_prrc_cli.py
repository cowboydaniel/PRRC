"""CLI integration tests for the PRRC prototype commands."""
from __future__ import annotations

import pytest

import prrc_cli


def test_status_command_emits_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`status` command wires telemetry snapshot through HQ analytics."""

    sentinel_snapshot = {
        "status": "ok",
        "collected_at": "2024-01-01T00:00:00+00:00",
        "metrics": {},
        "notes": [],
    }

    def fake_collect() -> object:
        return sentinel_snapshot

    def fake_summarize(payload: object) -> dict[str, object]:
        assert payload is sentinel_snapshot
        return {
            "overall_readiness": "nominal",
            "alerts": ["none"],
            "notes": ["All systems nominal"],
        }

    monkeypatch.setattr(prrc_cli, "collect_telemetry_snapshot", fake_collect)
    monkeypatch.setattr(prrc_cli, "summarize_field_telemetry", fake_summarize)

    prrc_cli.status_command()

    output = capsys.readouterr().out.splitlines()
    assert output[0] == "HQ Command status report:"
    assert "  overall_readiness: nominal" in output
    assert "  alerts: ['none']" in output
    assert "  notes: ['All systems nominal']" in output
