# PRRC OS Suite Integration Guide

## Overview

The PRRC OS Suite integration layer connects HQ Command, FieldOps, and Bridge modules to enable end-to-end communication and compliance auditing. This document describes the integration architecture, usage patterns, and API reference.

## Architecture

### Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HQ Command                             │
│  • Task scheduling & assignment                             │
│  • Telemetry aggregation & analytics                        │
│  • Operational dashboards                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ HQIntegration
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 Integration Layer                           │
│  • Shared protocol (MessageEnvelope)                        │
│  • Coordinator (routing & audit)                            │
│  • Message handlers                                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ Bridge
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    Bridge Module                            │
│  • BridgeCommsRouter (protocol adapters)                    │
│  • TamperEvidentAuditLog (compliance)                       │
│  • RoutingLedger & DeadLetterQueue                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ FieldOpsIntegration
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                     FieldOps                                │
│  • Mission loading & execution                              │
│  • Telemetry collection                                     │
│  • Offline operations queue                                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Protocol (`src/integration/protocol.py`)

Defines the shared message format and data contracts for HQ-FieldOps communication.

#### Message Types

- **HQ → FieldOps:**
  - `TASK_ASSIGNMENT` - Assign new tasks to field units
  - `TASK_UPDATE` - Modify existing task parameters
  - `TASK_CANCELLATION` - Cancel tasks

- **FieldOps → HQ:**
  - `TELEMETRY_REPORT` - Send telemetry snapshots
  - `OPERATIONS_SYNC` - Sync offline operations queue
  - `STATUS_UPDATE` - Report unit status changes

- **Bidirectional:**
  - `ACKNOWLEDGEMENT` - Confirm message receipt
  - `ERROR` - Report processing errors

#### Message Envelope

All messages are wrapped in a standard envelope:

```python
from integration import MessageEnvelope, MessageType

envelope = MessageEnvelope(
    message_id="unique-id",
    message_type=MessageType.TASK_ASSIGNMENT,
    sender_id="hq_001",
    recipient_id="fieldops_001",
    timestamp=datetime.utcnow(),
    payload={...},  # Type-specific payload
    correlation_id="request-id",  # Optional, for tracking
)
```

### 2. Coordinator (`src/integration/coordinator.py`)

The `IntegrationCoordinator` manages message routing, handler dispatch, and audit integration.

#### Features

- **Message Routing:** Routes messages through the Bridge to partner endpoints
- **Handler Registration:** Allows modules to register callbacks for message types
- **Audit Integration:** Automatically logs all messages to compliance audit log
- **Retry Logic:** Queues failed messages for retry
- **Statistics:** Tracks sent/received/failed message counts

#### Example Usage

```python
from integration import create_hq_coordinator, setup_bridge_components

# Set up Bridge components
router, audit_log = setup_bridge_components()

# Create coordinator for HQ Command
coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_001")

# Send a message
envelope = MessageEnvelope(...)
coordinator.send_message(envelope, partner_id="fieldops_001")

# Register a handler
def handle_telemetry(envelope):
    print(f"Received telemetry: {envelope.payload}")

coordinator.register_handler(
    MessageType.TELEMETRY_REPORT,
    handle_telemetry,
    "Process incoming telemetry"
)

# Receive and dispatch messages
coordinator.receive_message(incoming_envelope)

# Get statistics
stats = coordinator.get_statistics()
print(f"Sent: {stats['sent']}, Failed: {stats['failed']}")
```

### 3. HQ Integration (`src/integration/hq_integration.py`)

The `HQIntegration` class provides a high-level interface for HQ Command to communicate with FieldOps.

#### Outbound Methods

```python
from integration import HQIntegration

hq = HQIntegration(coordinator)

# Send tasks to a single field unit
hq.send_tasks_to_field_unit(
    unit_id="fieldops_001",
    tasks=[
        {"task_id": "task-1", "priority": 1, "capabilities_required": ["hazmat"]},
        {"task_id": "task-2", "priority": 2, "capabilities_required": ["medical"]},
    ],
    operator_id="operator_123",
)

# Send tasks to multiple units
assignments = {
    "fieldops_001": [task1, task2],
    "fieldops_002": [task3],
}
results = hq.send_tasks_to_multiple_units(assignments, operator_id="operator_123")
```

#### Inbound Callbacks

```python
# Register callback for telemetry reports
def handle_telemetry(payload):
    print(f"Device {payload.device_id} reported telemetry")
    print(f"Status: {payload.telemetry['status']}")

hq.on_telemetry_received(handle_telemetry)

# Register callback for operations sync
def handle_operations(payload):
    print(f"Device {payload.device_id} synced {len(payload.operations)} operations")

hq.on_operations_received(handle_operations)
```

