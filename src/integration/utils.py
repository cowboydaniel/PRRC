"""
Utility functions for integration setup

Provides convenience functions to set up Bridge components with
reasonable defaults for testing and development.
"""
from pathlib import Path


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
    partners = {
        # HQ Command endpoints
        "hq_command": PartnerEndpoint(
            name="HQ Command",
            protocol="rest",
            target="http://localhost:8001/api/messages",
        ),
        "hq_test": PartnerEndpoint(
            name="HQ Command Test",
            protocol="rest",
            target="http://localhost:8001/api/messages",
        ),
        "hq_cli": PartnerEndpoint(
            name="HQ Command CLI",
            protocol="rest",
            target="http://localhost:8001/api/messages",
        ),
        "hq_demo": PartnerEndpoint(
            name="HQ Command Demo",
            protocol="rest",
            target="http://localhost:8001/api/messages",
        ),
        # FieldOps endpoints
        "fieldops_001": PartnerEndpoint(
            name="FieldOps Unit 001",
            protocol="rest",
            target="http://localhost:9001/api/messages",
        ),
        "fieldops_002": PartnerEndpoint(
            name="FieldOps Unit 002",
            protocol="rest",
            target="http://localhost:9002/api/messages",
        ),
        "fieldops_003": PartnerEndpoint(
            name="FieldOps Unit 003",
            protocol="rest",
            target="http://localhost:9003/api/messages",
        ),
        "fieldops_test": PartnerEndpoint(
            name="FieldOps Test",
            protocol="rest",
            target="http://localhost:9000/api/messages",
        ),
        "fieldops_cli": PartnerEndpoint(
            name="FieldOps CLI",
            protocol="rest",
            target="http://localhost:9000/api/messages",
        ),
        "fieldops_demo": PartnerEndpoint(
            name="FieldOps Demo",
            protocol="rest",
            target="http://localhost:9000/api/messages",
        ),
    }

    # Create router with ledger and dead letter queue
    router = BridgeCommsRouter(
        partners=partners,
        ledger=RoutingLedger(),
        dead_letter_queue=DeadLetterQueue(),
    )

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
