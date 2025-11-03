"""Production readiness utilities for the HQ Command service (Phase 9)."""

from __future__ import annotations

import hmac
import json
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Sequence


# ---------------------------------------------------------------------------
# Environment planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerRequirement:
    """Describes compute requirements for a single deployment target."""

    identifier: str
    cpu_cores: int
    memory_gb: int
    storage_gb: int

    def as_dict(self) -> Dict[str, int | str]:
        return {
            "id": self.identifier,
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "storage_gb": self.storage_gb,
        }


class ProductionEnvironmentPlanner:
    """Track production environments and their required resources."""

    def __init__(self) -> None:
        self._definitions: Dict[str, Dict[str, Any]] = {}

    def define(
        self,
        name: str,
        *,
        servers: Sequence[ServerRequirement],
        secrets: Iterable[str],
    ) -> None:
        if not name:
            raise ValueError("Environment name cannot be empty")
        if not servers:
            raise ValueError("At least one server specification is required")

        self._definitions[name] = {
            "servers": tuple(servers),
            "secrets": frozenset(secrets),
        }

    def requirements(self, environment: str) -> Dict[str, Any]:
        definition = self._definitions[environment]
        servers: Sequence[ServerRequirement] = definition["servers"]
        totals = {
            "servers": len(servers),
            "cpu_cores": sum(server.cpu_cores for server in servers),
            "memory_gb": sum(server.memory_gb for server in servers),
            "storage_gb": sum(server.storage_gb for server in servers),
        }
        return {
            "environment": environment,
            "totals": totals,
            "servers": [server.as_dict() for server in servers],
            "secrets": sorted(definition["secrets"]),
        }

    def secrets_missing(
        self, environment: str, provided: Iterable[str] | Mapping[str, Any]
    ) -> frozenset[str]:
        definition = self._definitions[environment]
        if isinstance(provided, Mapping):
            provided_set = set(provided.keys())
        elif isinstance(provided, str):
            provided_set = {provided}
        else:
            provided_set = set(provided)
        return frozenset(definition["secrets"] - provided_set)

    def environments(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))


# ---------------------------------------------------------------------------
# Build and packaging
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildArtifact:
    """Represents a signed build manifest ready for distribution."""

    version: str
    build_number: int
    checksum: str
    signature: str
    components: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def manifest(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "build_number": self.build_number,
            "components": list(self.components),
            "metadata": dict(self.metadata),
            "checksum": self.checksum,
            "signature": self.signature,
        }


class BuildPipeline:
    """Create signed build artifacts with deterministic manifests."""

    def __init__(self, signing_key: bytes) -> None:
        if not signing_key:
            raise ValueError("signing_key must be provided")
        self._signing_key = signing_key
        self._artifacts: list[BuildArtifact] = []

    def create(
        self,
        *,
        version: str,
        components: Sequence[str],
        metadata: Mapping[str, Any],
    ) -> BuildArtifact:
        manifest_payload = {
            "version": version,
            "build_number": len(self._artifacts) + 1,
            "components": list(components),
            "metadata": dict(metadata),
        }
        serialized = json.dumps(manifest_payload, sort_keys=True).encode()
        checksum = sha256(serialized).hexdigest()
        signature = hmac.new(self._signing_key, serialized, sha256).hexdigest()
        artifact = BuildArtifact(
            version=version,
            build_number=manifest_payload["build_number"],
            checksum=checksum,
            signature=signature,
            components=tuple(components),
            metadata=dict(metadata),
        )
        self._artifacts.append(artifact)
        return artifact

    def verify(self, artifact: BuildArtifact) -> bool:
        manifest_payload = {
            "version": artifact.version,
            "build_number": artifact.build_number,
            "components": list(artifact.components),
            "metadata": dict(artifact.metadata),
        }
        serialized = json.dumps(manifest_payload, sort_keys=True).encode()
        expected_checksum = sha256(serialized).hexdigest()
        if expected_checksum != artifact.checksum:
            return False
        expected_signature = hmac.new(self._signing_key, serialized, sha256).hexdigest()
        return expected_signature == artifact.signature

    def history(self) -> tuple[BuildArtifact, ...]:
        return tuple(self._artifacts)


# ---------------------------------------------------------------------------
# Configuration management
# ---------------------------------------------------------------------------


class ConfigurationValidationError(ValueError):
    """Raised when configuration payloads fail validation checks."""


@dataclass(frozen=True)
class ConfigSnapshot:
    """Immutable view of an environment configuration state."""

    environment: str
    values: Mapping[str, Any]
    version: int
    secrets: frozenset[str]
    changed_keys: frozenset[str]
    updated_at: datetime


