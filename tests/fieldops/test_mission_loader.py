"""Tests for the FieldOps mission loader."""

from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from fieldops.mission_loader import (
    MissionAttachment,
    MissionManifest,
    MissionManifestError,
    MissionPackageError,
    _compute_sha256,
    load_mission_manifest,
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


def test_valid_package_persisted_to_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_root = tmp_path / "staging"
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))
    monkeypatch.setenv("PRRC_FIELDOPS_CACHE_DIR", str(cache_root))

    archive = tmp_path / "mission.zip"
    manifest = {
        "mission_id": "fs-4481",
        "name": "Flooded Substation Rescue",
        "version": "2024.04",
        "created_at": "2024-04-12T13:15:00Z",
    }

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "briefing.txt").write_text("critical intel", encoding="utf-8")

    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("manifest.json", json.dumps(manifest))
        handle.write(docs_dir / "briefing.txt", arcname="docs/briefing.txt")

    checksum = _write_sidecar(archive)

    summary = load_mission_package(archive)

    cache_dir = Path(summary["cache_directory"])
    assert cache_dir.exists()
    assert cache_dir.parent == cache_root
    # Directory naming should incorporate the mission identifier.
    assert cache_dir.name.startswith("fs-4481")
    assert summary["cached_files"] == sorted(["docs/briefing.txt", "manifest.json"])
    assert summary["cached_file_count"] == 2
    assert (cache_dir / "docs" / "briefing.txt").read_text(encoding="utf-8") == "critical intel"
    assert summary["checksum"] == checksum


def test_tampered_package_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_root = tmp_path / "staging"
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))
    monkeypatch.setenv("PRRC_FIELDOPS_CACHE_DIR", str(cache_root))

    archive = tmp_path / "tampered.zip"
    sample_file = tmp_path / "doc.txt"
    sample_file.write_text("payload", encoding="utf-8")

    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(sample_file, arcname="doc.txt")

    sidecar = archive.with_name(archive.name + ".sha256")
    sidecar.write_text("deadbeef", encoding="utf-8")

    with pytest.raises(MissionPackageError):
        load_mission_package(archive)

    assert not cache_root.exists()


def test_unsupported_package_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_root = tmp_path / "staging"
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))
    monkeypatch.setenv("PRRC_FIELDOPS_CACHE_DIR", str(cache_root))

    archive = tmp_path / "package.rar"
    archive.write_bytes(b"not really an archive")

    with pytest.raises(MissionPackageError):
        load_mission_package(archive)

    assert not cache_root.exists()


def test_directory_path_rejected(tmp_path: Path) -> None:
    directory_package = tmp_path / "folder"
    directory_package.mkdir()

    with pytest.raises(MissionPackageError):
        load_mission_package(directory_package)


def test_manifest_json_parsed_into_typed_structures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "mission.zip"
    manifest = {
        "mission_id": "fs-4481",
        "name": "Flooded Substation Rescue",
        "version": "2024.04",
        "summary": "Stabilize the grid and evac trapped technicians.",
        "classification": "SECRET//NOFORN",
        "created_at": "2024-04-12T13:15:00Z",
        "updated_at": "2024-04-12T14:00:00+00:00",
        "tags": ["rescue", "power"],
        "contacts": [
            {
                "role": "Incident Commander",
                "name": "Lt. C. Morales",
                "callsign": "RIVER-6",
                "channel": "hailing-1",
            }
        ],
        "attachments": [
            {
                "name": "Substation Layout",
                "path": "intel/layout.pdf",
                "media_type": "application/pdf",
                "size_bytes": 2048,
            }
        ],
    }

    intel_dir = tmp_path / "intel"
    intel_dir.mkdir()
    (intel_dir / "layout.pdf").write_bytes(b"%PDF-1.7\n")

    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("manifest.json", json.dumps(manifest))
        handle.write(intel_dir / "layout.pdf", arcname="intel/layout.pdf")

    _write_sidecar(archive)

    summary = load_mission_package(archive)
    manifest_obj = summary["manifest"]

    assert isinstance(manifest_obj, MissionManifest)
    assert manifest_obj.mission_id == "fs-4481"
    assert manifest_obj.tags == ("rescue", "power")
    assert manifest_obj.contacts[0].callsign == "RIVER-6"
    assert manifest_obj.attachments[0] == MissionAttachment(
        name="Substation Layout",
        path="intel/layout.pdf",
        media_type="application/pdf",
        checksum=None,
        size_bytes=2048,
    )
    assert manifest_obj.source_path.name == "manifest.json"


def test_manifest_yaml_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml = pytest.importorskip("yaml")

    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "mission.tar"
    manifest = {
        "mission_id": "dl-77",
        "name": "Dam Leak Assessment",
        "version": "1.0",
        "created_at": "2024-03-01T09:00:00Z",
    }

    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with tarfile.open(archive, "w") as handle:
        handle.add(manifest_path, arcname="manifest.yaml")

    _write_sidecar(archive)

    summary = load_mission_package(archive)
    manifest_obj = summary["manifest"]
    assert isinstance(manifest_obj, MissionManifest)
    assert manifest_obj.name == "Dam Leak Assessment"
    assert manifest_obj.created_at.isoformat() == "2024-03-01T09:00:00+00:00"


def test_invalid_manifest_surfaces_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging_root = tmp_path / "staging"
    monkeypatch.setenv("PRRC_FIELDOPS_STAGING_DIR", str(staging_root))

    archive = tmp_path / "mission_invalid.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "manifest.json",
            json.dumps({"name": "Missing Fields"}),
        )

    _write_sidecar(archive)

    with pytest.raises(MissionManifestError) as excinfo:
        load_mission_package(archive)
    assert "mission_id" in str(excinfo.value)

    # Ensure direct loader surfaces the same validation error context.
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"version": "0.0"}), encoding="utf-8")
    with pytest.raises(MissionManifestError):
        load_mission_manifest(manifest_path)
