from pathlib import Path

import pytest

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
