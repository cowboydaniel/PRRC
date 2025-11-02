"""Tests for launching the HQ Command GUI via the top-level CLI."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")

from hq_command import gui as hq_gui
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


def test_gui_main_creates_application(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> None:
    """The GUI entry point should wire up PySide6 constructs and execute the app."""

    recorded: dict[str, object] = {}

    class FakeApp:
        def __init__(self, argv: list[str]) -> None:
            recorded["argv"] = list(argv)

        def exec(self) -> int:
            recorded["exec_called"] = True
            return 7

    class FakeWindow:
        def __init__(self, controller, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            recorded["controller"] = controller
            recorded["window_args"] = (args, kwargs)

        def show(self) -> None:
            recorded["shown"] = True

        def refresh(self) -> None:
            recorded["refresh_called"] = True

    class FakeTimer:
        def __init__(self) -> None:
            recorded["timer_created"] = True

        def setInterval(self, interval: int) -> None:
            recorded["interval"] = interval

        def start(self) -> None:
            recorded["timer_started"] = True

    monkeypatch.setattr(hq_gui.QtWidgets, "QApplication", FakeApp)
    monkeypatch.setattr(hq_gui, "HQMainWindow", FakeWindow)
    monkeypatch.setattr(hq_gui.QtCore, "QTimer", FakeTimer)
    monkeypatch.setattr(hq_gui, "_connect_timer", lambda timer, cb: recorded.setdefault("connected_callback", cb))
    monkeypatch.setattr(hq_gui, "_start_timer", lambda timer: recorded.setdefault("timer_started_flag", True))

    exit_code = hq_gui.main(["--config", str(config_file), "--refresh-interval", "1.5"])

    assert exit_code == 7
    assert recorded["argv"][1:] == ["--config", str(config_file), "--refresh-interval", "1.5"]
    assert recorded["shown"] is True
    assert "controller" in recorded
    assert recorded["connected_callback"] is not None
    assert recorded["timer_started_flag"] is True
