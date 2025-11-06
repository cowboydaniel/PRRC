# PRRC OS Suite - Developer Onboarding Guide

Welcome to the PRRC OS Suite development team! This guide will help you get up to speed quickly.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Development Environment Setup](#development-environment-setup)
4. [Code Structure](#code-structure)
5. [Development Workflow](#development-workflow)
6. [Testing](#testing)
7. [Common Tasks](#common-tasks)
8. [Coding Standards](#coding-standards)
9. [Troubleshooting](#troubleshooting)
10. [Resources](#resources)

---

## System Overview

The PRRC OS Suite is an offline-first coordination system for managing emergency response operations. It consists of three main components:

- **HQ Command**: Command center application for task assignment and monitoring
- **FieldOps**: Field responder application for task execution and reporting
- **Bridge**: Secure communication layer for HQ-FieldOps synchronization

### Key Features

- **Offline-First Architecture**: All components work without network connectivity
- **Tamper-Evident Audit Logging**: Complete audit trail of all operations
- **Role-Based Access Control**: Operator-based permissions and capabilities
- **Mission Package System**: Self-contained mission data distribution
- **Mesh Network Communication**: Bridge-based message routing

---

## Architecture

### Component Overview

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│   HQ Command    │◄────────┤    Bridge    ├────────►│   FieldOps      │
│   (Desktop)     │         │  (Mesh/USB)  │         │   (Tablet)      │
└─────────────────┘         └──────────────┘         └─────────────────┘
        │                           │                         │
        ▼                           ▼                         ▼
  Audit Log DB            Message Queue              Local SQLite DB
```

### Key Design Patterns

1. **Immutable State Pattern**: GUI state objects are immutable for predictability
2. **Controller Pattern**: Business logic separated from UI
3. **Integration Layer**: Clean separation between components
4. **Message Envelope Pattern**: Standardized communication protocol

### Data Flow

1. **Task Assignment**:
   - HQ creates task → Controller validates → Integration layer packages → Bridge routes → FieldOps receives

2. **Telemetry Reporting**:
   - FieldOps collects → Controller serializes → Integration packages → Bridge routes → HQ displays

3. **Offline Sync**:
   - Operations queued locally → Sync timer triggers → Bridge attempts delivery → Retry on failure

---

## Development Environment Setup

### Prerequisites

```bash
# Required
- Python 3.11+
- PySide6 (Qt for Python)
- Git

# Recommended
- VS Code or PyCharm
- pytest for testing
- black for code formatting
- mypy for type checking
```

### Installation

```bash
# Clone repository
git clone https://github.com/cowboydaniel/PRRC.git
cd PRRC

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests to verify setup
pytest tests/
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Python Test Explorer

Settings (`.vscode/settings.json`):
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true
}
```

#### PyCharm

- Enable pytest as test runner
- Configure Python interpreter to use venv
- Enable type checking (mypy)

---

## Code Structure

```
PRRC/
├── src/
│   ├── hq_command/          # HQ Command application
│   │   ├── gui/             # Qt-based GUI
│   │   ├── controller.py    # Business logic
│   │   └── state.py         # Immutable state objects
│   ├── fieldops/            # FieldOps application
│   │   ├── gui/             # Qt-based GUI
│   │   ├── controller.py    # Business logic
│   │   └── state.py         # Immutable state objects
│   ├── bridge/              # Communication layer
│   │   ├── comms.py         # Message routing
│   │   └── audit_log.py     # Tamper-evident logging
│   ├── integration/         # Integration layer
│   │   ├── coordinator.py   # Message coordination
│   │   ├── protocol.py      # Message protocol
│   │   ├── schemas.py       # Message validation
│   │   ├── hq_integration.py
│   │   └── fieldops_integration.py
│   └── shared/              # Shared utilities
│       ├── schemas.py       # Priority mapping, data schemas
│       ├── error_handling.py  # Standardized error handling
│       └── security.py      # Security utilities
├── tests/                   # Test suite
│   ├── conftest.py          # Pytest configuration
│   ├── test_integration.py  # Integration tests
│   ├── hq_command/          # HQ Command tests
│   ├── fieldops/            # FieldOps tests
│   └── bridge/              # Bridge tests
├── docs/                    # Documentation
├── examples/                # Example code and data
└── README.md
```

### Key Modules

- **`src/integration/`**: Message passing between components
- **`src/shared/`**: Utilities used across all components
- **`src/bridge/`**: Communication and audit infrastructure
- **`src/*/gui/`**: Qt-based user interfaces
- **`src/*/controller.py`**: Business logic for each component

---

## Development Workflow

### Branch Strategy

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/name`: Feature development branches
- `bugfix/name`: Bug fix branches
- `claude/*`: AI assistant working branches

### Making Changes

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes**: Follow coding standards (see below)

3. **Write tests**: All new code must have tests

4. **Run tests**:
   ```bash
   pytest tests/
   ```

5. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: Add new feature

   - Detailed description of changes
   - Why the change was needed
   - Any breaking changes"
   ```

6. **Push and create PR**:
   ```bash
   git push -u origin feature/my-feature
   # Create pull request on GitHub
   ```

### Commit Message Format

Follow conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Build/tooling changes

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_integration.py

# Run with coverage
pytest --cov=src tests/

# Run with verbose output
pytest -v
```

### Test Structure

Tests are organized by component:
- `tests/test_integration.py`: Integration tests
- `tests/hq_command/`: HQ Command unit tests
- `tests/fieldops/`: FieldOps unit tests
- `tests/bridge/`: Bridge unit tests

### Writing Tests

```python
# tests/test_my_feature.py
import pytest
from src.integration import MessageEnvelope

def test_message_creation():
    """Test creating a message envelope."""
    envelope = MessageEnvelope(
        message_id="test-1",
        message_type=MessageType.TASK_ASSIGNMENT,
        sender_id="hq_001",
        recipient_id="fieldops_001",
        timestamp=datetime.utcnow(),
        payload={"test": "data"}
    )

    assert envelope.message_id == "test-1"
    assert envelope.sender_id == "hq_001"
```

### Test Guidelines

1. **Isolation**: Tests should be independent
2. **Clarity**: Test names should describe what they test
3. **Coverage**: Aim for >85% code coverage
4. **Speed**: Tests should run quickly (<1s per test)
5. **Mocking**: Use mocks for external dependencies

---

## Common Tasks

### Adding a New Message Type

1. Add enum to `src/integration/protocol.py`:
   ```python
   class MessageType(str, Enum):
       MY_NEW_TYPE = "my_new_type"
   ```

2. Create payload dataclass:
   ```python
   @dataclass
   class MyNewPayload:
       field1: str
       field2: int
   ```

3. Add schema validation in `src/integration/schemas.py`

4. Add handler in integration layers

5. Write tests

### Adding Error Handling

Use standardized error classes from `src/shared/error_handling.py`:

```python
from shared.error_handling import TaskOperationError, ErrorSeverity

def my_function(task_id: str):
    try:
        # ... operation ...
    except Exception as e:
        raise TaskOperationError(
            f"Failed to process task: {str(e)}",
            task_id=task_id,
            operation="my_operation",
            severity=ErrorSeverity.ERROR
        ) from e
```

### Adding Security Features

Use utilities from `src/shared/security.py`:

```python
from shared.security import RateLimiter, RateLimitConfig, PathSanitizer

# Rate limiting
limiter = RateLimiter(RateLimitConfig(max_requests=10, time_window=60))
if not limiter.allow_request(client_id):
    raise RateLimitError("Too many requests")

# Path sanitization
sanitizer = PathSanitizer(allowed_base_paths=["/safe/directory"])
safe_path = sanitizer.sanitize(user_input_path)
```

---

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use Black for formatting
- Use docstrings for all public functions/classes

### Code Example

```python
def process_task_assignment(
    task_id: str,
    responder_id: str,
    priority: int
) -> bool:
    """
    Assign a task to a responder.

    Args:
        task_id: Unique identifier for the task
        responder_id: Unique identifier for the responder
        priority: Task priority (1-5)

    Returns:
        True if assignment successful, False otherwise

    Raises:
        TaskOperationError: If assignment fails
    """
    # Implementation
    pass
```

### Documentation

- All public APIs must have docstrings
- Use Google-style docstrings
- Include type information
- Provide usage examples for complex functions

### Import Organization

```python
# Standard library
import os
import sys
from datetime import datetime

# Third-party
from PySide6.QtCore import Qt
import pytest

# Local
from integration import MessageEnvelope
from shared.error_handling import PRRCError
```

---

## Troubleshooting

### Common Issues

**Issue**: `ImportError: No module named 'PySide6'`
**Solution**: Install PySide6: `pip install PySide6`

**Issue**: Tests fail with import errors
**Solution**: Ensure you're running from project root and venv is activated

**Issue**: GUI doesn't start
**Solution**: Check Qt dependencies are installed: `pip install -r requirements.txt`

**Issue**: Rate limiter not working
**Solution**: Ensure you're using the same RateLimiter instance across requests

See `docs/TROUBLESHOOTING.md` for more detailed troubleshooting steps.

---

## Resources

### Documentation

- [README.md](../README.md): Project overview
- [ROADMAP.md](../ROADMAP.md): Development roadmap
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): Detailed troubleshooting guide
- [GUI_REFACTORING_PLAN.md](GUI_REFACTORING_PLAN.md): GUI refactoring plan

### External Resources

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [pytest Documentation](https://docs.pytest.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

### Getting Help

- **Code Reviews**: All PRs require review
- **Issues**: Use GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub discussions for questions

### Team Contacts

- **Architecture**: See ARCHITECTURE.md
- **Security**: See SECURITY.md
- **Testing**: See tests/README.md

---

## Next Steps

1. Set up your development environment
2. Run the test suite to verify setup
3. Read through the codebase structure
4. Pick a "good first issue" from GitHub
5. Join the team discussion channels

Welcome to the team! 🚀
