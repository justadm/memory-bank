import json
from pathlib import Path

from memlayer_connector.cli import main, run_connect


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
    assert json.loads((tmp_path / ".memlayer/memlayer.config.json").read_text())["project_id"] == "d8399b69-82ff-46ec-8e03-1930f1c84735"
