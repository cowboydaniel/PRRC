# PRRC OS Suite - Development Roadmap

**Last Updated:** 2025-11-05
**Based on:** CODE_REVIEW_REPORT.md (2025-11-05)

---

## Overview

This roadmap addresses critical bugs, integration issues, and improvements identified in the comprehensive code review. The PRRC OS Suite has a solid architectural foundation (Grade: B, targeting A with these fixes), but requires immediate attention to the integration layer and several critical bugs before production deployment.

**Current Status:**
- Architecture: A
- HQ Command GUI: B+
- FieldOps GUI: B+
- Integration Layer: B+ (Phase 1 critical bugs fixed)
- Documentation: A+
- Testing: B

**Target:** Production-ready system with all components at A- or better

---

## Phase 1: IMMEDIATE (Fix Now) ✅ **COMPLETED**

**Timeline:** Days 1-3
**Goal:** Eliminate critical data loss and integration bugs
**Status:** ✅ Complete (2025-11-05)

### 1.1 Critical Bug Fixes

#### Bug #1: Operator State Loss in Manual Assignment ✅
- **File:** `src/hq_command/gui/controller.py:329`
- **Fix:** Add `operator=self._state.operator` when creating new ControllerState
- **Impact:** Prevents operator profile data loss and RBAC failures
- **Testing:** Unit test for manual assignment preserving operator state
- **Status:** ✅ Fixed

#### Bug #3: Integration Layer Type Mismatch ✅
- **File:** `src/integration/fieldops_integration.py:368-376`
- **Fix:**
  - Validate `_task_baseline` type before merging
  - Convert to list before passing to `update_task_assignments()`
  - Add proper error handling
- **Impact:** Prevents task update failures in GUI
- **Testing:** Integration test for task assignment flow
- **Status:** ✅ Fixed

### 1.2 Integration Testing Framework ✅

- **Action:** Create end-to-end integration tests for HQ ↔ FieldOps communication
- **Coverage:**
  - Task assignment flow (HQ → FieldOps)
  - Status updates (FieldOps → HQ)
  - Telemetry reporting (FieldOps → HQ)
  - Offline queue sync
- **Files:** Enhanced `tests/test_integration.py` with Phase 1 specific tests
- **Status:** ✅ Complete

**Success Criteria:**
- ✅ All 2 critical bugs fixed
- ✅ Integration test suite created with >80% coverage of message flows
- ✅ No regressions in existing functionality
- ✅ All tests passing

---

## Phase 2: HIGH PRIORITY (This Week) 🟠

**Timeline:** Days 4-7
**Goal:** Fix remaining high-severity bugs and standardize data schemas

### 2.1 High-Severity Bug Fixes

#### Bug #2: Photo Path Serialization Error
- **File:** `src/fieldops/gui/app.py:834-836`
- **Fix:** Handle None case properly: `photos.append(stored if stored is not None else item.text())`
- **Impact:** Prevents invalid "None" string in photo paths
- **Testing:** Unit test for photo attachment with None UserRole

#### Bug #4: Telemetry Sensor Attribute Errors
- **File:** `src/integration/fieldops_integration.py:504-513`
- **Fix:**
  - Use `getattr()` with defaults for sensor attributes
  - Or validate sensor schema before serialization
  - Add error handling for missing attributes
- **Impact:** Prevents telemetry sync failures
- **Testing:** Test with sensors missing optional attributes

### 2.2 Data Schema Standardization

#### Priority Mapping Standardization
- **Issue:** HQ uses int (1-5), FieldOps uses string ("Routine", "High", "Critical")
- **Fix:**
  - Create shared priority enum in `src/shared/schemas.py`
  - Update integration layer to use consistent mapping
  - Add validation at integration boundaries
- **Files:**
  - `src/integration/fieldops_integration.py:352`
  - `src/integration/hq_integration.py`

#### Schema Validation Layer
- **Action:** Implement runtime schema validation for message payloads
- **Approach:**
  - Option A: Use Pydantic models for all messages
  - Option B: Use dataclass with validation decorators
  - Option C: Custom validation functions
