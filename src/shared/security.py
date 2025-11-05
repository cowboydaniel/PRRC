"""
Security utilities for PRRC OS Suite

This module provides security enhancements including:
- Rate limiting for API operations
- Path sanitization for file operations
- Input validation helpers
- Security event tracking
"""

import hashlib
import logging
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional


logger = logging.getLogger(__name__)


# ============================================================================
# Rate Limiting
# ============================================================================

@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.

    Attributes:
        max_requests: Maximum number of requests allowed
        time_window: Time window in seconds
        burst_allowance: Additional requests allowed in burst (default: 0)
    """
    max_requests: int
    time_window: float  # seconds
    burst_allowance: int = 0


class RateLimiter:
    """
    Token bucket rate limiter for controlling operation frequency.

    Supports:
    - Per-client rate limiting
    - Configurable burst allowance
    - Multiple rate limit tiers
    - Automatic cleanup of stale entries

    Usage:
        limiter = RateLimiter(RateLimitConfig(max_requests=10, time_window=60))

        if limiter.allow_request("client_id"):
            # Process request
            pass
        else:
            # Rate limit exceeded
            pass
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60.0  # Clean up every 60 seconds

    def allow_request(self, client_id: str) -> bool:
        """
        Check if request should be allowed for client.

        Args:
            client_id: Unique identifier for the client

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()

        # Periodic cleanup of old entries
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(current_time)

        # Get request history for this client
        requests = self._requests[client_id]

        # Remove requests outside the time window
        cutoff_time = current_time - self.config.time_window
        while requests and requests[0] < cutoff_time:
            requests.popleft()

        # Check if within limit (including burst allowance)
        max_allowed = self.config.max_requests + self.config.burst_allowance

        if len(requests) < max_allowed:
            requests.append(current_time)
            return True

        # Rate limit exceeded
        logger.warning(
            f"Rate limit exceeded for client {client_id}: "
            f"{len(requests)} requests in {self.config.time_window}s window"
        )
        return False

    def get_remaining_requests(self, client_id: str) -> int:
        """
        Get number of remaining requests for client.

        Args:
            client_id: Unique identifier for the client

        Returns:
            Number of requests remaining before rate limit
        """
        current_time = time.time()
        requests = self._requests[client_id]

        # Remove requests outside the time window
        cutoff_time = current_time - self.config.time_window
        while requests and requests[0] < cutoff_time:
            requests.popleft()

        max_allowed = self.config.max_requests + self.config.burst_allowance
        return max(0, max_allowed - len(requests))

    def reset_client(self, client_id: str) -> None:
        """
        Reset rate limit for a specific client.

        Args:
            client_id: Unique identifier for the client
        """
        if client_id in self._requests:
            del self._requests[client_id]
            logger.info(f"Rate limit reset for client {client_id}")

    def _cleanup_old_entries(self, current_time: float) -> None:
        """Clean up entries for clients with no recent requests."""
        cutoff_time = current_time - (self.config.time_window * 2)

        clients_to_remove = []
        for client_id, requests in self._requests.items():
            # Remove old requests
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Mark client for removal if no recent requests
            if not requests:
                clients_to_remove.append(client_id)

        # Remove stale clients
        for client_id in clients_to_remove:
            del self._requests[client_id]

        self._last_cleanup = current_time

        if clients_to_remove:
            logger.debug(f"Cleaned up {len(clients_to_remove)} stale rate limit entries")


# ============================================================================
# Path Sanitization
# ============================================================================

class PathSanitizer:
    """
    Sanitize and validate file paths to prevent directory traversal attacks.

    Features:
    - Remove path traversal sequences (../, ..\)
    - Validate against allowed directories
    - Normalize paths
    - Check for suspicious patterns
    """

    # Suspicious patterns that could indicate path traversal
    SUSPICIOUS_PATTERNS = [
        r'\.\.[\\/]',  # Parent directory traversal
        r'[\\/]\.\.',  # Parent directory at end
        r'~[\\/]',     # Home directory reference
        r'\$\{',       # Variable expansion
        r'%[0-9a-fA-F]{2}',  # URL encoding
    ]

    def __init__(self, allowed_base_paths: Optional[list[str]] = None):
        """
        Initialize path sanitizer.

        Args:
            allowed_base_paths: List of allowed base directory paths (optional)
        """
        self.allowed_base_paths = [
            Path(p).resolve() for p in (allowed_base_paths or [])
        ]

    def sanitize(self, file_path: str) -> str:
        """
        Sanitize a file path.

        Args:
            file_path: Path to sanitize

        Returns:
            Sanitized path string

        Raises:
            ValueError: If path contains suspicious patterns
        """
        # Check for suspicious patterns
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, file_path):
                raise ValueError(
                    f"Path contains suspicious pattern: {file_path}"
                )

        # Normalize path (resolve .., ., multiple slashes)
        try:
            normalized = os.path.normpath(file_path)
        except Exception as e:
            raise ValueError(f"Invalid path: {file_path}") from e

        # Remove any remaining .. sequences
        if '..' in normalized:
            raise ValueError(
                f"Path contains parent directory references: {file_path}"
            )

        return normalized

    def validate(self, file_path: str) -> bool:
        """
        Validate that a path is safe and within allowed directories.

        Args:
            file_path: Path to validate

        Returns:
            True if path is valid and safe
        """
        try:
            sanitized = self.sanitize(file_path)

            # If no base paths configured, just check sanitization
            if not self.allowed_base_paths:
                return True

            # Check if path is within allowed base paths
            resolved_path = Path(sanitized).resolve()

            for base_path in self.allowed_base_paths:
                try:
                    resolved_path.relative_to(base_path)
                    return True  # Path is within this base path
                except ValueError:
                    continue  # Not within this base path, try next

            # Path not within any allowed base path
            logger.warning(
                f"Path outside allowed directories: {file_path}"
            )
            return False

        except ValueError as e:
            logger.warning(f"Invalid path: {file_path} - {e}")
            return False

    def safe_join(self, base: str, *paths: str) -> str:
        """
        Safely join path components.

        Args:
            base: Base directory path
            *paths: Path components to join

        Returns:
            Sanitized joined path

        Raises:
            ValueError: If resulting path is invalid
        """
        # Sanitize each component
        sanitized_paths = [self.sanitize(p) for p in paths]

        # Join paths
        joined = os.path.join(base, *sanitized_paths)

        # Validate final path
        if not self.validate(joined):
            raise ValueError(f"Resulting path is not safe: {joined}")

        return joined


# ============================================================================
# Security Event Tracking
# ============================================================================

@dataclass
class SecurityEvent:
    """
    Record of a security-relevant event.

    Attributes:
        event_type: Type of security event
        severity: Severity level (low, medium, high, critical)
        description: Human-readable description
        client_id: Identifier of the client/user involved
        details: Additional event details
        timestamp: When the event occurred
    """
    event_type: str
    severity: str
    description: str
    client_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "client_id": self.client_id,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class SecurityEventTracker:
    """
    Track and log security-relevant events.

    Events include:
    - Rate limit violations
    - Path traversal attempts
    - Validation failures
    - Authentication failures
    - Suspicious patterns
    """

    def __init__(self, audit_callback: Optional[Callable[[SecurityEvent], None]] = None):
        """
        Initialize security event tracker.

        Args:
            audit_callback: Optional callback for audit logging
        """
        self.audit_callback = audit_callback
        self._events: deque = deque(maxlen=1000)  # Keep last 1000 events

    def record_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        client_id: Optional[str] = None,
        **details
    ) -> None:
        """
        Record a security event.

        Args:
            event_type: Type of event (e.g., "rate_limit_exceeded")
            severity: Severity level (low, medium, high, critical)
            description: Human-readable description
            client_id: Identifier of client involved
            **details: Additional event details
        """
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            description=description,
            client_id=client_id,
            details=details
        )

        self._events.append(event)

        # Log based on severity
        log_level = {
            "low": logging.INFO,
            "medium": logging.WARNING,
            "high": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.WARNING)

        logger.log(
            log_level,
            f"Security Event [{event_type}]: {description}",
            extra={"security_event": event.to_dict()}
        )

        # Call audit callback if configured
        if self.audit_callback:
            try:
                self.audit_callback(event)
            except Exception as e:
                logger.error(f"Error in security audit callback: {e}", exc_info=True)

    def get_recent_events(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> list[SecurityEvent]:
        """
        Get recent security events.

        Args:
            limit: Maximum number of events to return
            severity: Filter by severity level (optional)
            event_type: Filter by event type (optional)

        Returns:
            List of recent security events
        """
        events = list(self._events)

        # Apply filters
        if severity:
            events = [e for e in events if e.severity == severity]
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Return most recent first
        events.reverse()
        return events[:limit]


# ============================================================================
# Input Validation Helpers
# ============================================================================

def validate_identifier(identifier: str, max_length: int = 255) -> bool:
    """
    Validate that an identifier is safe (alphanumeric, dash, underscore).

    Args:
        identifier: String to validate
        max_length: Maximum allowed length

    Returns:
        True if valid
    """
    if not identifier or len(identifier) > max_length:
        return False

    # Allow alphanumeric, dash, underscore
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', identifier))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove dangerous characters.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace dangerous characters with underscore
    sanitized = re.sub(r'[^\w\s.-]', '_', filename)

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip().strip('.')

    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed_file"

    return sanitized


def hash_sensitive_data(data: str) -> str:
    """
    Hash sensitive data for logging/storage.

    Args:
        data: Sensitive data to hash

    Returns:
        SHA256 hash of the data
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
