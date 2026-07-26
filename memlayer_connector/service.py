from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from .artifacts import ArtifactSpec, OwnershipMode, RenderContext, artifact_registry, managed_values, render_artifact
from .filesystem import (
    RootBoundRemoveError,
    RootBoundWriteError,
    rmdir_beneath,
    root_identity,
    unlink_beneath,
    write_atomic_beneath,
)
from .manifest import ConnectionManifest, ManifestConflict, ManifestRecord, load_validated_manifest, safe_project_path, validate_manifest, validate_manifest_identity, write_manifest_atomic

START = "<!-- MEMLAYER_ROOT_PACK:START -->"
END = "<!-- MEMLAYER_ROOT_PACK:END -->"
MANIFEST_RELATIVE = PurePosixPath(".memlayer/connection-manifest.json")


class ConnectorConflict(ValueError):
    pass


@dataclass(frozen=True)
class ConnectorAction:
    kind: Literal["create", "adopt", "upgrade", "update_managed_section", "update_managed_keys", "preserve", "remove", "conflict"]
    path: str
    ownership: OwnershipMode
    reason: str


@dataclass(frozen=True)
class ConnectorConflictItem:
    code: str
    path: str
    reason: str


@dataclass(frozen=True)
class ConnectorPlan:
    operation: Literal["connect", "disconnect"]
    project_root: str
    actions: tuple[ConnectorAction, ...]
    conflicts: tuple[ConnectorConflictItem, ...]
    connector_identity: UUID | None = None
    project_id: UUID | None = None
    observed: tuple[tuple[str, str | None], ...] = ()
    manifest: ConnectionManifest | None = None

    @property
    def ready(self) -> bool:
        return not self.conflicts


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_atomic(
    path: Path,
    data: bytes,
    mode: int | None = None,
    *,
    root: Path | None = None,
    expected_root_identity: tuple[int, int] | None = None,
) -> None:
    if root is None:
        raise ConnectorConflict("root-bound atomic write requires project root")
    try:
        write_atomic_beneath(
            root=root,
            path=path,
            data=data,
            mode=mode,
            expected_root_identity=expected_root_identity,
        )
    except RootBoundWriteError as exc:
        raise ConnectorConflict(str(exc)) from exc


def _unlink(
    path: Path,
    *,
    root: Path,
    expected_root_identity: tuple[int, int] | None = None,
    missing_ok: bool = False,
) -> None:
    try:
        unlink_beneath(
            root=root,
            path=path,
            expected_root_identity=expected_root_identity,
            missing_ok=missing_ok,
        )
    except RootBoundRemoveError as exc:
        raise ConnectorConflict(str(exc)) from exc


def _rmdir(
    path: Path,
    *,
    root: Path,
    expected_root_identity: tuple[int, int] | None = None,
    missing_ok: bool = False,
) -> None:
    try:
        rmdir_beneath(
            root=root,
            path=path,
            expected_root_identity=expected_root_identity,
            missing_ok=missing_ok,
        )
    except RootBoundRemoveError as exc:
        raise ConnectorConflict(str(exc)) from exc


def _render_new_agents(context: RenderContext, section: bytes) -> bytes:
    return (
        f"# {context.project_name} Agent Guide\n\n"
        f"This repository is connected to MemLayer.\n\n{START}\n".encode()
        + section.rstrip()
        + f"\n{END}\n".encode()
    )


def _section(text: str) -> tuple[str, str] | None:
    if START not in text and END not in text:
        return None
    if START not in text or END not in text or text.index(START) >= text.index(END):
        raise ConnectorConflict("malformed managed AGENTS section")
    begin = text.index(START) + len(START)
    end = text.index(END)
    return text[begin:end].strip(), text[begin - len(START): end + len(END)]


