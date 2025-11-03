"""Role-based access control utilities for HQ Command."""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Iterator, Mapping, MutableMapping, Sequence

Permission = str


@dataclass(frozen=True)
class RoleDefinition:
    """Immutable description of a role and its capabilities."""

    identifier: str
    display_name: str
    permissions: FrozenSet[Permission]
    description: str = ""
    navigation_sections: Sequence[str] = ()
    default_section: str | None = None

    def allows(self, permission: Permission) -> bool:
        """Return ``True`` when the permission is granted by this role."""

        return permission in self.permissions


class RoleRegistry:
    """Registry mapping role identifiers to their definitions."""

    def __init__(
        self,
        definitions: Iterable[RoleDefinition] | None = None,
        *,
        default_role: str | None = None,
    ) -> None:
        self._roles: MutableMapping[str, RoleDefinition] = {}
        self._default_role: str | None = default_role

        if definitions is not None:
            for definition in definitions:
                self.register(definition)

        if self._default_role is None and self._roles:
            # Preserve insertion order so the first registered role becomes default.
            self._default_role = next(iter(self._roles))

    def register(self, definition: RoleDefinition) -> None:
        """Register a new role definition."""

        if definition.identifier in self._roles:
            raise ValueError(f"Role '{definition.identifier}' already registered")
        self._roles[definition.identifier] = definition
        if self._default_role is None:
            self._default_role = definition.identifier

    def get(self, identifier: str) -> RoleDefinition:
        """Return a role definition or raise ``KeyError`` if unknown."""

        try:
            return self._roles[identifier]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Unknown role identifier: {identifier}") from exc

    def has_role(self, identifier: str) -> bool:
        """Return ``True`` if the role identifier is registered."""

        return identifier in self._roles

    def roles(self) -> tuple[RoleDefinition, ...]:
        """Return all registered role definitions preserving insertion order."""

        return tuple(self._roles.values())

    def permission_matrix(self) -> Mapping[str, FrozenSet[Permission]]:
        """Return mapping of role identifier to its permissions."""

        return {identifier: role.permissions for identifier, role in self._roles.items()}

    @property
    def default_role(self) -> str:
        """Return the default role identifier."""

        if self._default_role is None:
            raise ValueError("Role registry is empty")
        return self._default_role

    def __iter__(self) -> Iterator[RoleDefinition]:
        return iter(self._roles.values())


class RoleContext:
    """Track assigned roles and the active context for an operator."""

    def __init__(
        self,
        registry: RoleRegistry,
        assigned_roles: Iterable[str] | None = None,
        *,
        active_role: str | None = None,
    ) -> None:
        self.registry = registry

        filtered_roles: list[str] = []
        if assigned_roles is not None:
            for role_id in assigned_roles:
                if registry.has_role(role_id):
                    if role_id not in filtered_roles:
                        filtered_roles.append(role_id)
        if not filtered_roles:
            filtered_roles.append(registry.default_role)

        if active_role and registry.has_role(active_role):
            if active_role not in filtered_roles:
                filtered_roles.append(active_role)
            self._active_role = active_role
        else:
            self._active_role = filtered_roles[0]

        self._assigned_roles: tuple[str, ...] = tuple(filtered_roles)

    @property
    def assigned_roles(self) -> tuple[str, ...]:
        """Return tuple of assigned role identifiers."""

        return self._assigned_roles

    @property
    def active_role_id(self) -> str:
        """Return identifier of the active role."""

        return self._active_role

    @property
    def active_role(self) -> RoleDefinition:
        """Return the active role definition."""

        return self.registry.get(self._active_role)

    def switch_role(self, role_id: str) -> RoleDefinition:
        """Switch the active role, raising ``KeyError`` if unknown."""

        if not self.registry.has_role(role_id):
            raise KeyError(f"Unknown role identifier: {role_id}")
        if role_id not in self._assigned_roles:
            self._assigned_roles = (*self._assigned_roles, role_id)
        self._active_role = role_id
        return self.registry.get(role_id)

    def permissions_for_active_role(self) -> FrozenSet[Permission]:
        """Return permissions granted by the active role."""

        return self.active_role.permissions

    def effective_permissions(self) -> FrozenSet[Permission]:
        """Return the union of permissions across all assigned roles."""

        permissions: set[Permission] = set()
        for role_id in self._assigned_roles:
            permissions.update(self.registry.get(role_id).permissions)
        return frozenset(permissions)

    def is_permitted(self, permission: Permission) -> bool:
        """Return ``True`` if any assigned role grants the permission."""

        return permission in self.effective_permissions()

    def active_navigation_sections(self) -> tuple[str, ...]:
        """Return navigation sections available to the active role."""

        sections = tuple(self.active_role.navigation_sections)
        if sections:
            return sections
        return (self.active_role.default_section,) if self.active_role.default_section else ()

    def is_section_allowed(self, section_id: str) -> bool:
        """Return ``True`` when the active role can access the section."""

        return section_id in self.active_navigation_sections()


