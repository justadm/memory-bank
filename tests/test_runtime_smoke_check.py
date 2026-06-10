from __future__ import annotations

import json
import os
import subprocess
import sys

from memorybank_sdk import MemoryBankError
from scripts import runtime_smoke_check


class FakeSmokeClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def __enter__(self) -> "FakeSmokeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def health(self):
        return {"status": "ok"}

    def auth_status(self):
        return {"authenticated": True}

    def runtime_self_check(self, **kwargs):
        raise MemoryBankError("MemoryBank error 403: admin scope required")

    def search_memory(self, query, **kwargs):
        return {"items": [{"id": "memory-1", "content": query}]}

    def get_relevant_memory(self, **kwargs):
        return {"context": [{"id": "memory-1", "content": kwargs["query"]}]}


def test_runtime_smoke_check_script_bootstraps_repo_import_path() -> None:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    result = subprocess.run(
        [sys.executable, str(runtime_smoke_check.ROOT / "scripts" / "runtime_smoke_check.py"), "--help"],
        cwd="/tmp",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Run MemLayer import -> search -> relevant smoke checks." in result.stdout


def test_runtime_smoke_check_keeps_read_smoke_when_admin_self_check_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MEMORYBANK_API_KEY", "test-key")
    monkeypatch.setattr(runtime_smoke_check, "MemoryBankClient", FakeSmokeClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime_smoke_check.py",
            "--memorybank-url",
            "https://api.memlayer.test",
            "--existing-project-id",
            "project-1",
            "--query",
            "SolutionArtifact feedback evidence trust",
        ],
    )

    runtime_smoke_check.main()

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
    assert output["runtime_self_check"]["status"] == "unavailable"
    assert "admin scope required" in output["runtime_self_check"]["detail"]
    assert output["search_results_count"] == 1
    assert output["relevant_results_count"] == 1