def _config_bytes(path: Path, context: RenderContext, identity: UUID, existing: dict | None = None) -> bytes:
    payload = dict(existing or {})
    generated = {
        "schema_version": 1,
        "project_name": context.project_name,
        "project_root": str(context.project_root),
        "preferred_url": context.preferred_url,
        "local_fallback_url": context.local_url,
        "human_preferred_url": context.human_url,
        "existing_entry_mode": "update",
        "read_before_write": True,
        "recommended_search_mode": "hybrid",
        "recommended_memory_types": ["decision", "constraint", "risk", "artifact", "task", "note", "event"],
        "connector_identity": str(identity),
    }
    payload.update(generated)
    return (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


class ConnectorService:
    def __init__(self, project_root: str | Path, *, preferred_url: str = "https://api.memlayer.ru", local_url: str = "http://127.0.0.1:18100", human_url: str = "https://api.memlayer.ru"):
        root = Path(project_root).expanduser().resolve()
        if not root.is_dir():
            raise ConnectorConflict(f"invalid project root: {root}")
        self.root = root
        self.context = RenderContext(root.name, root, preferred_url, local_url, human_url)
        self.registry = artifact_registry("codex", 1, self.context)
        self.manifest_path = root / MANIFEST_RELATIVE
        self.root_identity = root_identity(root)

    def _path(self, relative: PurePosixPath) -> Path:
        return safe_project_path(self.root, relative, self.registry)

    def _manifest(self) -> ConnectionManifest | None:
        if not self.manifest_path.exists():
            return None
        manifest = load_validated_manifest(
            self.manifest_path,
            project_root=self.root,
            registry=self.registry,
        )
        config = self._read_config()
        validate_manifest_identity(manifest, config=config)
        return manifest

    def _read_config(self) -> dict:
        path = self._path(PurePosixPath(".memlayer/memlayer.config.json"))
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ManifestConflict("connector config is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ManifestConflict("connector config must be a JSON object")
        return payload

    def _adoptable_project_id(self, config: dict) -> UUID | None:
        configured_root = config.get("project_root")
        configured_name = config.get("project_name")
        if configured_root is not None:
            try:
                if Path(str(configured_root)).expanduser().resolve() != self.root:
                    raise ManifestConflict(
                        "manifest-less config belongs to another project root"
                    )
            except OSError as exc:
                raise ManifestConflict(
                    "manifest-less config has an invalid project root"
                ) from exc
        if configured_name is not None and str(configured_name) != self.root.name:
            raise ManifestConflict(
                "manifest-less config belongs to another project name"
            )
        raw_project_id = config.get("project_id")
        if raw_project_id is None:
            return None
        if configured_root is None:
            raise ManifestConflict(
                "manifest-less project identity requires matching project_root"
            )
        try:
            return UUID(str(raw_project_id))
        except ValueError as exc:
            raise ManifestConflict("manifest-less config has invalid project_id") from exc

    def _validate_manifestless_managed_config(
        self,
        config: dict,
        spec: ArtifactSpec,
    ) -> None:
        expected = managed_values(spec, self.context)
        for key, expected_value in expected.items():
            if key in config and config[key] != expected_value:
                raise ManifestConflict(
                    f"manifest-less managed config differs at key: {key}"
                )

        raw_tenant_id = config.get("tenant_id")
        if raw_tenant_id is not None and (
            not isinstance(raw_tenant_id, str) or not raw_tenant_id.strip()
        ):
            raise ManifestConflict("manifest-less config has invalid tenant_id")

    def _observed(self) -> dict[str, str | None]:
        observed: dict[str, str | None] = {}
        for relative, spec in self.registry.items():
            path = self._path(relative)
            if spec.ownership is OwnershipMode.USER_OWNED:
                continue
            if not path.exists():
                observed[str(relative)] = None
            elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    values = {key: data.get(key) for key in spec.managed_keys}
                    observed[str(relative)] = _digest((json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())
                except (OSError, json.JSONDecodeError):
                    observed[str(relative)] = "invalid"
            elif spec.ownership is OwnershipMode.MANAGED_SECTION:
                text = path.read_text(encoding="utf-8")
                block = _section(text)
                observed[str(relative)] = _digest(block[1].encode()) if block else _digest(path.read_bytes())
            elif spec.ownership is OwnershipMode.MANAGED_LINE:
                text = path.read_text(encoding="utf-8")
                observed[str(relative)] = _digest(b".memlayer/\n") if text.splitlines().count(".memlayer/") == 1 else None
            else:
                observed[str(relative)] = _digest(path.read_bytes())
        return observed

    def local_integrity_findings(
        self,
        manifest: ConnectionManifest,
    ) -> tuple[ConnectorConflictItem, ...]:
        records = {PurePosixPath(record.path): record for record in manifest.managed_files}
        findings: list[ConnectorConflictItem] = []
        for relative, spec in self.registry.items():
            path = self._path(relative)
            record = records[relative]
            if not path.exists():
                findings.append(
                    ConnectorConflictItem(
                        "missing_managed_artifact",
                        str(relative),
                        "connector artifact is absent",
                    )
                )
                continue
            if spec.ownership is OwnershipMode.USER_OWNED:
                continue
            if spec.ownership is OwnershipMode.CREATE_IF_ABSENT:
                continue
            try:
                if spec.ownership is OwnershipMode.MANAGED_KEYS:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    managed = {key: payload.get(key) for key in spec.managed_keys}
                    actual = _digest(
                        (
                            json.dumps(
                                managed,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode()
                    )
                elif spec.ownership is OwnershipMode.MANAGED_SECTION:
                    block = _section(path.read_text(encoding="utf-8"))
                    actual = _digest(block[1].encode()) if block else None
                elif spec.ownership is OwnershipMode.MANAGED_LINE:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    actual = _digest(b".memlayer/\n") if lines.count(".memlayer/") == 1 else None
                else:
                    actual = _digest(path.read_bytes())
            except (OSError, UnicodeError, json.JSONDecodeError, ConnectorConflict):
                actual = None
            if actual != record.content_sha256:
                findings.append(
                    ConnectorConflictItem(
                        "managed_artifact_drift",
                        str(relative),
                        "managed content does not match the connection manifest",
                    )
                )
        return tuple(findings)

    def plan_connect(self) -> ConnectorPlan:
        conflicts: list[ConnectorConflictItem] = []
        actions: list[ConnectorAction] = []
        manifest = None
        adopted_project_id = None
        try:
            manifest = self._manifest()
        except ManifestConflict as exc:
            conflicts.append(ConnectorConflictItem("invalid_manifest", str(self.manifest_path), str(exc)))
        identity = manifest.connector_identity if manifest else None
        if manifest is not None:
            adopted_project_id = manifest.project_id
        else:
            try:
                adopted_project_id = self._adoptable_project_id(self._read_config())
            except ManifestConflict as exc:
                conflicts.append(
                    ConnectorConflictItem(
                        "foreign_or_invalid_config",
                        ".memlayer/memlayer.config.json",
                        str(exc),
                    )
                )
        identity = identity or uuid4()
        for relative, spec in self.registry.items():
            path = self._path(relative)
            exists = path.exists()
            expected = None if spec.ownership is OwnershipMode.USER_OWNED else render_artifact(spec, self.context)
            try:
                if spec.ownership is OwnershipMode.USER_OWNED:
                    actions.append(ConnectorAction("preserve" if exists else "create", str(relative), spec.ownership, "user-owned environment skeleton"))
                elif spec.ownership is OwnershipMode.CREATE_IF_ABSENT:
                    actions.append(ConnectorAction("preserve" if exists else "create", str(relative), spec.ownership, "create only when absent"))
                elif not exists:
                    actions.append(ConnectorAction("create", str(relative), spec.ownership, "managed artifact is absent"))
                elif spec.ownership is OwnershipMode.WHOLE_FILE:
                    if path.read_bytes() == expected:
                        actions.append(ConnectorAction("adopt", str(relative), spec.ownership, "matching released artifact"))
                    else:
                        conflicts.append(ConnectorConflictItem("modified_managed_file", str(relative), "whole-file content differs"))
                elif spec.ownership is OwnershipMode.MANAGED_SECTION:
                    text = path.read_text(encoding="utf-8")
                    if START in text or END in text:
                        block = _section(text)
                        expected_section = expected.decode().strip()
                        if block and block[0] == expected_section:
                            actions.append(ConnectorAction("adopt", str(relative), spec.ownership, "matching managed section"))
                        else:
                            conflicts.append(ConnectorConflictItem("modified_managed_section", str(relative), "managed section differs"))
                    else:
                        actions.append(ConnectorAction("update_managed_section", str(relative), spec.ownership, "insert managed section while preserving file"))
                elif spec.ownership is OwnershipMode.MANAGED_LINE:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    count = lines.count(".memlayer/")
                    if count == 1:
                        actions.append(ConnectorAction("adopt", str(relative), spec.ownership, "matching managed line"))
                    elif count > 1:
                        conflicts.append(ConnectorConflictItem("duplicate_managed_line", str(relative), "managed line occurs more than once"))
                    else:
                        actions.append(ConnectorAction("update_managed_section", str(relative), spec.ownership, "add managed ignore line"))
                elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                    try:
                        existing_config = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        conflicts.append(ConnectorConflictItem("invalid_managed_config", str(relative), "config is not a JSON object"))
                    else:
                        if not isinstance(existing_config, dict):
                            conflicts.append(ConnectorConflictItem("invalid_managed_config", str(relative), "config is not a JSON object"))
                        elif manifest is None:
                            try:
                                self._validate_manifestless_managed_config(
                                    existing_config,
                                    spec,
                                )
                            except ManifestConflict as exc:
                                conflicts.append(
                                    ConnectorConflictItem(
                                        "modified_managed_config",
                                        str(relative),
                                        str(exc),
                                    )
                                )
                            else:
                                actions.append(ConnectorAction("update_managed_keys", str(relative), spec.ownership, "adopt matching connector keys and preserve unknown keys"))
                        else:
                            actions.append(ConnectorAction("update_managed_keys", str(relative), spec.ownership, "merge connector keys and preserve unknown keys"))
            except (OSError, UnicodeError, ConnectorConflict) as exc:
                conflicts.append(ConnectorConflictItem("inventory_error", str(relative), str(exc)))
        return ConnectorPlan(
            operation="connect",
            project_root=str(self.root),
            actions=tuple(actions),
            conflicts=tuple(conflicts),
            connector_identity=identity,
            project_id=adopted_project_id,
            observed=tuple(sorted(self._observed().items())),
            manifest=manifest,
        )

    def apply_connect(self, plan: ConnectorPlan) -> ConnectionManifest:
        if plan.operation != "connect" or not plan.ready:
            raise ConnectorConflict("connect plan is not ready")
        if tuple(sorted(self._observed().items())) != plan.observed:
            raise ConnectorConflict("stale connect plan")
        identity = plan.connector_identity or uuid4()
        snapshots: dict[Path, tuple[bytes | None, int | None]] = {}

        def capture(path: Path, *, read_existing: bool = True) -> None:
            if path in snapshots:
                return
            if path.exists():
                snapshots[path] = (
                    path.read_bytes() if read_existing else None,
                    path.stat().st_mode & 0o777,
                )
            else:
                snapshots[path] = (None, None)

        def restore() -> None:
            for path, (content, mode) in reversed(tuple(snapshots.items())):
                if content is None:
                    _unlink(
                        path,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                        missing_ok=True,
                    )
                else:
                    _write_atomic(
                        path,
                        content,
                        mode,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
            for path in sorted(
                {item.parent for item in snapshots},
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                current = path
                while current != self.root and current.is_relative_to(self.root):
                    try:
                        _rmdir(
                            current,
                            root=self.root,
                            expected_root_identity=self.root_identity,
                            missing_ok=True,
                        )
                    except OSError:
                        break
                    current = current.parent

        try:
            for action in plan.actions:
                relative = PurePosixPath(action.path)
                spec = self.registry[relative]
                path = self._path(relative)
                if spec.ownership is OwnershipMode.USER_OWNED:
                    if not path.exists():
                        capture(path, read_existing=False)
                        _write_atomic(
                            path,
                            b"",
                            0o600,
                            root=self.root,
                            expected_root_identity=self.root_identity,
                        )
                    continue
                if action.kind in {"preserve", "adopt"}:
                    continue
                capture(path)
                if spec.ownership is OwnershipMode.MANAGED_SECTION:
                    section = render_artifact(spec, self.context).decode().strip()
                    if path.exists():
                        text = path.read_text(encoding="utf-8")
                        if START in text or END in text:
                            raise ConnectorConflict(f"managed section changed during apply: {relative}")
                        data = (text.rstrip() + f"\n\n{START}\n{section}\n{END}\n").encode()
                    else:
                        data = _render_new_agents(self.context, section.encode())
                    _write_atomic(
                        path,
                        data,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
                elif spec.ownership is OwnershipMode.MANAGED_LINE:
                    text = path.read_text(encoding="utf-8") if path.exists() else ""
                    data = (text.rstrip() + ("\n\n" if text.rstrip() else "") + ".memlayer/\n").encode()
                    _write_atomic(
                        path,
                        data,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
                elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                    _write_atomic(
                        path,
                        _config_bytes(path, self.context, identity, existing),
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
                elif spec.ownership is OwnershipMode.CREATE_IF_ABSENT:
                    if not path.exists():
                        _write_atomic(
                            path,
                            render_artifact(spec, self.context),
                            root=self.root,
                            expected_root_identity=self.root_identity,
                        )
                elif spec.ownership is OwnershipMode.WHOLE_FILE:
                    _write_atomic(
                        path,
                        render_artifact(spec, self.context),
                        0o755 if spec.executable else None,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
            records: list[ManifestRecord] = []
            for relative, spec in self.registry.items():
                path = self._path(relative)
                created = any(
                    action.path == str(relative)
                    and action.kind
                    in {
                        "create",
                        "update_managed_section",
                        "update_managed_keys",
                        "upgrade",
                    }
                    for action in plan.actions
                )
                if spec.ownership is OwnershipMode.USER_OWNED:
                    digest = None
                elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        values = {key: data.get(key) for key in spec.managed_keys}
                        digest = _digest((json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())
                    except (OSError, json.JSONDecodeError) as exc:
                        raise ConnectorConflict(f"cannot hash managed config: {relative}") from exc
                elif spec.ownership is OwnershipMode.MANAGED_SECTION:
                    block = _section(path.read_text(encoding="utf-8"))
                    if not block:
                        raise ConnectorConflict(f"managed section missing after apply: {relative}")
                    digest = _digest(block[1].encode())
                elif spec.ownership is OwnershipMode.MANAGED_LINE:
                    digest = _digest(b".memlayer/\n")
                else:
                    digest = _digest(path.read_bytes())
                records.append(ManifestRecord(path=str(relative), ownership=spec.ownership, created_by_connector=created, content_sha256=digest))
            manifest = ConnectionManifest(schema_version=1, agent="codex", project_root=str(self.root), connector_identity=identity, project_id=plan.project_id, root_pack_version=1, installed_at=datetime.now(timezone.utc), managed_files=records)
            capture(self.manifest_path)
            write_manifest_atomic(
                self.manifest_path,
                manifest,
                project_root=self.root,
                expected_root_identity=self.root_identity,
            )
            return manifest
        except BaseException:
            restore()
            raise

    def plan_disconnect(self) -> ConnectorPlan:
        conflicts: list[ConnectorConflictItem] = []
        actions: list[ConnectorAction] = []
        try:
            manifest = self._manifest()
        except ManifestConflict as exc:
            return ConnectorPlan(
                operation="disconnect",
                project_root=str(self.root),
                actions=(),
                conflicts=(
                    ConnectorConflictItem(
                        "invalid_manifest",
                        str(self.manifest_path),
                        str(exc),
                    ),
                ),
            )
        if manifest is None:
            return ConnectorPlan(
                operation="disconnect",
                project_root=str(self.root),
                actions=(),
                conflicts=(
                    ConnectorConflictItem(
                        "missing_manifest",
                        str(self.manifest_path),
                        "cannot safely disconnect without manifest",
                    ),
                ),
            )
        for record in manifest.managed_files:
            spec = self.registry[PurePosixPath(record.path)]
            path = self._path(PurePosixPath(record.path))
            if spec.ownership in {
                OwnershipMode.USER_OWNED,
                OwnershipMode.CREATE_IF_ABSENT,
                OwnershipMode.MANAGED_LINE,
            }:
                actions.append(
                    ConnectorAction(
                        "preserve",
                        record.path,
                        spec.ownership,
                        "ownership contract requires preservation",
                    )
                )
                continue
            if not record.created_by_connector:
                actions.append(ConnectorAction("preserve", record.path, spec.ownership, "not connector-owned"))
                continue
            if not path.exists():
                actions.append(ConnectorAction("preserve", record.path, spec.ownership, "already absent"))
                continue
            if spec.ownership is OwnershipMode.WHOLE_FILE:
                actual = _digest(path.read_bytes())
                if actual != record.content_sha256 or actual != spec.expected_sha256:
                    conflicts.append(ConnectorConflictItem("modified_managed_file", record.path, "hash differs from manifest"))
                else:
                    actions.append(ConnectorAction("remove", record.path, spec.ownership, "unchanged connector-created file"))
            elif spec.ownership is OwnershipMode.MANAGED_SECTION:
                block = _section(path.read_text(encoding="utf-8"))
                if (
                    not block
                    or _digest(block[1].encode()) != record.content_sha256
                    or record.content_sha256 != spec.expected_sha256
                ):
                    conflicts.append(ConnectorConflictItem("modified_managed_section", record.path, "managed section hash differs"))
                else:
                    actions.append(ConnectorAction("remove", record.path, spec.ownership, "remove unchanged managed section"))
            elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    managed = {key: payload.get(key) for key in spec.managed_keys}
                    actual = _digest(
                        (
                            json.dumps(
                                managed,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode()
                    )
                except (OSError, UnicodeError, json.JSONDecodeError):
                    actual = None
                if actual == record.content_sha256:
                    actions.append(ConnectorAction("remove", record.path, spec.ownership, "unchanged initial runtime file"))
                else:
                    conflicts.append(
                        ConnectorConflictItem(
                            "modified_managed_keys",
                            record.path,
                            "managed config keys differ from manifest",
                        )
                    )
        return ConnectorPlan(
            operation="disconnect",
            project_root=str(self.root),
            actions=tuple(actions),
            conflicts=tuple(conflicts),
            connector_identity=manifest.connector_identity,
            project_id=manifest.project_id,
            observed=tuple(sorted(self._observed().items())),
            manifest=manifest,
        )

    def apply_disconnect(self, plan: ConnectorPlan) -> None:
        if plan.operation != "disconnect" or not plan.ready or not plan.manifest:
            raise ConnectorConflict("disconnect plan is not ready")
        fresh = self.plan_disconnect()
        if not fresh.ready or fresh.actions != plan.actions:
            raise ConnectorConflict("stale disconnect plan")
        snapshots: dict[Path, tuple[bytes, int]] = {}

        def capture(path: Path) -> None:
            if path.exists() and path not in snapshots:
                snapshots[path] = (path.read_bytes(), path.stat().st_mode & 0o777)

        def restore() -> None:
            for path, (content, mode) in reversed(tuple(snapshots.items())):
                _write_atomic(
                    path,
                    content,
                    mode,
                    root=self.root,
                    expected_root_identity=self.root_identity,
                )

        try:
            for action in plan.actions:
                if action.kind != "remove":
                    continue
                relative = PurePosixPath(action.path)
                path = self._path(relative)
                spec = self.registry[relative]
                if not path.exists():
                    continue
                capture(path)
                if spec.ownership is OwnershipMode.MANAGED_SECTION:
                    text = path.read_text(encoding="utf-8")
                    block = _section(text)
                    if not block or _digest(block[1].encode()) != next(r.content_sha256 for r in plan.manifest.managed_files if r.path == action.path):
                        raise ConnectorConflict(f"stale disconnect plan: {action.path}")
                    cleaned = text.replace(block[1], "", 1)
                    data = (cleaned.strip() + "\n").encode() if cleaned.strip() else b""
                    _write_atomic(
                        path,
                        data,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
                elif spec.ownership is OwnershipMode.MANAGED_KEYS:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for key in spec.managed_keys:
                        data.pop(key, None)
                    if data:
                        _write_atomic(
                            path,
                            (
                                json.dumps(
                                    data,
                                    indent=2,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                                + "\n"
                            ).encode(),
                            root=self.root,
                            expected_root_identity=self.root_identity,
                        )
                    else:
                        _unlink(
                            path,
                            root=self.root,
                            expected_root_identity=self.root_identity,
                        )
                else:
                    _unlink(
                        path,
                        root=self.root,
                        expected_root_identity=self.root_identity,
                    )
            capture(self.manifest_path)
            _unlink(
                self.manifest_path,
                root=self.root,
                expected_root_identity=self.root_identity,
                missing_ok=True,
            )
        except BaseException:
            restore()
            raise
