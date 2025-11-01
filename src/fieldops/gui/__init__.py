"""Offline-first FieldOps GUI foundation exports."""
from __future__ import annotations

try:  # pragma: no cover - import guard for optional PySide6 runtime
    from .app import FieldOpsMainWindow, LocalEchoSyncAdapter, launch_app
except Exception as exc:  # pragma: no cover - only triggered when PySide6 missing
    _IMPORT_ERROR = exc

    class _UnavailableGUI:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PySide6 is required to use the FieldOps GUI components"
            ) from _IMPORT_ERROR

    def launch_app(*_args, **_kwargs):
        raise RuntimeError(
            "PySide6 is required to launch the FieldOps GUI"
        ) from _IMPORT_ERROR

    FieldOpsMainWindow = _UnavailableGUI  # type: ignore[assignment]
    LocalEchoSyncAdapter = _UnavailableGUI  # type: ignore[assignment]
from .controller import FieldOpsGUIController, SyncAdapter
from .state import (
    ConflictPrompt,
    FieldOpsGUIState,
    GPSFix,
    MissionAttachmentLink,
    MissionBriefing,
    MissionContactCard,
    MissionQuickLinks,
    MissionWorkspaceState,
    MeshLink,
    MeshTopology,
    OperationalLogDraft,
    OperationalLogFormState,
    PhotoAttachmentDraft,
    OfflineOperation,
    ResourceRequestBoardState,
    ResourceRequestCard,
    SyncResult,
    SyncState,
    TaskAssignmentCard,
    TaskDashboardState,
    default_operational_log_form,
    empty_mission_workspace,
    empty_resource_board,
    empty_task_dashboard,
)
from .styles import (
    COLOR_TOKENS,
    TYPOGRAPHY,
    ComponentStyles,
    ColorToken,
    TypographyToken,
    build_palette,
    component_styles,
    focus_ring_stylesheet,
    HORIZONTAL_PADDING_PX,
    MIN_CONTROL_HEIGHT_PX,
    SPACING_GRID_PX,
)

__all__ = [
    "FieldOpsMainWindow",
    "LocalEchoSyncAdapter",
    "launch_app",
    "FieldOpsGUIController",
    "SyncAdapter",
    "ConflictPrompt",
    "FieldOpsGUIState",
    "GPSFix",
    "MissionAttachmentLink",
    "MissionBriefing",
    "MissionContactCard",
    "MissionQuickLinks",
    "MissionWorkspaceState",
    "MeshLink",
    "MeshTopology",
    "OperationalLogDraft",
    "OperationalLogFormState",
    "PhotoAttachmentDraft",
    "OfflineOperation",
    "ResourceRequestBoardState",
    "ResourceRequestCard",
    "SyncResult",
    "SyncState",
    "TaskAssignmentCard",
    "TaskDashboardState",
    "default_operational_log_form",
    "empty_mission_workspace",
    "empty_resource_board",
    "empty_task_dashboard",
    "COLOR_TOKENS",
    "ComponentStyles",
    "ColorToken",
    "TYPOGRAPHY",
    "TypographyToken",
    "build_palette",
    "component_styles",
    "focus_ring_stylesheet",
    "HORIZONTAL_PADDING_PX",
    "MIN_CONTROL_HEIGHT_PX",
    "SPACING_GRID_PX",
]

