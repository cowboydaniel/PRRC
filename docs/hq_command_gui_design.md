# HQ Command GUI Design Blueprint

## Overview
This document consolidates the proposed interface layout, workflows, and styling guidelines for the HQ Command tasking console. The goal is to keep the command workstation visually and semantically aligned with the FieldOps experience while emphasizing command-level analytics and multi-role coordination.

## Layout Architecture

### Primary Regions
1. **Navigation Rail (left, 72 px fixed width):** Mirrors the FieldOps navigation spec using the `Primary` token (`#0C3D5B`) for the rail surface and `Primary Contrast` text/icon treatments. Tabs: *Live Ops*, *Task Board*, *Telemetry*, *Audit Trails*, *Admin*.
2. **Global Status Bar (top, 56 px height):** Surface Light background with Neutral 900 typography. Hosts sync, escalation, and communications badges that reuse the Accent (`#F6A000`), Success (`#3FA776`), and Danger (`#C4373B`) tokens described in `docs/fieldops_gui_style.md`.
3. **Mission Canvas (center flexible grid):** Splits into configurable panels depending on the selected tab. Default layout shows a two-column grid:
   - **Situational Timeline (left, 55%)**: scrollable event stream with task escalations, incoming 000 call metadata, and audit annotations.
   - **Task & Resource Board (right, 45%)**: Kanban-style swimlanes for `Queued`, `Active`, `Monitoring`, `After Action` columns.
4. **Context Drawer (right overlay):** 360 px slide-in panel triggered from timeline entries to show full call transcript, responder roster, or analytics deep dives. Styled with Surface Light backgrounds, Neutral 200 borders, and uses the Primary Light hover state for actionable pills.

### Responsive Behaviour
- **≥1440 px width:** Four-column analytics cards appear above the timeline summarizing readiness (`Success`), queue load (`Accent`), and telemetry alerts (`Danger`).
- **1024–1439 px width:** Cards collapse into a two-by-two grid and the context drawer becomes modal.
- **≤1023 px width:** Navigation rail condenses into an icon-only strip; mission canvas toggles between timeline and board via segmented control.

## Workflow Alignment

### 000-Style Call Handling & PRRC Roles
1. **Initial Triage (000 Call-Taker analogue → PRRC *Incident Intake Specialist*):** Incoming emergency calls populate the *Live Ops* timeline. Intake specialists capture key metadata (location, caller state, hazard category) through a quick-entry form. This feeds the `TaskingOrder` metadata and sets initial priority.
2. **Dispatch Decision (000 Dispatcher analogue → PRRC *Tasking Officer*):** Tasking officers review enriched call tiles, confirm capability requirements, and allocate responders via the Kanban board. The interface issues recommendations powered by `hq_command.tasking_engine.schedule_tasks_for_field_units`.
3. **Ongoing Coordination (000 Supervisor analogue → PRRC *Operations Supervisor*):** Supervisors monitor telemetry tiles (battery, environmental sensors) supplied by `hq_command.analytics.summarize_field_telemetry`, adjust task priorities, and authorize escalations when thresholds cross.
4. **Post-incident Review (000 Quality Assurance analogue → PRRC *Audit Lead*):** Audit leads access immutable event summaries, confirm responder acknowledgements, and annotate lessons learned before closing out incidents.

### Task Flow Summary
```
Incoming 000 Call → Intake Form → Task Draft (min units / capabilities) →
Tasking Engine Recommendation → Officer Review → Assignment Push to FieldOps →
Telemetry Feedback Loop → Escalation/Audit Entries → After Action Archive
```

## Styling Decisions
- **Color & Contrast:** Leverage FieldOps palette tokens: `Primary`/`Primary Light` for actionable surfaces, `Secondary` (`#1F6F43`) for logistics and resource availability indicators, and `Surface Dark` for telemetry cards when sensor feeds degrade.
- **Typography:** Maintain Noto Sans typographic scale (20 pt bold headers, 16 pt semibold subheads, 14 pt body). Navigation labels remain uppercase with letter-spacing for glove readability.
- **Spacing & Components:** Follow the 8 px spacing grid and minimum 44 px control height. Use pill-shaped status chips with token-specific colors (`Success` for synchronized responders, `Danger` for escalations, `Accent` for pending acknowledgements).
- **Feedback Patterns:** Sync indicator animations share FieldOps' tri-state color cycle (Accent → Success → Danger) to keep mental models consistent. Keyboard focus rings adopt the `#7AC1FF` outline offset 2 px outward.

## Data Contracts & Module Touchpoints

