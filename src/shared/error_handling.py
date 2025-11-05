"""
Error Handling Standardization for PRRC OS Suite

This module provides consistent error handling patterns, error classes,
and utilities for error propagation and logging across all components.

Key Features:
- Standardized exception hierarchy
- Error context preservation
- Consistent error logging
- User-friendly error messages for GUI display
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


# ============================================================================
# Error Severity Levels
# ============================================================================

class ErrorSeverity(str, Enum):
    """
    Standardized error severity levels.

    Used for categorizing errors and determining appropriate handling.
    """
    DEBUG = "debug"          # Debug information, not user-facing
    INFO = "info"            # Informational, no action needed
    WARNING = "warning"      # Warning, may need attention
    ERROR = "error"          # Error, operation failed but recoverable
    CRITICAL = "critical"    # Critical error, system stability at risk
    FATAL = "fatal"          # Fatal error, system cannot continue


# ============================================================================
# Base Exception Classes
# ============================================================================

class PRRCError(Exception):
    """
    Base exception class for all PRRC OS Suite errors.

    Provides consistent error handling with severity, context, and
    user-friendly messages.
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize PRRC error.

        Args:
            message: Technical error message for logging
            severity: Error severity level
            user_message: User-friendly message for GUI display (optional)
            context: Additional context information (optional)
            cause: Original exception that caused this error (optional)
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.user_message = user_message or self._generate_user_message()
        self.context = context or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()

    def _generate_user_message(self) -> str:
        """Generate a user-friendly message from the technical message."""
        # By default, use the technical message
        # Subclasses can override for more specific messages
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "user_message": self.user_message,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None,
        }

    def log(self, logger_instance: Optional[logging.Logger] = None) -> None:
        """
        Log this error with appropriate severity.

        Args:
            logger_instance: Logger to use (defaults to module logger)
        """
        log = logger_instance or logger

        # Map severity to logging level
        level_map = {
            ErrorSeverity.DEBUG: logging.DEBUG,
            ErrorSeverity.INFO: logging.INFO,
            ErrorSeverity.WARNING: logging.WARNING,
            ErrorSeverity.ERROR: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.FATAL: logging.CRITICAL,
        }

        level = level_map.get(self.severity, logging.ERROR)

        # Log with context
        log.log(
            level,
            f"{self.__class__.__name__}: {self.message}",
            extra={"error_context": self.context},
            exc_info=self.cause
        )


# ============================================================================
# Specific Exception Classes
# ============================================================================

class IntegrationError(PRRCError):
    """Errors related to HQ-FieldOps integration layer."""

    def _generate_user_message(self) -> str:
        return "Communication error occurred. Please check your connection and try again."


class ValidationError(PRRCError):
    """Errors related to data validation."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        invalid_value: Any = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        if field_name:
            context["field_name"] = field_name
        if invalid_value is not None:
            context["invalid_value"] = str(invalid_value)

        # Store field_name temporarily for user message generation
        self._field_name = field_name

        super().__init__(message, context=context, **kwargs)

    def _generate_user_message(self) -> str:
        # Use stored field_name or get from context if available
        field = getattr(self, '_field_name', None) or (
            self.context.get("field_name", "field") if hasattr(self, 'context') else "field"
        )
        return f"Invalid value for {field}. {self.message}"


class TaskOperationError(PRRCError):
    """Errors related to task operations (assignment, updates, etc.)."""

    def __init__(
        self,
        message: str,
        task_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.pop("context", {})
        if task_id:
            context["task_id"] = task_id
        if operation:
            context["operation"] = operation

        # Store operation temporarily for user message generation
        self._operation = operation

        super().__init__(message, context=context, **kwargs)

    def _generate_user_message(self) -> str:
        # Use stored operation or get from context if available
        operation = getattr(self, '_operation', None) or (
            self.context.get("operation", "operation") if hasattr(self, 'context') else "operation"
        )
        return f"Task {operation} failed. {self.message}"


class TelemetryError(PRRCError):
    """Errors related to telemetry collection and reporting."""

    def _generate_user_message(self) -> str:
        return "Telemetry system error. Data collection may be incomplete."


class BridgeError(PRRCError):
    """Errors related to Bridge communication."""

    def _generate_user_message(self) -> str:
        return "Communication bridge error. Some features may be unavailable."


class AuditError(PRRCError):
    """Errors related to audit logging."""

    def __init__(self, message: str, **kwargs):
        # Audit errors are always critical
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)
        super().__init__(message, **kwargs)

    def _generate_user_message(self) -> str:
        return "Audit system error. Please contact system administrator."


class ConfigurationError(PRRCError):
    """Errors related to system configuration."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault("severity", ErrorSeverity.CRITICAL)
        super().__init__(message, **kwargs)

    def _generate_user_message(self) -> str:
        return "Configuration error. Please check system settings."


