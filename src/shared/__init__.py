"""Shared schemas and data structures for PRRC OS Suite."""

from .schemas import Priority, priority_to_int, priority_to_string, TaskPriority
from .error_handling import (
    PRRCError,
    IntegrationError,
    ValidationError,
    TaskOperationError,
    TelemetryError,
    BridgeError,
    AuditError,
    ConfigurationError,
    ErrorSeverity,
    ErrorContext,
    safe_execute,
    format_error_for_display,
    log_error_with_context,
)

__all__ = [
    # Schemas
    "Priority",
    "priority_to_int",
    "priority_to_string",
    "TaskPriority",
    # Error Handling
    "PRRCError",
    "IntegrationError",
    "ValidationError",
    "TaskOperationError",
    "TelemetryError",
    "BridgeError",
    "AuditError",
    "ConfigurationError",
    "ErrorSeverity",
    "ErrorContext",
    "safe_execute",
    "format_error_for_display",
    "log_error_with_context",
]
