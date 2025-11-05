"""
Integration Module for PRRC OS Suite

This module provides the integration layer that connects HQ Command, FieldOps,
and Bridge modules for end-to-end communication and compliance.

Key Components:
- Protocol: Shared message format and data contracts
- Coordinator: Message routing and audit integration
- HQ Integration: HQ Command interface to FieldOps
- FieldOps Integration: FieldOps interface to HQ Command

Usage Example:

    # Initialize Bridge components
    from bridge import BridgeCommsRouter, TamperEvidentAuditLog
    from bridge.comms_router import configure_default_router
    from bridge.compliance import configure_audit_log

    router = configure_default_router()
    audit_log = configure_audit_log()

    # Create HQ integration
    from integration import create_hq_coordinator, HQIntegration

    hq_coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_001")
    hq = HQIntegration(hq_coordinator)

    # Send tasks to field units
    hq.send_tasks_to_field_unit(
        unit_id="fieldops_001",
        tasks=[...],
        operator_id="operator_123"
    )

    # Create FieldOps integration
    from integration import create_fieldops_coordinator, FieldOpsIntegration

    fo_coordinator = create_fieldops_coordinator(router, audit_log, device_id="fieldops_001")
    fieldops = FieldOpsIntegration(fo_coordinator)

    # Send telemetry to HQ
    fieldops.send_telemetry_to_hq(telemetry_snapshot)

    # Register task assignment handler
    def handle_tasks(payload):
        print(f"Received {len(payload.tasks)} tasks")

    fieldops.on_task_assignment(handle_tasks)
"""

from .protocol import (
    MessageType,
    MessageEnvelope,
    TaskAssignmentPayload,
    TaskUpdatePayload,
    TaskCancellationPayload,
    TelemetryReportPayload,
    OperationsSyncPayload,
    StatusUpdatePayload,
    AcknowledgementPayload,
    ErrorPayload,
    create_task_assignment_message,
    create_telemetry_report_message,
    create_operations_sync_message,
    create_acknowledgement_message,
)

from .coordinator import (
    IntegrationCoordinator,
    create_hq_coordinator,
    create_fieldops_coordinator,
    PersistentMessageQueue,
    start_message_polling,
)

from .hq_integration import (
    HQIntegration,
    integrate_with_tasking_engine,
    integrate_with_analytics,
)

from .fieldops_integration import (
    FieldOpsIntegration,
    integrate_with_gui_controller,
    create_bridge_sync_adapter,
    integrate_with_telemetry,
)

from .utils import (
    create_default_bridge_router,
    create_default_audit_log,
    setup_bridge_components,
)

__all__ = [
    # Protocol
    "MessageType",
    "MessageEnvelope",
    "TaskAssignmentPayload",
    "TaskUpdatePayload",
    "TaskCancellationPayload",
    "TelemetryReportPayload",
    "OperationsSyncPayload",
    "StatusUpdatePayload",
    "AcknowledgementPayload",
    "ErrorPayload",
    "create_task_assignment_message",
    "create_telemetry_report_message",
    "create_operations_sync_message",
    "create_acknowledgement_message",
    # Coordinator
    "IntegrationCoordinator",
    "create_hq_coordinator",
    "create_fieldops_coordinator",
    "PersistentMessageQueue",
    "start_message_polling",
    # HQ Integration
    "HQIntegration",
    "integrate_with_tasking_engine",
    "integrate_with_analytics",
    # FieldOps Integration
    "FieldOpsIntegration",
    "integrate_with_gui_controller",
    "create_bridge_sync_adapter",
    "integrate_with_telemetry",
    # Utilities
    "create_default_bridge_router",
    "create_default_audit_log",
    "setup_bridge_components",
]
