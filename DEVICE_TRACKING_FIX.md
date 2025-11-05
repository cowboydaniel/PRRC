# Device ID Tracking Fix

## Problem
When running FieldOps, the device ID was not appearing in HQ Command's Live Ops screen. There was no visible place to display connected FieldOps devices. The "Responder Roster" section is for human responders/operators, not for devices.

## Root Cause
1. The HQ Command GUI had no dedicated display for connected FieldOps devices
2. The GUI was not connected to the integration layer that receives device status updates
3. FieldOps was not sending initial status on startup

## Solution

### 1. Create Active Devices Display (`src/hq_command/gui/enhanced_panes.py`)
- **Replace Readiness Score gauge** with an "Active Devices" card in the Telemetry pane
- Display a scrollable list of connected devices showing:
  - Device ID (bold)
  - Status badge (Available/Busy with color coding)
  - Capabilities list
  - Current tasks / Max tasks
- Show device count in header ("N connected")
- Empty state message when no devices connected
- Real-time updates when devices connect/disconnect

### 2. Wire Integration to Active Devices Display (`src/hq_command/gui/__init__.py`)
- Import the integration layer components
- Initialize `HQIntegration` when the GUI starts
- Track active devices in a separate dictionary (not mixed with responders)
- Register a callback that:
  - Receives device status updates from FieldOps
  - Updates the active devices dictionary
  - Refreshes the Active Devices display immediately
- Store active_devices on window object for access during callbacks

### 3. Send Initial Status Update from FieldOps (`src/fieldops/main.py`)
- When FieldOps starts, send an initial STATUS_UPDATE message to HQ Command
- Include device ID, status (available), capabilities, and capacity
- This ensures HQ Command sees the device immediately upon startup

## How It Works

### Data Flow
```
FieldOps Startup
    ↓
Send STATUS_UPDATE (device_id, status, capabilities)
    ↓
Bridge/Router
    ↓
HQIntegration receives message
    ↓
handle_status_update_with_refresh callback
    ↓
Update active_devices dictionary
    ↓
Update Active Devices display in Telemetry Pane
    ↓
Device appears in "Active Devices" card (right column, top)
```

### Message Format
FieldOps sends:
```json
{
  "message_type": "STATUS_UPDATE",
  "payload": {
    "unit_id": "fieldops_001",
    "status": "available",
    "capabilities": ["basic_response", "transport", "communication"],
    "max_concurrent_tasks": 3,
    "current_task_count": 0,
    "fatigue_level": 0.0
  }
}
```

HQ Command displays in Active Devices card:
```
┌─────────────────────────────────────┐
│ Active Devices          1 connected │
├─────────────────────────────────────┤
│ fieldops_001           [Available]  │
│ Capabilities: basic_response,       │
│   transport, communication          │
│ Tasks: 0/3                          │
└─────────────────────────────────────┘
```

## Where to Find Active Devices

**Location**: Live Ops screen → Right column → Top card

The "Active Devices" card replaces the old "Readiness Score" gauge and shows:
- Device count in header
- List of connected devices
- Each device shows:
  - Device ID (e.g., fieldops_001)
  - Status badge with color (green = available, yellow = busy)
  - Capabilities
  - Task count (current/max)

## Testing
1. Start HQ Command: `python -m hq_command`
2. Check Live Ops → Active Devices shows "0 connected"
3. Start FieldOps: `python -m fieldops --device-id fieldops_001`
4. Device should appear immediately in Active Devices card
5. Start another: `python -m fieldops --device-id fieldops_002`
6. Now shows "2 connected" with both devices listed

## Benefits
- **Dedicated display**: Clear separation between devices and human responders
- **Real-time tracking**: Devices appear immediately when they connect
- **Live status updates**: Changes to device status/capabilities update instantly
- **Multiple devices**: Supports unlimited FieldOps instances
- **Visual feedback**: Color-coded status badges and device count
