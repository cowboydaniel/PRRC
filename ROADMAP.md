# Roadmap Checklist

## Overview
- [ ] Replace FieldOps mission loader stubs so mission ingestion, validation, and unpacking workflows provide real data.
- [ ] Implement telemetry collectors that surface actual sensor information for downstream analytics.
- [ ] Build HQ Command analytics and tasking layers to aggregate telemetry and schedule units with actionable intelligence.
- [ ] Deliver Bridge routing and compliance modules that enable secure interagency exchange with audit trails.
- [ ] Expand the CLI so it reflects fully implemented services rather than stubbed data.

## Phase 1 – FieldOps Mission Package Foundation
- [x] Verify mission package files exist, validate checksums/signatures, and support archive formats (ZIP, TAR) before extracting to a staging directory in `src/fieldops/mission_loader.py`.
- [x] Parse a mission manifest (YAML/JSON), normalize the metadata into typed structures, and surface validation errors.
- [x] Persist unpacked payloads to a configurable cache directory with tests covering valid, tampered, and unsupported packages.
- [x] Update docs or sample artifacts to document the accepted package schema and validation pipeline.

## Phase 2 – FieldOps Telemetry Snapshot & HQ Analytics
- [x] Expand `collect_telemetry_snapshot` in `src/fieldops/telemetry.py` to query sensor APIs, cached events, and queue depths while normalizing timestamps and units.
- [x] Define typed schemas (dataclasses or TypedDict) representing telemetry snapshots for downstream consumers.
- [x] Implement analytics in `src/hq_command/analytics.py` that compute readiness indicators, trend deltas, and alert thresholds.
- [x] Add unit tests with telemetry datasets, including edge cases, and integrate the status path in `src/prrc_cli.py`.

## Phase 3 – FieldOps GUI Foundation
- [x] Deliver an offline-first FieldOps GUI optimized for Dell Rugged hardware with clear sync status, conflict resolution prompts, mesh networking awareness, and visual styling that follows `docs/fieldops_gui_style.md`.
- [x] Implement mission intake and briefing flows that surface package metadata once `load_mission_package` verifies archives, with quick links to SOPs, maps, and communications.
- [x] Build operational logging forms supporting GPS tagging, photo attachments, offline queueing, and status banners displaying sync and backlog counts.
- [ ] Introduce resource request and task dashboards that allow accepting, deferring, and escalating assignments while offline with merges on reconnection.
- [ ] Surface telemetry snapshots from `collect_telemetry_snapshot` through card-based metrics that degrade gracefully when collectors are stubbed.
- [ ] Provide settings and hardware tools for calibration workflows (`plan_touchscreen_calibration`) and serial diagnostics (`enumerate_serial_interfaces`).
- [ ] Establish responsive, touch-friendly layouts with design tokens for high-contrast themes, large touch targets, and glove-friendly gestures.
- [ ] Sequence integration through data contracts and mocks, offline cache and sync, hardware-aware polish, and HQ interoperability milestones.

## Phase 4 – HQ Tasking Engine Rollout
- [ ] Introduce task and responder models in `src/hq_command/tasking_engine.py` describing constraints, priority, and capability requirements.
- [ ] Implement scoring and matching logic that allocates tasks to available units, handling conflicts, partial fulfillment, and escalation.
- [ ] Emit structured results with assignments, deferred tasks, and audit metadata exposed via an API/service layer for FieldOps synchronization.
- [ ] Create tests that simulate mixed-priority queues and responder availability scenarios to verify deterministic scheduling and error handling.

## Phase 5 – Bridge Communications & Compliance
- [ ] Implement protocol adapters in `src/bridge/comms_router.py` (REST, MQ, secure file drop) with configurable endpoints, mutual TLS, and payload signing.
- [ ] Integrate retry logic, dead-letter queues, and partner-specific transformations while storing routing outcomes for analytics.
- [ ] Build an audit persistence layer in `src/bridge/compliance.py` targeting tamper-evident storage with jurisdiction retention policies.
- [ ] Add automated tests simulating successful routes, partner failures, and compliance audits to confirm routing metadata and audit records.

## Phase 6 – CLI, Integration, and Testing Hardening
- [ ] Update `src/prrc_cli.py` to present enriched mission, telemetry, and bridge data with structured output options and robust error handling.
- [ ] Introduce integration tests exercising end-to-end workflows (`load-mission`, `status`, `bridge-send`) using temporary directories and mocked services.
- [ ] Wire the CLI into packaging/entry-point configuration (e.g., `pyproject.toml`) and document usage examples reflecting implemented functionality.
- [ ] Configure continuous integration to run unit and integration tests on each push, capturing artifacts or logs for debugging.
