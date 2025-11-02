from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hq_command import main as hq_main


@pytest.fixture()
def sample_payload(tmp_path: Path) -> Path:
    data = {
        "tasks": [
            {
                "task_id": "alpha",
                "priority": 3,
                "capabilities_required": ["medic"],
                "location": "zone-1",
            }
        ],
        "responders": [
            {
                "unit_id": "med-1",
                "capabilities": ["medic"],
                "location": "zone-1",
            }
        ],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(data))
    return config_path


def test_run_production_mode_outputs_json(sample_payload: Path) -> None:
    buffer = io.StringIO()
    exit_code = hq_main.run_production_mode(sample_payload, stdout=buffer)
    assert exit_code == 0

    payload = json.loads(buffer.getvalue())
    assert set(payload) == {"assignments", "audit", "deferred", "escalated", "status"}
    assert payload["assignments"][0]["task_id"] == "alpha"
    assert payload["assignments"][0]["unit_id"] == "med-1"


def test_run_production_mode_reports_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    buffer = io.StringIO()
    exit_code = hq_main.run_production_mode(missing, stderr=buffer)
    assert exit_code == 1
    assert "Config file not found" in buffer.getvalue()


def test_run_demo_mode_prints_human_readable(capsys: pytest.CaptureFixture[str]) -> None:
    hq_main.run_demo_mode()
    captured = capsys.readouterr()
    assert "HQ Command Tasking Engine Demo" in captured.out
    assert "Assignments:" in captured.out
    assert "Audit metadata:" in captured.out


def test_main_dispatches_to_demo_mode() -> None:
    with patch.object(hq_main, "run_demo_mode") as mock_demo:
        exit_code = hq_main.main(["--demo"])
    assert exit_code == 0
    mock_demo.assert_called_once_with()


def test_main_uses_production_mode(sample_payload: Path) -> None:
    with patch.object(hq_main, "run_production_mode") as mock_prod:
        mock_prod.return_value = 0
        exit_code = hq_main.main(["--config", str(sample_payload)])
    assert exit_code == 0
    mock_prod.assert_called_once_with(sample_payload)
