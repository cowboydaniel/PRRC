# Device ID Tracking Fix

## Problem
When running FieldOps, the device ID was not appearing in HQ Command's Live Ops screen. The "Responder Roster" section (which displays active devices) was only showing static data from the configuration file, not live device registrations from FieldOps.

## Root Cause
The HQ Command GUI was not connected to the integration layer that receives device status updates from FieldOps. The architecture had all the components in place:
- FieldOps sends telemetry and status updates with device IDs
- HQIntegration and HQSyncClient receive and track device status
- The GUI has a Responder Roster pane to display devices

However, these components were not wired together. The GUI controller only loaded static data from JSON files and never received live device updates.

## Solution

### 1. Wire HQ Integration to GUI Controller (`src/hq_command/gui/__init__.py`)
- Import the integration layer components
- Initialize `HQIntegration` when the GUI starts
- Register a callback (`handle_status_update`) that:
  - Receives device status updates from FieldOps
  - Updates the controller's responder list with new/updated devices
  - Refreshes the GUI to display the changes
- Log when integration is successfully initialized

### 2. Send Initial Status Update from FieldOps (`src/fieldops/main.py`)
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
handle_status_update callback
    ↓
Update HQCommandController state
    ↓
Refresh GUI models
    ↓
Device appears in Responder Roster
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

HQ Command receives and displays in Roster Pane:
- **Unit ID**: fieldops_001
- **Status**: Available
- **Capabilities**: basic_response, transport, communication
- **Tasks**: 0
- **Capacity**: 3
- **Fatigue**: 0%

## Testing
1. Start HQ Command: `python -m hq_command`
2. Start FieldOps with device ID: `python -m fieldops --device-id fieldops_001`
3. Check HQ Command Live Ops → Responder Roster
4. Device should appear automatically

## Benefits
- **Real-time device tracking**: Devices register automatically when they come online
- **Live status updates**: Changes to device status/capabilities appear immediately
- **Multiple devices**: Supports multiple FieldOps instances with different device IDs
- **Backward compatible**: Still loads static responders from config file
