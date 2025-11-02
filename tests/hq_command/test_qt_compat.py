"""Tests for Qt compatibility helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")

from hq_command.gui.qt_compat import QPolygonF, QPointF, qt_exec


class _ExecRecorder:
    def __init__(self) -> None:
        self.called_with: tuple[tuple[object, ...], dict[str, object]] | None = None

    def exec(self, *args: object, **kwargs: object) -> str:
        self.called_with = (args, kwargs)
        return "exec"


class _ExecUnderscoreRecorder:
    def __init__(self) -> None:
        self.called = False

    def exec_(self) -> str:
        self.called = True
        return "exec_"


def test_qt_exec_prefers_exec_over_exec_() -> None:
    recorder = _ExecRecorder()

    result = qt_exec(recorder, 1, keyword="value")

    assert result == "exec"
    assert recorder.called_with == ((1,), {"keyword": "value"})


def test_qt_exec_falls_back_to_exec_() -> None:
    recorder = _ExecUnderscoreRecorder()

    result = qt_exec(recorder)

    assert result == "exec_"
    assert recorder.called is True


def test_qt_exec_returns_none_when_no_method() -> None:
    class _NoExec:
        pass

    assert qt_exec(_NoExec()) is None


def test_polygon_classes_available() -> None:
    """PySide6 polygon helpers are provided by the compatibility layer."""

    polygon = QPolygonF([QPointF(0, 0), QPointF(1, 1)])

    assert isinstance(polygon, QPolygonF)
