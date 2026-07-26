from pathlib import Path
import json

import pytest

import memlayer_connector.service as connector_service_module
from memlayer_connector.manifest import write_manifest_atomic
from memlayer_connector.service import ConnectorConflict, ConnectorService


def test_matching_manifestless_pack_is_adopted_without_rewrite(tmp_path: Path) -> None:
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
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file() if path.name != "connection-manifest.json"} == {path: value for path, value in before.items() if path.name != "connection-manifest.json"}


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
