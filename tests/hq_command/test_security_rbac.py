from hq_command.security import (
    RoleContext,
    build_default_role_context,
    build_default_role_registry,
)


def test_default_role_registry_contains_expected_roles() -> None:
    registry = build_default_role_registry()
    role_ids = {role.identifier for role in registry.roles()}
    assert {
        "incident_intake_specialist",
        "tasking_officer",
        "operations_supervisor",
        "audit_lead",
        "administrator",
    }.issubset(role_ids)

    intake = registry.get("incident_intake_specialist")
    assert "calls:create" in intake.permissions
    assert intake.default_section == "live_ops"


def test_role_context_switching_and_permissions() -> None:
    registry = build_default_role_registry()
    context = RoleContext(
        registry,
        assigned_roles=("incident_intake_specialist", "tasking_officer"),
        active_role="incident_intake_specialist",
    )

    assert context.active_role.identifier == "incident_intake_specialist"
    assert context.is_permitted("calls:create")
    assert context.is_permitted("tasks:assign")  # From tasking officer role
    assert context.is_section_allowed("live_ops")
    assert not context.is_section_allowed("admin")

    context.switch_role("tasking_officer")
    assert context.active_role.identifier == "tasking_officer"
    assert context.is_section_allowed("task_board")


def test_role_context_defaults_when_roles_unknown() -> None:
    context = build_default_role_context(assigned_roles=("unknown-role",))
    assert context.active_role.identifier == "tasking_officer"
    assert "tasks:assign" in context.effective_permissions()
