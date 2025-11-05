# PRRC OS Suite - Troubleshooting Guide

This guide provides solutions to common problems you might encounter while developing or running the PRRC OS Suite.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Runtime Errors](#runtime-errors)
3. [Integration Issues](#integration-issues)
4. [GUI Problems](#gui-problems)
5. [Performance Issues](#performance-issues)
6. [Testing Problems](#testing-problems)
7. [Security Issues](#security-issues)
8. [Debugging Tips](#debugging-tips)

---

## Installation Issues

### Python Version Incompatibility

**Symptoms**: Import errors, syntax errors when running code

**Diagnosis**:
```bash
python --version  # Should be 3.11+
```

**Solution**:
- Install Python 3.11 or higher
- Update your virtual environment:
  ```bash
  python3.11 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### PySide6 Installation Fails

**Symptoms**:
- `ERROR: Could not find a version that satisfies the requirement PySide6`
- GUI applications don't start

**Diagnosis**:
```bash
pip list | grep PySide6
```

**Solutions**:

1. **Linux**: Install Qt dependencies
   ```bash
   # Ubuntu/Debian
   sudo apt-get install qt6-base-dev libgl1-mesa-dev

   # Fedora
   sudo dnf install qt6-qtbase-devel mesa-libGL-devel
   ```

2. **macOS**: Install with Homebrew
   ```bash
   brew install qt@6
   pip install PySide6
   ```

3. **Windows**: Usually works out of the box
   ```bash
   pip install PySide6
   ```

4. **Alternative**: Use PyQt6 instead
   ```bash
   pip install PyQt6
   # Update qt_compat.py to use PyQt6
   ```

### Module Not Found Errors

**Symptoms**: `ModuleNotFoundError: No module named 'integration'`

**Diagnosis**:
```bash
pwd  # Should be in PRRC root directory
python -c "import sys; print(sys.path)"
```

**Solutions**:

1. **Add src to PYTHONPATH**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
   ```

2. **Run from correct directory**:
   ```bash
   cd /path/to/PRRC
   python -m src.prrc_cli
   ```

3. **Install in development mode**:
   ```bash
   pip install -e .
   ```

---

## Runtime Errors

### ValidationError: task_id must be a non-empty string

**Symptoms**: Validation errors when creating tasks

**Cause**: Missing or invalid required fields in task data

**Solution**:
```python
# Ensure all required fields are provided
task = {
    "task_id": "task-001",  # Must be non-empty string
    "priority": 3,          # Must be 1-5
    "capabilities_required": ["hazmat"],  # Must be list
}
```

### PRRCError: Communication error occurred

**Symptoms**: Integration layer failures, message delivery errors

**Diagnosis**:
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Solutions**:

1. **Check Bridge connection**:
   ```python
   # Verify Bridge router is initialized
   assert bridge_router is not None
   ```

2. **Check message format**:
   ```python
   # Use schema validation
   from integration.schemas import validate_task_assignment
   validate_task_assignment(task_data)
   ```

3. **Check rate limiting**:
   ```python
   # Verify not rate-limited
   from shared.security import RateLimiter
   remaining = limiter.get_remaining_requests(client_id)
   print(f"Remaining requests: {remaining}")
   ```

### AttributeError in telemetry serialization

**Symptoms**: `AttributeError: 'Sensor' object has no attribute 'unit'`

**Cause**: Sensor objects missing optional attributes (Bug #4)

**Solution**:
Already fixed in Phase 2. Ensure you're using the latest code:
```python
# Correct approach (uses getattr with defaults)
sensor_data = {
    "id": getattr(sensor, 'id', 'unknown'),
    "type": getattr(sensor, 'type', 'unknown'),
    "value": getattr(sensor, 'value', None),
    "unit": getattr(sensor, 'unit', ''),
}
```

### Photo path contains "None" string

**Symptoms**: Invalid photo paths with literal "None"

**Cause**: str(None) instead of None check (Bug #2)

**Solution**:
Already fixed in Phase 2. Update to latest code:
```python
# Correct approach
photo_path = stored if stored is not None else item.text()
```

---

## Integration Issues

### Messages not being delivered

**Symptoms**:
- Tasks don't appear in FieldOps
- Telemetry doesn't reach HQ

**Diagnosis**:
```python
# Check coordinator statistics
stats = coordinator.get_statistics()
print(f"Sent: {stats['sent']}, Failed: {stats['failed']}")

# Check pending retries
print(f"Pending retry: {stats['pending_retry']}")
```

**Solutions**:

1. **Check routing record status**:
   ```python
   # In coordinator.py
   if routing_record.status != "delivered":
       print(f"Delivery failed: {routing_record.error}")
   ```

2. **Retry failed messages**:
   ```python
   retry_count = coordinator.retry_failed_messages()
   print(f"Retried {retry_count} messages")
   ```

3. **Verify partner_id**:
   ```python
   # Ensure correct partner ID
   success = coordinator.send_message(envelope, partner_id="fieldops_001")
   ```

### Priority mapping inconsistencies

**Symptoms**: Wrong priority levels between HQ and FieldOps

**Cause**: Int vs string priority mismatch (Fixed in Phase 2)

**Solution**:
Use standardized conversion functions:
```python
from shared.schemas import priority_to_int, priority_to_string

# HQ uses int (1-5)
hq_priority = priority_to_int("High")  # Returns 4

# FieldOps uses string
fieldops_priority = priority_to_string(4)  # Returns "High"
```

### Schema validation failures

**Symptoms**: `ValidationError` when processing messages

**Diagnosis**:
```python
from integration.schemas import validate_task_assignment

try:
    schema = validate_task_assignment(task_data)
except ValidationError as e:
    print(f"Validation error: {e.message}")
    print(f"Context: {e.context}")
```

**Solutions**:

1. **Check required fields**:
   - task_id (string)
   - priority (1-5 or "Routine"/"High"/"Critical")
   - capabilities_required (list of strings)

2. **Validate priority**:
   ```python
   from shared.schemas import validate_priority
   if not validate_priority(priority):
       print(f"Invalid priority: {priority}")
   ```

3. **Check data types**:
   ```python
   assert isinstance(task_id, str)
   assert isinstance(capabilities_required, list)
   ```

---

## GUI Problems

### GUI doesn't start

**Symptoms**: Application crashes on startup

**Diagnosis**:
```bash
# Run with verbose logging
python -m src.prrc_cli --debug hq
```

**Solutions**:

1. **Check Qt installation**:
   ```python
   python -c "from PySide6.QtWidgets import QApplication; print('Qt OK')"
   ```

2. **Check display server** (Linux):
   ```bash
   echo $DISPLAY  # Should be set (e.g., :0)
   export DISPLAY=:0  # If not set
   ```

3. **Run in virtual display** (headless):
   ```bash
   Xvfb :99 -screen 0 1024x768x24 &
   export DISPLAY=:99
   python -m src.prrc_cli hq
   ```

### Task action fails silently

**Symptoms**: No feedback when performing task actions

**Cause**: Missing error handling (Fixed in Phase 3)

**Solution**:
Phase 3 added comprehensive validation and feedback. Update to latest code:
```python
# Now includes:
# - Input validation
# - Error feedback (QMessageBox)
# - Success messages
# - Detailed logging
```

### State not refreshing

**Symptoms**: GUI shows stale data

**Diagnosis**:
```python
# Check if refresh is being called
def _refresh_state(self):
    print("Refreshing state...")  # Add logging
    self._controller.refresh()
```

**Solutions**:

1. **Manual refresh**:
   ```python
   self._refresh_state()
   ```

2. **Check immutable state**:
   ```python
   # Ensure new state object is created
   new_state = ControllerState(
       tasks=new_tasks,
       responders=new_responders,
       operator=self._state.operator  # Don't forget this!
   )
   ```

---

## Performance Issues

### Slow task loading

**Symptoms**: GUI freezes when loading many tasks

**Temporary Solution**:
```python
# Limit displayed tasks
tasks = all_tasks[:1000]  # Show first 1000

# Add pagination
page_size = 100
start = page * page_size
end = start + page_size
displayed_tasks = all_tasks[start:end]
```

**Long-term Solution**: Implement virtual scrolling (Phase 4 backlog)

### High memory usage

**Symptoms**: Application uses excessive memory

**Diagnosis**:
```python
import tracemalloc
tracemalloc.start()
# ... run operation ...
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

**Solutions**:

1. **Clear old data**:
   ```python
   # Limit history size
   self._events = deque(maxlen=1000)
   ```

2. **Use generators for large datasets**:
   ```python
   def get_tasks():
       for task in large_task_list:
           yield process_task(task)
   ```

### Slow sync operations

**Symptoms**: Sync takes too long

**Diagnosis**:
```python
import time
start = time.time()
coordinator.sync_operations()
print(f"Sync took {time.time() - start:.2f}s")
```

**Solutions**:

1. **Batch operations**:
   ```python
   # Send multiple operations in one message
   operations = collect_pending_operations()
   fieldops.sync_operations_to_hq(operations)
   ```

2. **Compress payloads** (future enhancement):
   ```python
   import gzip
   compressed = gzip.compress(json.dumps(payload).encode())
   ```

---

## Testing Problems

### Tests fail with import errors

**Symptoms**: `ModuleNotFoundError` in tests

**Solution**:
```bash
# Run from project root
cd /path/to/PRRC
pytest tests/

# Or add to pytest.ini:
[pytest]
pythonpath = src
```

### Tests fail randomly

**Symptoms**: Intermittent test failures

**Causes & Solutions**:

1. **Race conditions**:
   ```python
   # Use proper synchronization
   import time
   time.sleep(0.1)  # Allow async operation to complete
   ```

2. **Shared state between tests**:
   ```python
   @pytest.fixture
   def clean_state():
       # Reset global state
       coordinator.reset()
       yield
       coordinator.reset()
   ```

3. **Time-dependent tests**:
   ```python
   # Mock datetime
   from unittest.mock import patch
   with patch('module.datetime') as mock_dt:
       mock_dt.utcnow.return_value = fixed_time
       # test code
   ```

### Mock objects not working

**Symptoms**: Mocks don't intercept calls

**Solution**:
```python
# Patch where it's used, not where it's defined
from unittest.mock import patch

# Wrong
@patch('integration.coordinator.RoutingRecord')

# Correct
@patch('src.integration.coordinator.RoutingRecord')
```

---

## Security Issues

### Rate limit not enforced

**Symptoms**: Clients can exceed rate limits

**Diagnosis**:
```python
from shared.security import RateLimiter, RateLimitConfig

limiter = RateLimiter(RateLimitConfig(max_requests=10, time_window=60))

# Test rate limiting
for i in range(15):
    allowed = limiter.allow_request("test_client")
    print(f"Request {i+1}: {allowed}")
```

**Solutions**:

1. **Use same limiter instance**:
   ```python
   # Create once, reuse
   limiter = RateLimiter(config)

   # Share across requests
   def handle_request(client_id):
       if not limiter.allow_request(client_id):
           raise RateLimitError()
   ```

2. **Check remaining requests**:
   ```python
   remaining = limiter.get_remaining_requests(client_id)
   if remaining < 2:
       logger.warning(f"Client {client_id} approaching limit")
   ```

### Path traversal vulnerability

**Symptoms**: User can access files outside allowed directories

**Solution**:
Use PathSanitizer for all file paths:
```python
from shared.security import PathSanitizer

sanitizer = PathSanitizer(allowed_base_paths=["/safe/dir"])

# Validate before use
if not sanitizer.validate(user_path):
    raise SecurityError("Invalid path")

# Or sanitize
safe_path = sanitizer.sanitize(user_path)
```

### Security events not logged

**Symptoms**: No audit trail for security events

**Solution**:
```python
from shared.security import SecurityEventTracker

tracker = SecurityEventTracker(audit_callback=audit_log.audit_event)

# Record events
tracker.record_event(
    event_type="rate_limit_exceeded",
    severity="medium",
    description=f"Client {client_id} exceeded rate limit",
    client_id=client_id
)
```

---

## Debugging Tips

### Enable Debug Logging

```python
import logging

# Enable for all modules
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable for specific module
logger = logging.getLogger('integration.coordinator')
logger.setLevel(logging.DEBUG)
```

### Use Python Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use built-in breakpoint() in Python 3.7+
breakpoint()
```

### Trace Function Calls

```python
import sys

def trace_calls(frame, event, arg):
    if event == 'call':
        code = frame.f_code
        print(f"Calling {code.co_name} in {code.co_filename}:{frame.f_lineno}")
    return trace_calls

sys.settrace(trace_calls)
# ... code to trace ...
sys.settrace(None)
```

### Profile Performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... code to profile ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def my_function():
    # ... code to profile ...
    pass
```

---

## Getting Additional Help

If you can't resolve an issue using this guide:

1. **Search GitHub Issues**: Someone may have encountered the same problem
2. **Check Documentation**: Review relevant docs in `docs/`
3. **Enable Debug Logging**: Get detailed error information
4. **Create Minimal Reproduction**: Isolate the problem
5. **Ask for Help**: Create a GitHub issue with:
   - Python version
   - OS and version
   - Steps to reproduce
   - Error messages and logs
   - Expected vs actual behavior

---

## Frequently Asked Questions

**Q: Why do I get "operator state loss" errors?**
A: Fixed in Phase 1. Update to latest code.

**Q: How do I test without a GUI?**
A: Use headless mode with Xvfb (Linux) or run unit tests only.

**Q: Can I use PyQt6 instead of PySide6?**
A: Yes, update `qt_compat.py` to import from PyQt6.

**Q: How do I reset the audit log?**
A: Delete the audit log database file (location in config).

**Q: Why are my changes not taking effect?**
A: Ensure you restarted the application and cleared any caches.

---

Last Updated: 2025-11-05
