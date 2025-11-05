"""Bridge communications router with protocol adapters and routing ledger."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional


class PartnerDeliveryError(RuntimeError):
    """Error raised when a partner adapter fails to deliver a payload."""


@dataclass(frozen=True)
class MutualTLSConfig:
    """Configuration describing mutual TLS material for a partner endpoint."""

    client_certificate: str
    client_key: str
    ca_bundle: str

    def as_metadata(self) -> Dict[str, str]:
        """Expose TLS material in a serialisable form for auditing."""

        return {
            "client_certificate": self.client_certificate,
            "client_key": self.client_key,
            "ca_bundle": self.ca_bundle,
        }


Transformation = Callable[[Mapping[str, Any]], Dict[str, Any]]


@dataclass
class PartnerEndpoint:
    """Partner endpoint configuration consumed by the communications router."""

    name: str
    protocol: str
    target: str
    mutual_tls: MutualTLSConfig | None = None
    signing_key: str | None = None
    max_retries: int = 3
    transform: Transformation | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def apply_transform(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Apply partner-specific transformation if configured."""

        if self.transform is None:
            return dict(payload)
        transformed = self.transform(payload)
        if not isinstance(transformed, MutableMapping):
            raise TypeError("Partner transform must return a mapping-compatible object.")
        return dict(transformed)


@dataclass
class RoutingRecord:
    """Record produced for each routing attempt and stored for analytics."""

    partner: str
    protocol: str
    target: str
    status: str
    attempts: int
    signature: str | None
    delivered_at: datetime | None
    error: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    payload_preview: Dict[str, Any] = field(default_factory=dict)


class RoutingLedger:
    """In-memory ledger storing routing outcomes for HQ analytics."""

    def __init__(self) -> None:
        self._records: list[RoutingRecord] = []

    def record(self, record: RoutingRecord) -> None:
        self._records.append(record)

    def history(self) -> Iterable[RoutingRecord]:
        return tuple(self._records)

    def history_for_partner(self, partner: str) -> Iterable[RoutingRecord]:
        return tuple(record for record in self._records if record.partner == partner)


@dataclass
class DeadLetterMessage:
    """Payload captured after exhausting retry attempts."""

    partner: str
    payload: Dict[str, Any]
    error: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DeadLetterQueue:
    """In-memory dead letter queue for failed routing attempts."""

    def __init__(self) -> None:
        self._messages: list[DeadLetterMessage] = []

    def enqueue(self, partner: str, payload: Dict[str, Any], error: str) -> DeadLetterMessage:
        message = DeadLetterMessage(partner=partner, payload=dict(payload), error=error)
        self._messages.append(message)
        return message

    def pending(self) -> Iterable[DeadLetterMessage]:
        return tuple(self._messages)


class ProtocolAdapter:
    """Adapter interface for protocol-specific delivery implementations."""

    protocol: str

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class RestProtocolAdapter(ProtocolAdapter):
    protocol = "rest"

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if not endpoint.target.startswith("http"):
            raise PartnerDeliveryError("REST target must be an HTTP(S) URL.")
        if endpoint.mutual_tls and not all(endpoint.mutual_tls.as_metadata().values()):
            raise PartnerDeliveryError("Mutual TLS configuration incomplete for REST endpoint.")
        return {
            "method": "POST",
            "url": endpoint.target,
            "tls": endpoint.mutual_tls.as_metadata() if endpoint.mutual_tls else None,
            "payload_size": len(json.dumps(payload, default=str).encode("utf-8")),
        }


class MessageQueueAdapter(ProtocolAdapter):
    protocol = "mq"

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if not endpoint.target:
            raise PartnerDeliveryError("Message queue target must be defined.")
        queue_name = endpoint.metadata.get("queue", endpoint.target)
        return {
            "queue": queue_name,
            "messages_enqueued": 1,
            "payload_checksum": _stable_checksum(payload),
        }


class SecureFileDropAdapter(ProtocolAdapter):
    protocol = "secure_file_drop"

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> Dict[str, Any]:
        if not endpoint.target:
            raise PartnerDeliveryError("Secure file drop target must be provided.")
        filename = endpoint.metadata.get("filename", f"drop_{int(datetime.now().timestamp())}.json")
        return {
            "location": endpoint.target,
            "filename": filename,
            "bytes_written": len(json.dumps(payload, default=str).encode("utf-8")),
        }


