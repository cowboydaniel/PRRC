# FieldOps GUI PySide6 Styling Proposal

## Design Principles
- Optimize for offline-first mission work with clear sync/conflict visibility, glove-friendly targets, and telemetry awareness aligned with the Phase 2.5 roadmap goals.

## Color System
| Role | Hex | Usage Guidelines |
| --- | --- | --- |
| Primary | `#0C3D5B` | Navigation rail, primary buttons, headers. |
| Primary Light | `#145A80` | Hover/focus states. |
| Primary Contrast | `#E8F4FF` | Text/icons over primary surfaces. |
| Secondary | `#1F6F43` | Mission status pills, confirmation cues. |
| Accent | `#F6A000` | Attention-grabbing sync prompts, warning banners. |
| Success | `#3FA776` | Sync-complete indicators, resolved conflicts. |
| Danger | `#C4373B` | Failed sync, tampered package alerts. |
| Neutral 900 | `#121417` | Primary text on light surfaces. |
| Neutral 700 | `#2D3035` | Secondary text/iconography. |
| Neutral 200 | `#C9CFD6` | Borders, dividers, disabled controls. |
| Surface Light | `#F5F7FA` | Mission brief panels, forms. |
| Surface Dark | `#1B1E22` | Optional high-contrast telemetry cards. |

All primary/secondary foreground combinations maintain ≥4.5:1 contrast to support bright sunlight and low-light modes; pair `Neutral 900` text on `Surface Light`, and `Primary Contrast` text on `Primary/Secondary` surfaces.

## Typography & Spacing
- Adopt an 8 px spacing grid for consistent touch interactions (minimum control height 44 px, horizontal padding ≥16 px).
- Use **Noto Sans** (or Qt fallback) with styles: 20 pt Bold (section headers), 16 pt SemiBold (card titles), 14 pt Regular (body text), 12 pt Medium (metadata).
- Apply uppercase, letter-spaced labels for navigation rail buttons to improve glove-friendly readability.

## Component Styling

### Navigation Rail & Top Bar
- Rail: 72 px wide, Primary background, white icons with 60% opacity when inactive; focus/hover adds a Primary Light pill.
- Top bar: Neutral 900 text on Surface Light; reserve the right side for sync/battery badges using Accent and Success/Danger tokens.

### Mission Intake Workspace
- Tab bar (Briefing, Files, Comms): Surface Light background with a Primary underline for the active tab.
- Metadata cards: Rounded 8 px corners, subtle drop shadow (`rgba(12, 61, 91, 0.12)`), status chips matching mission verdict colors.

### Operational Logging Forms
- Field group frames with a left-accent stripe (Primary) to reinforce context.
- Attachment drop zones: dashed Neutral 200 border, Accent hover glow.
- Offline queue list rows tinted Surface Dark with Primary Contrast text when pending sync.

### Task Dashboard
- Kanban columns use Secondary headers; cards show priority stripes (Danger, Accent, Success).
- Offline badge uses an Accent background with Neutral 900 text; reconnection merges animate via subtle opacity fades.

### Telemetry
- Card grid with Surface Dark backgrounds and luminous Success/Accent progress arcs; degrade gracefully by dimming cards and overlaying a Neutral 200 pattern when telemetry is unavailable.

### Settings & Hardware Tools
- Tool tiles sized 140×140 px with iconography; calibration actions use Secondary, diagnostics use Primary.
- Confirmation dialogs: Surface Light background, Primary button (affirm), Neutral 200 outlined cancel.

## Interaction & Feedback
- Sync indicator: animated bar beneath top bar cycling between Accent (syncing), Success (complete), Danger (failed).
- Conflict resolution dialog: multi-step wizard with a timeline indicator using Primary/Accent segments.
- Keyboard focus outlines: 3 px `#7AC1FF` (accessible focus ring) offset 2 px outward.

## PySide6 Implementation Notes
- Centralize palette in a `QPalette` plus a custom Qt Style Sheet module (`styles/theme.py`) exposing helper functions to apply tokens to widgets.
- Build reusable widget subclasses (`MissionStatusBadge`, `SyncBanner`, `TelemetryCard`) to encapsulate complex styling and state transitions.
- Provide light/dark mode toggles by swapping palette constants while preserving contrast ratios.
- Bundle SVG iconography and convert to `QIcon` with `QIcon.addPixmap` to support high DPI on Dell Rugged displays.
