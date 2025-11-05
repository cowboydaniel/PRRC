"""
Integration Coordinator for HQ Command <-> FieldOps Communication

This module provides the glue that connects HQ Command, FieldOps, and Bridge:
- Routes messages between HQ and FieldOps through the Bridge
- Handles compliance auditing for all cross-module communication
- Manages message queues and delivery guarantees
- Provides callbacks for message processing
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Protocol
from pathlib import Path

from .protocol import (
    MessageEnvelope,
    MessageType,
    create_acknowledgement_message,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Message Handler Protocols
# ============================================================================

class MessageHandler(Protocol):
    """Protocol for message processing callbacks"""

    def handle_message(self, envelope: MessageEnvelope) -> None:
        """Process an incoming message"""
        ...


@dataclass
class HandlerRegistration:
    """Registration of a message handler"""
    message_type: MessageType
    handler: Callable[[MessageEnvelope], None]
    description: str


# ============================================================================
# Integration Coordinator
# ============================================================================

@dataclass
class IntegrationCoordinator:
    """
    Central coordinator for HQ-FieldOps integration

    Routes messages between modules through the Bridge and handles
    compliance auditing.

    Usage:
        # Initialize with Bridge router and audit log
        coordinator = IntegrationCoordinator(
            router=bridge_router,
            audit_log=audit_log,
            node_id="hq_command_01",
        )

        # Register message handlers
        coordinator.register_handler(
            MessageType.TASK_ASSIGNMENT,
            handle_task_assignment,
            "Process incoming task assignments"
        )

        # Send messages
        coordinator.send_message(envelope, partner_id="fieldops_device_001")

        # Process incoming messages
        coordinator.receive_message(envelope)
    """
    # Bridge dependencies
    router: "BridgeCommsRouter"  # type: ignore  # Forward reference
    audit_log: "TamperEvidentAuditLog"  # type: ignore  # Forward reference

    # Node identification
    node_id: str  # ID of this HQ/FieldOps instance

    # Message handlers
    _handlers: dict[MessageType, list[HandlerRegistration]] = field(default_factory=dict)

    # Message queue for failed deliveries
    _outbox: list[tuple[MessageEnvelope, str]] = field(default_factory=list)  # (envelope, partner_id)

    # Statistics
    _sent_count: int = 0
    _received_count: int = 0
    _failed_count: int = 0

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[MessageEnvelope], None],
        description: str = "",
    ) -> None:
        """
        Register a handler for a specific message type

        Args:
            message_type: Type of message to handle
            handler: Callback function that processes the message
            description: Human-readable description of what the handler does
        """
        if message_type not in self._handlers:
            self._handlers[message_type] = []

        registration = HandlerRegistration(
            message_type=message_type,
            handler=handler,
            description=description or f"Handle {message_type.value}",
        )

        self._handlers[message_type].append(registration)
        logger.info(f"Registered handler for {message_type.value}: {description}")

    def send_message(
        self,
        envelope: MessageEnvelope,
        partner_id: str,
        protocol: str = "rest",
    ) -> bool:
        """
        Send a message to a partner through the Bridge

        Args:
            envelope: Message envelope to send
            partner_id: ID of recipient (maps to Bridge partner endpoint)
            protocol: Protocol to use (rest, message_queue, file_drop)

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            # Audit the outbound message
            self._audit_outbound(envelope, partner_id)

            # Serialize envelope
            payload = envelope.to_dict()

            # Route through Bridge
            result = self.router.route(partner_id, payload)

            # Extract status from result
            routing_record = type('RoutingRecord', (), {
                'status': result.get('status', 'failed'),
                'error': result.get('error')
            })()

            if routing_record.status == "delivered":
                self._sent_count += 1
                logger.info(
                    f"Sent {envelope.message_type.value} to {partner_id}: "
                    f"{envelope.message_id}"
                )
                return True
            else:
                # Delivery failed, add to outbox for retry
                self._outbox.append((envelope, partner_id))
                self._failed_count += 1
                logger.warning(
                    f"Failed to send {envelope.message_type.value} to {partner_id}: "
                    f"{routing_record.error}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            self._outbox.append((envelope, partner_id))
            self._failed_count += 1
            return False

    def receive_message(self, envelope: MessageEnvelope) -> None:
        """
        Process an incoming message

        Args:
            envelope: Incoming message envelope

        This will:
        1. Audit the incoming message
        2. Dispatch to registered handlers
        3. Send acknowledgement back to sender
        """
        try:
            # Audit the inbound message
            self._audit_inbound(envelope)

            # Dispatch to handlers
            handlers = self._handlers.get(envelope.message_type, [])

            if not handlers:
                logger.warning(
                    f"No handlers registered for {envelope.message_type.value}"
                )
                # Send error acknowledgement
                self._send_ack(
                    envelope,
                    status="failed",
                    details=f"No handler for {envelope.message_type.value}",
                )
                return

            # Process with each handler
            for registration in handlers:
                try:
                    logger.debug(f"Processing with handler: {registration.description}")
                    registration.handler(envelope)
                except Exception as e:
                    logger.error(
                        f"Handler {registration.description} failed: {e}",
                        exc_info=True,
                    )
                    self._send_ack(
                        envelope,
                        status="failed",
                        details=f"Handler error: {str(e)}",
                    )
                    return

            # Send success acknowledgement
            self._send_ack(envelope, status="completed")
            self._received_count += 1

        except Exception as e:
            logger.error(f"Error receiving message: {e}", exc_info=True)
            self._send_ack(
                envelope,
                status="failed",
                details=f"Processing error: {str(e)}",
            )

    def retry_failed_messages(self) -> int:
        """
        Retry sending messages from the outbox

        Returns:
            Number of messages successfully sent
        """
        if not self._outbox:
            return 0

        retry_count = 0
        failed_again = []

        for envelope, partner_id in self._outbox:
            if self.send_message(envelope, partner_id):
                retry_count += 1
            else:
                failed_again.append((envelope, partner_id))

        self._outbox = failed_again
        logger.info(f"Retried {retry_count} messages, {len(self._outbox)} still pending")
        return retry_count

    def get_statistics(self) -> dict[str, int]:
        """Get message statistics"""
        return {
            "sent": self._sent_count,
            "received": self._received_count,
            "failed": self._failed_count,
            "pending_retry": len(self._outbox),
        }

    def _audit_outbound(self, envelope: MessageEnvelope, partner_id: str) -> None:
        """Audit an outbound message"""
        try:
            self.audit_log.record({
                "jurisdiction": "internal",
                "event_type": f"outbound_{envelope.message_type.value}",
                "message_id": envelope.message_id,
                "sender": envelope.sender_id,
                "recipient": envelope.recipient_id,
                "partner_id": partner_id,
                "timestamp": envelope.timestamp.isoformat(),
            })
        except Exception as e:
            logger.error(f"Failed to audit outbound message: {e}")

    def _audit_inbound(self, envelope: MessageEnvelope) -> None:
        """Audit an inbound message"""
        try:
            self.audit_log.record({
                "jurisdiction": "internal",
                "event_type": f"inbound_{envelope.message_type.value}",
                "message_id": envelope.message_id,
                "sender": envelope.sender_id,
                "recipient": envelope.recipient_id,
                "timestamp": envelope.timestamp.isoformat(),
            })
        except Exception as e:
            logger.error(f"Failed to audit inbound message: {e}")

    def _send_ack(
        self,
        original: MessageEnvelope,
        status: str,
        details: str | None = None,
    ) -> None:
        """Send an acknowledgement message back to the sender"""
        try:
            ack = create_acknowledgement_message(
                ack_message_id=original.message_id,
                status=status,  # type: ignore
                sender_id=self.node_id,
                recipient_id=original.sender_id,
                details=details,
            )
            self.send_message(ack, partner_id=original.sender_id)
        except Exception as e:
            logger.error(f"Failed to send acknowledgement: {e}")


# ============================================================================
# Integration Helpers
# ============================================================================

def create_hq_coordinator(
    router: "BridgeCommsRouter",  # type: ignore
    audit_log: "TamperEvidentAuditLog",  # type: ignore
    hq_id: str = "hq_command",
) -> IntegrationCoordinator:
    """
    Create an IntegrationCoordinator for HQ Command

    Args:
        router: Configured BridgeCommsRouter instance
        audit_log: Configured TamperEvidentAuditLog instance
        hq_id: ID of this HQ Command instance

    Returns:
        Configured IntegrationCoordinator
    """
    coordinator = IntegrationCoordinator(
        router=router,
        audit_log=audit_log,
        node_id=hq_id,
    )

    logger.info(f"Created HQ coordinator with ID: {hq_id}")
    return coordinator


def create_fieldops_coordinator(
    router: "BridgeCommsRouter",  # type: ignore
    audit_log: "TamperEvidentAuditLog",  # type: ignore
    device_id: str,
) -> IntegrationCoordinator:
    """
    Create an IntegrationCoordinator for FieldOps

    Args:
        router: Configured BridgeCommsRouter instance
        audit_log: Configured TamperEvidentAuditLog instance
        device_id: ID of this FieldOps device

    Returns:
        Configured IntegrationCoordinator
    """
    coordinator = IntegrationCoordinator(
        router=router,
        audit_log=audit_log,
        node_id=device_id,
    )

    logger.info(f"Created FieldOps coordinator with ID: {device_id}")
    return coordinator


# ============================================================================
# Message Queue Storage (for persistent outbox)
# ============================================================================

class PersistentMessageQueue:
    """
    Persistent storage for message outbox

    Stores failed messages to disk for retry after restart
    """

    def __init__(self, queue_file: Path):
        self.queue_file = queue_file
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure queue directory exists"""
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

    def save_outbox(self, outbox: list[tuple[MessageEnvelope, str]]) -> None:
        """Save outbox to disk"""
        try:
            data = [
                {
                    "envelope": envelope.to_dict(),
                    "partner_id": partner_id,
                }
                for envelope, partner_id in outbox
            ]

            with open(self.queue_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(outbox)} messages to outbox")

        except Exception as e:
            logger.error(f"Failed to save outbox: {e}")

    def load_outbox(self) -> list[tuple[MessageEnvelope, str]]:
        """Load outbox from disk"""
        if not self.queue_file.exists():
            return []

        try:
            with open(self.queue_file, "r") as f:
                data = json.load(f)

            outbox = [
                (
                    MessageEnvelope.from_dict(item["envelope"]),
                    item["partner_id"],
                )
                for item in data
            ]

            logger.debug(f"Loaded {len(outbox)} messages from outbox")
            return outbox

        except Exception as e:
            logger.error(f"Failed to load outbox: {e}")
            return []

    def clear_outbox(self) -> None:
        """Clear the outbox file"""
        if self.queue_file.exists():
            self.queue_file.unlink()