# ============================================================================
# Error Context Manager
# ============================================================================

@dataclass
class ErrorContext:
    """
    Context manager for tracking errors within a specific operation.

    Usage:
        with ErrorContext("sync_operations") as ctx:
            # Perform operation
            risky_operation()

        if ctx.has_errors():
            logger.error(f"Operation failed with {ctx.error_count} errors")
    """

    operation: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, optionally handling exception."""
        if exc_val:
            # Add exception to errors
            if isinstance(exc_val, PRRCError):
                self.add_error(exc_val)
            else:
                self.add_error(
                    PRRCError(
                        str(exc_val),
                        cause=exc_val,
                        context={"operation": self.operation}
                    )
                )

        # Don't suppress the exception
        return False

    def add_error(self, error: PRRCError) -> None:
        """Add an error to this context."""
        self.errors.append(error)
        error.log()

    def add_warning(self, warning: PRRCError) -> None:
        """Add a warning to this context."""
        self.warnings.append(warning)
        warning.log()

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings occurred."""
        return len(self.warnings) > 0

    @property
    def error_count(self) -> int:
        """Get number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get number of warnings."""
        return len(self.warnings)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all errors and warnings."""
        return {
            "operation": self.operation,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# ============================================================================
# Error Handling Utilities
# ============================================================================

def safe_execute(
    func: callable,
    *args,
    error_class: type[PRRCError] = PRRCError,
    default_return: Any = None,
    log_errors: bool = True,
    **kwargs
) -> tuple[Any, Optional[PRRCError]]:
    """
    Safely execute a function, catching and logging errors.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        error_class: Exception class to use for wrapping errors
        default_return: Value to return if function fails
        log_errors: Whether to log errors
        **kwargs: Keyword arguments for func

    Returns:
        Tuple of (result, error). If successful, error is None.
        If failed, result is default_return and error is the exception.

    Example:
        result, error = safe_execute(risky_function, arg1, arg2)
        if error:
            display_error(error.user_message)
        else:
            process_result(result)
    """
    try:
        result = func(*args, **kwargs)
        return result, None
    except PRRCError as e:
        if log_errors:
            e.log()
        return default_return, e
    except Exception as e:
        wrapped_error = error_class(
            str(e),
            cause=e,
            context={
                "function": func.__name__,
                "traceback": traceback.format_exc()
            }
        )
        if log_errors:
            wrapped_error.log()
        return default_return, wrapped_error


def format_error_for_display(error: Exception) -> str:
    """
    Format an error for user-friendly display.

    Args:
        error: Exception to format

    Returns:
        User-friendly error message
    """
    if isinstance(error, PRRCError):
        return error.user_message
    else:
        return f"An unexpected error occurred: {str(error)}"


def log_error_with_context(
    logger_instance: logging.Logger,
    message: str,
    error: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR
) -> None:
    """
    Log an error with full context information.

    Args:
        logger_instance: Logger to use
        message: Error message
        error: Optional exception
        context: Additional context
        severity: Error severity
    """
    # Map severity to logging level
    level_map = {
        ErrorSeverity.DEBUG: logging.DEBUG,
        ErrorSeverity.INFO: logging.INFO,
        ErrorSeverity.WARNING: logging.WARNING,
        ErrorSeverity.ERROR: logging.ERROR,
        ErrorSeverity.CRITICAL: logging.CRITICAL,
        ErrorSeverity.FATAL: logging.CRITICAL,
    }

    level = level_map.get(severity, logging.ERROR)

    # Log with context
    logger_instance.log(
        level,
        message,
        extra={"error_context": context or {}},
        exc_info=error
    )