class LocalMessageBusAdapter(ProtocolAdapter):
    """Adapter for local file-based message bus"""
    protocol = "local"

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Send message via local message bus"""
        try:
            from .local_message_bus import get_message_bus

            bus = get_message_bus()

            # Extract sender and recipient from payload
            sender = payload.get("sender_id", "unknown")
            recipient = endpoint.target  # Use target as recipient ID

            # Send message
            message_id = bus.send(sender, recipient, dict(payload))

            return {
                "message_id": message_id,
                "recipient": recipient,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            raise PartnerDeliveryError(f"Failed to send via local message bus: {e}")


class BridgeCommsRouter:
    """Route payloads to partner endpoints with retries and auditing hooks."""

    def __init__(
        self,
        partners: Mapping[str, PartnerEndpoint],
        *,
        ledger: RoutingLedger | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
        adapters: Optional[Mapping[str, ProtocolAdapter]] = None,
    ) -> None:
        self._partners = dict(partners)
        self.ledger = ledger or RoutingLedger()
        self.dead_letter_queue = dead_letter_queue or DeadLetterQueue()
        self._adapters = {
            "rest": RestProtocolAdapter(),
            "mq": MessageQueueAdapter(),
            "secure_file_drop": SecureFileDropAdapter(),
            "local": LocalMessageBusAdapter(),
        }
        if adapters:
            self._adapters.update(adapters)

    def route(self, partner: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        endpoint = self._partners.get(partner)
        if endpoint is None:
            raise KeyError(f"Partner '{partner}' is not configured for routing.")

        adapter = self._adapters.get(endpoint.protocol)
        if adapter is None:
            raise ValueError(f"No adapter registered for protocol '{endpoint.protocol}'.")

        transformed_payload = endpoint.apply_transform(payload)
        signature = _maybe_sign_payload(endpoint, transformed_payload)
        payload_with_signature = dict(transformed_payload)
        if signature:
            payload_with_signature["signature"] = signature

        attempts = 0
        last_error: str | None = None
        delivery_metadata: Dict[str, Any] | None = None
        for attempts in range(1, endpoint.max_retries + 1):
            try:
                delivery_metadata = adapter.send(endpoint, payload_with_signature)
            except PartnerDeliveryError as exc:  # pragma: no cover - error path tested explicitly
                last_error = str(exc)
                continue
            else:
                break

        status = "delivered" if delivery_metadata is not None else "dead_letter"

        if status == "dead_letter":
            last_error = last_error or "Unknown delivery failure"
            self.dead_letter_queue.enqueue(partner, payload_with_signature, last_error)

        record = RoutingRecord(
            partner=partner,
            protocol=endpoint.protocol,
            target=endpoint.target,
            status=status,
            attempts=attempts,
            signature=signature,
            delivered_at=datetime.now(timezone.utc) if status == "delivered" else None,
            error=last_error,
            metadata=dict(delivery_metadata or {}),
            payload_preview=_preview_payload(payload_with_signature),
        )
        self.ledger.record(record)

        response = {
            "partner": partner,
            "protocol": endpoint.protocol,
            "status": status,
            "attempts": attempts,
            "signature": signature,
            "delivery_metadata": delivery_metadata,
        }
        if last_error:
            response["error"] = last_error
        return response


_DEFAULT_ROUTER: BridgeCommsRouter | None = None


def configure_default_router(router: BridgeCommsRouter) -> None:
    """Register a default router instance for convenience helpers."""

    global _DEFAULT_ROUTER
    _DEFAULT_ROUTER = router


def route_message_to_partner(
    message: Mapping[str, Any], *, router: BridgeCommsRouter | None = None
) -> Dict[str, Any]:
    """Route a message to a configured partner endpoint.

    The function is a thin wrapper over :class:`BridgeCommsRouter` that preserves
    backwards compatibility with earlier call sites that directly invoked the
    module-level function.  Callers supply the partner identifier and payload in
    the message structure.  Router instances can be injected for testing or
    provided globally via :func:`configure_default_router`.

    Args:
        message: Mapping containing ``partner`` and ``payload`` keys.
        router: Optional router instance to use for this invocation.

    Returns:
        Metadata describing the routing attempt and status.
    """

    active_router = router or _DEFAULT_ROUTER
    if active_router is None:
        raise RuntimeError("No default Bridge router configured.")

    partner = message.get("partner")
    if not isinstance(partner, str) or not partner:
        raise ValueError("Message must include a non-empty 'partner' identifier.")

    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("Message must include a mapping payload under the 'payload' key.")

    return active_router.route(partner, payload)


def _maybe_sign_payload(endpoint: PartnerEndpoint, payload: Mapping[str, Any]) -> str | None:
    if not endpoint.signing_key:
        return None

    serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hmac.new(endpoint.signing_key.encode("utf-8"), serialized, hashlib.sha256)
    return digest.hexdigest()


def _preview_payload(payload: Mapping[str, Any], limit: int = 5) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}
    for idx, (key, value) in enumerate(payload.items()):
        preview[str(key)] = value
        if idx + 1 >= limit:
            break
    return preview


def _stable_checksum(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(serialized).hexdigest()
