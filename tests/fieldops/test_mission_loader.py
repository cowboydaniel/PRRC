"""Tests for the FieldOps mission loader."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from fieldops.mission_loader import (
    MissionPackageError,
    _compute_sha256,
    load_mission_package,
)


def _write_sidecar(path: Path) -> str:
    checksum = _compute_sha256(path)
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(checksum, encoding="utf-8")
    return checksum


def test_zip_package_validates_and_extracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "mission.zip"
    file_1 = tmp_path / "intel" / "manifest.txt"
    file_1.parent.mkdir()
    file_1.write_text("field intel", encoding="utf-8")

    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(file_1, arcname="intel/manifest.txt")

    checksum = _write_sidecar(archive)

    summary = load_mission_package(archive)

    assert summary["status"] == "staged"
    assert summary["archive_type"] == "zip"
    assert summary["checksum"] == checksum

    staged_dir = Path(summary["staging_directory"])
    assert staged_dir.exists()
    staged_manifest = staged_dir / "intel" / "manifest.txt"
    assert staged_manifest.read_text(encoding="utf-8") == "field intel"
    assert "intel/manifest.txt" in summary["extracted_files"]


def test_tar_package_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "package.tar.gz"
    inner_file = tmp_path / "payload" / "data.json"
    inner_file.parent.mkdir()
    inner_file.write_text("{}", encoding="utf-8")

    with tarfile.open(archive, "w:gz") as handle:
        handle.add(inner_file, arcname="payload/data.json")

    _write_sidecar(archive)

    summary = load_mission_package(archive)

    assert summary["archive_type"] == "tar"
    staged_dir = Path(summary["staging_directory"])
    assert (staged_dir / "payload" / "data.json").exists()


def test_missing_package_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_mission_package(tmp_path / "missing.zip")


def test_invalid_checksum_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "bad.zip"
    sample = tmp_path / "doc.txt"
    sample.write_text("payload", encoding="utf-8")

    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(sample, arcname="doc.txt")

    sidecar = archive.with_name(archive.name + ".sha256")
    sidecar.write_text("deadbeef", encoding="utf-8")

    with pytest.raises(MissionPackageError):
        load_mission_package(archive)


def test_signature_sidecar_with_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "signed.tar"
    payload = tmp_path / "config.ini"
    payload.write_text("[core]", encoding="utf-8")

    with tarfile.open(archive, "w") as handle:
        handle.add(payload, arcname="config.ini")

    checksum = _compute_sha256(archive)
    sidecar = archive.with_name(archive.name + ".sig")
    sidecar.write_text(f"sha256:{checksum}\n", encoding="utf-8")

    summary = load_mission_package(archive)

    assert summary["checksum"] == checksum


def test_directory_path_rejected(tmp_path: Path) -> None:
    directory_package = tmp_path / "folder"
    directory_package.mkdir()

    with pytest.raises(MissionPackageError):
        load_mission_package(directory_package)
