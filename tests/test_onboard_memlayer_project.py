from __future__ import annotations

import json
from pathlib import Path

from scripts.onboard_memlayer_project import OnboardOptions, onboard_project, resolve_project_roots


class FakeMemoryBankClient:
    def __init__(self, result_project_id: str = "new-project-id") -> None:
        self.result_project_id = result_project_id
        self.import_payloads: list[dict] = []

    def __enter__(self) -> "FakeMemoryBankClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def import_project_scan(self, **payload):
        self.import_payloads.append(payload)
        return {
            "project": {"id": self.result_project_id},
            "entries_created": 2,
            "entries_updated": 1,
            "conflicts_detected": 0,
            "quality_review_required_count": 0,
        }


def test_resolve_project_roots_uses_only_requested_names(tmp_path: Path) -> None:
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    node_modules = tmp_path / "node_modules"
    alpha.mkdir()
    beta.mkdir()
    node_modules.mkdir()

    roots = resolve_project_roots(projects_root=tmp_path, names=["beta"])

    assert roots == [beta.resolve()]


def test_dry_run_does_not_write_pack_or_config(tmp_path: Path) -> None:
    project_root = tmp_path / "DemoProject"
    project_root.mkdir()
    (project_root / "README.md").write_text("# Demo\n", encoding="utf-8")

    summary = onboard_project(project_root, OnboardOptions(apply=False))

    assert summary["mode"] == "dry_run"
    assert summary["pack"]["status"] == "planned"
    assert summary["import"]["status"] == "planned"
    assert not (project_root / "AGENTS.md").exists()
    assert not (project_root / ".memlayer").exists()


def test_apply_uses_existing_project_id_and_preserves_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORYBANK_API_KEY", "test-key")
    project_root = tmp_path / "ExistingProject"
    memlayer_dir = project_root / ".memlayer"
    memlayer_dir.mkdir(parents=True)
    (project_root / "README.md").write_text("# Existing\n", encoding="utf-8")
    config_path = memlayer_dir / "memlayer.config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_name": "ExistingProject",
                "project_root": str(project_root),
                "project_id": "existing-project-id",
                "preferred_url": "https://custom.example/api",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    fake_client = FakeMemoryBankClient(result_project_id="existing-project-id")

    summary = onboard_project(
        project_root,
        OnboardOptions(apply=True, skip_pack=True, skip_snapshot=True),
        client_factory=lambda *args, **kwargs: fake_client,
    )

    assert fake_client.import_payloads
    payload = fake_client.import_payloads[0]
    assert payload["project_id"] == "existing-project-id"
    assert payload["project"] is None
    assert payload["existing_entry_mode"] == "update"
    assert summary["project_id"] == "existing-project-id"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["project_id"] == "existing-project-id"
    assert config["preferred_url"] == "https://custom.example/api"


def test_apply_persists_new_project_id_after_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEMORYBANK_API_KEY", "test-key")
    project_root = tmp_path / "NewProject"
    project_root.mkdir()
    (project_root / "README.md").write_text("# New\n", encoding="utf-8")
    fake_client = FakeMemoryBankClient(result_project_id="created-project-id")

    summary = onboard_project(
        project_root,
        OnboardOptions(apply=True, skip_snapshot=True),
        client_factory=lambda *args, **kwargs: fake_client,
    )

    assert summary["project_id"] == "created-project-id"
    config_path = project_root / ".memlayer" / "memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["project_id"] == "created-project-id"


def test_apply_reads_project_local_memlayer_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MEMORYBANK_API_KEY", raising=False)
    monkeypatch.delenv("MEMLAYER_WRITE_API_KEY", raising=False)
    project_root = tmp_path / "LocalEnvProject"
    memlayer_dir = project_root / ".memlayer"
    memlayer_dir.mkdir(parents=True)
    (project_root / "README.md").write_text("# Local env\n", encoding="utf-8")
    (memlayer_dir / ".env.memlayer").write_text("MEMLAYER_WRITE_API_KEY=local-write-key\n", encoding="utf-8")
    fake_client = FakeMemoryBankClient(result_project_id="local-env-project-id")
    seen: dict[str, str | None] = {}

    def fake_client_factory(base_url: str, api_key: str | None = None):
        seen["base_url"] = base_url
        seen["api_key"] = api_key
        return fake_client

    summary = onboard_project(
        project_root,
        OnboardOptions(apply=True, skip_pack=True, skip_snapshot=True),
        client_factory=fake_client_factory,
    )

    assert summary["status"] == "ok"
    assert summary["project_id"] == "local-env-project-id"
    assert seen["api_key"] == "local-write-key"


def test_apply_without_api_key_fails_before_live_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MEMORYBANK_API_KEY", raising=False)
    monkeypatch.delenv("MEMLAYER_WRITE_API_KEY", raising=False)
    project_root = tmp_path / "NoKeyProject"
    project_root.mkdir()
    (project_root / "README.md").write_text("# No key\n", encoding="utf-8")

    summary = onboard_project(
        project_root,
        OnboardOptions(apply=True, skip_pack=True, skip_snapshot=True),
    )

    assert summary["status"] == "failed"
    assert summary["import"]["status"] == "failed"
    assert "MEMORYBANK_API_KEY" in summary["import"]["error"]