class ConfigurationManager:
    """Manage environment specific configuration payloads with validation."""

    def __init__(self, required_keys: Iterable[str]) -> None:
        self._required = frozenset(required_keys)
        self._profiles: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        environment: str,
        *,
        base: Mapping[str, Any],
        overrides: Mapping[str, Any] | None = None,
        secrets: Iterable[str] | None = None,
    ) -> ConfigSnapshot:
        if environment in self._profiles:
            raise ValueError(f"Configuration for '{environment}' already registered")
        state = {
            "base": dict(base),
            "overrides": dict(overrides or {}),
            "secrets": frozenset(secrets or ()),
            "version": 1,
        }
        snapshot = self._build_snapshot(environment, state, changed_keys=set(state["base"]) | set(state["overrides"]))
        self._profiles[environment] = state
        return snapshot

    def get(self, environment: str) -> ConfigSnapshot:
        state = self._profiles[environment]
        return self._build_snapshot(environment, state, changed_keys=set())

    def hot_reload(
        self,
        environment: str,
        updates: Mapping[str, Any],
        *,
        update_secrets: Iterable[str] | None = None,
    ) -> ConfigSnapshot:
        state = self._profiles[environment]
        old_effective = self._effective_config(state)
        state["overrides"].update(dict(updates))
        if update_secrets is not None:
            state["secrets"] = frozenset(update_secrets)
        state["version"] += 1
        new_effective = self._effective_config(state)
        changed_keys = {
            key
            for key, value in new_effective.items()
            if old_effective.get(key) != value
        }
        return self._build_snapshot(environment, state, changed_keys=changed_keys)

    def _effective_config(self, state: MutableMapping[str, Any]) -> Dict[str, Any]:
        merged = dict(state["base"])
        merged.update(state["overrides"])
        missing = self._required - merged.keys()
        if missing:
            raise ConfigurationValidationError(
                f"Configuration missing required keys: {', '.join(sorted(missing))}"
            )
        return merged

    def _build_snapshot(
        self,
        environment: str,
        state: Mapping[str, Any],
        *,
        changed_keys: Iterable[str],
    ) -> ConfigSnapshot:
        effective = self._effective_config(state)
        return ConfigSnapshot(
            environment=environment,
            values=effective,
            version=state["version"],
            secrets=frozenset(state["secrets"]),
            changed_keys=frozenset(changed_keys),
            updated_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Logging, monitoring, and observability
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealthCheckResult:
    """Result for a registered health check."""

    name: str
    status: str
    detail: str | None
    measured_at: datetime


class StructuredLogger:
    """Emit structured JSON logs with retention-aware storage."""

    def __init__(self, *, default_context: Mapping[str, Any] | None = None, retention_days: int = 30) -> None:
        self._default_context = dict(default_context or {})
        self._retention = retention_days
        self._records: list[Dict[str, Any]] = []

    def log(
        self,
        level: str,
        message: str,
        *,
        timestamp: datetime | None = None,
        **context: Any,
    ) -> str:
        record: Dict[str, Any] = {
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "level": level.upper(),
            "message": message,
        }
        record.update(self._default_context)
        record.update(context)
        self._records.append(record)
        return json.dumps(record, sort_keys=True)

    def export(self) -> tuple[Dict[str, Any], ...]:
        return tuple(self._records)

    def prune(self, *, older_than: datetime) -> None:
        self._records = [
            record for record in self._records if datetime.fromisoformat(record["timestamp"]) >= older_than
        ]

    @property
    def retention_days(self) -> int:
        return self._retention


class HealthMonitor:
    """Track health checks and provide aggregate service status."""

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[[], HealthCheckResult | tuple[bool, str | None]]] = {}

    def register(
        self,
        name: str,
        check: Callable[[], HealthCheckResult | tuple[bool, str | None]],
    ) -> None:
        if name in self._checks:
            raise ValueError(f"Health check '{name}' already registered")
        self._checks[name] = check

    def run(self) -> tuple[HealthCheckResult, ...]:
        results: list[HealthCheckResult] = []
        for name, check in self._checks.items():
            outcome = check()
            if isinstance(outcome, HealthCheckResult):
                if outcome.name != name:
                    outcome = HealthCheckResult(
                        name=name,
                        status=outcome.status,
                        detail=outcome.detail,
                        measured_at=outcome.measured_at,
                    )
                results.append(outcome)
            else:
                ok, detail = outcome
                results.append(
                    HealthCheckResult(
                        name=name,
                        status="pass" if ok else "fail",
                        detail=detail,
                        measured_at=datetime.now(timezone.utc),
                    )
                )
        return tuple(results)

    def aggregate(self, results: Sequence[HealthCheckResult]) -> Dict[str, Any]:
        status = "pass"
        details: list[str] = []
        for result in results:
            if result.status.lower() == "fail":
                status = "fail"
            elif result.status.lower() == "warn" and status == "pass":
                status = "warn"
            if result.detail:
                details.append(f"{result.name}: {result.detail}")
        return {"status": status, "details": details}


