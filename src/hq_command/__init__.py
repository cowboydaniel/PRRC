"""HQ Command package initialization.

Exposes placeholder orchestration utilities for future tasking and analytics
workflows.
"""

from .analytics import summarize_field_telemetry
from .tasking_engine import ResponderStatus, TaskingOrder, schedule_tasks_for_field_units
from .sync import (
    HQSyncClient,
    MemoryTransport,
    OutboundChange,
    SyncEvent,
)
from .production import (
    BackupManager,
    BuildArtifact,
    BuildPipeline,
    ConfigSnapshot,
    ConfigurationManager,
    ConfigurationValidationError,
    FailoverPlan,
    HealthCheckResult,
    HealthMonitor,
    HighAvailabilityPlanner,
    MetricsCollector,
    ProductionEnvironmentPlanner,
    ServerRequirement,
    StructuredLogger,
)

__all__ = [
    "schedule_tasks_for_field_units",
    "summarize_field_telemetry",
    "TaskingOrder",
    "ResponderStatus",
    "HQSyncClient",
    "MemoryTransport",
    "OutboundChange",
    "SyncEvent",
    "ProductionEnvironmentPlanner",
    "ServerRequirement",
    "BuildPipeline",
    "BuildArtifact",
    "ConfigurationManager",
    "ConfigSnapshot",
    "ConfigurationValidationError",
    "StructuredLogger",
    "HealthMonitor",
    "HealthCheckResult",
    "MetricsCollector",
    "BackupManager",
    "FailoverPlan",
    "HighAvailabilityPlanner",
]