### 4. FieldOps Integration (`src/integration/fieldops_integration.py`)

The `FieldOpsIntegration` class provides a high-level interface for FieldOps to communicate with HQ Command.

#### Outbound Methods

```python
from integration import FieldOpsIntegration

fieldops = FieldOpsIntegration(coordinator)

# Send telemetry to HQ
telemetry = {
    "status": "operational",
    "collected_at": datetime.utcnow().isoformat(),
    "metrics": {...},
}
fieldops.send_telemetry_to_hq(telemetry, location=(34.0522, -118.2437))

# Sync offline operations to HQ
operations = [
    {"id": "op-1", "type": "task_complete", "payload": {...}},
    {"id": "op-2", "type": "resource_request", "payload": {...}},
]
fieldops.sync_operations_to_hq(operations)

# Send status update to HQ
fieldops.send_status_update_to_hq(
    status="busy",
    capabilities=["hazmat", "medical"],
    max_concurrent_tasks=3,
    current_task_count=2,
    fatigue_level=0.4,
)
```

#### Inbound Callbacks

```python
# Register callback for task assignments
def handle_tasks(payload):
    print(f"Received {len(payload.tasks)} task assignments")
    for task in payload.tasks:
        print(f"  - Task {task['task_id']}: priority {task['priority']}")

fieldops.on_task_assignment(handle_tasks)

# Register callback for task updates
def handle_task_update(payload):
    print(f"Task {payload['task_id']} updated: {payload['updates']}")

fieldops.on_task_update(handle_task_update)
```

## Integration with Existing Modules

### HQ Command Integration

The integration layer is automatically set up when HQ Command starts:

```python
# In src/hq_command/main.py
from integration import setup_bridge_components, create_hq_coordinator, HQIntegration

router, audit_log = setup_bridge_components()
coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_001")
hq = HQIntegration(coordinator)

# Integration with tasking engine
import hq_command.tasking_engine as tasking_module
integrate_with_tasking_engine(hq, tasking_module)

# Now tasking engine has send_assignments_to_field() method
result = schedule_tasks_for_field_units(tasks, responders)
tasking_module.send_assignments_to_field(result)
```

### FieldOps Integration

The integration layer is set up in FieldOps main:

```python
# In src/fieldops/main.py
from integration import setup_bridge_components, create_fieldops_coordinator, FieldOpsIntegration

router, audit_log = setup_bridge_components()
coordinator = create_fieldops_coordinator(router, audit_log, device_id="fieldops_001")
fieldops = FieldOpsIntegration(coordinator)

# Integration with GUI controller (optional)
integrate_with_gui_controller(fieldops, gui_controller)

# Integration with telemetry (optional, auto-sync)
integrate_with_telemetry(fieldops, telemetry_module, sync_interval=60)
```

### Bridge Sync Adapter

Replace the stub `LocalEchoSyncAdapter` with a real implementation:

```python
from integration import create_bridge_sync_adapter

# Create real sync adapter
sync_adapter = create_bridge_sync_adapter(fieldops)

# Use with GUI controller
controller = FieldOpsGUIController(
    sync_adapter=sync_adapter,
    mission_loader=mission_loader,
)

# Now sync operations actually send to HQ
controller.push_operations([operation1, operation2])
```

## Message Flow Examples

### Task Assignment Flow

```
1. HQ schedules tasks
   └─> schedule_tasks_for_field_units(tasks, responders)

2. HQ sends to FieldOps via Bridge
   └─> hq.send_tasks_to_field_unit(unit_id, tasks, operator_id)
       └─> coordinator.send_message(envelope, partner_id)
           └─> audit_log.record(outbound_event)
           └─> router.route(partner_id, payload)
               └─> RestProtocolAdapter.deliver(endpoint, payload)

3. FieldOps receives and processes
   └─> coordinator.receive_message(envelope)
       └─> audit_log.record(inbound_event)
       └─> handlers[TASK_ASSIGNMENT](envelope)
           └─> update GUI task dashboard
```

### Telemetry Reporting Flow

```
1. FieldOps collects telemetry
   └─> telemetry = collect_telemetry_snapshot()

2. FieldOps sends to HQ via Bridge
   └─> fieldops.send_telemetry_to_hq(telemetry)
       └─> coordinator.send_message(envelope, partner_id)
           └─> audit_log.record(outbound_event)
           └─> router.route(partner_id, payload)

3. HQ receives and analyzes
   └─> coordinator.receive_message(envelope)
       └─> audit_log.record(inbound_event)
       └─> handlers[TELEMETRY_REPORT](envelope)
           └─> summarize_field_telemetry(telemetry)
           └─> update analytics dashboard
```

## Testing

### Unit Tests

Test individual integration components:

