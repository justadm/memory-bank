from pathlib import Path
import json
from uuid import uuid4

import pytest

import memlayer_connector.service as connector_service_module
from memlayer_connector.manifest import write_manifest_atomic
from memlayer_connector.service import (
    ConnectorConflict,
    ConnectorService,
    _digest,
    _write_atomic,
)

CURRENT_SKILL_DOCTOR_LINE = (
    b"7. Run `./.memlayer/memlayer_api.sh doctor` when endpoint or auth routing "
    b"is unclear. Use the connector CLI's `doctor` command from the MemLayer "
    b"installation when connector identity or readiness must be verified.\n"
)
PRIOR_SKILL_DOCTOR_LINE = (
    b"7. Run `./.memlayer/../memlayer doctor --project-root .` when auth, routing, "
    b"identity, or readiness is unclear.\n"
)


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


def test_reconnect_upgrades_known_prior_released_skill(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    skill_path = tmp_path / ".agents/skills/memlayer/SKILL.md"
    current = skill_path.read_bytes()
    prior = current.replace(
        CURRENT_SKILL_DOCTOR_LINE,
        PRIOR_SKILL_DOCTOR_LINE,
    )
    assert prior != current
    skill_path.write_bytes(prior)
    skill_record = next(
        record
        for record in manifest.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    skill_record.content_sha256 = _digest(prior)
    write_manifest_atomic(service.manifest_path, manifest)

    plan = service.plan_connect()

    assert plan.ready
    assert any(
        action.kind == "upgrade"
        and action.path == ".agents/skills/memlayer/SKILL.md"
        for action in plan.actions
    )
    upgraded_manifest = service.apply_connect(plan)
    assert skill_path.read_bytes() == current
    upgraded_record = next(
        record
        for record in upgraded_manifest.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert upgraded_record.created_by_connector is True
    assert upgraded_record.content_sha256 == _digest(current)


def test_manifestless_upgrade_preserves_preexisting_skill_ownership(
    tmp_path: Path,
) -> None:
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    skill_path = tmp_path / ".agents/skills/memlayer/SKILL.md"
    current = skill_path.read_bytes()
    skill_path.write_bytes(
        current.replace(
            CURRENT_SKILL_DOCTOR_LINE,
            PRIOR_SKILL_DOCTOR_LINE,
        )
    )
    service.manifest_path.unlink()

    plan = service.plan_connect()

    assert plan.ready
    manifest = service.apply_connect(plan)
    skill_record = next(
        record
        for record in manifest.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert skill_path.read_bytes() == current
    assert skill_record.created_by_connector is False
    disconnect = service.plan_disconnect()
    skill_action = next(
        action
        for action in disconnect.actions
        if action.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert skill_action.kind == "preserve"


def test_reconnect_rejects_manifest_and_file_release_hash_mismatch(
    tmp_path: Path,
) -> None:
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    skill_path = tmp_path / ".agents/skills/memlayer/SKILL.md"
    current = skill_path.read_bytes()
    prior = current.replace(
        CURRENT_SKILL_DOCTOR_LINE,
        PRIOR_SKILL_DOCTOR_LINE,
    )
    skill_path.write_bytes(prior)
    current_hash = _digest(current)
    record = next(
        record
        for record in manifest.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert record.content_sha256 == current_hash
    write_manifest_atomic(service.manifest_path, manifest)

    plan = service.plan_connect()

    assert not plan.ready
    assert any(
        conflict.code == "modified_managed_file"
        and conflict.path == ".agents/skills/memlayer/SKILL.md"
        for conflict in plan.conflicts
    )


def test_reconnect_preserves_connector_created_ownership(
    tmp_path: Path,
) -> None:
    service = ConnectorService(tmp_path)
    initial = service.apply_connect(service.plan_connect())
    initial_record = next(
        record
        for record in initial.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert initial_record.created_by_connector is True

    reconnected = service.apply_connect(service.plan_connect())

    reconnected_record = next(
        record
        for record in reconnected.managed_files
        if record.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert reconnected_record.created_by_connector is True
    disconnect = service.plan_disconnect()
    skill_action = next(
        action
        for action in disconnect.actions
        if action.path == ".agents/skills/memlayer/SKILL.md"
    )
    assert skill_action.kind == "remove"


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

    def fail_after_first_write(path, data, mode=None, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("synthetic apply failure")
        return real_write(path, data, mode, **kwargs)

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

    def fail_on_config(path, data, mode=None, **kwargs):
        nonlocal failed
        if path.name == "memlayer.config.json" and not failed:
            failed = True
            raise OSError("synthetic disconnect failure")
        return real_write(path, data, mode, **kwargs)

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


def test_manifestless_modified_managed_config_is_rejected(tmp_path: Path) -> None:
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    service.manifest_path.unlink()
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["preferred_url"] = "https://modified.invalid"
    config_path.write_text(json.dumps(config) + "\n", encoding="utf-8")

    plan = service.plan_connect()

    assert plan.ready is False
    assert any(
        item.code == "modified_managed_config"
        for item in plan.conflicts
    )


def test_root_bound_atomic_write_rejects_symlink_parent(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / ".memlayer").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ConnectorConflict, match="symlink"):
        _write_atomic(
            tmp_path / ".memlayer/memlayer.config.json",
            b'{"safe": true}\n',
            root=tmp_path,
        )

    assert not (outside / "memlayer.config.json").exists()


def test_disconnect_rejects_parent_symlink_swap_before_unlink(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    plan = service.plan_disconnect()
    target = tmp_path / ".memlayer/MEMLAYER.md"
    original_parent = tmp_path / ".memlayer-original"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / target.name
    outside_target.write_text("must survive\n", encoding="utf-8")
    original_read_bytes = Path.read_bytes
    swapped = False
    fresh_plan_completed = False
    original_plan_disconnect = service.plan_disconnect

    def swap_parent_after_capture(path: Path) -> bytes:
        nonlocal swapped
        content = original_read_bytes(path)
        if path == target and fresh_plan_completed and not swapped:
            swapped = True
            target.parent.rename(original_parent)
            target.parent.symlink_to(outside, target_is_directory=True)
        return content

    def mark_fresh_plan_completed():
        nonlocal fresh_plan_completed
        result = original_plan_disconnect()
        fresh_plan_completed = True
        return result

    monkeypatch.setattr(Path, "read_bytes", swap_parent_after_capture)
    monkeypatch.setattr(service, "plan_disconnect", mark_fresh_plan_completed)

    with pytest.raises(ConnectorConflict, match="symlink"):
        service.apply_disconnect(plan)

    assert outside_target.read_text(encoding="utf-8") == "must survive\n"


def test_connect_rollback_rejects_parent_symlink_swap_before_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = ConnectorService(tmp_path)
    plan = service.plan_connect()
    original_parent = tmp_path / ".memlayer-original"
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_target = outside / "MEMLAYER.md"
    outside_target.write_text("must survive\n", encoding="utf-8")
    trigger = tmp_path / ".memlayer/.env.memlayer.example"
    real_write_atomic = connector_service_module._write_atomic

    def swap_parent_then_fail(path, data, mode=None, **kwargs):
        if path == trigger:
            path.parent.rename(original_parent)
            path.parent.symlink_to(outside, target_is_directory=True)
            raise OSError("synthetic apply failure")
        return real_write_atomic(path, data, mode, **kwargs)

    monkeypatch.setattr(
        connector_service_module,
        "_write_atomic",
        swap_parent_then_fail,
    )

    with pytest.raises(ConnectorConflict, match="symlink"):
        service.apply_connect(plan)

    assert outside_target.read_text(encoding="utf-8") == "must survive\n"
