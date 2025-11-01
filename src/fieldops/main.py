"""Entry point for launching the FieldOps GUI demo."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ""}:
    # Allow running "python src/fieldops/main.py" by ensuring the project
    # source directory is importable for absolute package imports.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fieldops.gui.app import launch_app
else:  # pragma: no cover - exercised when imported as a package module.
    from .gui.app import launch_app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the FieldOps GUI")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Start the application with demo data and sample mission package",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the FieldOps Field GUI."""
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return launch_app(demo_mode=args.demo)


if __name__ == "__main__":
    raise SystemExit(main())
