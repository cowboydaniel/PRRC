"""
Utility functions for integration setup

Provides convenience functions to set up Bridge components with
reasonable defaults for testing and development.
"""
from pathlib import Path
from typing import Any, Mapping, Dict


class DynamicBridgeCommsRouter:
    """
    Wrapper around BridgeCommsRouter that supports dynamic partner registration.

    This router automatically creates partner endpoints for unknown partners
    using a default configuration, which is useful for development and testing
    where partner IDs may not be known in advance.
    """

    def __init__(self, base_router, default_protocol="local"):
        """
        Initialize the dynamic router wrapper.

        Args:
            base_router: The underlying BridgeCommsRouter instance
            default_protocol: Protocol to use for dynamically created partners
        """
        self._router = base_router
        self._default_protocol = default_protocol

    def route(self, partner: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Route a message to a partner, creating the partner endpoint if needed.

        Args:
            partner: Partner ID to route to
            payload: Message payload

        Returns:
            Routing result metadata
        """
        # Check if partner exists
        if partner not in self._router._partners:
            # Dynamically create partner endpoint
            from bridge.comms_router import PartnerEndpoint

            endpoint = PartnerEndpoint(
                name=f"Dynamic Partner {partner}",
                protocol=self._default_protocol,
                target=partner,
            )
            self._router._partners[partner] = endpoint

        # Route the message using the base router
        return self._router.route(partner, payload)

    def __getattr__(self, name):
        """Delegate all other attributes to the base router"""
        return getattr(self._router, name)


def create_default_bridge_router():
    """
    Create a BridgeCommsRouter with default configuration

    Returns:
        Configured BridgeCommsRouter instance
    """
    from bridge.comms_router import (
        BridgeCommsRouter,
        PartnerEndpoint,
        RoutingLedger,
        DeadLetterQueue,
    )

    # Create default partner endpoints
    # Use "local" protocol for development/demo mode (file-based message bus)
    # For production, switch to "rest" protocol with actual HTTP servers
    partners = {
        # HQ Command endpoints
        "hq_command": PartnerEndpoint(
            name="HQ Command",
            protocol="local",
            target="hq_command",  # Recipient ID for local message bus
        ),
        "hq_test": PartnerEndpoint(
            name="HQ Command Test",
            protocol="local",
            target="hq_command",
        ),
        "hq_cli": PartnerEndpoint(
            name="HQ Command CLI",
            protocol="local",
            target="hq_command",
        ),
        "hq_demo": PartnerEndpoint(
            name="HQ Command Demo",
            protocol="local",
            target="hq_command",
        ),
        # FieldOps endpoints
        "fieldops_001": PartnerEndpoint(
            name="FieldOps Unit 001",
            protocol="local",
            target="fieldops_001",  # Recipient ID for local message bus
        ),
        "fieldops_002": PartnerEndpoint(
            name="FieldOps Unit 002",
            protocol="local",
            target="fieldops_002",
        ),
        "fieldops_003": PartnerEndpoint(
            name="FieldOps Unit 003",
            protocol="local",
            target="fieldops_003",
        ),
        "fieldops_test": PartnerEndpoint(
            name="FieldOps Test",
            protocol="local",
            target="fieldops_test",
        ),
        "fieldops_cli": PartnerEndpoint(
            name="FieldOps CLI",
            protocol="local",
            target="fieldops_cli",
        ),
        "fieldops_demo": PartnerEndpoint(
            name="FieldOps Demo",
            protocol="local",
            target="fieldops_demo",
        ),
    }

    # Create router with ledger and dead letter queue
    base_router = BridgeCommsRouter(
        partners=partners,
        ledger=RoutingLedger(),
        dead_letter_queue=DeadLetterQueue(),
    )

    # Wrap in dynamic router to support automatic partner registration
    router = DynamicBridgeCommsRouter(base_router, default_protocol="local")

    return router


def create_default_audit_log():
    """
    Create a TamperEvidentAuditLog with default configuration

    Returns:
        Configured TamperEvidentAuditLog instance
    """
    from bridge.compliance import TamperEvidentAuditLog

    # Use ~/.prrc/audit/ as default log directory
    log_dir = Path.home() / ".prrc" / "audit"
    log_dir.mkdir(parents=True, exist_ok=True)

    audit_log = TamperEvidentAuditLog()

    return audit_log


def setup_bridge_components():
    """
    Set up Bridge router and audit log with defaults

    Returns:
        Tuple of (router, audit_log)
    """
    router = create_default_bridge_router()
    audit_log = create_default_audit_log()

    return router, audit_log
