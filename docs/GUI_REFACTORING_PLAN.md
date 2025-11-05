# GUI Refactoring Plan - Phase 3

**Status:** Planning
**Target:** Reduce main_window.py from 1,461 lines to <500 lines per module

## Current State

- `src/hq_command/gui/main_window.py`: 1,461 lines
- Single large class with multiple responsibilities
- Complex UI logic mixed with business logic

## Refactoring Strategy

### Step 1: Extract Dialog Components
**Target:** `src/hq_command/gui/dialogs/`

Create separate dialog modules for:
- `workflow_dialogs.py` - Workflow creation and management dialogs
- `mission_dialogs.py` - Mission package dialogs
- `task_dialogs.py` - Task creation and editing dialogs
- `assignment_dialogs.py` - Responder assignment dialogs

**Estimated Lines:** ~300-400 lines moved

### Step 2: Extract View Components
**Target:** `src/hq_command/gui/views/`

Create focused view modules for:
- `task_view.py` - Task list and filtering
- `responder_view.py` - Responder roster and status
- `telemetry_view.py` - Telemetry display and visualization
- `map_view.py` - Geographic visualization

**Estimated Lines:** ~400-500 lines moved

### Step 3: Extract Reusable Components
**Target:** `src/hq_command/gui/components/`

Create shared component modules:
- `context_drawer.py` - Context panel component
- `filter_presets.py` - Filter preset management
- `status_bar.py` - Status bar component
- `toolbar.py` - Toolbar component

**Estimated Lines:** ~200-300 lines moved

### Step 4: Extract UI Utilities
**Target:** `src/hq_command/gui/ui_utils.py`

Utility functions for:
- Common UI operations
- Style management
- Layout helpers
- Widget factories

**Estimated Lines:** ~100-150 lines moved

## Final Structure

```
src/hq_command/gui/
├── main_window.py (~300 lines)        # Main window coordination
├── dialogs/
│   ├── __init__.py
│   ├── workflow_dialogs.py
│   ├── mission_dialogs.py
│   ├── task_dialogs.py
│   └── assignment_dialogs.py
├── views/
│   ├── __init__.py
│   ├── task_view.py
│   ├── responder_view.py
│   ├── telemetry_view.py
│   └── map_view.py
├── components/
│   ├── __init__.py
│   ├── context_drawer.py
│   ├── filter_presets.py
│   ├── status_bar.py
│   └── toolbar.py
└── ui_utils.py
```

## Testing Strategy

After each refactoring step:
1. Run GUI manually to verify functionality
2. Test all dialog workflows
3. Test view switching and updates
4. Verify no regressions in task/responder operations

## Dependencies

- PySide6 for GUI testing
- Full integration testing environment
- User acceptance testing for UI changes

## Implementation Priority

1. **High Priority:** Extract dialogs (most self-contained)
2. **Medium Priority:** Extract views (requires careful state management)
3. **Low Priority:** Extract components (can be done incrementally)

## Notes

- This refactoring should be done incrementally
- Each module should maintain backward compatibility during transition
- Full test coverage required before merging
- Consider this for Phase 4 when full test environment is available
