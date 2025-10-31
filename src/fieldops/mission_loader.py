"""Mission package loading utilities for FieldOps.

Phase 1 focuses on file validation and staging the archive contents. The
implementation deliberately keeps crypto lightweight by trusting local SHA256
sidecar files until Dell Rugged hardware integrations introduce a full signing
pipeline.
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple


class MissionPackageError(RuntimeError):
    """Raised when a mission package fails validation."""


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

    return {
        "package_path": str(resolved_path),
        "status": "staged",
        "archive_type": archive_type,
        "checksum": checksum,
        "staging_directory": str(extract_dir),
        "extracted_files": extracted_files,
        "extracted_file_count": len(extracted_files),
    }


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