class MetricsCollector:
    """Collect counters, gauges, and timer metrics for observability."""

    def __init__(self) -> None:
        self._counters: defaultdict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._timers: defaultdict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, amount: float = 1.0) -> None:
        self._counters[name] += amount

    def gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    @contextmanager
    def time(self, name: str) -> None:
        start = perf_counter()
        try:
            yield
        finally:
            duration = perf_counter() - start
            self._timers[name].append(duration)

    def snapshot(self) -> Dict[str, Any]:
        timers = {
            name: {
                "count": len(samples),
                "avg": sum(samples) / len(samples) if samples else 0.0,
                "max": max(samples) if samples else 0.0,
            }
            for name, samples in self._timers.items()
        }
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timers": timers,
        }


# ---------------------------------------------------------------------------
# Backup and availability planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupJob:
    job_id: str
    source: str
    frequency_hours: int
    retention_days: int


@dataclass(frozen=True)
class BackupExecution:
    job_id: str
    status: str
    size_bytes: int
    checksum: str
    started_at: datetime
    completed_at: datetime


class BackupManager:
    """Track backup schedules and verify retention compliance."""

    def __init__(self) -> None:
        self._jobs: Dict[str, BackupJob] = {}
        self._history: list[BackupExecution] = []

    def schedule(
        self,
        job_id: str,
        *,
        source: str,
        frequency_hours: int,
        retention_days: int,
    ) -> BackupJob:
        job = BackupJob(job_id, source, frequency_hours, retention_days)
        self._jobs[job_id] = job
        return job

    def record_execution(
        self,
        job_id: str,
        *,
        status: str,
        size_bytes: int,
        checksum: str,
        started_at: datetime,
        completed_at: datetime,
    ) -> BackupExecution:
        if job_id not in self._jobs:
            raise KeyError(f"Backup job '{job_id}' is not scheduled")
        execution = BackupExecution(job_id, status, size_bytes, checksum, started_at, completed_at)
        self._history.append(execution)
        return execution

    def retention_report(self, *, reference_time: datetime | None = None) -> Dict[str, Dict[str, Any]]:
        now = reference_time or datetime.now(timezone.utc)
        report: Dict[str, Dict[str, Any]] = {}
        for job_id, job in self._jobs.items():
            executions = [entry for entry in self._history if entry.job_id == job_id]
            if not executions:
                report[job_id] = {
                    "status": "missing",
                    "last_backup": None,
                    "next_due": now + timedelta(hours=job.frequency_hours),
                }
                continue
            last = max(executions, key=lambda execution: execution.completed_at)
            age = now - last.completed_at
            stale_threshold = timedelta(days=job.retention_days)
            if last.status.lower() != "success":
                status = "failed"
            elif age > stale_threshold:
                status = "stale"
            else:
                status = "ok"
            report[job_id] = {
                "status": status,
                "last_backup": last.completed_at,
                "next_due": last.completed_at + timedelta(hours=job.frequency_hours),
                "age": age,
            }
        return report


@dataclass(frozen=True)
class FailoverPlan:
    service: str
    primary: str
    replicas: tuple[str, ...]
    health_endpoint: str
    strategy: str


class HighAvailabilityPlanner:
    """Maintain failover plans for HQ Command services."""

    def __init__(self) -> None:
        self._plans: Dict[str, FailoverPlan] = {}

    def register(
        self,
        service: str,
        *,
        primary: str,
        replicas: Sequence[str],
        health_endpoint: str,
        strategy: str = "automatic",
    ) -> FailoverPlan:
        plan = FailoverPlan(
            service=service,
            primary=primary,
            replicas=tuple(replicas),
            health_endpoint=health_endpoint,
            strategy=strategy,
        )
        self._plans[service] = plan
        return plan

    def plan(self, service: str) -> FailoverPlan:
        return self._plans[service]

    def failover_sequence(self, service: str) -> tuple[str, ...]:
        plan = self._plans[service]
        return (plan.primary, *plan.replicas)

    def summary(self) -> Dict[str, Dict[str, Any]]:
        return {
            service: {
                "primary": plan.primary,
                "replicas": list(plan.replicas),
                "health_endpoint": plan.health_endpoint,
                "strategy": plan.strategy,
            }
            for service, plan in self._plans.items()
        }

