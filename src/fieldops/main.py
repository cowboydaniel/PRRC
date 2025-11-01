"""Entry point for launching the FieldOps GUI demo."""
from __future__ import annotations

from pathlib import Path
import sys

if __package__ in {None, ""}:
    # Allow running "python src/fieldops/main.py" by ensuring the project
    # source directory is importable for absolute package imports.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fieldops.gui.app import launch_app
else:  # pragma: no cover - exercised when imported as a package module.
    from .gui.app import launch_app


def main() -> int:
    """Launch the FieldOps Field GUI."""
    return launch_app()


if __name__ == "__main__":
    raise SystemExit(main())
