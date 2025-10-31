# PRRC OS Suite

## Overview
The PRRC OS Suite is a modular, mission-focused operating environment designed to help Paramilitary Response and Rescue Corps (PRRC) teams coordinate field operations, central command decision-making, and cross-agency bridge communications. The suite delivers integrated situational awareness, secure data synchronization, and offline-first workflows tailored for crisis response scenarios.

## Module Breakdown
### FieldOps
* **Purpose:** Mobile-first toolkit for responders in the field.
* **Key Capabilities:**
  * Incident logging with geospatial tagging and offline queueing.
  * Resource request workflows synchronized with HQ Command.
  * Local cache encryption for sensitive case data.
  * Mesh-compatible data sync for austere environments.

### HQ Command
* **Purpose:** Central planning and analysis console for command staff.
* **Key Capabilities:**
  * Live operational dashboard aggregating FieldOps telemetry.
  * Tasking engine that pushes assignments to FieldOps units.
  * Analytics layer for staffing, logistics, and situational forecasting.
  * Interoperability APIs to ingest civil agency data feeds.

### Bridge
* **Purpose:** Interagency integration service that brokers secure data exchange.
* **Key Capabilities:**
  * Protocol translation for municipal, state, and NGO systems.
  * Role-based data redaction before distribution.
  * Audit logging and immutable event trails.
  * Automated compliance reporting for post-incident review.

## Installation Prerequisites
### Debian-based Systems (Debian, Ubuntu, Pop!_OS)
1. Ensure the system is up to date:
   ```bash
   sudo apt update && sudo apt upgrade
   ```
2. Install core dependencies:
   ```bash
   sudo apt install git build-essential python3 python3-venv python3-pip postgresql redis-server
   ```
3. (Optional) Install container runtime for deployment:
   ```bash
   sudo apt install podman
   ```

### Arch-based Systems (Arch, Manjaro, EndeavourOS)
1. Synchronize package databases and upgrade:
   ```bash
   sudo pacman -Syu
   ```
2. Install core dependencies:
   ```bash
   sudo pacman -S git base-devel python python-virtualenv python-pip postgresql redis podman
   ```
3. Enable and initialize PostgreSQL before first launch:
   ```bash
   sudo systemctl enable --now postgresql
   sudo -u postgres initdb -D /var/lib/postgres/data
   ```

## Initial Setup & Usage Workflow
1. **Clone the repository and bootstrap the environment:**
   ```bash
   git clone https://example.org/prrc/prrc-os-suite.git
   cd prrc-os-suite
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure environment secrets:**
   * Copy `config/example.env` to `.env` and set database credentials, API keys, and encryption secrets.
3. **Provision databases and services:**
   ```bash
   createdb prrc_os
   redis-cli ping
   ```
4. **Run migrations and seed baseline data:**
   ```bash
   ./manage.py migrate
   ./manage.py loaddata baseline
   ```
5. **Launch modular services:**
   * FieldOps: `./services/fieldops/start.sh`
   * HQ Command: `./services/hq/start.sh`
   * Bridge: `./services/bridge/start.sh`
6. **Access operational interfaces:**
   * FieldOps mobile progressive web app at `https://fieldops.local`
   * HQ Command dashboard at `https://hq.local`
   * Bridge API gateway at `https://bridge.local`

## Security Architecture
* **Zero-Trust Posture:** Every service authenticates via mutual TLS and short-lived OAuth2 tokens issued by the Bridge authority.
* **Role-Based Access Control:** Permissions derive from PRRC duty positions; least-privilege principles gate access to datasets and actions.
* **Data Protection:**
  * AES-256 encryption for data at rest, using hardware-backed key storage where available.
  * FieldOps devices leverage file-level encryption with remote wipe triggers.
* **Auditability:** Immutable event store in Bridge ensures every cross-agency transaction is logged and tamper-evident.
* **Compliance:** Security controls mapped to NIST SP 800-53 moderate baseline with documented deviations.

## Offline Operation Guidelines
* **Local Caching:** FieldOps maintains encrypted local caches for tasks, maps, and contact rosters. Sync conflicts are resolved via last-writer-wins policy with operator prompts.
* **Peer-to-Peer Sync:** In absence of HQ connectivity, FieldOps nodes form a mesh using Wi-Fi Direct or LoRa gateways; Bridge queues remote messages until uplink restores.
* **Deferred Command Updates:** HQ Command dashboards present cached metrics and highlight stale data. Commanders can draft orders offline; Bridge releases them when connectivity resumes.
* **Operational Checklists:** Teams should follow the `docs/offline-playbook.md` (coming soon) for pre-deployment synchronization, manual key rotation, and cache verification.

## Future Roadmap
* **Scenario Simulation Engine:** Build red/blue team training scenarios within HQ Command to stress-test response plans.
* **Edge AI Insights:** Deploy on-device models in FieldOps to flag emerging hazards (radiation, chemical exposure) without relying on cloud inference.
* **Satellite Relay Integration:** Extend Bridge to interface with low-earth-orbit providers for resilient backhaul.
* **Incident Knowledge Graph:** Develop cross-incident intelligence overlays for after-action review and lessons learned.

## Contribution Guidelines
1. Fork the repository and create topic branches (`feature/`, `fix/`, `docs/`).
2. Adhere to the code style enforced by `pre-commit` hooks and project linters.
3. Write tests for new features or bug fixes and ensure `make test` passes locally.
4. Submit pull requests with:
   * Clear summary and linked issue references.
   * Security considerations for data handling changes.
   * Screenshots for UI-affecting modifications.
5. Participate in peer review with constructive feedback and ensure at least one maintainer approves before merge.

## License
Unless otherwise noted, the PRRC OS Suite is distributed under the MIT License. See `LICENSE` for full terms. Government or agency deployments should consult legal counsel for compliance with jurisdictional requirements.
