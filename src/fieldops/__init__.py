"""FieldOps package initialization.

Provides top-level exports for mission package loading and field telemetry
coordination utilities.
"""

from .mission_loader import load_mission_package
from .telemetry import collect_telemetry_snapshot

__all__ = ["load_mission_package", "collect_telemetry_snapshot"]
