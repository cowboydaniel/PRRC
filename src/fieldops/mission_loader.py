"""Mission package loading and manifest parsing utilities for FieldOps.

Phase 1 focuses on validating mission package archives and preparing their
contents for downstream workflows. This module now also owns manifest parsing
so the CLI and future FieldOps UI layers can rely on typed metadata instead of
unstructured dictionaries.
"""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple

try:  # pragma: no cover - exercised indirectly via YAML fixtures
    import yaml  # type: ignore
except Exception:  # pragma: no cover - dependency is optional at runtime
    yaml = None


class MissionPackageError(RuntimeError):
    """Raised when a mission package fails validation."""


class MissionManifestError(MissionPackageError):
    """Raised when a mission manifest cannot be parsed or validated."""


@dataclass(frozen=True)
class MissionContact:
    """Structured representation of a mission contact role."""

    role: str
    name: str
    callsign: str | None = None
    channel: str | None = None


@dataclass(frozen=True)
class MissionAttachment:
    """Metadata describing supporting mission artifacts."""

    name: str
    path: str
    media_type: str | None = None
    checksum: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class MissionManifest:
    """Normalized, strongly-typed mission manifest data."""

    mission_id: str
    name: str
    version: str
    summary: str | None
    created_at: datetime
    updated_at: datetime | None
    classification: str | None
    tags: tuple[str, ...]
    contacts: tuple[MissionContact, ...]
    attachments: tuple[MissionAttachment, ...]
    source_path: Path


def load_mission_package(package_path: Path) -> Dict[str, Any]:
    """Load and stage a mission package archive.

    The function verifies the archive exists, validates optional SHA256
    sidecar/signature files, and extracts supported archives (ZIP, TAR variants)
    into a staging directory that mimics Dell Rugged Extreme deployments.

    Args:
        package_path: Location of the mission package archive.

    Returns:
        A dictionary summarizing the package contents for UI presentation.

    Raises:
        FileNotFoundError: If ``package_path`` does not exist.
        MissionPackageError: If validation fails or the format is unsupported.
    """

    resolved_path = package_path.expanduser()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Mission package not found: {resolved_path}")
    if not resolved_path.is_file():
        raise MissionPackageError(
            f"Mission package must be a file: {resolved_path}"
        )

    archive_type, extractor = _resolve_extractor(resolved_path)
    checksum = _compute_sha256(resolved_path)
    _validate_sidecar_checksum(resolved_path, checksum)

    staging_dir = _resolve_staging_directory()
    extract_dir = _prepare_extract_directory(staging_dir, resolved_path, checksum)
    extracted_files = extractor(extract_dir)
    manifest = _discover_manifest(extract_dir)

    return {
        "package_path": str(resolved_path),
        "status": "staged",
        "archive_type": archive_type,
        "checksum": checksum,
        "staging_directory": str(extract_dir),
        "extracted_files": extracted_files,
        "extracted_file_count": len(extracted_files),
        "manifest": manifest,
    }


def load_mission_manifest(manifest_path: Path) -> MissionManifest:
    """Load and validate a mission manifest document."""

    resolved = manifest_path.expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Mission manifest not found: {resolved}")
    if not resolved.is_file():
        raise MissionManifestError(f"Mission manifest must be a file: {resolved}")

    document = _read_manifest_document(resolved)
    return _normalize_manifest(document, resolved)


def _discover_manifest(extracted_root: Path) -> MissionManifest | None:
    """Search ``extracted_root`` for a mission manifest."""

    manifest_candidates = [
        extracted_root / "manifest.json",
        extracted_root / "manifest.yaml",
        extracted_root / "manifest.yml",
        extracted_root / "mission_manifest.json",
        extracted_root / "mission_manifest.yaml",
        extracted_root / "mission_manifest.yml",
    ]

    for candidate in manifest_candidates:
        if candidate.exists():
            return load_mission_manifest(candidate)

    # Fall back to a recursive search for atypical package layouts.
    for path in extracted_root.rglob("*.json"):
        if path.name.lower().startswith("manifest"):
            return load_mission_manifest(path)
    for path in extracted_root.rglob("*.yml"):
        if path.name.lower().startswith("manifest") or path.name.lower().startswith("mission_manifest"):
            return load_mission_manifest(path)
    for path in extracted_root.rglob("*.yaml"):
        if path.name.lower().startswith("manifest") or path.name.lower().startswith("mission_manifest"):
            return load_mission_manifest(path)

    return None


