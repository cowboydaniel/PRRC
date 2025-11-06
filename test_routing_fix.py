#!/usr/bin/env python3
"""Test script to verify the dynamic partner routing fix"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from integration.utils import create_default_bridge_router, create_default_audit_log
from integration.coordinator import create_hq_coordinator
from integration.protocol import create_task_assignment_message

def test_dynamic_partner():
    """Test that dynamic partner '46WJKW2' can be routed"""
    print("Setting up router and coordinator...")
    router = create_default_bridge_router()
    audit_log = create_default_audit_log()
    coordinator = create_hq_coordinator(router, audit_log, hq_id="hq_test")

    print("\nTesting routing to partner '46WJKW2'...")

    # Create a test message
    envelope = create_task_assignment_message(
        tasks=[
            {
                "task_id": "TEST-001",
                "priority": "High",
                "capabilities_required": ["communication"],
            }
        ],
        operator_id="test_operator",
        sender_id="hq_test",
        recipient_id="46WJKW2",
    )

    # Try to send the message
    try:
        success = coordinator.send_message(envelope, partner_id="46WJKW2")
        if success:
            print("✓ Successfully sent message to partner '46WJKW2'")
            print(f"✓ Message ID: {envelope.message_id}")

            # Verify the partner was added to the router
            if "46WJKW2" in router._router._partners:
                partner = router._router._partners["46WJKW2"]
                print(f"✓ Partner endpoint created: {partner.name}")
                print(f"✓ Protocol: {partner.protocol}")
                print(f"✓ Target: {partner.target}")
        else:
            print("✗ Failed to send message (but no exception)")
            return False

    except KeyError as e:
        print(f"✗ KeyError (fix didn't work): {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n✓ All tests passed! The routing fix works correctly.")
    return True

if __name__ == "__main__":
    success = test_dynamic_partner()
    sys.exit(0 if success else 1)
