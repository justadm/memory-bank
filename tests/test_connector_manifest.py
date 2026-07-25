import json
from pathlib import Path, PurePosixPath
from uuid import uuid4

import pytest

from memlayer_connector.artifacts import RenderContext, artifact_registry
from memlayer_connector.manifest import (
    ConnectionManifest,
    ManifestConflict,
    load_validated_manifest,
    safe_project_path,
    validate_manifest,
    validate_manifest_identity,
    write_manifest_atomic,
)


def registry_for(root: Path):
    return artifact_registry("codex", 1, RenderContext("demo", root, "https://api.memlayer.ru", "http://127.0.0.1:18100", "https://api.memlayer.ru"))


def valid_payload(root: Path) -> dict:
    registry = registry_for(root)
    return {
        "schema_version": 1,
        "agent": "codex",
        "project_root": str(root.resolve()),
        "connector_identity": str(uuid4()),
        "project_id": None,
        "root_pack_version": 1,
        "installed_at": "2026-07-25T10:00:00Z",
        "managed_files": [
            {
                "path": str(path),
                "ownership": spec.ownership.value,
                "created_by_connector": spec.ownership.value not in {"user_owned", "create_if_absent"},
                "content_sha256": None if spec.ownership.value == "user_owned" else spec.expected_sha256,
            }
            for path, spec in registry.items()
        ],
    }


@pytest.mark.parametrize("unsafe", ["/etc/passwd", "../AGENTS.md", ".", "", "a\\b"])
def test_manifest_rejects_unsafe_paths(tmp_path: Path, unsafe: str) -> None:
    with pytest.raises(ManifestConflict):
        safe_project_path(tmp_path, unsafe, registry_for(tmp_path))


def test_manifest_rejects_forged_ownership_and_registry_mismatch(tmp_path: Path) -> None:
    payload = valid_payload(tmp_path)
    payload["managed_files"][0]["ownership"] = "whole_file"
    with pytest.raises(ManifestConflict, match="ownership"):
        validate_manifest(payload, project_root=tmp_path, registry=registry_for(tmp_path))

    payload = valid_payload(tmp_path)
    payload["managed_files"].pop()
    with pytest.raises(ManifestConflict, match="registry mismatch"):
        validate_manifest(payload, project_root=tmp_path, registry=registry_for(tmp_path))


def test_manifest_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "manifest-outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / ".memlayer").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ManifestConflict, match="symlink"):
        safe_project_path(tmp_path, ".memlayer/MEMLAYER.md", registry_for(tmp_path))


def test_manifest_identity_must_match_config(tmp_path: Path) -> None:
    manifest = ConnectionManifest.model_validate(valid_payload(tmp_path))
    with pytest.raises(ManifestConflict, match="connector_identity"):
        validate_manifest_identity(manifest, config={"connector_identity": str(uuid4())})


def test_manifest_atomic_round_trip_and_user_owned_hash(tmp_path: Path) -> None:
    payload = valid_payload(tmp_path)
    manifest = validate_manifest(payload, project_root=tmp_path, registry=registry_for(tmp_path))
    path = tmp_path / ".memlayer" / "connection-manifest.json"
    write_manifest_atomic(path, manifest)
    loaded = load_validated_manifest(path, project_root=tmp_path, registry=registry_for(tmp_path))
    assert loaded.connector_identity == manifest.connector_identity
    assert json.loads(path.read_text(encoding="utf-8"))["managed_files"]
    env = tmp_path / ".memlayer" / ".env.memlayer"
    env.write_text("MEMORYBANK_API_KEY=secret\n", encoding="utf-8")
    assert env.read_text(encoding="utf-8") == "MEMORYBANK_API_KEY=secret\n"
