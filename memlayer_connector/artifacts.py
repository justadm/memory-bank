from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates" / "project_root_pack"
SUPPORTED_AGENT = "codex"
SUPPORTED_ROOT_PACK_VERSION = 1
FORMATTED_TEMPLATES = {
    "AGENTS_SECTION.md.tmpl",
    "MEMLAYER.md.tmpl",
    "env.memlayer.example.tmpl",
}


class OwnershipMode(str, Enum):
    MANAGED_SECTION = "managed_section"
    MANAGED_LINE = "managed_line"
    WHOLE_FILE = "whole_file"
    MANAGED_KEYS = "managed_keys"
    CREATE_IF_ABSENT = "create_if_absent"
    USER_OWNED = "user_owned"


@dataclass(frozen=True)
class RenderContext:
    project_name: str
    project_root: Path
    preferred_url: str
    local_url: str
    human_url: str


@dataclass(frozen=True)
class ArtifactSpec:
    path: PurePosixPath
    ownership: OwnershipMode
    template_name: str | None
    executable: bool = False
    managed_keys: tuple[str, ...] = ()
    preserve_on_disconnect: bool = False
    expected_sha256: str | None = None


def _specs() -> tuple[ArtifactSpec, ...]:
    whole_files = (
        (".agents/skills/memlayer/SKILL.md", "memlayer_skill.md.tmpl", False),
        (".memlayer/MEMLAYER.md", "MEMLAYER.md.tmpl", False),
        (".memlayer/.env.memlayer.example", "env.memlayer.example.tmpl", False),
        (".memlayer/memlayer_api.sh", "memlayer_api.sh.tmpl", True),
        (".memlayer/memlayer_watchdog.sh", "memlayer_watchdog.sh.tmpl", True),
        (".memlayer/memlayer_recover.sh", "memlayer_recover.sh.tmpl", True),
        (".memlayer/memlayer_launchd_install.sh", "memlayer_launchd_install.sh.tmpl", True),
        (".memlayer/memlayer_context.sh", "memlayer_context.sh.tmpl", True),
        (".memlayer/memlayer_write.sh", "memlayer_write.sh.tmpl", True),
        (".memlayer/memlayer_sync.sh", "memlayer_sync.sh.tmpl", True),
        (".memlayer/memlayer_snapshot_pull.sh", "memlayer_snapshot_pull.sh.tmpl", True),
        (".memlayer/memlayer_payload.py", "memlayer_payload.py.tmpl", True),
    )
    specs = [
        ArtifactSpec(PurePosixPath("AGENTS.md"), OwnershipMode.MANAGED_SECTION, "AGENTS_SECTION.md.tmpl"),
        ArtifactSpec(PurePosixPath(".gitignore"), OwnershipMode.MANAGED_LINE, None),
        *(
            ArtifactSpec(PurePosixPath(path), OwnershipMode.WHOLE_FILE, template, executable=executable)
            for path, template, executable in whole_files
        ),
        ArtifactSpec(
            PurePosixPath(".memlayer/memlayer.config.json"),
            OwnershipMode.MANAGED_KEYS,
            None,
            managed_keys=(
                "schema_version",
                "project_name",
                "project_root",
                "connector_identity",
                "preferred_url",
                "local_fallback_url",
                "human_preferred_url",
                "existing_entry_mode",
                "read_before_write",
                "recommended_search_mode",
                "recommended_memory_types",
                "write_check",
            ),
        ),
        ArtifactSpec(PurePosixPath(".memlayer/.env.memlayer"), OwnershipMode.USER_OWNED, None, preserve_on_disconnect=True),
        ArtifactSpec(PurePosixPath(".memlayer/memlayer.snapshot.json"), OwnershipMode.CREATE_IF_ABSENT, "memlayer.snapshot.json.tmpl"),
        ArtifactSpec(PurePosixPath(".memlayer/memlayer.snapshot.md"), OwnershipMode.CREATE_IF_ABSENT, "memlayer.snapshot.md.tmpl"),
        ArtifactSpec(PurePosixPath(".memlayer/memlayer.offline.log.md"), OwnershipMode.CREATE_IF_ABSENT, "memlayer.offline.log.md.tmpl"),
        ArtifactSpec(PurePosixPath(".memlayer/memlayer.offline.queue.jsonl"), OwnershipMode.CREATE_IF_ABSENT, "memlayer.offline.queue.jsonl.tmpl"),
    ]
    return tuple(specs)


def _template_values(context: RenderContext) -> dict[str, str]:
    return {
        "project_name": context.project_name,
        "project_root": str(context.project_root),
        "preferred_url": context.preferred_url,
        "local_url": context.local_url,
        "human_url": context.human_url,
    }


def _config_payload(context: RenderContext) -> dict[str, object]:
    return {
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
    }


def _read_template(name: str) -> bytes:
    path = TEMPLATES / name
    if not path.is_file():
        raise ValueError(f"missing connector template: {name}")
    return path.read_bytes()


def render_artifact(spec: ArtifactSpec, context: RenderContext) -> bytes:
    """Render one artifact deterministically for a project context."""
    if spec.ownership is OwnershipMode.USER_OWNED:
        raise ValueError("user-owned artifacts are never rendered")
    if spec.ownership is OwnershipMode.MANAGED_LINE:
        return b".memlayer/\n"
    if spec.ownership is OwnershipMode.MANAGED_KEYS:
        payload = {key: _config_payload(context)[key] for key in spec.managed_keys if key in _config_payload(context)}
        return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    raw = _read_template(spec.template_name or "")
    text = raw.decode("utf-8")
    rendered = text.format(**_template_values(context)) if spec.template_name in FORMATTED_TEMPLATES else text
    return rendered.encode("utf-8")


def artifact_registry(agent: str, root_pack_version: int, context: RenderContext) -> dict[PurePosixPath, ArtifactSpec]:
    if agent != SUPPORTED_AGENT:
        raise ValueError(f"unsupported agent: {agent}; supported: {SUPPORTED_AGENT}")
    if root_pack_version != SUPPORTED_ROOT_PACK_VERSION:
        raise ValueError(f"unsupported root-pack version: {root_pack_version}")
    result: dict[PurePosixPath, ArtifactSpec] = {}
    for spec in _specs():
        if spec.path in result:
            raise ValueError(f"duplicate artifact path: {spec.path}")
        expected = None
        if spec.ownership is not OwnershipMode.USER_OWNED:
            expected = "sha256:" + hashlib.sha256(render_artifact(spec, context)).hexdigest()
        result[spec.path] = replace(spec, expected_sha256=expected)
    return result


def managed_values(spec: ArtifactSpec, context: RenderContext) -> Mapping[str, object]:
    if spec.ownership is not OwnershipMode.MANAGED_KEYS:
        raise ValueError("managed_values requires a managed-keys artifact")
    payload = _config_payload(context)
    return {key: payload[key] for key in spec.managed_keys if key in payload}
