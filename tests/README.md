# PRRC Test Suite
**Phase 0: Testing Infrastructure Documentation**
**Last Updated:** 2025-11-02

---

## Overview

The PRRC test suite provides comprehensive testing coverage for HQ Command GUI, FieldOps, and Bridge modules. The test infrastructure is built on pytest with Qt-specific testing support through pytest-qt and a custom Qt shim for headless CI/CD execution.

---

## Test Structure

```
tests/
├── conftest.py                           # Pytest configuration + Qt shims (324 LOC)
├── README.md                             # This documentation
├── hq_command/                           # HQ Command tests (423 LOC)
│   ├── test_analytics.py                 # Telemetry analytics tests (133 LOC)
│   ├── test_gui_controller_models.py     # GUI model tests (71 LOC)
│   ├── test_hq_main.py                   # Core logic tests (81 LOC)
│   ├── test_main_gui_dispatch.py         # GUI dispatch tests (54 LOC)
│   └── test_tasking_engine.py            # Scheduling algorithm tests (84 LOC)
├── fieldops/                             # FieldOps tests (1,109 LOC)
│   ├── test_connectors.py                # Hardware connectors tests (95 LOC)
│   ├── test_gui_app_launch.py            # App initialization tests (111 LOC)
│   ├── test_gui_controller.py            # GUI state management tests (468 LOC)
│   ├── test_mission_loader.py            # Mission package tests (322 LOC)
│   └── test_telemetry.py                 # Telemetry collection tests (208 LOC)
```

**Total Test LOC:** ~1,951
**Test Coverage Ratio:** ~35% (test-to-source)
**Target Coverage:** ≥80% line coverage

---

## Running Tests

### Basic Test Execution
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with test output (print statements)
pytest -v -s

# Run specific test file
pytest tests/hq_command/test_analytics.py

# Run specific test function
pytest tests/hq_command/test_analytics.py::test_summarize_telemetry_empty_data

# Run tests matching pattern
pytest -k "test_calculate_score"
```

### Coverage Reporting
```bash
# Run with coverage report (terminal)
pytest --cov=src --cov-report=term

# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

# Generate XML coverage (for CI/CD)
pytest --cov=src --cov-report=xml
```

### Test Markers
```bash
# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run only GUI tests
pytest -m gui
```

### Parallel Execution
```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with 4 workers
pytest -n 4
```

---

## Test Infrastructure

### PySide6 Test Requirements

The `conftest.py` file verifies that PySide6 is installed and ensures the `src` directory is importable. Tests now execute against the real PySide6 runtime, aligning test behavior with production deployments.

**Key Expectations:**
- Install PySide6 before running the test suite
- Ensure CI environments provide the PySide6 wheel (headless mode is supported)
- Maintain tests that interact with Qt APIs by patching specific PySide6 classes where isolation is needed

### Fixtures

**Available fixtures from conftest.py:**
- `qapp`: QApplication instance (or mock)
- Custom fixtures for test data (add as needed)

---

## Writing Tests

### Test Naming Convention
```python
def test_<function>_<scenario>_<expected_result>():
    """Test description."""
    ...
```

### Test Structure (Arrange-Act-Assert)
```python
def test_assign_task_updates_responder_capacity():
    # Arrange: Set up test data
    task = {"id": "t1", "capabilities": ["medical"]}
    responder = {"id": "r1", "capacity": 2, "assigned": []}

    # Act: Execute the function under test
    result = assign_task(task, responder)

    # Assert: Verify expected outcomes
    assert result is True
    assert len(responder["assigned"]) == 1
    assert responder["assigned"][0] == "t1"
```

### Example Test Cases

**Unit Test (Pure Python):**
```python
def test_calculate_scheduling_score_matching_capabilities():
    """Test that matching capabilities yield high scores."""
    from hq_command.tasking_engine import calculate_scheduling_score

    task = {
        "capabilities": ["medical", "transport"],
        "location": [0, 0]
    }
    responder = {
        "capabilities": ["medical", "transport", "search"],
        "location": [1, 1],
        "fatigue": 10,
        "capacity": 3
    }

    score = calculate_scheduling_score(task, responder)

    assert score > 80.0  # High score for good match
    assert score <= 100.0  # Max score is 100
