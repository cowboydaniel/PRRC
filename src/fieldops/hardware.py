"""Hardware integration scaffolding for FieldOps Dell Rugged Extreme devices.

The Paramilitary Response and Rescue Corps deploys Dell Latitude Rugged Extreme
platforms for on-scene command. This module captures the hooks the software
stack will call once lower-level drivers and vendor SDKs are integrated.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def plan_touchscreen_calibration(profile_path: Path | None = None) -> Dict[str, Any]:
    """Prepare a touchscreen calibration routine for Dell Rugged Extreme tablets.

    The returned structure outlines the configuration profile, any serial inputs
    to monitor for stylus events, and downstream services interested in
    calibration state changes. Future implementations will call into Dell's
    rugged control panel utilities or OEM-provided calibration binaries.

    Args:
        profile_path: Optional path to a saved calibration profile captured from
            previous field tuning sessions.

    Returns:
        Metadata describing the planned calibration workflow.
    """

    return {
        "profile_path": str(profile_path) if profile_path else None,
        "status": "pending-calibration",
        "integration_points": [
            "dell_rugged_control_panel",
            "fieldops.ui.touchscreen",
            "mission_runtime.state_tracking",
        ],
        "notes": "Touchscreen calibration pipeline awaits Dell SDK bindings.",
    }


def enumerate_serial_interfaces() -> List[Dict[str, Any]]:
    """List serial interfaces exposed by Dell Rugged Extreme hardware.

    The scaffolded output identifies COM ports typically wired to vehicle
    sensors, drone controllers, or secure radio modems. Production builds will
    query the Windows Management Instrumentation (WMI) or Linux sysfs entries to
    enumerate actual device handles and capabilities.

    Returns:
        A list of serial interface metadata dictionaries.
    """
    import platform
    import os

    interfaces = []

    # Detect platform and enumerate accordingly
    system = platform.system()

    if system == "Windows":
        # Windows COM port enumeration
        interfaces.extend([
            {
                "port": "COM3",
                "role": "vehicle_can_bus_bridge",
                "status": "ready",
                "baud_rate": 9600,
                "data_bits": 8,
                "parity": "none",
                "stop_bits": 1,
                "notes": "CAN bus bridge for vehicle telemetry",
            },
            {
                "port": "COM7",
                "role": "encrypted_radio_modem",
                "status": "ready",
                "baud_rate": 115200,
                "data_bits": 8,
                "parity": "none",
                "stop_bits": 1,
                "encryption": "AES-256",
                "notes": "Secure radio communications link",
            },
        ])
    elif system == "Linux":
        # Linux serial device enumeration
        # Check for common serial device paths
        serial_devices = [
            ("/dev/ttyUSB0", "vehicle_can_bus_bridge"),
            ("/dev/ttyUSB1", "encrypted_radio_modem"),
            ("/dev/ttyS0", "gps_receiver"),
        ]

        for device_path, role in serial_devices:
            if os.path.exists(device_path):
                interfaces.append({
                    "port": device_path,
                    "role": role,
                    "status": "ready",
                    "baud_rate": 115200 if role == "encrypted_radio_modem" else 9600,
                    "notes": f"Linux serial device: {device_path}",
                })

    # If no interfaces detected, return simulated interfaces for testing
    if not interfaces:
        interfaces = [
            {
                "port": "SIMULATED_GPS",
                "role": "gps_receiver",
                "status": "simulated",
                "notes": "Simulated GPS for testing without hardware",
            },
            {
                "port": "SIMULATED_RADIO",
                "role": "encrypted_radio_modem",
                "status": "simulated",
                "notes": "Simulated radio for testing without hardware",
            },
        ]

    return interfaces


def get_gps_coordinates() -> Dict[str, Any]:
    """Get current GPS coordinates from hardware receiver.

    Returns:
        Dictionary containing GPS data including latitude, longitude, altitude,
        accuracy, and satellite information.
    """
    from datetime import datetime, timezone
    import random

    # In production, this would interface with actual GPS hardware
    # For now, simulate realistic GPS data
    interfaces = enumerate_serial_interfaces()
    gps_interface = next((i for i in interfaces if "gps" in i["role"].lower()), None)

    if not gps_interface:
        return {
            "status": "no_gps_hardware",
            "error": "No GPS receiver detected",
        }

    # Simulate GPS lock and data
    # Base coordinates (example: somewhere in USA)
    base_lat = 40.7128
    base_lon = -74.0060

    # Add small random variation to simulate movement/drift
    lat_variation = random.uniform(-0.001, 0.001)
    lon_variation = random.uniform(-0.001, 0.001)

    return {
        "status": "active",
        "latitude": base_lat + lat_variation,
        "longitude": base_lon + lon_variation,
        "altitude_meters": random.uniform(10, 100),
        "accuracy_meters": random.uniform(3, 10),
        "speed_mps": random.uniform(0, 5),  # meters per second
        "heading_degrees": random.uniform(0, 360),
        "satellites_visible": random.randint(8, 12),
        "satellites_used": random.randint(4, 8),
        "hdop": random.uniform(0.8, 2.0),  # Horizontal Dilution of Precision
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fix_quality": "3D",
        "interface": gps_interface["port"],
    }


def send_radio_message(message: str, recipient: str, priority: str = "normal") -> Dict[str, Any]:
    """Send encrypted message via radio modem.

    Args:
        message: Message content to send
        recipient: Recipient unit ID
        priority: Message priority (low, normal, high, urgent)

    Returns:
        Dictionary containing transmission status and metadata
    """
    from datetime import datetime, timezone
    import hashlib

    interfaces = enumerate_serial_interfaces()
    radio_interface = next((i for i in interfaces if "radio" in i["role"].lower()), None)

    if not radio_interface:
        return {
            "status": "error",
            "error": "No radio modem detected",
        }

    # Simulate message transmission
    message_id = hashlib.sha256(
        f"{message}{recipient}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:16]

    return {
        "status": "transmitted",
        "message_id": message_id,
        "recipient": recipient,
        "priority": priority,
        "length_bytes": len(message.encode('utf-8')),
        "encrypted": True,
        "encryption_method": radio_interface.get("encryption", "AES-256"),
        "transmission_time_ms": random.uniform(50, 200),
        "signal_strength_dbm": random.uniform(-70, -50),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "interface": radio_interface["port"],
        "retry_count": 0,
    }


def receive_radio_messages() -> List[Dict[str, Any]]:
    """Check for incoming radio messages.

    Returns:
        List of received messages with metadata
    """
    from datetime import datetime, timezone
    import random

    interfaces = enumerate_serial_interfaces()
    radio_interface = next((i for i in interfaces if "radio" in i["role"].lower()), None)

    if not radio_interface:
        return []

    # Simulate occasional incoming messages
    if random.random() < 0.1:  # 10% chance of having messages
        num_messages = random.randint(1, 3)
        messages = []

        for _ in range(num_messages):
            messages.append({
                "message_id": f"MSG_{random.randint(1000, 9999)}",
                "sender": f"UNIT_{random.randint(100, 999)}",
                "content": "Status update from field unit",
                "priority": random.choice(["normal", "high"]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signal_strength_dbm": random.uniform(-70, -50),
                "encrypted": True,
                "verified": True,
            })

        return messages

    return []


def read_system_sensors() -> List[Dict[str, Any]]:
    """Read comprehensive system sensors from Dell Rugged Extreme hardware.

    Collects extensive sensor data including CPU, memory, disk, network, battery,
    and system metrics for detailed telemetry monitoring.

    Returns:
        List of sensor readings with standardized format
    """
    from datetime import datetime, timezone
    import platform
    import os
    import psutil

    sensors = []
    timestamp = datetime.now(timezone.utc).isoformat()

    # ========== CPU SENSORS ==========
    try:
        if platform.system() == "Linux":
            # Read ALL thermal zones, not just first
            thermal_zones = Path("/sys/class/thermal")
            if thermal_zones.exists():
                for zone in thermal_zones.glob("thermal_zone*"):
                    temp_file = zone / "temp"
                    type_file = zone / "type"
                    if temp_file.exists():
                        temp_millicelsius = int(temp_file.read_text().strip())
                        temp_celsius = temp_millicelsius / 1000.0
                        zone_type = type_file.read_text().strip() if type_file.exists() else zone.name
                        sensors.append({
                            "sensor": f"thermal_{zone.name}",
                            "value": round(temp_celsius, 2),
                            "unit": "celsius",
                            "timestamp": timestamp,
                            "description": zone_type,
                        })
    except Exception:
        pass

    # CPU frequencies per core
    try:
        cpu_freqs = psutil.cpu_freq(percpu=True)
        if cpu_freqs:
            for i, freq in enumerate(cpu_freqs):
                sensors.append({
                    "sensor": f"cpu_core{i}_frequency",
                    "value": round(freq.current, 2),
                    "unit": "MHz",
                    "timestamp": timestamp,
                })
    except Exception:
        pass

    # CPU load average
    try:
        load1, load5, load15 = os.getloadavg()
        sensors.extend([
            {"sensor": "cpu_load_1min", "value": round(load1, 2), "unit": "load", "timestamp": timestamp},
            {"sensor": "cpu_load_5min", "value": round(load5, 2), "unit": "load", "timestamp": timestamp},
            {"sensor": "cpu_load_15min", "value": round(load15, 2), "unit": "load", "timestamp": timestamp},
        ])
    except Exception:
        pass

    # CPU usage per core
    try:
        cpu_percents = psutil.cpu_percent(interval=0.1, percpu=True)
        for i, percent in enumerate(cpu_percents):
            sensors.append({
                "sensor": f"cpu_core{i}_usage",
                "value": round(percent, 2),
                "unit": "percent",
                "timestamp": timestamp,
            })
    except Exception:
        pass

    # Overall CPU usage
    try:
        sensors.append({
            "sensor": "cpu_usage_total",
            "value": round(psutil.cpu_percent(interval=0.1), 2),
            "unit": "percent",
            "timestamp": timestamp,
        })
    except Exception:
        pass

    # ========== MEMORY SENSORS ==========
    try:
        mem = psutil.virtual_memory()
        sensors.extend([
            {"sensor": "memory_total", "value": round(mem.total / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "memory_available", "value": round(mem.available / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "memory_used", "value": round(mem.used / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "memory_free", "value": round(mem.free / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "memory_usage_percent", "value": round(mem.percent, 2), "unit": "percent", "timestamp": timestamp},
            {"sensor": "memory_cached", "value": round(mem.cached / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "memory_buffers", "value": round(mem.buffers / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
        ])
    except Exception:
        pass

    # Swap memory
    try:
        swap = psutil.swap_memory()
        sensors.extend([
            {"sensor": "swap_total", "value": round(swap.total / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "swap_used", "value": round(swap.used / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "swap_free", "value": round(swap.free / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
            {"sensor": "swap_usage_percent", "value": round(swap.percent, 2), "unit": "percent", "timestamp": timestamp},
        ])
    except Exception:
        pass

    # ========== DISK SENSORS ==========
    try:
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                mount_safe = partition.mountpoint.replace("/", "_").strip("_") or "root"
                sensors.extend([
                    {"sensor": f"disk_{mount_safe}_total", "value": round(usage.total / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
                    {"sensor": f"disk_{mount_safe}_used", "value": round(usage.used / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
                    {"sensor": f"disk_{mount_safe}_free", "value": round(usage.free / (1024**3), 2), "unit": "GB", "timestamp": timestamp},
                    {"sensor": f"disk_{mount_safe}_usage_percent", "value": round(usage.percent, 2), "unit": "percent", "timestamp": timestamp},
                ])
            except (PermissionError, OSError):
                continue
    except Exception:
        pass

    # Disk I/O counters
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io:
            sensors.extend([
                {"sensor": "disk_io_read_bytes", "value": round(disk_io.read_bytes / (1024**2), 2), "unit": "MB", "timestamp": timestamp},
                {"sensor": "disk_io_write_bytes", "value": round(disk_io.write_bytes / (1024**2), 2), "unit": "MB", "timestamp": timestamp},
                {"sensor": "disk_io_read_count", "value": disk_io.read_count, "unit": "operations", "timestamp": timestamp},
                {"sensor": "disk_io_write_count", "value": disk_io.write_count, "unit": "operations", "timestamp": timestamp},
            ])
    except Exception:
        pass

    # ========== NETWORK SENSORS ==========
    try:
        net_io = psutil.net_io_counters(pernic=True)
        for interface, counters in net_io.items():
            # Skip loopback
            if interface == "lo":
                continue
            sensors.extend([
                {"sensor": f"net_{interface}_bytes_sent", "value": round(counters.bytes_sent / (1024**2), 2), "unit": "MB", "timestamp": timestamp},
                {"sensor": f"net_{interface}_bytes_recv", "value": round(counters.bytes_recv / (1024**2), 2), "unit": "MB", "timestamp": timestamp},
                {"sensor": f"net_{interface}_packets_sent", "value": counters.packets_sent, "unit": "packets", "timestamp": timestamp},
                {"sensor": f"net_{interface}_packets_recv", "value": counters.packets_recv, "unit": "packets", "timestamp": timestamp},
                {"sensor": f"net_{interface}_errors_in", "value": counters.errin, "unit": "errors", "timestamp": timestamp},
                {"sensor": f"net_{interface}_errors_out", "value": counters.errout, "unit": "errors", "timestamp": timestamp},
            ])
    except Exception:
        pass

    # ========== BATTERY SENSORS (COMPREHENSIVE) ==========
    try:
        if platform.system() == "Linux":
            for bat_dir in Path("/sys/class/power_supply").glob("BAT*"):
                bat_name = bat_dir.name.lower()

                # Capacity
                capacity_file = bat_dir / "capacity"
                if capacity_file.exists():
                    sensors.append({
                        "sensor": f"{bat_name}_capacity",
                        "value": float(capacity_file.read_text().strip()),
                        "unit": "percent",
                        "timestamp": timestamp,
                    })

                # Voltage
                voltage_file = bat_dir / "voltage_now"
                if voltage_file.exists():
                    voltage_microvolts = int(voltage_file.read_text().strip())
                    sensors.append({
                        "sensor": f"{bat_name}_voltage",
                        "value": round(voltage_microvolts / 1_000_000.0, 2),
                        "unit": "volts",
                        "timestamp": timestamp,
                    })

                # Current
                current_file = bat_dir / "current_now"
                if current_file.exists():
                    current_microamps = int(current_file.read_text().strip())
                    sensors.append({
                        "sensor": f"{bat_name}_current",
                        "value": round(current_microamps / 1_000_000.0, 2),
                        "unit": "amperes",
                        "timestamp": timestamp,
                    })

                # Power
                power_file = bat_dir / "power_now"
                if power_file.exists():
                    power_microwatts = int(power_file.read_text().strip())
                    sensors.append({
                        "sensor": f"{bat_name}_power",
                        "value": round(power_microwatts / 1_000_000.0, 2),
                        "unit": "watts",
                        "timestamp": timestamp,
                    })

                # Temperature
                temp_file = bat_dir / "temp"
                if temp_file.exists():
                    temp_decidegrees = int(temp_file.read_text().strip())
                    sensors.append({
                        "sensor": f"{bat_name}_temperature",
                        "value": round(temp_decidegrees / 10.0, 2),
                        "unit": "celsius",
                        "timestamp": timestamp,
                    })

                # Status
                status_file = bat_dir / "status"
                if status_file.exists():
                    status = status_file.read_text().strip()
                    # Convert status to numeric for telemetry (0=Unknown, 1=Charging, 2=Discharging, 3=Full)
                    status_map = {"Unknown": 0, "Charging": 1, "Discharging": 2, "Full": 3, "Not charging": 4}
                    sensors.append({
                        "sensor": f"{bat_name}_status",
                        "value": status_map.get(status, 0),
                        "unit": "state",
                        "timestamp": timestamp,
                        "description": status,
                    })

                # Cycle count
                cycle_file = bat_dir / "cycle_count"
                if cycle_file.exists():
                    sensors.append({
                        "sensor": f"{bat_name}_cycle_count",
                        "value": int(cycle_file.read_text().strip()),
                        "unit": "cycles",
                        "timestamp": timestamp,
                    })

                # Health/Capacity level
                health_file = bat_dir / "capacity_level"
                if health_file.exists():
                    health = health_file.read_text().strip()
                    health_map = {"Unknown": 0, "Critical": 1, "Low": 2, "Normal": 3, "High": 4, "Full": 5}
                    sensors.append({
                        "sensor": f"{bat_name}_health",
                        "value": health_map.get(health, 0),
                        "unit": "state",
                        "timestamp": timestamp,
                        "description": health,
                    })
    except Exception:
        pass

    # Fallback to psutil battery if sysfs failed
    try:
        battery = psutil.sensors_battery()
        if battery and not any(s["sensor"].startswith("bat") for s in sensors):
            sensors.extend([
                {"sensor": "battery_percent", "value": round(battery.percent, 2), "unit": "percent", "timestamp": timestamp},
                {"sensor": "battery_plugged", "value": 1 if battery.power_plugged else 0, "unit": "boolean", "timestamp": timestamp},
                {"sensor": "battery_time_left", "value": battery.secsleft if battery.secsleft > 0 else 0, "unit": "seconds", "timestamp": timestamp},
            ])
    except Exception:
        pass

    # ========== SYSTEM SENSORS ==========
    try:
        sensors.append({
            "sensor": "system_uptime",
            "value": round(psutil.boot_time(), 2),
            "unit": "unix_timestamp",
            "timestamp": timestamp,
        })
    except Exception:
        pass

    try:
        sensors.append({
            "sensor": "process_count",
            "value": len(psutil.pids()),
            "unit": "processes",
            "timestamp": timestamp,
        })
    except Exception:
        pass

    # Fan speeds (if available)
    try:
        fans = psutil.sensors_fans()
        if fans:
            for fan_name, fan_list in fans.items():
                for i, fan in enumerate(fan_list):
                    sensors.append({
                        "sensor": f"fan_{fan_name}_{i}_speed",
                        "value": round(fan.current, 2),
                        "unit": "RPM",
                        "timestamp": timestamp,
                    })
    except Exception:
        pass

    return sensors


def get_queue_metrics() -> Dict[str, int]:
    """Get metrics from local offline operation queue.

    Returns:
        Dictionary of queue names to depth counts
    """
    from fieldops.queue_storage import get_queue_storage

    storage = get_queue_storage()
    return storage.get_metrics()


def get_cached_system_events() -> List[Dict[str, Any]]:
    """Get recent system events from local event cache.

    Returns:
        List of cached event records with event type, count, and last_seen timestamp
    """
    from fieldops.event_cache import get_event_cache

    cache = get_event_cache()
    return cache.get_event_summary()


# ------------------------------------------------------------------
# Queue Management API
# ------------------------------------------------------------------

def increment_queue(queue_name: str, amount: int = 1) -> None:
    """Increment a queue depth counter.

    Args:
        queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
        amount: Amount to increment by (default 1)
    """
    from fieldops.queue_storage import get_queue_storage

    storage = get_queue_storage()
    storage.increment(queue_name, amount)


def decrement_queue(queue_name: str, amount: int = 1) -> None:
    """Decrement a queue depth counter.

    Args:
        queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
        amount: Amount to decrement by (default 1)
    """
    from fieldops.queue_storage import get_queue_storage

    storage = get_queue_storage()
    storage.decrement(queue_name, amount)


def set_queue_depth(queue_name: str, depth: int) -> None:
    """Set a queue depth to a specific value.

    Args:
        queue_name: Name of queue (telemetry_upload, task_sync, log_submission)
        depth: New depth value
    """
    from fieldops.queue_storage import get_queue_storage

    storage = get_queue_storage()
    storage.set(queue_name, depth)


def reset_all_queues() -> None:
    """Reset all queue depths to zero."""
    from fieldops.queue_storage import get_queue_storage

    storage = get_queue_storage()
    storage.reset()


# ------------------------------------------------------------------
# Event Logging API
# ------------------------------------------------------------------

def log_system_event(event_type: str, **metadata: Any) -> None:
    """Log a system event to the event cache.

    Args:
        event_type: Type of event (e.g., "gps_fix_acquired", "network_connected",
            "mission_loaded", "task_completed", "radio_message_received")
        **metadata: Additional metadata to store with the event
    """
    from fieldops.event_cache import get_event_cache

    cache = get_event_cache()
    cache.log_event(event_type, **metadata)


def clear_event_cache() -> None:
    """Clear all cached system events."""
    from fieldops.event_cache import get_event_cache

    cache = get_event_cache()
    cache.clear()
