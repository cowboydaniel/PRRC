"""FieldOps package initialization.

Provides top-level exports for mission package loading, Dell Rugged Extreme
hardware coordination, and field telemetry utilities.
"""

from .mission_loader import load_mission_package
from .telemetry import collect_telemetry_snapshot
from .hardware import plan_touchscreen_calibration, enumerate_serial_interfaces

__all__ = [
    "load_mission_package",
    "collect_telemetry_snapshot",
    "plan_touchscreen_calibration",
    "enumerate_serial_interfaces",
]
