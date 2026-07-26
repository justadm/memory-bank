from pathlib import Path
import json
from uuid import uuid4

import pytest

import memlayer_connector.service as connector_service_module
from memlayer_connector.manifest import write_manifest_atomic
from memlayer_connector.service import ConnectorConflict, ConnectorService


def test_matching_manifestless_pack_adopts_artifacts_and_rotates_untrusted_identity(
    tmp_path: Path,
) -> None:
    service = ConnectorService(tmp_path)
    plan = service.plan_connect()
    assert plan.ready
    service.apply_connect(plan)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    (tmp_path / ".memlayer" / "connection-manifest.json").unlink()
    adopted = service.plan_connect()
    assert adopted.ready
    assert any(action.kind == "adopt" for action in adopted.actions)
    service.apply_connect(adopted)
    after = {
        path: path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and path.name != "connection-manifest.json"
    }
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    before_without_control_files = {
        path: value
        for path, value in before.items()
        if path.name != "connection-manifest.json" and path != config_path
    }
    after_without_control_files = {
        path: value
        for path, value in after.items()
        if path != config_path
    }
    assert after_without_control_files == before_without_control_files
    assert (
        json.loads(config_path.read_text(encoding="utf-8"))["connector_identity"]
        != json.loads(before[config_path])["connector_identity"]
    )


def test_unknown_managed_block_fails_before_any_write(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("<!-- MEMLAYER_ROOT_PACK:START -->\nuser content\n<!-- MEMLAYER_ROOT_PACK:END -->\n", encoding="utf-8")
    plan = ConnectorService(tmp_path).plan_connect()
    assert not plan.ready
    assert plan.conflicts[0].code == "modified_managed_section"


def test_apply_rejects_file_changed_after_plan(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    plan = service.plan_connect()
    (tmp_path / "AGENTS.md").write_text("changed after plan\n", encoding="utf-8")
    with pytest.raises(ConnectorConflict, match="stale"):
        service.apply_connect(plan)


def test_disconnect_preserves_runtime_and_env(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    queue = tmp_path / ".memlayer/memlayer.offline.queue.jsonl"
    env = tmp_path / ".memlayer/.env.memlayer"
    queue.write_text('{"pending":true}\n', encoding="utf-8")
    env.write_text("MEMORYBANK_API_KEY=secret\n", encoding="utf-8")
    plan = service.plan_disconnect()
    assert plan.ready
    service.apply_disconnect(plan)
    assert queue.exists()
    assert env.read_text(encoding="utf-8") == "MEMORYBANK_API_KEY=secret\n"


def test_disconnect_preserves_initial_runtime_files_and_gitignore_guard(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    runtime_paths = [
        tmp_path / ".memlayer/memlayer.snapshot.json",
        tmp_path / ".memlayer/memlayer.snapshot.md",
        tmp_path / ".memlayer/memlayer.offline.log.md",
        tmp_path / ".memlayer/memlayer.offline.queue.jsonl",
    ]

    plan = service.plan_disconnect()
    assert plan.ready
    service.apply_disconnect(plan)

    assert all(path.exists() for path in runtime_paths)
    assert ".memlayer/" in (tmp_path / ".gitignore").read_text().splitlines()


def test_disconnect_removes_only_connector_managed_config_keys(tmp_path: Path) -> None:
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps({"user_setting": "preserve"}) + "\n", encoding="utf-8")
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())

    plan = service.plan_disconnect()
    assert plan.ready
    service.apply_disconnect(plan)

    assert json.loads(config_path.read_text(encoding="utf-8")) == {"user_setting": "preserve"}


def test_disconnect_rejects_manifest_hash_forged_to_match_modified_file(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    target = tmp_path / ".memlayer/memlayer_api.sh"
    target.write_text("#!/bin/sh\nprintf modified\n", encoding="utf-8")
    forged = manifest.model_dump(mode="json")
    record = next(item for item in forged["managed_files"] if item["path"] == ".memlayer/memlayer_api.sh")
    from memlayer_connector.service import _digest

    record["content_sha256"] = _digest(target.read_bytes())
    write_manifest_atomic(service.manifest_path, forged)

    plan = service.plan_disconnect()

    assert not plan.ready
    assert plan.conflicts[0].code == "invalid_manifest"
    assert target.exists()


def test_connect_rolls_back_all_files_when_apply_fails_midway(tmp_path: Path, monkeypatch) -> None:
    original_agents = "user-owned instructions\n"
    (tmp_path / "AGENTS.md").write_text(original_agents, encoding="utf-8")
    service = ConnectorService(tmp_path)
    plan = service.plan_connect()
    real_write = connector_service_module._write_atomic
    writes = 0

    def fail_after_first_write(path, data, mode=None):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("synthetic apply failure")
        return real_write(path, data, mode)

    monkeypatch.setattr(connector_service_module, "_write_atomic", fail_after_first_write)

    with pytest.raises(OSError, match="synthetic apply failure"):
        service.apply_connect(plan)

    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == original_agents
    assert not service.manifest_path.exists()
    assert not any(path.is_file() for path in (tmp_path / ".memlayer").rglob("*"))


def test_disconnect_rolls_back_all_files_when_apply_fails_midway(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps({"user_setting": "preserve"}) + "\n",
        encoding="utf-8",
    )
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    before = {
        path.relative_to(tmp_path): (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    real_write = connector_service_module._write_atomic
    failed = False

    def fail_on_config(path, data, mode=None):
        nonlocal failed
        if path.name == "memlayer.config.json" and not failed:
            failed = True
            raise OSError("synthetic disconnect failure")
        return real_write(path, data, mode)

    monkeypatch.setattr(connector_service_module, "_write_atomic", fail_on_config)

    with pytest.raises(OSError, match="synthetic disconnect failure"):
        service.apply_disconnect(service.plan_disconnect())

    after = {
        path.relative_to(tmp_path): (path.read_bytes(), path.stat().st_mode & 0o777)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_reconnect_and_disconnect_reject_config_identity_mismatch(
    tmp_path: Path,
) -> None:
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["connector_identity"] = str(uuid4())
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    config_spec = service.registry[
        next(
            path
            for path in service.registry
            if str(path) == ".memlayer/memlayer.config.json"
        )
    ]
    managed = {key: config.get(key) for key in config_spec.managed_keys}
    from memlayer_connector.service import _digest

    config_hash = _digest(
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
    for record in manifest.managed_files:
        if record.path == ".memlayer/memlayer.config.json":
            record.content_sha256 = config_hash
    write_manifest_atomic(service.manifest_path, manifest)

    assert service.plan_connect().ready is False
    assert service.plan_disconnect().ready is False


def test_manifestless_foreign_config_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "connector_identity": str(uuid4()),
                "project_id": str(uuid4()),
                "project_root": "/foreign/project",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    plan = ConnectorService(tmp_path).plan_connect()

    assert plan.ready is False
    assert any(item.code == "foreign_or_invalid_config" for item in plan.conflicts)


def test_manifestless_matching_root_adopts_project_with_new_connector_identity(
    tmp_path: Path,
) -> None:
    old_identity = uuid4()
    project_id = uuid4()
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "connector_identity": str(old_identity),
                "project_id": str(project_id),
                "project_name": tmp_path.name,
                "project_root": str(tmp_path),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    service = ConnectorService(tmp_path)

    plan = service.plan_connect()
    manifest = service.apply_connect(plan)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert plan.ready is True
    assert plan.connector_identity != old_identity
    assert manifest.project_id == project_id
    assert config["project_id"] == str(project_id)
    assert config["connector_identity"] == str(plan.connector_identity)
