from __future__ import annotations

import fieldops.main as fieldops_main


def test_main_defaults_to_production(monkeypatch):
    recorded: dict[str, bool] = {}

    def fake_launch_app(*, demo_mode: bool) -> int:
        recorded["demo_mode"] = demo_mode
        return 0

    monkeypatch.setattr(fieldops_main, "launch_app", fake_launch_app)

    result = fieldops_main.main(())

    assert result == 0
    assert recorded["demo_mode"] is False


def test_main_accepts_demo_flag(monkeypatch):
    recorded: dict[str, bool] = {}

    def fake_launch_app(*, demo_mode: bool) -> int:
        recorded["demo_mode"] = demo_mode
        return 0

    monkeypatch.setattr(fieldops_main, "launch_app", fake_launch_app)

    result = fieldops_main.main(("--demo",))

    assert result == 0
    assert recorded["demo_mode"] is True