```

**GUI Test (Qt Components):**
```python
def test_roster_list_model_row_count(qapp):
    """Test that RosterListModel reports correct row count."""
    from hq_command.gui.controller import RosterListModel

    # Arrange
    responders = [
        {"id": "r1", "status": "available"},
        {"id": "r2", "status": "busy"},
    ]
    model = RosterListModel(responders)

    # Act
    row_count = model.rowCount(None)

    # Assert
    assert row_count == 2
```

### Using Markers
```python
import pytest

@pytest.mark.slow
def test_large_dataset_processing():
    """Test processing 10,000 tasks (slow)."""
    ...

@pytest.mark.integration
def test_full_workflow_end_to_end():
    """Test complete workflow from intake to completion."""
    ...

@pytest.mark.gui
def test_main_window_launch(qapp):
    """Test that main window can be instantiated."""
    ...
```

### Parametrized Tests
```python
import pytest

@pytest.mark.parametrize("input_value,expected", [
    (0, "zero"),
    (1, "one"),
    (5, "many"),
])
def test_classify_number(input_value, expected):
    result = classify_number(input_value)
    assert result == expected
```

---

## Test Coverage Goals

### Current Baseline
- **Overall Coverage:** ~35% (test-to-source LOC ratio)
- **HQ Command:** Partial coverage (core logic covered, GUI minimal)
- **FieldOps:** Good coverage (controller and mission loader well-tested)
- **Bridge:** Minimal (placeholder code)

### Phase 0 Targets
- **Minimum:** 80% line coverage
- **Branch Coverage:** 70% minimum
- **Critical Paths:** 100% (scheduling, telemetry, assignment)

### Coverage by Module (Target)
| Module | Current | Target |
|--------|---------|--------|
| hq_command.tasking_engine | ~70% | 90% |
| hq_command.analytics | ~80% | 90% |
| hq_command.gui.controller | ~50% | 80% |
| fieldops.mission_loader | ~90% | 95% |
| fieldops.gui.controller | ~85% | 90% |

---

## Continuous Integration

### CI/CD Pipeline (Future)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
    - name: Run tests with coverage
      run: |
        pytest --cov=src --cov-report=xml --cov-report=term
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## Troubleshooting

### Qt Import Errors
**Problem:** Tests fail with "ModuleNotFoundError: No module named 'PySide6'"

**Solution:** The Qt shim in conftest.py should handle this automatically. If not:
1. Check that conftest.py is being loaded (should be in tests/)
2. Verify PYTHONPATH includes src/ directory
3. Run: `pytest --collect-only` to verify test discovery

### Display/X11 Errors
**Problem:** Tests fail with "cannot connect to X server" or "DISPLAY not set"

**Solution:** Set headless mode:
```bash
export QT_QPA_PLATFORM=offscreen
pytest
```

Or use Xvfb:
```bash
xvfb-run pytest
```

### Slow Test Execution
**Problem:** Test suite takes too long to run

**Solutions:**
1. Skip slow tests: `pytest -m "not slow"`
2. Run in parallel: `pytest -n auto`
3. Run specific modules: `pytest tests/hq_command/`

---

## Adding New Tests

### Step-by-Step
1. **Create test file** matching `test_*.py` pattern
2. **Import modules** to test
3. **Write test functions** with `test_` prefix
4. **Add docstrings** explaining test purpose
5. **Use markers** for categorization (slow, integration, gui)
6. **Run tests** to verify: `pytest tests/module/test_file.py`
7. **Check coverage**: `pytest --cov=src.module tests/module/`

### Test Checklist
- [ ] Test file named `test_*.py`
- [ ] Test functions named `test_*`
- [ ] Docstrings for all test functions
- [ ] Arrange-Act-Assert structure
- [ ] Edge cases covered (empty input, null, invalid)
- [ ] Error cases tested (exceptions)
- [ ] Coverage checked and improved

---

## Best Practices

1. **Keep tests focused** - One test per behavior/scenario
2. **Use descriptive names** - Test name should explain what it tests
3. **Arrange-Act-Assert** - Clear test structure
4. **Avoid test interdependencies** - Tests should run in any order
5. **Mock external dependencies** - Don't rely on network, filesystem (except fixtures)
6. **Test edge cases** - Empty lists, null values, invalid inputs
7. **Test error handling** - Verify exceptions are raised correctly
8. **Keep tests fast** - Use markers for slow tests
9. **Maintain high coverage** - Aim for 80%+ line coverage
10. **Document complex tests** - Add comments for non-obvious logic

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

**Test Suite Version:** 1.0.0
**Last Updated:** 2025-11-02
**Maintained by:** PRRC Engineering
