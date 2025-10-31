# FieldOps Mission Package Schema and Validation Pipeline

FieldOps mission packages bundle planning material, manifests, and attachments
into a single archive that can be staged on Dell Rugged deployments before
syncing with HQ services. This document explains what the loader validates and
how to author packages that pass automated checks.

## Archive expectations

Mission packages are supplied as `.zip` or `.tar` (including gzip/bzip2
variants) archives. The loader rejects directories or other formats.

Each archive should include the mission manifest at its root. The loader scans
for these canonical filenames before falling back to a recursive search:

- `manifest.json`
- `manifest.yaml` / `manifest.yml`
- `mission_manifest.json`
- `mission_manifest.yaml` / `mission_manifest.yml`

Additional payload files (maps, briefs, imagery, etc.) may live in nested
folders and will be cached alongside the manifest metadata.

### Checksum sidecars

If a checksum sidecar is present, its digest must match the archive contents
before extraction proceeds. The loader inspects `<archive>.sha256` and
`<archive>.sig` files and accepts either raw hexadecimal digests or strings with
an algorithm prefix (for example `sha256:<digest>`). Any other algorithm name or
an empty sidecar will fail validation.

## Staging and cache layout

Archives are extracted to a staging directory before being persisted into a
cache for FieldOps clients. Both locations default to the user's home directory
but can be overridden with environment variables:

| Purpose | Default | Override |
| --- | --- | --- |
| Staging extracted archives | `~/.prrc/fieldops/staging` | `PRRC_FIELDOPS_STAGING_DIR` |
| Persisted payload cache | `~/.prrc/fieldops/cache` | `PRRC_FIELDOPS_CACHE_DIR` |

The cache directory name is derived from the manifest `mission_id`, `version`,
the original archive name, and its SHA256 checksum. Components are sanitized so
cached payloads remain filesystem safe.

## Manifest schema

The manifest provides structured metadata for downstream systems. The loader
normalizes manifests into the `MissionManifest` dataclass and enforces the
following fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `mission_id` | string | ✅ | Stable identifier used when persisting cache entries. |
| `name` | string | ✅ | Human-readable mission title. |
| `version` | string | ✅ | Semantic or incremental version of the package. |
| `summary` | string | Optional | Short description for mission overviews. |
| `classification` | string | Optional | Security marking applied to mission data. |
| `created_at` | ISO 8601 string | ✅ | Creation timestamp. `Z` suffixes are treated as UTC. |
| `updated_at` | ISO 8601 string | Optional | Last modification timestamp. |
| `tags` | list of strings | Optional | Empty or falsey values are discarded. |
| `contacts` | list of objects | Optional | See [Contacts](#contacts). |
| `attachments` | list of objects | Optional | See [Attachments](#attachments). |

Values must be strings when provided. Empty strings are rejected for required
fields and converted to `null` for optional fields.

### Contacts

Each contact record describes a role and communication details for the mission.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `role` | string | ✅ | e.g., `Operations Lead`. |
| `name` | string | ✅ | Full name or duty position. |
| `callsign` | string | Optional | Tactical callsign or identifier. |
| `channel` | string | Optional | Preferred communications channel. |

### Attachments

Attachments document supporting artifacts within the archive.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | ✅ | Display label for the artifact. |
| `path` | string | ✅ | Relative path inside the archive. |
| `media_type` | string | Optional | MIME type hint (e.g., `application/pdf`). |
| `checksum` | string | Optional | Hash of the attachment itself. |
| `size_bytes` | integer | Optional | Must be non-negative when provided. |

## Validation pipeline overview

`load_mission_package` orchestrates the following checks:

1. Confirm the archive exists and is a regular file.
2. Identify the archive type (`zip` or `tar`) and compute its SHA256 checksum.
3. Validate optional checksum/signature sidecars against the computed digest.
4. Extract the archive into the staging directory.
5. Locate and parse the manifest, normalizing data into `MissionManifest`.
6. Persist payloads into the cache directory using sanitized identifiers.
7. Return a structured summary describing archive, manifest, and cached files.

Downstream services (CLI, GUI, HQ integrations) can rely on this summary for a
consistent view of mission metadata and staged artifacts.

## Sample manifest

A reference manifest is provided at `docs/samples/mission_manifest.yaml` and can
be copied into new packages with mission-specific values.