def build_default_role_definitions() -> tuple[RoleDefinition, ...]:
    """Return the canonical HQ Command role definitions."""

    return (
        RoleDefinition(
            identifier="incident_intake_specialist",
            display_name="Incident Intake Specialist",
            description="Handles call intake, caller triage, and metadata capture.",
            permissions=frozenset(
                {
                    "calls:create",
                    "calls:read",
                    "calls:update",
                    "tasks:read",
                    "responders:read",
                }
            ),
            navigation_sections=("live_ops",),
            default_section="live_ops",
        ),
        RoleDefinition(
            identifier="tasking_officer",
            display_name="Tasking Officer",
            description="Manages task queues and assignment workflows.",
            permissions=frozenset(
                {
                    "tasks:create",
                    "tasks:read",
                    "tasks:update",
                    "tasks:assign",
                    "responders:read",
                    "responders:update",
                    "telemetry:read",
                }
            ),
            navigation_sections=("live_ops", "task_board", "telemetry"),
            default_section="task_board",
        ),
        RoleDefinition(
            identifier="operations_supervisor",
            display_name="Operations Supervisor",
            description="Oversees operations, escalations, and analytics.",
            permissions=frozenset(
                {
                    "tasks:create",
                    "tasks:read",
                    "tasks:update",
                    "tasks:assign",
                    "tasks:override",
                    "tasks:escalate",
                    "responders:read",
                    "responders:update",
                    "responders:manage",
                    "telemetry:read",
                    "analytics:read",
                }
            ),
            navigation_sections=("live_ops", "task_board", "telemetry", "audit"),
            default_section="live_ops",
        ),
        RoleDefinition(
            identifier="audit_lead",
            display_name="Audit Lead",
            description="Conducts post-incident reviews and compliance checks.",
            permissions=frozenset(
                {
                    "calls:read",
                    "tasks:read",
                    "responders:read",
                    "telemetry:read",
                    "analytics:read",
                    "audit:read",
                    "reports:generate",
                    "data:export",
                }
            ),
            navigation_sections=("audit", "telemetry"),
            default_section="audit",
        ),
        RoleDefinition(
            identifier="administrator",
            display_name="Administrator",
            description="Configures system settings and manages operator access.",
            permissions=frozenset(
                {
                    "calls:create",
                    "calls:read",
                    "calls:update",
                    "calls:delete",
                    "tasks:create",
                    "tasks:read",
                    "tasks:update",
                    "tasks:delete",
                    "tasks:assign",
                    "responders:create",
                    "responders:read",
                    "responders:update",
                    "responders:delete",
                    "responders:manage",
                    "telemetry:read",
                    "analytics:read",
                    "audit:read",
                    "reports:generate",
                    "data:export",
                    "config:update",
                    "users:manage",
                }
            ),
            navigation_sections=("live_ops", "task_board", "telemetry", "audit", "admin"),
            default_section="admin",
        ),
    )


def build_default_role_registry() -> RoleRegistry:
    """Create a registry populated with the default role definitions."""

    return RoleRegistry(build_default_role_definitions(), default_role="tasking_officer")


def build_default_role_context(
    *,
    assigned_roles: Iterable[str] | None = None,
    active_role: str | None = None,
) -> RoleContext:
    """Create a ``RoleContext`` seeded with default definitions."""

    registry = build_default_role_registry()
    return RoleContext(registry, assigned_roles=assigned_roles, active_role=active_role)


__all__ = [
    "Permission",
    "RoleDefinition",
    "RoleRegistry",
    "RoleContext",
    "build_default_role_context",
    "build_default_role_definitions",
    "build_default_role_registry",
]