```bash
pytest tests/test_integration.py -v
```

Tests include:
- Message envelope serialization/deserialization
- Coordinator routing and audit
- HQ integration task sending
- FieldOps integration telemetry reporting
- End-to-end message flows

### Integration Tests

Test with mock Bridge components:

```python
from unittest.mock import Mock
from integration import create_hq_coordinator, HQIntegration

# Create mock dependencies
mock_router = Mock()
mock_router.route = Mock(return_value={"status": "delivered", "error": None})
mock_audit_log = Mock()

# Create coordinator with mocks
coordinator = create_hq_coordinator(mock_router, mock_audit_log, hq_id="test")
hq = HQIntegration(coordinator)

# Test task sending
hq.send_tasks_to_field_unit(unit_id="test_unit", tasks=[...], operator_id="test_op")

# Verify router was called
assert mock_router.route.called
```

## Configuration

### Bridge Router Configuration

The default router configuration includes endpoints for common HQ and FieldOps instances:

```python
from integration import setup_bridge_components

router, audit_log = setup_bridge_components()

# Default partners:
# - hq_command (http://localhost:8001/api/messages)
# - fieldops_001 (http://localhost:9001/api/messages)
# - fieldops_002 (http://localhost:9002/api/messages)
# - fieldops_003 (http://localhost:9003/api/messages)
```

To add custom endpoints:

```python
from bridge.comms_router import BridgeCommsRouter, PartnerEndpoint

partners = {
    "custom_unit": PartnerEndpoint(
        name="Custom FieldOps Unit",
        protocol="rest",
        target="https://custom.example.com/api/messages",
        mutual_tls=None,  # Optional mTLS config
        signing_key=None,  # Optional HMAC signing key
    ),
}

router = BridgeCommsRouter(partners=partners)
```

### Audit Log Configuration

The default audit log stores records in memory with 90-day retention:

```python
from bridge.compliance import TamperEvidentAuditLog

audit_log = TamperEvidentAuditLog(default_retention_days=90)

# Records are automatically retained per jurisdiction
# Latest record always kept for chain continuity
```

## Troubleshooting

### Messages Not Delivering

1. **Check router configuration:**
   ```python
   print(router._partners.keys())  # List configured partners
   ```

2. **Check coordinator statistics:**
   ```python
   stats = coordinator.get_statistics()
   print(f"Failed: {stats['failed']}, Pending: {stats['pending_retry']}")
   ```

3. **Retry failed messages:**
   ```python
   retry_count = coordinator.retry_failed_messages()
   print(f"Retried {retry_count} messages")
   ```

### Audit Records Not Appearing

1. **Verify audit log is configured:**
   ```python
   records = audit_log.history()
   print(f"Total records: {len(list(records))}")
   ```

2. **Check audit log for errors:**
   - Look for "Failed to audit" log messages
   - Ensure `audit_log.record()` method is available

### Handler Not Being Called

1. **Verify handler is registered:**
   ```python
   print(coordinator._handlers)  # Show registered handlers
   ```

2. **Check message type matches:**
   ```python
   print(envelope.message_type)  # Should match registered type
   ```

3. **Look for handler exceptions:**
   - Handlers that raise exceptions will log errors
   - Check logs for "Handler ... failed" messages

## Best Practices

1. **Always use MessageEnvelope:** Don't bypass the protocol layer
2. **Register handlers early:** Set up callbacks before starting message processing
3. **Handle failures gracefully:** Use try/except in message handlers
4. **Monitor statistics:** Periodically check coordinator stats for failures
5. **Audit everything:** All cross-module communication should be logged
6. **Use correlation IDs:** Track related messages with correlation_id field
7. **Test with mocks:** Use mock Bridge components for unit testing
8. **Validate payloads:** Check payload structure before processing

## API Reference

See module documentation for detailed API reference:
- `integration.protocol` - Message types and payloads
- `integration.coordinator` - Message routing and coordination
- `integration.hq_integration` - HQ Command interface
- `integration.fieldops_integration` - FieldOps interface
- `integration.utils` - Setup utilities

## Future Enhancements

Planned improvements to the integration layer:

1. **WebSocket Support:** Real-time bidirectional communication
2. **Message Compression:** Reduce bandwidth for telemetry
3. **Encryption:** End-to-end encryption for sensitive payloads
4. **Rate Limiting:** Prevent message flooding
5. **Priority Queues:** Prioritize critical messages
6. **Dead Letter Analysis:** Automated failure pattern detection
7. **Distributed Tracing:** Cross-module request tracing
8. **Schema Validation:** Automatic payload validation

## Support

For issues or questions about the integration layer:
1. Check this documentation
2. Review test cases in `tests/test_integration.py`
3. Check logs for error messages
