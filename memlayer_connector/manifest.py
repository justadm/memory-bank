from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .artifacts import ArtifactSpec, OwnershipMode


class ManifestConflict(ValueError):
    pass


class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    ownership: OwnershipMode
    created_by_connector: bool
    content_sha256: str | None


class ConnectionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    agent: str
    project_root: str
    connector_identity: UUID
    project_id: UUID | None
    root_pack_version: int = Field(ge=1, le=1)
    installed_at: datetime
    managed_files: list[ManifestRecord]


def _canonical_root(project_root: str | Path) -> Path:
    root = Path(project_root).expanduser()
    if not root.exists() or not root.is_dir():
        raise ManifestConflict(f"project root is not a directory: {root}")
    return root.resolve()


def _validate_hash(record: ManifestRecord, spec: ArtifactSpec) -> None:
    if spec.ownership is OwnershipMode.USER_OWNED:
        if record.content_sha256 is not None:
            raise ManifestConflict(f"user-owned artifact must not have a hash: {record.path}")
        return
    if not record.content_sha256 or not record.content_sha256.startswith("sha256:"):
        raise ManifestConflict(f"missing content hash: {record.path}")
    digest = record.content_sha256.removeprefix("sha256:")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ManifestConflict(f"invalid content hash: {record.path}")
    if (
        spec.ownership
        in {
            OwnershipMode.WHOLE_FILE,
            OwnershipMode.MANAGED_SECTION,
            OwnershipMode.MANAGED_LINE,
        }
        and record.content_sha256 != spec.expected_sha256
    ):
        raise ManifestConflict(f"manifest hash is not a released connector artifact: {record.path}")


def safe_project_path(
    project_root: str | Path,
    relative_path: str | PurePosixPath,
    registry_paths: Mapping[PurePosixPath, ArtifactSpec] | set[PurePosixPath] | list[PurePosixPath],
) -> Path:
    root = _canonical_root(project_root)
    raw = str(relative_path)
    if not raw or "\x00" in raw or "\\" in raw:
        raise ManifestConflict(f"unsafe manifest path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise ManifestConflict(f"unsafe manifest path: {raw!r}")
    allowed = set(registry_paths.keys()) if isinstance(registry_paths, Mapping) else set(registry_paths)
    if path not in allowed:
        raise ManifestConflict(f"path is not in connector registry: {raw}")

    candidate = root.joinpath(*path.parts)
    current = root
    for part in path.parts:
        current = current / part
        try:
            if current.is_symlink() or current.exists() and current.lstat().st_mode and current.resolve() != current:
                raise ManifestConflict(f"symlink in manifest path: {raw}")
        except OSError as exc:
            raise ManifestConflict(f"cannot inspect manifest path: {raw}") from exc

    try:
        resolved_parent = candidate.parent.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
        if os.path.commonpath((str(root), str(resolved_parent))) != str(root):
            raise ManifestConflict(f"manifest path escapes project root: {raw}")
        if candidate.exists() and os.path.commonpath((str(root), str(resolved_candidate))) != str(root):
            raise ManifestConflict(f"manifest path escapes project root: {raw}")
    except ValueError as exc:
        raise ManifestConflict(f"manifest path escapes project root: {raw}") from exc
    return candidate


def validate_manifest(
    payload: Mapping[str, Any] | ConnectionManifest,
    *,
    project_root: str | Path,
    registry: Mapping[PurePosixPath, ArtifactSpec],
) -> ConnectionManifest:
    root = _canonical_root(project_root)
    try:
        manifest = payload if isinstance(payload, ConnectionManifest) else ConnectionManifest.model_validate(payload)
    except ValidationError as exc:
        raise ManifestConflict(f"invalid connection manifest: {exc}") from exc
    if manifest.schema_version != 1 or manifest.agent != "codex" or manifest.root_pack_version != 1:
        raise ManifestConflict("unsupported connection manifest version or agent")
    try:
        if Path(manifest.project_root).expanduser().resolve() != root:
            raise ManifestConflict("manifest project_root does not match CLI project root")
    except OSError as exc:
        raise ManifestConflict("invalid manifest project_root") from exc

    expected_paths = set(registry)
    seen: set[PurePosixPath] = set()
    for record in manifest.managed_files:
        try:
            path = PurePosixPath(record.path)
        except Exception as exc:
            raise ManifestConflict(f"invalid manifest path: {record.path!r}") from exc
        if path in seen:
            raise ManifestConflict(f"duplicate manifest path: {record.path}")
        seen.add(path)
        safe_project_path(root, record.path, registry)
        expected = registry[path]
        if record.ownership is not expected.ownership:
            raise ManifestConflict(f"manifest ownership mismatch: {record.path}")
        _validate_hash(record, expected)
    if seen != expected_paths:
        missing = sorted(str(path) for path in expected_paths - seen)
        extra = sorted(str(path) for path in seen - expected_paths)
        raise ManifestConflict(f"manifest registry mismatch; missing={missing}, extra={extra}")
    return manifest


def load_validated_manifest(
    path: str | Path,
    *,
    project_root: str | Path,
    registry: Mapping[PurePosixPath, ArtifactSpec],
) -> ConnectionManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestConflict(f"cannot read connection manifest: {manifest_path}") from exc
    return validate_manifest(payload, project_root=project_root, registry=registry)


def validate_manifest_identity(manifest: ConnectionManifest, *, config: Mapping[str, Any]) -> None:
    configured = config.get("connector_identity")
    if configured and str(manifest.connector_identity) != str(configured):
        raise ManifestConflict("connector_identity does not match config")
    if manifest.project_id is not None and config.get("project_id") and str(manifest.project_id) != str(config["project_id"]):
        raise ManifestConflict("project_id does not match config")


def write_manifest_atomic(path: str | Path, manifest: ConnectionManifest | Mapping[str, Any]) -> None:
    destination = Path(path)
    if destination.name != "connection-manifest.json" or destination.parent.name != ".memlayer":
        raise ManifestConflict("manifest destination is not the connector manifest path")
    root = destination.parent.parent.resolve()
    safe_project_path(root, ".memlayer/connection-manifest.json", {
        PurePosixPath(".memlayer/connection-manifest.json"): ArtifactSpec(
            path=PurePosixPath(".memlayer/connection-manifest.json"),
            ownership=OwnershipMode.WHOLE_FILE,
            template_name=None,
        )
    })
    payload = manifest.model_dump(mode="json") if isinstance(manifest, ConnectionManifest) else dict(manifest)
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
