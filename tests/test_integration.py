"""
Integration Tests for HQ Command <-> FieldOps Communication

Tests the end-to-end workflow of task assignments, telemetry reporting,
and operations sync through the Bridge.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from integration import (
    MessageType,
    MessageEnvelope,
    create_hq_coordinator,
    create_fieldops_coordinator,
    HQIntegration,
    FieldOpsIntegration,
)


@pytest.fixture
def mock_router():
    """Create a mock BridgeCommsRouter"""
    router = Mock()
    router.route_message_to_partner = Mock(return_value=Mock(status="delivered", error=None))
    return router


@pytest.fixture
def mock_audit_log():
    """Create a mock TamperEvidentAuditLog"""
    audit_log = Mock()
    audit_log.audit_event = Mock()
    return audit_log


@pytest.fixture
def hq_coordinator(mock_router, mock_audit_log):
    """Create an HQ coordinator with mock dependencies"""
    return create_hq_coordinator(mock_router, mock_audit_log, hq_id="hq_test")


@pytest.fixture
def fieldops_coordinator(mock_router, mock_audit_log):
    """Create a FieldOps coordinator with mock dependencies"""
    return create_fieldops_coordinator(mock_router, mock_audit_log, device_id="fieldops_test")


@pytest.fixture
def hq_integration(hq_coordinator):
    """Create HQ integration"""
    return HQIntegration(hq_coordinator)


@pytest.fixture
def fieldops_integration(fieldops_coordinator):
    """Create FieldOps integration"""
    return FieldOpsIntegration(fieldops_coordinator)


# ============================================================================
# Message Envelope Tests
# ============================================================================

def test_message_envelope_serialization():
    """Test message envelope serialization and deserialization"""
    envelope = MessageEnvelope(
        message_id="test-123",
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id="hq_001",
        recipient_id="fieldops_001",
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
        payload={"test": "data"},
        correlation_id="corr-456",
    )

    # Serialize
    data = envelope.to_dict()
    assert data["message_id"] == "test-123"
    assert data["message_type"] == "task_assignment"
    assert data["sender_id"] == "hq_001"
    assert data["recipient_id"] == "fieldops_001"
    assert data["correlation_id"] == "corr-456"

    # Deserialize
    restored = MessageEnvelope.from_dict(data)
    assert restored.message_id == envelope.message_id
    assert restored.message_type == envelope.message_type
    assert restored.sender_id == envelope.sender_id
    assert restored.recipient_id == envelope.recipient_id
    assert restored.correlation_id == envelope.correlation_id


# ============================================================================
# HQ Integration Tests
# ============================================================================

def test_hq_send_tasks_to_field_unit(hq_integration):
    """Test HQ sending tasks to a field unit"""
    tasks = [
        {
            "task_id": "task-1",
            "priority": 1,
            "capabilities_required": ["hazmat"],
            "location": "sector-alpha",
        },
        {
            "task_id": "task-2",
            "priority": 2,
            "capabilities_required": ["medical"],
            "location": "sector-beta",
        },
    ]

    success = hq_integration.send_tasks_to_field_unit(
        unit_id="fieldops_001",
        tasks=tasks,
        operator_id="operator_123",
    )

    assert success is True
    assert hq_integration.coordinator.router.route_message_to_partner.called


def test_hq_send_tasks_to_multiple_units(hq_integration):
    """Test HQ sending tasks to multiple field units"""
    assignments = {
        "fieldops_001": [{"task_id": "task-1", "priority": 1}],
        "fieldops_002": [{"task_id": "task-2", "priority": 2}],
        "fieldops_003": [{"task_id": "task-3", "priority": 3}],
    }

    results = hq_integration.send_tasks_to_multiple_units(
        assignments=assignments,
        operator_id="operator_123",
    )

    assert len(results) == 3
    assert all(results.values())  # All successful


def test_hq_receives_telemetry(hq_integration):
    """Test HQ receiving telemetry from FieldOps"""
    callback_called = False
    received_payload = None

    def handle_telemetry(payload):
        nonlocal callback_called, received_payload
        callback_called = True
        received_payload = payload

    hq_integration.on_telemetry_received(handle_telemetry)

    # Simulate incoming telemetry
    envelope = MessageEnvelope(
        message_id="msg-123",
        message_type=MessageType.TELEMETRY_REPORT,
        sender_id="fieldops_001",
        recipient_id="hq_test",
        timestamp=datetime.utcnow(),
        payload={
            "device_id": "fieldops_001",
            "telemetry": {"status": "operational", "metrics": {}},
            "collected_at": datetime.utcnow().isoformat(),
            "location": None,
        },
    )

    hq_integration.coordinator.receive_message(envelope)

    assert callback_called
    assert received_payload.device_id == "fieldops_001"


def test_hq_receives_operations_sync(hq_integration):
    """Test HQ receiving operations sync from FieldOps"""
    callback_called = False
    received_payload = None

    def handle_operations(payload):
        nonlocal callback_called, received_payload
        callback_called = True
        received_payload = payload

    hq_integration.on_operations_received(handle_operations)

    # Simulate incoming operations sync
    envelope = MessageEnvelope(
        message_id="msg-456",
        message_type=MessageType.OPERATIONS_SYNC,
        sender_id="fieldops_001",
        recipient_id="hq_test",
        timestamp=datetime.utcnow(),
        payload={
            "device_id": "fieldops_001",
            "operations": [
                {"id": "op-1", "type": "task_complete"},
                {"id": "op-2", "type": "resource_request"},
            ],
            "synced_at": datetime.utcnow().isoformat(),
            "sequence_number": 1,
        },
    )

    hq_integration.coordinator.receive_message(envelope)

    assert callback_called
    assert received_payload.device_id == "fieldops_001"
    assert len(received_payload.operations) == 2


# ============================================================================
# FieldOps Integration Tests
# ============================================================================

def test_fieldops_send_telemetry_to_hq(fieldops_integration):
    """Test FieldOps sending telemetry to HQ"""
    telemetry = {
        "status": "operational",
        "collected_at": datetime.utcnow().isoformat(),
        "metrics": {
            "sensors": [],
            "events": [],
            "queues": [],
        },
    }

    success = fieldops_integration.send_telemetry_to_hq(
        telemetry=telemetry,
        location=(34.0522, -118.2437),  # Los Angeles coordinates
    )

    assert success is True
    assert fieldops_integration.coordinator.router.route_message_to_partner.called


def test_fieldops_sync_operations_to_hq(fieldops_integration):
    """Test FieldOps syncing operations to HQ"""
    operations = [
        {
            "id": "op-1",
            "type": "task_complete",
            "payload": {"task_id": "task-1"},
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "id": "op-2",
            "type": "resource_request",
            "payload": {"resource": "medical_supplies"},
            "created_at": datetime.utcnow().isoformat(),
        },
    ]

    success = fieldops_integration.sync_operations_to_hq(operations)

    assert success is True
    assert fieldops_integration.coordinator.router.route_message_to_partner.called
    assert fieldops_integration._sequence_number == 1


def test_fieldops_send_status_update(fieldops_integration):
    """Test FieldOps sending status update to HQ"""
    success = fieldops_integration.send_status_update_to_hq(
        status="busy",
        capabilities=["hazmat", "medical"],
        max_concurrent_tasks=3,
        current_task_count=2,
        fatigue_level=0.4,
    )

    assert success is True
    assert fieldops_integration.coordinator.router.route_message_to_partner.called


def test_fieldops_receives_task_assignment(fieldops_integration):
    """Test FieldOps receiving task assignment from HQ"""
    callback_called = False
    received_payload = None

    def handle_tasks(payload):
        nonlocal callback_called, received_payload
        callback_called = True
        received_payload = payload

    fieldops_integration.on_task_assignment(handle_tasks)

    # Simulate incoming task assignment
    envelope = MessageEnvelope(
        message_id="msg-789",
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id="hq_001",
        recipient_id="fieldops_test",
        timestamp=datetime.utcnow(),
        payload={
            "tasks": [
                {"task_id": "task-1", "priority": 1},
                {"task_id": "task-2", "priority": 2},
            ],
            "operator_id": "operator_123",
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": None,
            "priority_override": None,
        },
    )

    fieldops_integration.coordinator.receive_message(envelope)

    assert callback_called
    assert len(received_payload.tasks) == 2
    assert received_payload.operator_id == "operator_123"


# ============================================================================
# End-to-End Integration Tests
# ============================================================================

def test_end_to_end_task_assignment_flow(mock_router, mock_audit_log):
    """Test end-to-end task assignment from HQ to FieldOps"""
    # Set up HQ and FieldOps
    hq_coord = create_hq_coordinator(mock_router, mock_audit_log, hq_id="hq_001")
    hq = HQIntegration(hq_coord)

    fo_coord = create_fieldops_coordinator(mock_router, mock_audit_log, device_id="fieldops_001")
    fieldops = FieldOpsIntegration(fo_coord)

    # Register FieldOps callback
    received_tasks = []

    def handle_tasks(payload):
        received_tasks.extend(payload.tasks)

    fieldops.on_task_assignment(handle_tasks)

    # HQ sends tasks
    tasks = [
        {"task_id": "task-1", "priority": 1, "capabilities_required": ["hazmat"]},
        {"task_id": "task-2", "priority": 2, "capabilities_required": ["medical"]},
    ]

    hq.send_tasks_to_field_unit(
        unit_id="fieldops_001",
        tasks=tasks,
        operator_id="operator_123",
    )

    # Simulate message delivery (in real system, Bridge routes this)
    # Get the message that was sent
    call_args = mock_router.route_message_to_partner.call_args
    assert call_args is not None

    partner_id = call_args[1]["partner_id"]
    payload = call_args[1]["payload"]

    # Create envelope from payload and deliver to FieldOps
    envelope = MessageEnvelope.from_dict(payload)
    fieldops.coordinator.receive_message(envelope)

    # Verify FieldOps received the tasks
    assert len(received_tasks) == 2
    assert received_tasks[0]["task_id"] == "task-1"
    assert received_tasks[1]["task_id"] == "task-2"


def test_end_to_end_telemetry_reporting_flow(mock_router, mock_audit_log):
    """Test end-to-end telemetry reporting from FieldOps to HQ"""
    # Set up HQ and FieldOps
    hq_coord = create_hq_coordinator(mock_router, mock_audit_log, hq_id="hq_001")
    hq = HQIntegration(hq_coord)

    fo_coord = create_fieldops_coordinator(mock_router, mock_audit_log, device_id="fieldops_001")
    fieldops = FieldOpsIntegration(fo_coord)

    # Register HQ callback
    received_telemetry = []

    def handle_telemetry(payload):
        received_telemetry.append(payload)

    hq.on_telemetry_received(handle_telemetry)

    # FieldOps sends telemetry
    telemetry = {
        "status": "operational",
        "collected_at": datetime.utcnow().isoformat(),
        "metrics": {"sensors": [], "events": [], "queues": []},
    }

    fieldops.send_telemetry_to_hq(telemetry, location=(34.0522, -118.2437))

    # Simulate message delivery
    call_args = mock_router.route_message_to_partner.call_args
    payload = call_args[1]["payload"]

    envelope = MessageEnvelope.from_dict(payload)
    hq.coordinator.receive_message(envelope)

    # Verify HQ received the telemetry
    assert len(received_telemetry) == 1
    assert received_telemetry[0].device_id == "fieldops_001"
    assert received_telemetry[0].location == (34.0522, -118.2437)


# ============================================================================
# Coordinator Tests
# ============================================================================

def test_coordinator_message_statistics(hq_coordinator):
    """Test coordinator tracks message statistics"""
    stats = hq_coordinator.get_statistics()

    assert stats["sent"] == 0
    assert stats["received"] == 0
    assert stats["failed"] == 0
    assert stats["pending_retry"] == 0


def test_coordinator_retry_failed_messages(hq_coordinator):
    """Test coordinator retries failed messages"""
    # Simulate a failed send by making router return failure
    hq_coordinator.router.route_message_to_partner.return_value = Mock(
        status="failed", error="Connection timeout"
    )

    envelope = MessageEnvelope(
        message_id="msg-fail",
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id="hq_test",
        recipient_id="fieldops_001",
        timestamp=datetime.utcnow(),
        payload={},
    )

    # Try to send (will fail)
    success = hq_coordinator.send_message(envelope, partner_id="fieldops_001")
    assert success is False

    stats = hq_coordinator.get_statistics()
    assert stats["pending_retry"] == 1

    # Now make router succeed
    hq_coordinator.router.route_message_to_partner.return_value = Mock(
        status="delivered", error=None
    )

    # Retry failed messages
    retry_count = hq_coordinator.retry_failed_messages()
    assert retry_count == 1

    stats = hq_coordinator.get_statistics()
    assert stats["pending_retry"] == 0


def test_coordinator_audits_messages(hq_coordinator):
    """Test coordinator audits all messages"""
    envelope = MessageEnvelope(
        message_id="msg-audit",
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id="hq_test",
        recipient_id="fieldops_001",
        timestamp=datetime.utcnow(),
        payload={},
    )

    hq_coordinator.send_message(envelope, partner_id="fieldops_001")

    # Verify audit log was called
    assert hq_coordinator.audit_log.audit_event.called
    call_args = hq_coordinator.audit_log.audit_event.call_args
    assert "outbound_task_assignment" in str(call_args)
