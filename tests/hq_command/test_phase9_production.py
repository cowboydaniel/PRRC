from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from hq_command import (
    BackupManager,
    BuildPipeline,
    ConfigurationManager,
    ConfigurationValidationError,
    HealthCheckResult,
    HealthMonitor,
    HighAvailabilityPlanner,
    MetricsCollector,
    ProductionEnvironmentPlanner,
    ServerRequirement,
    StructuredLogger,
)


def test_environment_planner_summarizes_requirements() -> None:
    planner = ProductionEnvironmentPlanner()
    planner.define(
        "prod",
        servers=(
            ServerRequirement("hq-app-1", cpu_cores=8, memory_gb=32, storage_gb=512),
            ServerRequirement("hq-app-2", cpu_cores=8, memory_gb=32, storage_gb=512),
        ),
        secrets={"DB_URL", "API_TOKEN"},
    )

    summary = planner.requirements("prod")
    assert summary["totals"]["cpu_cores"] == 16
    assert summary["totals"]["memory_gb"] == 64
    assert summary["secrets"] == ["API_TOKEN", "DB_URL"]
    missing = planner.secrets_missing("prod", {"DB_URL"})
    assert missing == frozenset({"API_TOKEN"})


def test_build_pipeline_creates_signed_artifact() -> None:
    pipeline = BuildPipeline(signing_key=b"deploy-secret")
    artifact = pipeline.create(
        version="1.2.3",
        components=("gui", "scheduler"),
        metadata={"commit": "abc123", "build_host": "ci"},
    )

    assert artifact.build_number == 1
    manifest = artifact.manifest()
    assert manifest["metadata"]["commit"] == "abc123"
    assert pipeline.verify(artifact)
    assert pipeline.history()[0] == artifact


def test_configuration_manager_hot_reload_tracks_changes() -> None:
    manager = ConfigurationManager(required_keys={"database_url", "log_level"})
    initial = manager.register(
        "prod",
        base={"database_url": "postgres://prod", "log_level": "INFO"},
        overrides={"feature_flag": False},
        secrets={"API_TOKEN"},
    )
    assert initial.version == 1

    updated = manager.hot_reload(
        "prod",
        {"log_level": "DEBUG", "feature_flag": True},
        update_secrets={"API_TOKEN", "SERVICE_KEY"},
    )
    assert updated.version == 2
    assert updated.values["log_level"] == "DEBUG"
    assert updated.changed_keys == frozenset({"log_level", "feature_flag"})
    assert updated.secrets == frozenset({"API_TOKEN", "SERVICE_KEY"})

    with pytest.raises(ConfigurationValidationError):
        manager.register("staging", base={"log_level": "INFO"})


def test_structured_logger_and_health_monitor() -> None:
    logger = StructuredLogger(default_context={"service": "hq"}, retention_days=7)
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=10)
    logger.log("info", "previous deployment", timestamp=old_timestamp)
    emitted = logger.log("error", "deployment failed", release="2025.11")
    record = json.loads(emitted)
    assert record["service"] == "hq"
    logger.prune(older_than=datetime.now(timezone.utc) - timedelta(days=5))
    exported = logger.export()
    assert len(exported) == 1

    monitor = HealthMonitor()
    monitor.register("database", lambda: (True, "connected"))

    def queue_check() -> HealthCheckResult:
        return HealthCheckResult(
            name="queue",
            status="warn",
            detail="lagging",
            measured_at=datetime.now(timezone.utc),
        )

    monitor.register("queue", queue_check)
    results = monitor.run()
    aggregate = monitor.aggregate(results)
    assert aggregate["status"] == "warn"
    assert any("queue" in detail for detail in aggregate["details"])


def test_metrics_and_backup_manager_report_status() -> None:
    metrics = MetricsCollector()
    metrics.increment("deployments")
    metrics.gauge("uptime", 99.5)
    with metrics.time("build_time"):
        pass
    snapshot = metrics.snapshot()
    assert snapshot["counters"]["deployments"] == 1.0
    assert snapshot["gauges"]["uptime"] == 99.5
    assert snapshot["timers"]["build_time"]["count"] == 1

    backups = BackupManager()
    backups.schedule("hq-db", source="postgres", frequency_hours=6, retention_days=1)
    now = datetime.now(timezone.utc)
    backups.record_execution(
        "hq-db",
        status="success",
        size_bytes=1024,
        checksum="deadbeef",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    backups.schedule("hq-cache", source="redis", frequency_hours=1, retention_days=0)
    report = backups.retention_report(reference_time=now)
    assert report["hq-db"]["status"] == "ok"
    assert report["hq-cache"]["status"] == "missing"


def test_high_availability_planner_provides_failover_sequence() -> None:
    planner = HighAvailabilityPlanner()
    planner.register(
        "hq-gui",
        primary="hq-gui-1",
        replicas=("hq-gui-2", "hq-gui-3"),
        health_endpoint="/healthz",
    )
    plan = planner.plan("hq-gui")
    assert plan.primary == "hq-gui-1"
    sequence = planner.failover_sequence("hq-gui")
    assert sequence[1:] == ("hq-gui-2", "hq-gui-3")
    summary = planner.summary()
    assert summary["hq-gui"]["strategy"] == "automatic"

