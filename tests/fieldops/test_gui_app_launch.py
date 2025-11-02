from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")

import fieldops.gui.app as app


class DummyApplication:
    """Minimal QApplication replacement for launch tests."""

    _instance: "DummyApplication | None" = None

    def __init__(self, argv: list[str] | None = None) -> None:
        type(self)._instance = self
        self.argv = list(argv or [])
        self.exec_called = False

    @classmethod
    def instance(cls) -> "DummyApplication | None":
        return cls._instance

    def exec(self) -> int:
        self.exec_called = True
        return 7


class DummyWindow:
    def __init__(self, controller, *, telemetry_provider, sync_adapter, demo_package) -> None:  # noqa: D401
        self.controller = controller
        self.telemetry_provider = telemetry_provider
        self.sync_adapter = sync_adapter
        self.demo_package = demo_package
        self.shown = False
        self.maximized = False

    def show(self) -> None:  # pragma: no cover - trivial setter
        self.shown = True

    def showMaximized(self) -> None:  # pragma: no cover - trivial setter
        self.maximized = True
        self.shown = True


class DummyController:
    def __init__(self, cache_path: Path, adapter) -> None:  # noqa: D401
        self.cache_path = cache_path
        self.adapter = adapter


@pytest.fixture(autouse=True)
def reset_dummy_application() -> None:
    DummyApplication._instance = None


def test_launch_app_production_flow(monkeypatch):
    monkeypatch.setattr(app, "QApplication", DummyApplication)
    monkeypatch.setattr(app, "FieldOpsGUIController", DummyController)
    created_windows: list[DummyWindow] = []

    def build_window(*args, **kwargs):
        window = DummyWindow(*args, **kwargs)
        created_windows.append(window)
        return window

    monkeypatch.setattr(app, "FieldOpsMainWindow", build_window)

    def fail_prepare() -> Path | None:
        raise AssertionError("Demo package should not be prepared for production flow")

    monkeypatch.setattr(app, "_prepare_demo_package", fail_prepare)

    result = app.launch_app()

    assert result == 7
    assert created_windows
    assert created_windows[0].demo_package is None
    assert created_windows[0].shown is True
    assert created_windows[0].maximized is True


def test_launch_app_demo_flow(monkeypatch, tmp_path: Path):
    demo_path = tmp_path / "demo.pkg"
    demo_path.touch()
    prepare_calls: list[Path | None] = []

    def fake_prepare() -> Path | None:
        prepare_calls.append(demo_path)
        return demo_path

    monkeypatch.setattr(app, "QApplication", DummyApplication)
    monkeypatch.setattr(app, "FieldOpsGUIController", DummyController)
    created_windows: list[DummyWindow] = []

    def build_window(*args, **kwargs):
        window = DummyWindow(*args, **kwargs)
        created_windows.append(window)
        return window

    monkeypatch.setattr(app, "FieldOpsMainWindow", build_window)
    monkeypatch.setattr(app, "_prepare_demo_package", fake_prepare)

    result = app.launch_app(demo_mode=True)

    assert result == 7
    assert prepare_calls == [demo_path]
    assert created_windows
    assert created_windows[0].demo_package == demo_path
    assert created_windows[0].shown is True
    assert created_windows[0].maximized is True
