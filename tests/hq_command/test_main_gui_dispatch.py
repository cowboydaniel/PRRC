"""Tests for launching the HQ Command GUI via the top-level CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

from hq_command import main as hq_main


@pytest.fixture()
def config_file(tmp_path: Path) -> Path:
    config = tmp_path / "config.json"
    config.write_text("{}")
    return config


def test_main_launches_gui(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> None:
    """Verify that ``hq_command.main`` dispatches to the GUI launcher by default."""

    captured: dict[str, list[str] | int] = {}

    def fake_gui_main(argv: list[str] | None = None) -> int:
        captured["argv"] = [] if argv is None else list(argv)
        captured["return"] = 42
        return 42

    monkeypatch.setattr("hq_command.gui.main", fake_gui_main)

    exit_code = hq_main.main([
        "--config",
        str(config_file),
        "--refresh-interval",
        "1.5",
    ])

    assert exit_code == 42
    assert captured["argv"] == ["--config", str(config_file), "--refresh-interval", "1.5"]
    assert captured["return"] == 42
