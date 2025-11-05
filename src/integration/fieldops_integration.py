"""
FieldOps Integration Layer

This module provides the integration layer for FieldOps to communicate
with HQ Command through the Bridge.

Responsibilities:
- Receive task assignments from HQ Command
- Send telemetry reports to HQ
- Sync offline operations queue to HQ
- Update task status back to HQ
"""
import logging
from datetime import datetime
from typing import Callable

from .protocol import (
    MessageEnvelope,
    MessageType,
    TaskAssignmentPayload,
    create_telemetry_report_message,
    create_operations_sync_message,
)
from .coordinator import IntegrationCoordinator

# Import shared schemas - handle both package and module imports
try:
    from shared.schemas import priority_to_string
except ImportError:
    from ..shared.schemas import priority_to_string

logger = logging.getLogger(__name__)


# ============================================================================
# FieldOps Integration Interface
# ============================================================================

class FieldOpsIntegration:
    """
    FieldOps integration interface

    Provides high-level methods for FieldOps to interact with HQ Command
    through the Bridge.

    Usage:
        fieldops = FieldOpsIntegration(coordinator)

        # Send telemetry to HQ
        fieldops.send_telemetry_to_hq(telemetry_snapshot)

        # Sync offline operations to HQ
        fieldops.sync_operations_to_hq(operations)

        # Register callbacks for incoming tasks
        fieldops.on_task_assignment(handle_tasks)
    """

    def __init__(self, coordinator: IntegrationCoordinator):
        self.coordinator = coordinator
        self._hq_id = "hq_command"  # Default HQ ID
        self._sequence_number = 0
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message handlers for incoming HQ messages"""
        self.coordinator.register_handler(
            MessageType.TASK_ASSIGNMENT,
            self._handle_task_assignment,
            "Process task assignments from HQ",
        )

        self.coordinator.register_handler(
            MessageType.TASK_UPDATE,
            self._handle_task_update,
            "Process task updates from HQ",
        )

        self.coordinator.register_handler(
            MessageType.TASK_CANCELLATION,
            self._handle_task_cancellation,
            "Process task cancellations from HQ",
        )

    def set_hq_id(self, hq_id: str) -> None:
        """Set the HQ Command instance ID to communicate with"""
        self._hq_id = hq_id
        logger.info(f"Set HQ ID to: {hq_id}")

    # ========================================================================
    # Outbound: FieldOps → HQ
    # ========================================================================

    def send_telemetry_to_hq(
        self,
        telemetry: dict,
        location: tuple[float, float] | None = None,
    ) -> bool:
        """
        Send telemetry snapshot to HQ Command

        Args:
            telemetry: Serialized TelemetrySnapshot dict
            location: Optional GPS coordinates (lat, lon)

        Returns:
            True if telemetry was sent successfully
        """
        try:
            # Create message envelope
            envelope = create_telemetry_report_message(
                device_id=self.coordinator.node_id,
                telemetry=telemetry,
                sender_id=self.coordinator.node_id,
                recipient_id=self._hq_id,
                location=location,
            )

            # Send through coordinator
            success = self.coordinator.send_message(envelope, partner_id=self._hq_id)

            if success:
                logger.info(f"Sent telemetry to HQ (message {envelope.message_id})")
            else:
                logger.warning("Failed to send telemetry to HQ")

            return success

        except Exception as e:
            logger.error(f"Error sending telemetry to HQ: {e}", exc_info=True)
            return False

    def sync_operations_to_hq(self, operations: list[dict]) -> bool:
        """
        Sync offline operations to HQ Command

        Args:
            operations: List of serialized OfflineOperation dicts

        Returns:
            True if operations were synced successfully
        """
        try:
            # Increment sequence number
            self._sequence_number += 1

            # Create message envelope
            envelope = create_operations_sync_message(
                device_id=self.coordinator.node_id,
                operations=operations,
                sequence_number=self._sequence_number,
                sender_id=self.coordinator.node_id,
                recipient_id=self._hq_id,
            )

            # Send through coordinator
            success = self.coordinator.send_message(envelope, partner_id=self._hq_id)

            if success:
                logger.info(
                    f"Synced {len(operations)} operations to HQ "
                    f"(seq {self._sequence_number})"
                )
            else:
                logger.warning("Failed to sync operations to HQ")

            return success

        except Exception as e:
            logger.error(f"Error syncing operations to HQ: {e}", exc_info=True)
            return False

    def send_status_update_to_hq(
        self,
        status: str,
        capabilities: list[str],
        max_concurrent_tasks: int,
        current_task_count: int,
        fatigue_level: float,
    ) -> bool:
        """
        Send status update to HQ Command

        Args:
            status: Unit status (available, busy, offline, maintenance)
            capabilities: List of capability tags
            max_concurrent_tasks: Maximum concurrent task capacity
            current_task_count: Current number of active tasks
            fatigue_level: Fatigue level (0.0 to 1.0)

        Returns:
            True if status was sent successfully
        """
        try:
            from .protocol import MessageEnvelope, MessageType, StatusUpdatePayload
            import uuid

            payload = StatusUpdatePayload(
                unit_id=self.coordinator.node_id,
                status=status,  # type: ignore
                capabilities=capabilities,
                max_concurrent_tasks=max_concurrent_tasks,
                current_task_count=current_task_count,
                fatigue_level=fatigue_level,
            )

            envelope = MessageEnvelope(
                message_id=str(uuid.uuid4()),
                message_type=MessageType.STATUS_UPDATE,
                sender_id=self.coordinator.node_id,
                recipient_id=self._hq_id,
                timestamp=datetime.utcnow(),
                payload=payload.to_dict(),
            )

            success = self.coordinator.send_message(envelope, partner_id=self._hq_id)

            if success:
                logger.info(f"Sent status update to HQ: {status}")
            else:
                logger.warning("Failed to send status update to HQ")

            return success

        except Exception as e:
            logger.error(f"Error sending status update to HQ: {e}", exc_info=True)
            return False

    # ========================================================================
    # Inbound: HQ → FieldOps
    # ========================================================================

    def _handle_task_assignment(self, envelope: MessageEnvelope) -> None:
        """Handle incoming task assignment from HQ"""
        try:
            payload = TaskAssignmentPayload.from_dict(envelope.payload)

            # Normalize task priorities to string format for FieldOps
            # HQ may send int (1-5), we need string ("Routine", "High", "Critical")
            for task in payload.tasks:
                if "priority" in task:
                    task["priority"] = priority_to_string(task["priority"])

            logger.info(
                f"Received {len(payload.tasks)} task assignments from HQ "
                f"(operator: {payload.operator_id})"
            )

            # Call registered callback if exists
            if hasattr(self, "_task_callback"):
                self._task_callback(payload)

        except Exception as e:
            logger.error(f"Error handling task assignment: {e}", exc_info=True)
            raise

    def _handle_task_update(self, envelope: MessageEnvelope) -> None:
        """Handle incoming task update from HQ"""
        try:
            payload = envelope.payload

            logger.info(
                f"Received task update from HQ: {payload['task_id']}"
            )

            # Call registered callback if exists
            if hasattr(self, "_update_callback"):
                self._update_callback(payload)

        except Exception as e:
            logger.error(f"Error handling task update: {e}", exc_info=True)
            raise

    def _handle_task_cancellation(self, envelope: MessageEnvelope) -> None:
        """Handle incoming task cancellation from HQ"""
        try:
            payload = envelope.payload

            logger.info(
                f"Received task cancellation from HQ: "
                f"{len(payload['task_ids'])} tasks"
            )

            # Call registered callback if exists
            if hasattr(self, "_cancellation_callback"):
                self._cancellation_callback(payload)

        except Exception as e:
            logger.error(f"Error handling task cancellation: {e}", exc_info=True)
            raise

    # ========================================================================
    # Callback Registration
    # ========================================================================

    def on_task_assignment(
        self,
        callback: Callable[[TaskAssignmentPayload], None],
    ) -> None:
        """
        Register a callback for task assignments

        Args:
            callback: Function that receives TaskAssignmentPayload
        """
        self._task_callback = callback
        logger.info("Registered task assignment callback")

    def on_task_update(
        self,
        callback: Callable[[dict], None],
    ) -> None:
        """
        Register a callback for task updates

        Args:
            callback: Function that receives task update dict
        """
        self._update_callback = callback
        logger.info("Registered task update callback")

    def on_task_cancellation(
        self,
        callback: Callable[[dict], None],
    ) -> None:
        """
        Register a callback for task cancellations

        Args:
            callback: Function that receives cancellation dict
        """
        self._cancellation_callback = callback
        logger.info("Registered task cancellation callback")


# ============================================================================
# Convenience Functions
# ============================================================================

def integrate_with_gui_controller(
    fieldops: FieldOpsIntegration,
    gui_controller,
) -> None:
    """
    Wire FieldOps integration to GUI controller

    Args:
        fieldops: FieldOpsIntegration instance
        gui_controller: FieldOpsGUIController instance

    This function:
    - Registers callbacks to update GUI state when tasks arrive
    - Wires GUI controller sync operations to send through Bridge
    """
    def handle_task_assignment(payload: TaskAssignmentPayload) -> None:
        """Update GUI with new task assignments"""
        try:
            from ..fieldops.gui.state import TaskAssignmentCard

            # Convert tasks to GUI cards
            cards = []
            for task in payload.tasks:
                # Ensure priority is in string format for FieldOps GUI
                # HQ may send int (1-5) or string ("Routine", "High", "Critical")
                # Convert to standardized string format
                priority_value = task.get("priority", 3)
                priority_str = priority_to_string(priority_value)

                card = TaskAssignmentCard(
                    task_id=task["task_id"],
                    title=task.get("location") or f"Task {task['task_id']}",
                    status="pending",
                    priority=priority_str,
                    display_status="Pending Assignment",
                    summary=f"Required: {', '.join(task.get('capabilities_required', []))}",
                    location=task.get("location"),
                )
                cards.append(card)

            # Update GUI state by merging new tasks with existing baseline
            # Get existing tasks from the private baseline (controller maintains this)
            existing_tasks = getattr(gui_controller, '_task_baseline', {})

            # Validate and convert _task_baseline to dict if needed
            if not isinstance(existing_tasks, dict):
                # Convert to dict by task_id if it's a sequence
                if hasattr(existing_tasks, '__iter__'):
                    existing_tasks = {task.task_id: task for task in existing_tasks if hasattr(task, 'task_id')}
                else:
                    existing_tasks = {}

            # Merge new cards with existing tasks (new tasks override by task_id)
            merged_tasks = dict(existing_tasks)
            for card in cards:
                merged_tasks[card.task_id] = card

            # Update through controller (which rebuilds immutable state)
            # Convert values to list before passing
            gui_controller.update_task_assignments(list(merged_tasks.values()))

            logger.info(f"Updated GUI with {len(cards)} new tasks ({len(merged_tasks)} total)")

        except Exception as e:
            logger.error(f"Error updating GUI with tasks: {e}", exc_info=True)

    # Register callback
    fieldops.on_task_assignment(handle_task_assignment)

    logger.info("Integrated FieldOps with GUI controller")


def create_bridge_sync_adapter(fieldops: FieldOpsIntegration):
    """
    Create a SyncAdapter implementation that uses the Bridge

    Args:
        fieldops: FieldOpsIntegration instance

    Returns:
        BridgeSyncAdapter instance

    This replaces LocalEchoSyncAdapter with a real implementation
    that syncs through the Bridge to HQ Command.
    """
    class BridgeSyncAdapter:
        """Real SyncAdapter implementation using Bridge"""

        def __init__(self, fieldops_integration: FieldOpsIntegration):
            self.fieldops = fieldops_integration

        def push_operations(self, operations: list) -> dict:
            """
            Push offline operations to HQ through Bridge

            Args:
                operations: List of OfflineOperation objects

            Returns:
                Sync result with accepted/rejected operations
            """
            # Serialize operations
            serialized = []
            failed_ids = []
            for op in operations:
                try:
                    op_dict = {
                        "id": op.id,
                        "type": op.type,
                        "payload": op.payload,
                        "created_at": op.created_at.isoformat() if hasattr(op.created_at, 'isoformat') else str(op.created_at),
                    }
                    serialized.append(op_dict)
                except Exception as e:
                    logger.error(f"Error serializing operation {op.id}: {e}")
                    failed_ids.append(op.id)
                    continue

            # Send through Bridge
            success = self.fieldops.sync_operations_to_hq(serialized)

            # Return result
            if success:
                return {
                    "accepted": [op.id for op in operations if op.id not in failed_ids],
                    "rejected": failed_ids,
                    "errors": [f"Serialization failed: {fid}" for fid in failed_ids],
                }
            else:
                return {
                    "accepted": [],
                    "rejected": [op.id for op in operations],
                    "errors": ["Failed to sync through Bridge"],
                }

        def pull_changes(self) -> list:
            """
            Pull changes from HQ (not implemented in this version)

            Returns:
                Empty list (changes come via push messages)
            """
            # In this architecture, HQ pushes changes rather than FieldOps polling
            return []

        def resolve_conflict(self, change_id: str) -> dict:
            """
            Resolve a conflict (not implemented in this version)

            Returns:
                Empty dict
            """
            return {}

    return BridgeSyncAdapter(fieldops)


def integrate_with_telemetry(
    fieldops: FieldOpsIntegration,
    telemetry_module,
    sync_interval: int = 60,
) -> None:
    """
    Wire FieldOps integration to periodically send telemetry

    Args:
        fieldops: FieldOpsIntegration instance
        telemetry_module: The fieldops.telemetry module
        sync_interval: Telemetry sync interval in seconds

    This function sets up automatic telemetry reporting to HQ.
    """
    import threading
    import time

    def telemetry_sync_loop():
        """Background thread that syncs telemetry periodically"""
        while True:
            try:
                # Collect telemetry
                snapshot = telemetry_module.collect_telemetry_snapshot()

                # Serialize snapshot
                telemetry_dict = {
                    "status": snapshot.status,
                    "collected_at": snapshot.collected_at.isoformat(),
                    "metrics": {
                        "sensors": [
                            {
                                "id": getattr(s, 'id', 'unknown'),
                                "type": getattr(s, 'type', 'unknown'),
                                "value": getattr(s, 'value', None),
                                "unit": getattr(s, 'unit', ''),
                                "timestamp": getattr(s, 'timestamp', snapshot.collected_at).isoformat(),
                            }
                            for s in snapshot.metrics.sensors
                        ],
                        "events": snapshot.metrics.events,
                        "queues": snapshot.metrics.queues,
                    },
                }

                # Send to HQ
                fieldops.send_telemetry_to_hq(telemetry_dict)

            except Exception as e:
                logger.error(f"Error in telemetry sync loop: {e}", exc_info=True)

            # Wait for next sync
            time.sleep(sync_interval)

    # Start background thread
    thread = threading.Thread(target=telemetry_sync_loop, daemon=True)
    thread.start()

    logger.info(f"Started telemetry sync loop (interval: {sync_interval}s)")