def _read_manifest_document(path: Path) -> Dict[str, Any]:
    """Deserialize the manifest at ``path`` into a Python mapping."""

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - exercised via tests
            raise MissionManifestError(
                f"Invalid JSON manifest ({path.name}): {exc.msg}"
            ) from exc
    elif suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise MissionManifestError(
                "YAML manifest support requires the 'PyYAML' optional dependency"
            )
        try:
            data = yaml.safe_load(text)
        except Exception as exc:  # pragma: no cover - depends on PyYAML's error types
            raise MissionManifestError(
                f"Invalid YAML manifest ({path.name}): {exc}"
            ) from exc
    else:
        # Attempt JSON first, then YAML if installed.
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                raise MissionManifestError(
                    f"Unsupported manifest extension '{suffix}' and YAML support unavailable"
                )
            try:
                data = yaml.safe_load(text)
            except Exception as exc:  # pragma: no cover
                raise MissionManifestError(
                    f"Manifest {path.name} is not valid JSON or YAML: {exc}"
                ) from exc

    if not isinstance(data, dict):
        raise MissionManifestError(
            f"Manifest root must be a mapping, got {type(data).__name__}"
        )
    return data


def _normalize_manifest(document: Dict[str, Any], source: Path) -> MissionManifest:
    """Normalize manifest ``document`` into ``MissionManifest``."""

    mission_id = _require_string(document, "mission_id", source)
    name = _require_string(document, "name", source)
    version = _require_string(document, "version", source)
    summary = _optional_string(document, "summary")
    classification = _optional_string(document, "classification")

    created_at = _parse_datetime(
        _require_string(document, "created_at", source),
        "created_at",
        source,
    )
    updated_at_raw = document.get("updated_at")
    updated_at = _parse_datetime(updated_at_raw, "updated_at", source)

    tags_value = document.get("tags", [])
    if not isinstance(tags_value, Iterable) or isinstance(tags_value, (str, bytes)):
        raise MissionManifestError(
            f"Manifest tags must be an iterable of strings ({source.name})"
        )
    tags = tuple(
        tag
        for tag in (
            str(item).strip()
            for item in tags_value
        )
        if tag
    )

    contacts = _normalize_contacts(document.get("contacts"), source)
    attachments = _normalize_attachments(document.get("attachments"), source)

    return MissionManifest(
        mission_id=mission_id,
        name=name,
        version=version,
        summary=summary,
        created_at=created_at,
        updated_at=updated_at,
        classification=classification,
        tags=tags,
        contacts=contacts,
        attachments=attachments,
        source_path=source,
    )


def _require_string(data: Dict[str, Any], field: str, source: Path) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MissionManifestError(
            f"Manifest field '{field}' must be a non-empty string ({source.name})"
        )
    return value.strip()


def _optional_string(data: Dict[str, Any], field: str) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MissionManifestError(
            f"Manifest field '{field}' must be a string when provided"
        )
    stripped = value.strip()
    return stripped or None


def _parse_datetime(value: Any, field: str, source: Path) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MissionManifestError(
            f"Manifest field '{field}' must be an ISO 8601 string ({source.name})"
        )
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise MissionManifestError(
            f"Manifest field '{field}' is not a valid ISO 8601 timestamp"
        ) from exc


def _normalize_contacts(value: Any, source: Path) -> tuple[MissionContact, ...]:
    if value is None:
        return tuple()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise MissionManifestError(
            f"Manifest contacts must be a list of mappings ({source.name})"
        )

    contacts: list[MissionContact] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise MissionManifestError(
                f"Manifest contact at index {idx} must be a mapping ({source.name})"
            )
        role = _require_nested_string(item, "role", source, f"contacts[{idx}]")
        name = _require_nested_string(item, "name", source, f"contacts[{idx}]")
        callsign = _optional_nested_string(item, "callsign", source, f"contacts[{idx}]")
        channel = _optional_nested_string(item, "channel", source, f"contacts[{idx}]")
        contacts.append(
            MissionContact(
                role=role,
                name=name,
                callsign=callsign,
                channel=channel,
            )
        )
    return tuple(contacts)


def _normalize_attachments(value: Any, source: Path) -> tuple[MissionAttachment, ...]:
    if value is None:
        return tuple()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise MissionManifestError(
            f"Manifest attachments must be a list of mappings ({source.name})"
        )

    attachments: list[MissionAttachment] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise MissionManifestError(
                f"Manifest attachment at index {idx} must be a mapping ({source.name})"
            )
        name = _require_nested_string(item, "name", source, f"attachments[{idx}]")
        path_value = _require_nested_string(item, "path", source, f"attachments[{idx}]")
        media_type = _optional_nested_string(item, "media_type", source, f"attachments[{idx}]")
        checksum = _optional_nested_string(item, "checksum", source, f"attachments[{idx}]")
        size_value = item.get("size_bytes")
        if size_value is not None:
            if isinstance(size_value, bool) or not isinstance(size_value, int):
                raise MissionManifestError(
                    f"Manifest attachment 'size_bytes' must be an integer ({source.name})"
                )
            if size_value < 0:
                raise MissionManifestError(
                    "Manifest attachment 'size_bytes' must be non-negative"
                )
        attachments.append(
            MissionAttachment(
                name=name,
                path=path_value,
                media_type=media_type,
                checksum=checksum,
                size_bytes=size_value,
            )
        )
    return tuple(attachments)


