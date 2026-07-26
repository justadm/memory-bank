import json
from pathlib import Path

import pytest

import memlayer_connector.cli as connector_cli
from memlayer_connector.cli import main, run_connect
from memlayer_connector.manifest import load_validated_manifest
from memlayer_connector.service import ConnectorService


def test_connect_is_dry_run_by_default(tmp_path: Path, capsys):
    code = main(["connect", "codex", "--project-root", str(tmp_path), "--json"])

    assert code == 0
    assert not (tmp_path / ".memlayer").exists()
    assert json.loads(capsys.readouterr().out)["mode"] == "dry_run"


def test_register_requires_apply(tmp_path: Path, capsys):
    code = main([
        "connect", "codex", "--project-root", str(tmp_path),
        "--register-project", "--json",
    ])

    assert code == 2
    assert "requires --apply" in capsys.readouterr().err


class FakeClient:
    def __init__(self):
        self.connector_identities = []
        self.import_calls = []
        self.attempts = 0

    def resolve_project(self, **kwargs):
        self.connector_identities.append(kwargs["connector_identity"])
        self.attempts += 1
        if self.attempts == 1:
            raise TimeoutError("temporary")
        return {"project_id": "d8399b69-82ff-46ec-8e03-1930f1c84735", "status": "created"}

    def get_project(self, project_id):
        return {"id": project_id, "name": "demo"}

    def close(self):
        pass


def test_registration_retry_reuses_connector_identity(tmp_path: Path):
    fake = FakeClient()
    result = run_connect(tmp_path, apply=True, register_project=True, client_factory=lambda **_: fake)

    assert fake.connector_identities == [result["connector_identity"]] * 2
    assert fake.import_calls == []
    assert result["status"] == "registered"
    config = json.loads((tmp_path / ".memlayer/memlayer.config.json").read_text())
    assert config["project_id"] == "d8399b69-82ff-46ec-8e03-1930f1c84735"
    assert config["last_write_check"]["status"] == "success"
    assert config["last_write_check"]["target_id"] == config["project_id"]
    assert config["last_write_check"]["receipt_id"]

    service = ConnectorService(tmp_path)
    manifest = load_validated_manifest(
        service.manifest_path,
        project_root=tmp_path,
        registry=service.registry,
    )
    assert str(manifest.project_id) == config["project_id"]
    assert service.local_integrity_findings(manifest) == ()


def test_registration_persistence_rolls_back_config_when_manifest_write_fails(
    tmp_path: Path,
    monkeypatch,
):
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config_before = config_path.read_bytes()
    manifest_before = service.manifest_path.read_bytes()

    def fail_manifest_write(*args, **kwargs):
        raise OSError("synthetic manifest failure")

    monkeypatch.setattr(
        connector_cli,
        "write_manifest_atomic",
        fail_manifest_write,
    )

    with pytest.raises(OSError, match="synthetic manifest failure"):
        connector_cli._persist_registration(
            service,
            manifest,
            {"project_id": "d8399b69-82ff-46ec-8e03-1930f1c84735"},
        )

    assert config_path.read_bytes() == config_before
    assert service.manifest_path.read_bytes() == manifest_before


def test_registration_rollback_reports_every_unresolved_path(
    tmp_path: Path,
    monkeypatch,
):
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    manifest_before = service.manifest_path.read_bytes()
    real_write_atomic = connector_cli._write_atomic
    config_writes = 0

    def fail_config_rollback(path, payload, mode=None):
        nonlocal config_writes
        if path == config_path:
            config_writes += 1
            if config_writes == 2:
                raise OSError("synthetic config rollback failure")
        return real_write_atomic(path, payload, mode)

    def fail_manifest_write(*args, **kwargs):
        raise OSError("synthetic manifest failure")

    monkeypatch.setattr(connector_cli, "_write_atomic", fail_config_rollback)
    monkeypatch.setattr(
        connector_cli,
        "write_manifest_atomic",
        fail_manifest_write,
    )

    with pytest.raises(
        connector_cli.ConnectorConflict,
        match="rollback is incomplete",
    ) as exc_info:
        connector_cli._persist_registration(
            service,
            manifest,
            {"project_id": "d8399b69-82ff-46ec-8e03-1930f1c84735"},
        )

    assert str(config_path) in str(exc_info.value)
    assert service.manifest_path.read_bytes() == manifest_before
