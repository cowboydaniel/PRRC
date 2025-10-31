"""Bridge package initialization.

Exports stubs for interagency communications routing and compliance auditing.
"""

from .comms_router import route_message_to_partner
from .compliance import audit_event

__all__ = ["route_message_to_partner", "audit_event"]