- **Files:** Create `src/integration/schemas.py`
- **Coverage:**
  - Task assignment messages
  - Status update messages
  - Telemetry messages
  - Resource allocation messages

**Success Criteria:**
- ✅ All 2 high-severity bugs fixed
- ✅ Priority mapping standardized across HQ and FieldOps
- ✅ Schema validation implemented for all message types
- ✅ Integration tests passing with new validation

---

## Phase 3: MEDIUM PRIORITY (This Sprint) 🟡

**Timeline:** Weeks 2-3
**Goal:** Improve code quality, UX, and maintainability

### 3.1 Medium-Severity Bug Fixes

#### Bug #5: Integration Coordinator Routing Result Access
- **File:** `src/integration/coordinator.py:148-154`
- **Fix:** Create proper dataclass for RoutingRecord
- **Impact:** Better type checking and maintainability
- **Testing:** Update existing coordinator tests

### 3.2 GUI Refactoring

#### HQ Command GUI Split
- **File:** `src/hq_command/gui/main_window.py` (1,462 lines)
- **Action:** Split into smaller, focused modules
- **Structure:**
  ```
  src/hq_command/gui/
    ├── main_window.py (core window, ~300 lines)
    ├── dialogs/
    │   ├── workflow_dialogs.py
    │   ├── mission_dialogs.py
    │   └── task_dialogs.py
    ├── views/
    │   ├── task_view.py
    │   ├── responder_view.py
    │   └── telemetry_view.py
    └── components/
        ├── context_drawer.py
        └── filter_presets.py
  ```

#### FieldOps GUI Improvements
- **Add validation:** Task action metadata validation
- **Error feedback:** Visual feedback for failed operations
- **Loading states:** Show loading during sync operations
- **Photo handling:** Additional validation for photo paths

### 3.3 Error Handling Standardization

- **Action:** Create consistent error handling patterns
- **Areas:**
  - Integration layer error propagation
  - GUI error display
  - Logging standardization
- **Files:** Create `src/shared/error_handling.py`

### 3.4 UX Improvements

#### HQ Command UX
- Add loading states for async operations
- Improve context drawer positioning
- Better visual feedback for filter presets

#### FieldOps UX
- Cache navigation rail width calculation
- Add telemetry card loading states
- Visual feedback during sync operations
- Better offline mode indicators

**Success Criteria:**
- ✅ Bug #5 fixed
- ✅ Main window refactored into <500 line modules
- ✅ Consistent error handling across all modules
- ✅ Loading states implemented in all async operations
- ✅ User testing feedback incorporated

---

## Phase 4: LOW PRIORITY (Backlog) ⚪

**Timeline:** Ongoing
**Goal:** Performance, security, and code quality improvements

### 4.1 Performance Optimizations

#### HQ Command Performance
- **Issue:** Refreshes all models on every change
- **Fix:** Implement incremental updates
- **Target:** Reduce refresh time by 70%

#### FieldOps Performance
- **Issue:** Sync timer runs every 15s regardless of activity
- **Fix:** Implement adaptive sync intervals based on activity
- **Target:** Reduce unnecessary sync operations by 60%

#### Data Loading
- **Issue:** No lazy loading for large task lists
- **Fix:** Implement virtual scrolling and pagination
- **Target:** Support 10,000+ tasks without performance degradation

#### Telemetry Collection
- **Issue:** Snapshot collection could block GUI
- **Fix:** Move to background thread with proper synchronization
- **Target:** <50ms GUI blocking time

### 4.2 Security Enhancements

- **Input validation:** Validate all message payloads at integration boundaries
- **Rate limiting:** Implement rate limiting on sync operations
- **Path sanitization:** Sanitize file paths in mission packages
- **Audit improvements:** Enhance audit logging with security events
- **Penetration testing:** Conduct security audit of integration layer

### 4.3 Code Quality Improvements

