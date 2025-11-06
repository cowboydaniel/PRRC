# PRRC OS Suite

## Overview
The PRRC OS Suite is a Python desktop application for coordinating crisis response operations. It provides tools for field responders to manage tasks, log operations, and communicate with command centers, with full offline capability and automatic synchronization.

## What It Actually Does

This is a **PySide6 (Qt6) desktop application** with three main components:

### FieldOps (Desktop GUI)
A desktop application for field responders that provides:
- **Mission Management** - Load mission packages from ZIP/TAR archives
- **Operational Logging** - Submit incident logs with GPS coordinates
- **Task Dashboard** - View and manage assigned tasks (Pending/Accepted/Completed)
- **Resource Requests** - Request supplies and equipment
- **Telemetry Monitoring** - Track sensor data and system status
- **Offline Queue** - All operations work offline and sync when connectivity returns

**Launch the GUI:**
```bash
python -m fieldops.main
```

### HQ Command (Task Scheduling)
Task scheduling and analytics engine that:
- Assigns tasks to field units based on capabilities, location, and availability
- Uses intelligent scoring algorithm to match responders to tasks
- Aggregates telemetry from field units
- Generates compliance reports

**Run via CLI:**
```bash
prrc send-tasks tasks.json responders.json
```

### Bridge (Message Router)
Inter-module communication and compliance auditing:
- Routes messages between HQ and FieldOps
- Supports multiple protocols (REST, Message Queue, File Drop, Local)
- Creates tamper-evident audit logs for compliance
- Handles message signing and encryption

**Test via CLI:**
```bash
prrc integration-demo
```

## Installation

### Prerequisites
Install Python 3.9 or higher on your Linux system.

### Install Dependencies
```bash
git clone <repository-url>
cd PRRC
pip install -r requirements.txt --break-system-packages
```

That's it. No databases, no services to configure, no containers needed.

## Usage

### Run the FieldOps GUI
```bash
python -m fieldops.main
```

On first run, you'll be prompted to configure:
- Device ID
- Team assignment
- Operator capabilities

### CLI Commands
The `prrc` command provides several utilities:

```bash
# Load a mission package
prrc load-mission path/to/mission.zip

# Check system status
prrc status

# Send tasks to field units
prrc send-tasks tasks.json responders.json

# Send telemetry reports
prrc send-telemetry telemetry.json

# Test Bridge routing
prrc bridge-send message.json partner-id

# Run integration demo
prrc integration-demo

# Calibrate touchscreen (for rugged hardware)
prrc calibrate-touchscreen
```

### Mission Package Format
Mission packages are ZIP or TAR archives containing:
- `manifest.json` - Mission metadata
- `briefing.txt` - Operation briefing
- `contacts.json` - Team roster
- Supporting documents

Example manifest.json:
```json
{
  "mission_id": "RESP-2024-001",
  "name": "Emergency Response",
  "briefing_file": "briefing.txt",
  "contacts_file": "contacts.json"
}
```

## How It Works

### Offline-First Architecture
The application is designed to work completely offline:

1. **Local Storage** - All data stored in `~/.prrc/` as JSON files
2. **Offline Queue** - Operations queue locally when network is unavailable
3. **Automatic Sync** - Every 15 seconds, attempts to sync with HQ
4. **Conflict Resolution** - Last-writer-wins with operator prompts

### Message Flow
```
FieldOps GUI
    ↓
Controller (state management)
    ↓
Offline Queue (JSON storage)
    ↓
Integration Layer
    ↓
Bridge Router → Audit Log
    ↓
Message Bus
    ↓
HQ Command
```

### Data Storage
All data is stored in `~/.prrc/`:
- `missions/` - Extracted mission packages
- `logs/` - Operational logs
- `queue/` - Offline operations queue
- `config.json` - Application configuration

## Hardware Support

While the application runs on any Linux system, it includes optional hardware integration for:
- Dell Rugged Extreme tablets (Latitude 7230/7330)
- Touchscreen calibration
- GPS/GNSS sensors
- Serial device interfaces (barcode scanners, RFID readers)

Hardware features are detected automatically and gracefully degrade if not present.

## Actual Technical Stack

- **Python 3.9+** - Core language
- **PySide6 6.6+** - Qt6 GUI framework
- **PyYAML** - Configuration files
- **JSON** - Data storage (no database required)
- **Dataclasses** - Type-safe message protocols

No PostgreSQL, Redis, web servers, or container orchestration required.

## Development

### Project Structure
```
src/
├── fieldops/          # Desktop GUI application
│   ├── main.py        # Entry point
│   ├── gui/           # PySide6 interface
│   └── telemetry.py   # Sensor integration
├── hq_command/        # Task scheduling engine
│   ├── tasking_engine.py
│   └── analytics.py
├── bridge/            # Message routing
│   ├── comms_router.py
│   └── compliance.py
└── integration/       # Inter-module communication
    ├── protocol.py
    └── coordinator.py
```

### Running Tests
```bash
pytest
```

Test markers:
- `@pytest.mark.slow` - Slow tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.gui` - GUI tests (require display)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Ensure `pytest` passes
6. Submit a pull request

## License
MIT License - See LICENSE file for details.

## What This Is NOT

This is NOT:
- A web application (it's a desktop GUI)
- A microservices architecture (it's a monolithic Python app)
- A database-backed system (it uses JSON files)
- A containerized deployment (it's just Python + pip)
- A mesh network implementation (it has local message queuing)

It's a straightforward Python desktop application designed for offline-first crisis response coordination.
