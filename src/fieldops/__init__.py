"""FieldOps package initialization.

Provides top-level exports for mission package loading, Dell Rugged Extreme
hardware coordination, and field telemetry utilities.
"""

from .mission_loader import (
    MissionAttachment,
    MissionContact,
    MissionManifest,
    load_mission_manifest,
    load_mission_package,
)
from .telemetry import collect_telemetry_snapshot
from .hardware import plan_touchscreen_calibration, enumerate_serial_interfaces

__all__ = [
    "MissionAttachment",
    "MissionContact",
    "MissionManifest",
    "load_mission_package",
    "load_mission_manifest",
    "collect_telemetry_snapshot",
    "plan_touchscreen_calibration",
    "enumerate_serial_interfaces",
]
