from __future__ import annotations

from typing import Mapping

import pytest

from bridge.comms_router import (
    BridgeCommsRouter,
    MutualTLSConfig,
    PartnerDeliveryError,
    PartnerEndpoint,
    RestProtocolAdapter,
)


class FlakyRestAdapter(RestProtocolAdapter):
    """Adapter that raises for a configurable number of invocations."""

    def __init__(self, failures: int) -> None:
        super().__init__()
        self._failures = failures
        self.invocations = 0

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, object]) -> dict:  # type: ignore[override]
        self.invocations += 1
        if self.invocations <= self._failures:
            raise PartnerDeliveryError("transient outage")
        return super().send(endpoint, payload)


class AlwaysFailAdapter(RestProtocolAdapter):
    """Adapter that always raises a delivery error."""

    def send(self, endpoint: PartnerEndpoint, payload: Mapping[str, object]) -> dict:  # type: ignore[override]
        raise PartnerDeliveryError("permanent failure")


@pytest.fixture
def tls_config() -> MutualTLSConfig:
    return MutualTLSConfig(
        client_certificate="/etc/certs/alpha.crt",
        client_key="/etc/certs/alpha.key",
        ca_bundle="/etc/certs/alpha-ca.pem",
    )


def test_router_successful_route_records_metadata(tls_config: MutualTLSConfig) -> None:
    endpoint = PartnerEndpoint(
        name="alpha",
        protocol="rest",
        target="https://partner.alpha/api/messages",
        mutual_tls=tls_config,
        signing_key="super-secret",
        transform=lambda payload: {
            "partner_payload": payload["data"],
            "timestamp": payload["timestamp"],
        },
    )
    router = BridgeCommsRouter({"alpha": endpoint})

    result = router.route(
        "alpha",
        {
            "data": {"message": "ready"},
            "timestamp": "2024-01-01T00:00:00Z",
        },
    )

    assert result["status"] == "delivered"
    assert result["signature"] is not None
    ledger_entries = list(router.ledger.history_for_partner("alpha"))
    assert len(ledger_entries) == 1
    record = ledger_entries[0]
    assert record.metadata["method"] == "POST"
    assert record.signature == result["signature"]
    assert record.payload_preview["partner_payload"]["message"] == "ready"


def test_router_retries_and_succeeds_after_transient_errors() -> None:
    endpoint = PartnerEndpoint(
        name="bravo",
        protocol="rest",
        target="https://partner.bravo/api",
        signing_key="retry-key",
        max_retries=3,
    )
    flaky_adapter = FlakyRestAdapter(failures=2)
    router = BridgeCommsRouter({"bravo": endpoint}, adapters={"rest": flaky_adapter})

    result = router.route("bravo", {"payload": "value"})

    assert result["status"] == "delivered"
    assert result["attempts"] == 3
    history = list(router.ledger.history_for_partner("bravo"))
    assert history[0].attempts == 3
    assert flaky_adapter.invocations == 3


def test_router_moves_message_to_dead_letter_after_exhausting_retries() -> None:
    endpoint = PartnerEndpoint(
        name="charlie",
        protocol="rest",
        target="https://partner.charlie/api",
        max_retries=2,
    )
    router = BridgeCommsRouter({"charlie": endpoint}, adapters={"rest": AlwaysFailAdapter()})

    result = router.route("charlie", {"payload": "value"})

    assert result["status"] == "dead_letter"
    assert "error" in result
    dlq_messages = list(router.dead_letter_queue.pending())
    assert len(dlq_messages) == 1
    assert dlq_messages[0].partner == "charlie"
    ledger_entry = list(router.ledger.history_for_partner("charlie"))[0]
    assert ledger_entry.status == "dead_letter"
