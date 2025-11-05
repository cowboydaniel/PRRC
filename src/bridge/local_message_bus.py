"""
Local Message Bus for inter-process communication

This module provides a file-based message bus that allows FieldOps and HQ Command
to communicate when running as separate processes on the same machine.

Messages are written to a shared directory and polled by recipients.
"""
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class LocalMessage:
    """A message in the local message bus"""
    message_id: str
    sender: str
    recipient: str
    payload: Dict[str, Any]
    timestamp: datetime
    delivered: bool = False


class LocalMessageBus:
    """
    File-based message bus for local inter-process communication

    Messages are stored in ~/.prrc/messages/ directory with separate inboxes
    for each recipient.
    """

    def __init__(self, bus_dir: Path | None = None):
        """
        Initialize the local message bus

        Args:
            bus_dir: Directory for message storage (default: ~/.prrc/messages)
        """
        if bus_dir is None:
            bus_dir = Path.home() / ".prrc" / "messages"

        self.bus_dir = bus_dir
        self.bus_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized local message bus at {self.bus_dir}")

    def send(self, sender: str, recipient: str, payload: Dict[str, Any]) -> str:
        """
        Send a message to a recipient

        Args:
            sender: ID of the sender
            recipient: ID of the recipient
            payload: Message payload

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())

        message = LocalMessage(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            payload=payload,
            timestamp=datetime.now(timezone.utc),
        )

        # Create recipient inbox if it doesn't exist
        inbox_dir = self.bus_dir / recipient
        inbox_dir.mkdir(parents=True, exist_ok=True)

        # Write message to recipient's inbox
        message_file = inbox_dir / f"{message_id}.json"
        message_data = {
            "message_id": message.message_id,
            "sender": message.sender,
            "recipient": message.recipient,
            "payload": message.payload,
            "timestamp": message.timestamp.isoformat(),
            "delivered": False,
        }

        try:
            message_file.write_text(json.dumps(message_data, indent=2))
            logger.debug(f"Sent message {message_id} from {sender} to {recipient}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def receive(self, recipient: str, mark_delivered: bool = True) -> list[LocalMessage]:
        """
        Receive all pending messages for a recipient

        Args:
            recipient: ID of the recipient
            mark_delivered: If True, mark messages as delivered and delete them

        Returns:
            List of messages
        """
        inbox_dir = self.bus_dir / recipient
        if not inbox_dir.exists():
            return []

        messages = []

        # Read all message files
        for message_file in inbox_dir.glob("*.json"):
            try:
                message_data = json.loads(message_file.read_text())

                message = LocalMessage(
                    message_id=message_data["message_id"],
                    sender=message_data["sender"],
                    recipient=message_data["recipient"],
                    payload=message_data["payload"],
                    timestamp=datetime.fromisoformat(message_data["timestamp"]),
                    delivered=message_data.get("delivered", False),
                )

                messages.append(message)

                # Delete message file if marking as delivered
                if mark_delivered:
                    message_file.unlink()
                    logger.debug(f"Received and deleted message {message.message_id}")

            except Exception as e:
                logger.error(f"Failed to read message {message_file}: {e}")
                continue

        return messages

    def poll(
        self,
        recipient: str,
        callback: callable,
        interval: float = 1.0,
        stop_condition: callable = None,
    ) -> None:
        """
        Poll for messages and call callback for each new message

        Args:
            recipient: ID of the recipient
            callback: Function to call with each message payload
            interval: Polling interval in seconds
            stop_condition: Optional function that returns True to stop polling
        """
        logger.info(f"Starting message polling for {recipient}")

        while True:
            if stop_condition and stop_condition():
                break

            messages = self.receive(recipient, mark_delivered=True)

            for message in messages:
                try:
                    callback(message.payload)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}", exc_info=True)

            time.sleep(interval)


# Global message bus instance
_global_bus = None


def get_message_bus() -> LocalMessageBus:
    """Get the global message bus instance"""
    global _global_bus
    if _global_bus is None:
        _global_bus = LocalMessageBus()
    return _global_bus
