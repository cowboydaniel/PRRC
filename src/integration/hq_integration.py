"""
HQ Command Integration Layer

This module provides the integration layer for HQ Command to communicate
with FieldOps through the Bridge.

Responsibilities:
- Convert HQ Command tasks to protocol messages
- Send task assignments to FieldOps units
- Receive and process telemetry from FieldOps
- Handle operations sync from FieldOps
"""
import logging
from datetime import datetime
from typing import Callable

from .protocol import (
    MessageEnvelope,
    MessageType,
    TaskAssignmentPayload,
    TelemetryReportPayload,
    OperationsSyncPayload,
    create_task_assignment_message,
)
from .coordinator import IntegrationCoordinator

# Import priority conversion utilities
try:
    from shared.schemas import priority_to_string
except ImportError:
    from ..shared.schemas import priority_to_string

logger = logging.getLogger(__name__)


# ============================================================================
# HQ Integration Interface
# ============================================================================

class HQIntegration:
    """
    HQ Command integration interface

    Provides high-level methods for HQ Command to interact with FieldOps
    through the Bridge.

    Usage:
        hq = HQIntegration(coordinator)

        # Send tasks to field units
        hq.send_tasks_to_field_unit(
            unit_id="fieldops_device_001",
            tasks=[...],  # List of TaskingOrder objects
            operator_id="operator_123"
        )

        # Register callbacks for incoming data
        hq.on_telemetry_received(handle_telemetry)
        hq.on_operations_received(handle_operations)
    """

    def __init__(self, coordinator: IntegrationCoordinator):
        self.coordinator = coordinator
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message handlers for incoming FieldOps messages"""
        self.coordinator.register_handler(
            MessageType.TELEMETRY_REPORT,
            self._handle_telemetry_report,
            "Process telemetry from FieldOps",
        )

        self.coordinator.register_handler(
            MessageType.OPERATIONS_SYNC,
            self._handle_operations_sync,
            "Process operations sync from FieldOps",
        )

        self.coordinator.register_handler(
            MessageType.STATUS_UPDATE,
            self._handle_status_update,
            "Process status updates from FieldOps",
        )

    # ========================================================================
    # Outbound: HQ → FieldOps
    # ========================================================================

    def send_tasks_to_field_unit(
        self,
        unit_id: str,
        tasks: list[dict],
        operator_id: str,
        expires_at: datetime | None = None,
    ) -> bool:
        """
        Send task assignments to a FieldOps unit

        Args:
            unit_id: ID of the FieldOps unit/device
            tasks: List of TaskingOrder objects (as dicts)
            operator_id: ID of operator issuing the tasks
            expires_at: Optional expiration time

        Returns:
            True if tasks were sent successfully
        """
        try:
            # Convert task data from HQ format to FieldOps format
            # HQ Command uses int priorities (1-5), FieldOps expects string ("Routine", "High", "Critical")
            # HQ Command uses frozenset for capabilities, FieldOps expects list
            converted_tasks = []
            for task in tasks:
                task_copy = task.copy()

                # Convert priority from int to string
                if "priority" in task_copy:
                    task_copy["priority"] = priority_to_string(task_copy["priority"])

                # Convert capabilities_required from frozenset to list
                if "capabilities_required" in task_copy:
                    capabilities = task_copy["capabilities_required"]
                    if isinstance(capabilities, frozenset):
                        task_copy["capabilities_required"] = list(capabilities)

                converted_tasks.append(task_copy)

            # Create message envelope
            envelope = create_task_assignment_message(
                tasks=converted_tasks,
                operator_id=operator_id,
                sender_id=self.coordinator.node_id,
                recipient_id=unit_id,
                expires_at=expires_at,
            )

            # Send through coordinator
            success = self.coordinator.send_message(envelope, partner_id=unit_id)

            if success:
                logger.info(
                    f"Sent {len(tasks)} tasks to {unit_id} "
                    f"(message {envelope.message_id})"
                )
            else:
                logger.warning(f"Failed to send tasks to {unit_id}")

            return success

        except Exception as e:
            logger.error(f"Error sending tasks to {unit_id}: {e}", exc_info=True)
            return False

    def send_tasks_to_multiple_units(
        self,
        assignments: dict[str, list[dict]],
        operator_id: str,
    ) -> dict[str, bool]:
        """
        Send task assignments to multiple FieldOps units

        Args:
            assignments: Map of unit_id -> list of TaskingOrder dicts
            operator_id: ID of operator issuing the tasks

        Returns:
            Map of unit_id -> success status
        """
        results = {}

        for unit_id, tasks in assignments.items():
            success = self.send_tasks_to_field_unit(
                unit_id=unit_id,
                tasks=tasks,
                operator_id=operator_id,
            )
            results[unit_id] = success

        successful = sum(1 for s in results.values() if s)
        logger.info(
            f"Sent tasks to {successful}/{len(assignments)} units successfully"
        )

        return results

    # ========================================================================
    # Inbound: FieldOps → HQ
    # ========================================================================

    def _handle_telemetry_report(self, envelope: MessageEnvelope) -> None:
        """Handle incoming telemetry report from FieldOps"""
        try:
            payload = TelemetryReportPayload.from_dict(envelope.payload)

            logger.info(
                f"Received telemetry from {payload.device_id} "
                f"(collected at {payload.collected_at})"
            )

            # Call registered callback if exists
            if hasattr(self, "_telemetry_callback"):
                self._telemetry_callback(payload)

        except Exception as e:
            logger.error(f"Error handling telemetry report: {e}", exc_info=True)
            raise

    def _handle_operations_sync(self, envelope: MessageEnvelope) -> None:
        """Handle incoming operations sync from FieldOps"""
        try:
            payload = OperationsSyncPayload.from_dict(envelope.payload)

            logger.info(
                f"Received {len(payload.operations)} operations from "
                f"{payload.device_id} (seq {payload.sequence_number})"
            )

            # Call registered callback if exists
            if hasattr(self, "_operations_callback"):
                self._operations_callback(payload)

        except Exception as e:
            logger.error(f"Error handling operations sync: {e}", exc_info=True)
            raise

    def _handle_status_update(self, envelope: MessageEnvelope) -> None:
        """Handle incoming status update from FieldOps"""
        try:
            payload = envelope.payload

            logger.info(
                f"Received status update from {payload['unit_id']}: "
                f"{payload['status']}"
            )

            # Call registered callback if exists
            if hasattr(self, "_status_callback"):
                self._status_callback(payload)

        except Exception as e:
            logger.error(f"Error handling status update: {e}", exc_info=True)
            raise

    # ========================================================================
    # Callback Registration
    # ========================================================================

    def on_telemetry_received(
        self,
        callback: Callable[[TelemetryReportPayload], None],
    ) -> None:
        """
        Register a callback for telemetry reports

        Args:
            callback: Function that receives TelemetryReportPayload
        """
        self._telemetry_callback = callback
        logger.info("Registered telemetry callback")

    def on_operations_received(
        self,
        callback: Callable[[OperationsSyncPayload], None],
    ) -> None:
        """
        Register a callback for operations sync

        Args:
            callback: Function that receives OperationsSyncPayload
        """
        self._operations_callback = callback
        logger.info("Registered operations callback")

    def on_status_update_received(
        self,
        callback: Callable[[dict], None],
    ) -> None:
        """
        Register a callback for status updates

        Args:
            callback: Function that receives status update dict
        """
        self._status_callback = callback
        logger.info("Registered status update callback")


# ============================================================================
# Convenience Functions
# ============================================================================

def integrate_with_tasking_engine(
    hq: HQIntegration,
    tasking_engine_module,
) -> None:
    """
    Wire HQ integration to send TaskingEngine output to FieldOps

    Args:
        hq: HQIntegration instance
        tasking_engine_module: The hq_command.tasking_engine module

    This function adds a send-to-field method to the tasking engine
    that automatically dispatches task assignments through the Bridge.
    """
    def send_assignments_to_field(assignments: dict) -> dict[str, bool]:
        """
        Send task assignments to FieldOps units

        Args:
            assignments: Output from schedule_tasks_for_field_units()

        Returns:
            Map of unit_id -> success status
        """
        if "assignments" not in assignments:
            logger.warning("No assignments field in input")
            return {}

        # Convert assignments to unit_id -> tasks mapping
        unit_tasks = {}
        for assignment in assignments["assignments"]:
            for unit_id in assignment.get("assigned_units", []):
                if unit_id not in unit_tasks:
                    unit_tasks[unit_id] = []

                # Serialize the task with proper format conversions
                capabilities = assignment.get("capabilities_required", [])
                # Convert frozenset to list if needed
                if isinstance(capabilities, frozenset):
                    capabilities = list(capabilities)

                task_dict = {
                    "task_id": assignment["task_id"],
                    "priority": assignment["priority"],
                    "capabilities_required": capabilities,
                    "location": assignment.get("location"),
                }
                unit_tasks[unit_id].append(task_dict)

        # Send to all units
        return hq.send_tasks_to_multiple_units(
            assignments=unit_tasks,
            operator_id=assignments.get("operator_id", "system"),
        )

    # Attach method to module
    tasking_engine_module.send_assignments_to_field = send_assignments_to_field
    logger.info("Integrated HQ with tasking engine")


def integrate_with_analytics(
    hq: HQIntegration,
    analytics_module,
    event_store=None,
) -> None:
    """
    Wire HQ integration to receive telemetry into analytics

    Args:
        hq: HQIntegration instance
        analytics_module: The hq_command.analytics module
        event_store: Optional EventStore for audit logging

    This function registers callbacks that feed incoming telemetry
    and operations into the analytics and event store.
    """
    def handle_telemetry(payload: TelemetryReportPayload) -> None:
        """Process incoming telemetry"""
        try:
            # Store telemetry (could feed into analytics)
            logger.info(f"Analytics: Processing telemetry from {payload.device_id}")

            # If event store exists, log the telemetry
            if event_store:
                event_store.record_event(
                    event_type="telemetry_received",
                    actor=payload.device_id,
                    resource=f"telemetry/{payload.device_id}",
                    action="report",
                    details={
                        "collected_at": payload.collected_at.isoformat(),
                        "location": payload.location,
                        "metrics_count": len(payload.telemetry.get("metrics", {})),
                    },
                )

        except Exception as e:
            logger.error(f"Error processing telemetry in analytics: {e}")

    def handle_operations(payload: OperationsSyncPayload) -> None:
        """Process incoming operations"""
        try:
            logger.info(
                f"Analytics: Processing {len(payload.operations)} operations "
                f"from {payload.device_id}"
            )

            # If event store exists, log the operations
            if event_store:
                event_store.record_event(
                    event_type="operations_synced",
                    actor=payload.device_id,
                    resource=f"operations/{payload.device_id}",
                    action="sync",
                    details={
                        "synced_at": payload.synced_at.isoformat(),
                        "sequence_number": payload.sequence_number,
                        "operation_count": len(payload.operations),
                    },
                )

        except Exception as e:
            logger.error(f"Error processing operations in analytics: {e}")

    # Register callbacks
    hq.on_telemetry_received(handle_telemetry)
    hq.on_operations_received(handle_operations)

    logger.info("Integrated HQ with analytics")