### Tasking Payloads
- **Source:** `hq_command.tasking_engine.TaskingOrder`
- **Fields:**
  - `task_id` *(str, required)* – unique identifier referenced in audit and telemetry streams.
  - `priority` *(int ≥0)* – drives scheduling order; `≥4` flags for escalation review.
  - `capabilities_required` *(frozenset[str])* – matched against responder capabilities.
  - `min_units` / `max_units` *(int)* – staffing bounds that influence escalation when unmet.
  - `location` *(str | None)* – cross-referenced with responder proximity.
  - `metadata` *(Mapping[str, Any])* – arbitrary context stored for audit exports.

### Responder Status
- **Source:** `hq_command.tasking_engine.ResponderStatus`
- **Fields:**
  - `unit_id` *(str, required)* – matches FieldOps device roster.
  - `capabilities` *(frozenset[str])* – skill tags (e.g., `HAZMAT`, `ALS`).
  - `status` *("available" | "busy" | "offline")* – governs scheduling eligibility.
  - `max_concurrent_tasks` *(int ≥1)* and `current_tasks` *(MutableSequence[str])* – enforce workload caps.
  - `fatigue` *(float ≥0)* – influences assignment scoring.
  - `location` *(str | None)* – used for proximity boosts.
  - `metadata` *(Mapping[str, Any])* – additional roster notes.

### Scheduling Result Contract
- **Generator:** `hq_command.tasking_engine.schedule_tasks_for_field_units`
- **Shape:**
  - `status` *("complete" | "escalated")* – top-level orchestration state.
  - `assignments` *(list[dict])* – includes `task_id`, `unit_id`, `score`, `priority` for downstream sync.
  - `deferred` *(list[str])* – task IDs waiting for capacity.
  - `escalated` *(list[str])* – tasks needing supervisory action.
  - `audit` *(dict)* – timestamp (`generated_at`), counts (`tasks_processed`, `units_considered`, `assignments_made`, `deferred_tasks`, `escalated_tasks`).

### Telemetry Analytics Payloads
- **Processor:** `hq_command.analytics.summarize_field_telemetry`
- **Expected Input:** Mapping with keys `status`, `collected_at`, and nested `metrics` containing `sensors`, `events`, `queues` collections.
- **Output Contract:**
  - `source_status`, `collected_at` – direct snapshot echoes.
  - `overall_readiness` *(str)* and `readiness_score` *(int)* – readiness KPI.
  - `alerts` *(list[str])* – concatenated sensor/queue alerts.
  - `sensor_states`, `sensor_trends`, `queue_health`, `event_overview` – dictionaries keyed by sensor/queue names.
  - `notes` *(list[str])* – appended context, including alert summaries.

### Audit Feed Integration
- **Sources:**
  - Scheduling `audit` dict (above).
  - Timeline annotations from the *Live Ops* panel.
  - Manual notes appended during After Action workflows.
- **Consumers:** Bridge event store and QA review exports. Ensure every timeline action references `task_id` or call identifier for traceability.

## Wireframes

### Live Ops Dashboard (Desktop)
```
┌──────────────────────────────────────────────────────────────────────────────┐
│NAV│ Global Status Bar [Sync ▣][Escalations ▲][Comms ●●]                      │
│   ├──────────────────────────────────────────────────────────────────────────┤
│   │ Readiness Cards │ Queue Health │ Sensor Alerts │ Mission Tempo │        │
│   ├──────────────────────────────────────────────────────────────────────────┤
│   │ Situational Timeline (000 Intake → Dispatch → Updates)      │ Task/Resp │
│   │ [Time][Priority Pill][Incident Summary][Actions ▷]          │  Kanban   │
│   │ [Time][Telemetry Alert][Sensor Detail][Open Drawer]         │  Columns  │
│   │                                                            │ (Queued)  │
│   │                                                            │ (Active)  │
│   │                                                            │ (Monitoring)
│   │                                                            │ (After Action)
│   ├──────────────────────────────────────────────────────────────────────────┤
│   │ Context Drawer (Transcript, Responder Roster, Analytics Deep Dive)       │
└───┴──────────────────────────────────────────────────────────────────────────┘
```

### Task Assignment Modal (<=1023 px)
```
┌─────────────────────────────┐
│ Incident Intake Summary     │
├─────────────────────────────┤
│ Priority     ▣▣▣▢           │
│ Capabilities HAZMAT, ALS    │
│ Recommended Units (score)   │
│  • Unit-17  (235)           │
│  • Unit-04  (228)           │
├─────────────────────────────┤
│ Actions: [Assign Primary] [Escalate] [Hold]  (Primary/Accent/Danger tokens) │
└─────────────────────────────┘
```

## Implementation Notes
- Centralize theme tokens via a shared palette module to ensure parity with FieldOps. Consider importing color constants from `fieldops.gui.styles.theme` for single-source-of-truth management.
- Hook timeline entries to data contract adapters so every UI interaction produces compliant `TaskingOrder` or telemetry payloads before invoking the scheduling/analytics modules.
- Extend audit exports to stream both assignment audit dicts and operator annotations into Bridge’s immutable log for compliance.