def _require_nested_string(
    data: Dict[str, Any],
    field: str,
    source: Path,
    context: str,
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MissionManifestError(
            f"Manifest field '{context}.{field}' must be a non-empty string ({source.name})"
        )
    return value.strip()


def _optional_nested_string(
    data: Dict[str, Any],
    field: str,
    source: Path,
    context: str,
) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MissionManifestError(
            f"Manifest field '{context}.{field}' must be a string when provided ({source.name})"
        )
    stripped = value.strip()
    return stripped or None


def _resolve_staging_directory() -> Path:
    """Return (and create) the FieldOps staging directory."""

    custom = os.getenv("PRRC_FIELDOPS_STAGING_DIR")
    base_dir = Path(custom) if custom else Path.home() / ".prrc" / "fieldops" / "staging"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _prepare_extract_directory(staging_root: Path, archive_path: Path, checksum: str) -> Path:
    """Compute a unique directory for the extracted package contents."""

    unique_suffix = checksum[:8] or uuid.uuid4().hex[:8]
    candidate = staging_root / f"{archive_path.stem}-{unique_suffix}"
    if candidate.exists():
        # Avoid reusing stale data by creating a new directory with a UUID.
        candidate = staging_root / f"{archive_path.stem}-{uuid.uuid4().hex[:8]}"
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _resolve_extractor(archive_path: Path) -> Tuple[str, Callable[[Path], list[str]]]:
    """Determine the archive type and return an extractor callback."""

    if zipfile.is_zipfile(archive_path):
        return "zip", lambda dest: _extract_zip(archive_path, dest)
    if tarfile.is_tarfile(archive_path):
        return "tar", lambda dest: _extract_tar(archive_path, dest)
    raise MissionPackageError(f"Unsupported mission package format: {archive_path}")


def _compute_sha256(file_path: Path) -> str:
    """Compute the SHA256 checksum for ``file_path``."""

    sha256 = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _validate_sidecar_checksum(archive_path: Path, actual_checksum: str) -> None:
    """Validate checksum/signature sidecar files if present."""

    expected = None
    for extension in (".sha256", ".sig"):
        candidate = archive_path.with_name(archive_path.name + extension)
        if candidate.exists():
            data = candidate.read_text(encoding="utf-8").strip()
            if not data:
                raise MissionPackageError(f"Empty checksum file: {candidate}")
            # Sidecar files may embed an algorithm prefix like ``sha256:``.
            if ":" in data:
                algorithm, _, digest = data.partition(":")
                if algorithm.lower() != "sha256":
                    raise MissionPackageError(
                        f"Unsupported checksum algorithm '{algorithm}' in {candidate}"
                    )
                expected = digest.strip()
            else:
                expected = data.split()[0]
            break

    if expected and expected.lower() != actual_checksum.lower():
        raise MissionPackageError(
            "Mission package checksum validation failed."
        )


def _extract_zip(archive_path: Path, destination: Path) -> list[str]:
    """Extract a ZIP archive and return the extracted file paths."""

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)
        members = archive.namelist()
    return _list_files(destination, members)


def _extract_tar(archive_path: Path, destination: Path) -> list[str]:
    """Extract a TAR archive and return the extracted file paths."""

    def is_within_directory(directory: Path, target: Path) -> bool:
        try:
            target.relative_to(directory)
            return True
        except ValueError:
            return False

    members: Iterable[tarfile.TarInfo]
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        for member in members:
            if member.isdir():
                continue
            member_path = destination / member.name
            if not is_within_directory(destination, member_path.resolve()) or ".." in Path(member.name).parts:
                raise MissionPackageError(
                    f"Unsafe path detected in tar archive: {member.name}"
                )
        archive.extractall(destination)
    return _list_files(destination, [m.name for m in members if m.isfile()])


def _list_files(root: Path, archive_members: Iterable[str]) -> list[str]:
    """Return a sorted list of extracted files relative to ``root``."""

    files: set[str] = set()
    for member in archive_members:
        member_path = (root / member).resolve()
        if member_path.is_file():
            files.add(member_path.relative_to(root).as_posix())
    # Include any additional files created during extraction (e.g., nested dirs).
    for path in root.rglob("*"):
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return sorted(files)