#### Code Smell Cleanup
- Refactor God objects (overly large controller classes)
- Eliminate duplicate code in integration helpers
- Standardize error handling patterns
- Improve method decomposition in large classes

#### Documentation Enhancements
- Add architecture diagrams (C4 model)
- Create developer onboarding guide
- Document message protocol versioning
- Add troubleshooting guides

### 4.4 Testing Improvements

- **Unit test coverage:** Increase from current to >85%
- **Integration tests:** Expand beyond happy path
- **Edge case testing:** Focus on error conditions and boundary cases
- **Performance tests:** Add benchmarks for critical paths
- **Load testing:** Test with realistic mission scales

**Success Criteria:**
- ✅ Performance targets met
- ✅ Security audit completed with no critical findings
- ✅ Code quality metrics improved (complexity, duplication)
- ✅ Test coverage >85%

---

## Phase 5: Future Enhancements 🚀

**Timeline:** Future sprints
**Goal:** New features and advanced capabilities

### 5.1 Protocol Versioning

- Add version field to message envelope
- Implement version negotiation
- Support backward compatibility
- Migration tools for protocol changes

### 5.2 Advanced Telemetry

- Pluggable sensor architecture
- Custom sensor type support
- Real-time telemetry streaming
- Telemetry analytics and alerting

### 5.3 Enhanced Offline Support

- Predictive pre-caching
- Conflict resolution UI improvements
- Offline mode simulation for testing
- Bandwidth optimization

### 5.4 Mobile Support

- Responsive GUI layouts
- Touch-optimized interfaces
- Mobile-specific workflows
- Offline-first mobile architecture

---

## Dependencies & Blockers

### External Dependencies
- None currently identified

### Internal Dependencies
- Phase 2 requires Phase 1 completion (schema validation depends on integration tests)
- Phase 3 GUI refactoring should wait for bug fixes to avoid rework
- Phase 4 performance work requires stable baseline from Phases 1-3

### Known Blockers
- None currently identified

---

## Success Metrics

### Code Quality Metrics
- **Bug count:** 5 critical bugs → 0 critical bugs
- **Integration layer grade:** C → A-
- **Test coverage:** Current → >85%
- **Code complexity:** Large files (>1000 lines) → <500 lines per file

### Functionality Metrics
- **HQ ↔ FieldOps compatibility:** 100% message success rate
- **Data integrity:** Zero data loss incidents
- **Error handling:** 100% of error paths tested

### Performance Metrics
- **GUI responsiveness:** <100ms for all user interactions
- **Sync efficiency:** <5s for typical sync operations
- **Memory usage:** <500MB for typical mission load

### Production Readiness
- **Overall grade:** B → A
- **Integration layer:** Production-ready
- **Security:** Penetration test passed
- **Documentation:** Complete for all modules

---

## Review & Update Schedule

- **Weekly:** Review progress on current phase
- **Bi-weekly:** Update roadmap based on discoveries
- **Monthly:** Stakeholder review and priority adjustment
- **Per phase:** Retrospective and lessons learned

---

## Appendix: Bug Reference

### Bug Summary Table

| ID | Title | File | Severity | Phase |
|----|-------|------|----------|-------|
| #1 | Operator State Loss | `controller.py:329` | CRITICAL | Phase 1 |
| #2 | Photo Path Serialization | `app.py:834` | HIGH | Phase 2 |
| #3 | Integration Type Mismatch | `fieldops_integration.py:368` | CRITICAL | Phase 1 |
| #4 | Telemetry Sensor Attributes | `fieldops_integration.py:504` | HIGH | Phase 2 |
| #5 | Routing Result Access | `coordinator.py:148` | MEDIUM | Phase 3 |

### Integration Issues Reference

1. **Priority Mapping:** HQ (int) vs FieldOps (string) - Phase 2
2. **Task Schema:** Inconsistent field names - Phase 2
3. **Telemetry Schema:** Variable sensor attributes - Phase 2
4. **Status Updates:** No schema validation - Phase 2

---

**End of Roadmap**
