"""Test configuration helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure() -> None:
    """Ensure the ``src`` directory is importable during tests."""

    src_dir = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(src_dir))
