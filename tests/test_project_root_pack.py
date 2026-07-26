from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.install_memlayer_project_pack import (
    MANAGED_END,
    MANAGED_START,
    LOCAL_API_URL,
    LOCAL_EXTRA_URLS,
    PRODUCTION_API_URL,
    apply_env_secret_seed,
    build_project_config,
    install_for_project,
    merge_project_config,
    merge_env_text,
    upsert_managed_section,
)


def test_upsert_managed_section_appends_new_block() -> None:
    base = "# Existing Guide\n\nLocal project rules.\n"
    updated = upsert_managed_section(base, "Managed content")

    assert "# Existing Guide" in updated
    assert MANAGED_START in updated
    assert "Managed content" in updated
    assert MANAGED_END in updated


def test_upsert_managed_section_replaces_existing_block() -> None:
    base = (
        "# Existing Guide\n\n"
        f"{MANAGED_START}\nOld content\n{MANAGED_END}\n"
    )
    updated = upsert_managed_section(base, "New content")

    assert "Old content" not in updated
    assert "New content" in updated
    assert updated.count(MANAGED_START) == 1


def test_build_project_config_contains_expected_defaults(tmp_path: Path) -> None:
    project_root = tmp_path / "ExampleProject"
    config = build_project_config(
        project_root,
        PRODUCTION_API_URL,
        LOCAL_API_URL,
        PRODUCTION_API_URL,
    )

    assert config["project_name"] == "ExampleProject"
    assert config["project_root"] == str(project_root)
    assert config["preferred_url"] == PRODUCTION_API_URL
    assert config["local_fallback_url"] == LOCAL_API_URL
    assert config["human_preferred_url"] == PRODUCTION_API_URL
    assert config["existing_entry_mode"] == "update"
    assert config["recommended_search_mode"] == "hybrid"


def test_install_for_project_creates_pack_files(tmp_path: Path) -> None:
    project_root = tmp_path / "SampleProject"
    project_root.mkdir()
    memlayer_root = project_root / ".memlayer"

    result = install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )

    assert result["agents"] == "created"
    assert (project_root / "AGENTS.md").exists()
    assert (project_root / ".gitignore").exists()
    assert ".memlayer/" in (project_root / ".gitignore").read_text(encoding="utf-8")
    assert memlayer_root.exists()
    assert (memlayer_root / "MEMLAYER.md").exists()
    assert (memlayer_root / ".env.memlayer.example").exists()
    assert (memlayer_root / ".env.memlayer").exists()
    assert (memlayer_root / "memlayer.config.json").exists()
    assert (memlayer_root / "memlayer_api.sh").exists()
    assert (memlayer_root / "memlayer_watchdog.sh").exists()
    assert (memlayer_root / "memlayer_recover.sh").exists()
    assert (memlayer_root / "memlayer_launchd_install.sh").exists()
    assert (memlayer_root / "memlayer_context.sh").exists()
    assert (memlayer_root / "memlayer_write.sh").exists()
    assert (memlayer_root / "memlayer_sync.sh").exists()
    assert (memlayer_root / "memlayer_snapshot_pull.sh").exists()
    assert (memlayer_root / "memlayer_payload.py").exists()
    assert (memlayer_root / "memlayer.snapshot.json").exists()
    assert (memlayer_root / "memlayer.snapshot.md").exists()
    assert (memlayer_root / "memlayer.offline.log.md").exists()
    assert (memlayer_root / "memlayer.offline.queue.jsonl").exists()
    assert (memlayer_root / "memlayer_api.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_watchdog.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_recover.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_launchd_install.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_context.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_write.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_sync.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_snapshot_pull.sh").stat().st_mode & 0o111
    assert (memlayer_root / "memlayer_payload.py").stat().st_mode & 0o111
    context_text = (memlayer_root / "memlayer_context.sh").read_text(encoding="utf-8")
    assert "REFRESH_MODE" in context_text
    assert 'print_snapshot' in context_text
    assert 'print_local_query_context' in context_text
    assert 'matched_items' in context_text
    assert 'memlayer_snapshot_pull.sh' in context_text
    assert 'write_read_receipt' in context_text
    api_text = (memlayer_root / "memlayer_api.sh").read_text(encoding="utf-8")
    write_text = (memlayer_root / "memlayer_write.sh").read_text(encoding="utf-8")
    payload_helper_text = (memlayer_root / "memlayer_payload.py").read_text(encoding="utf-8")
    assert "ensure-memory" in write_text
    assert "ensure-task-log" in write_text
    assert "source_agent" in payload_helper_text
    assert "project_id" in payload_helper_text
    assert PRODUCTION_API_URL in (memlayer_root / "memlayer.config.json").read_text(encoding="utf-8")
    assert "host.docker.internal:18100" in api_text
    assert 'http://api:8000' in api_text
    assert 'http://memorybank-api-1:8000' in api_text
    assert 'doctor' in api_text
    recover_text = (memlayer_root / "memlayer_recover.sh").read_text(encoding="utf-8")
    assert 'compose up -d' in recover_text
    assert 'MEMLAYER_RECOVER_HEALTH_TIMEOUT_SECONDS' in recover_text
    launchd_text = (memlayer_root / "memlayer_launchd_install.sh").read_text(encoding="utf-8")
    assert 'Library/LaunchAgents' in launchd_text
    assert 'launchctl load' in launchd_text
    snapshot_pull_text = (memlayer_root / "memlayer_snapshot_pull.sh").read_text(encoding="utf-8")
    assert 'data.setdefault("generated_at"' in snapshot_pull_text
    assert 'data["project_id"] = project_id' in snapshot_pull_text
    assert 'read-receipt' in snapshot_pull_text


def test_context_helper_reads_top_level_snapshot_project_id(tmp_path: Path) -> None:
    project_root = tmp_path / "SnapshotProject"
    project_root.mkdir()

    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )

    memlayer_root = project_root / ".memlayer"
    (memlayer_root / "memlayer.snapshot.json").write_text(
        json.dumps(
            {
                "project_id": "project-from-snapshot",
                "summary": {},
                "context": {
                    "active_decisions": [
                        {
                            "type": "decision",
                            "title": "Architecture source",
                            "content": "Architecture context is available.",
                            "importance": 3,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(memlayer_root / "memlayer_context.sh"), "architecture"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "project_id: project-from-snapshot" in result.stdout
    assert "Architecture source" in result.stdout


def test_install_for_project_merges_existing_agents_file(tmp_path: Path) -> None:
    project_root = tmp_path / "ExistingProject"
    project_root.mkdir()
    agents_path = project_root / "AGENTS.md"
    agents_path.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")

    result = install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )

    text = agents_path.read_text(encoding="utf-8")

    assert result["agents"] == "updated"
    assert "# Existing" in text
    assert "Keep this." in text
    assert "MemLayer Working Memory" in text


def test_install_for_project_preserves_existing_local_env(tmp_path: Path) -> None:
    project_root = tmp_path / "LocalEnvProject"
    project_root.mkdir()
    memlayer_root = project_root / ".memlayer"
    memlayer_root.mkdir()
    local_env_path = memlayer_root / ".env.memlayer"
    local_env_path.write_text("MEMORYBANK_API_KEY=secret\n", encoding="utf-8")

    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )

    local_env = local_env_path.read_text(encoding="utf-8")
    assert "MEMORYBANK_API_KEY=secret" in local_env
    assert f"MEMLAYER_API_URL={PRODUCTION_API_URL}" in local_env
    assert f"MEMLAYER_EXTRA_URLS={LOCAL_EXTRA_URLS}" in local_env
    assert "MEMLAYER_RECOVER_MODE=up" in local_env
    assert "MEMLAYER_RECOVER_HEALTH_TIMEOUT_SECONDS=30" in local_env
    assert "MEMLAYER_LAUNCHD_LABEL=loc.memlayer.runtime" in local_env
    assert "MEMLAYER_SOURCE_AGENT=codex" in local_env
    assert "MEMLAYER_READ_RECEIPT_ENABLED=true" in local_env


def test_connector_mode_does_not_seed_environment_key(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "ConnectorProject"
    project_root.mkdir()
    monkeypatch.setenv("MEMORYBANK_API_KEY", "must-not-be-copied")

    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
        connector_mode=True,
    )

    assert "must-not-be-copied" not in (project_root / ".memlayer/.env.memlayer").read_text(encoding="utf-8")


def test_installer_parser_exposes_explicit_connector_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["install_memlayer_project_pack.py", "--names", "demo", "--connector-mode"],
    )

    from scripts.install_memlayer_project_pack import parse_args

    assert parse_args().connector_mode is True


def test_installed_api_helper_accepts_memlayer_write_api_key_alias(tmp_path: Path) -> None:
    project_root = tmp_path / "AliasKeyProject"
    project_root.mkdir()
    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )
    env_path = project_root / ".memlayer" / ".env.memlayer"
    env_text = env_path.read_text(encoding="utf-8")
    env_text += "\nMEMLAYER_WRITE_API_KEY=write-key\n"
    env_path.write_text(env_text, encoding="utf-8")

    completed = subprocess.run(
        [
            str(project_root / ".memlayer" / "memlayer_api.sh"),
            "doctor",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "MEMLAYER_API_URL": "http://127.0.0.1:1",
            "MEMLAYER_EXTRA_URLS": "",
            "MEMLAYER_RETRY_ATTEMPTS": "1",
            "MEMLAYER_CURL_TIMEOUT_SECONDS": "1",
        },
    )

    assert "memorybank_api_key_configured=yes" in completed.stdout


def test_installed_write_helper_accepts_flag_style_task_outcome_alias(tmp_path: Path) -> None:
    project_root = tmp_path / "WriteCliProject"
    project_root.mkdir()
    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )
    config_path = project_root / ".memlayer" / "memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["project_id"] = "project-123"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    api_path = project_root / ".memlayer" / "memlayer_api.sh"
    api_path.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    api_path.chmod(0o755)

    completed = subprocess.run(
        [
            str(project_root / ".memlayer" / "memlayer_write.sh"),
            "--type",
            "task_outcome",
            "--title",
            "Inventory done",
            "--content",
            "source inventory ready",
            "--importance",
            "4",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin:/usr/sbin:/sbin",
            "MEMLAYER_SOURCE_AGENT": "agent-under-test",
        },
    )

    assert completed.returncode == 0
    assert "queued memory write" in completed.stderr
    queue_path = project_root / ".memlayer" / "memlayer.offline.queue.jsonl"
    queued = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(queued) == 1
    payload = queued[0]["payload"]
    assert payload["type"] == "task"
    assert payload["title"] == "Inventory done"
    assert payload["content"] == "source inventory ready"
    assert payload["importance"] == 4
    assert payload["source_agent"] == "agent-under-test"
    assert payload["project_id"] == "project-123"


def test_installed_payload_helper_normalizes_task_outcome_alias(tmp_path: Path) -> None:
    project_root = tmp_path / "PayloadAliasProject"
    project_root.mkdir()
    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )
    config_path = project_root / ".memlayer" / "memlayer.config.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / ".memlayer" / "memlayer_payload.py"),
            "ensure-memory",
            str(config_path),
            json.dumps({"type": "task_outcome", "title": "Done", "content": "Outcome"}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["type"] == "task"


def test_installed_payload_helper_adds_source_agent_and_project_id(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "PayloadProject"
    project_root.mkdir()
    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )
    config_path = project_root / ".memlayer" / "memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["project_id"] = "project-123"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("MEMLAYER_SOURCE_AGENT", "agent-under-test")

    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / ".memlayer" / "memlayer_payload.py"),
            "ensure-memory",
            str(config_path),
            json.dumps({"type": "note", "content": "hello"}),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["source_agent"] == "agent-under-test"
    assert payload["project_id"] == "project-123"
    assert payload["metadata"]["project_name"] == "PayloadProject"
    assert payload["metadata"]["memlayer_pack"] == "project_root_pack"

    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / ".memlayer" / "memlayer_payload.py"),
            "read-receipt",
            str(config_path),
            "context query",
            "snapshot",
            "3",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    receipt = json.loads(completed.stdout)
    assert receipt["type"] == "event"
    assert receipt["source_agent"] == "agent-under-test"
    assert receipt["project_id"] == "project-123"
    assert receipt["metadata"]["agent_id"] == "agent-under-test"
    assert receipt["metadata"]["receipt_type"] == "memlayer_read"
    assert receipt["metadata"]["read_receipt"] is True
    assert receipt["metadata"]["read_source"] == "snapshot"
    assert receipt["metadata"]["query"] == "context query"
    assert receipt["metadata"]["matched_items"] == 3


def test_installed_payload_helper_runs_with_apple_python39(tmp_path: Path, monkeypatch) -> None:
    apple_python = Path("/usr/bin/python3")
    if not apple_python.exists():
        return

    completed_version = subprocess.run(
        [str(apple_python), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    if "Python 3.9" not in completed_version.stdout + completed_version.stderr:
        return

    project_root = tmp_path / "ApplePythonProject"
    project_root.mkdir()
    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )
    config_path = project_root / ".memlayer" / "memlayer.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["project_id"] = "project-apple-python"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("MEMLAYER_SOURCE_AGENT", "agent-under-test")

    completed = subprocess.run(
        [
            str(apple_python),
            str(project_root / ".memlayer" / "memlayer_payload.py"),
            "read-receipt",
            str(config_path),
            "context query",
            "snapshot",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    receipt = json.loads(completed.stdout)
    assert receipt["metadata"]["receipt_type"] == "memlayer_read"
    assert receipt["metadata"]["matched_items"] == 1


def test_install_for_project_moves_legacy_root_files_into_memlayer_dir(tmp_path: Path) -> None:
    project_root = tmp_path / "LegacyProject"
    project_root.mkdir()
    (project_root / "memlayer.config.json").write_text('{"project_id":"legacy-id"}\n', encoding="utf-8")
    (project_root / ".env.memlayer").write_text("MEMORYBANK_API_KEY=legacy\n", encoding="utf-8")

    install_for_project(
        project_root,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
    )

    assert not (project_root / "memlayer.config.json").exists()
    assert not (project_root / ".env.memlayer").exists()
    assert (project_root / ".memlayer" / "memlayer.config.json").exists()
    assert (project_root / ".memlayer" / ".env.memlayer").exists()


def test_merge_env_text_appends_missing_keys_without_overwriting_existing_values() -> None:
    existing = "MEMORYBANK_API_KEY=secret\nMEMLAYER_API_URL=http://custom:8000\n"
    template = f"MEMORYBANK_API_KEY=\nMEMLAYER_API_URL={PRODUCTION_API_URL}\nMEMLAYER_EXTRA_URLS=http://api:8000\n"

    merged = merge_env_text(existing, template)

    assert "MEMORYBANK_API_KEY=secret" in merged
    assert "MEMLAYER_API_URL=http://custom:8000" in merged
    assert "MEMLAYER_EXTRA_URLS=http://api:8000" in merged


def test_merge_env_text_updates_legacy_managed_endpoint_defaults() -> None:
    existing = (
        "MEMORYBANK_API_KEY=secret\n"
        "MEMLAYER_API_URL=http://127.0.0.1:18100\n"
        "MEMLAYER_EXTRA_URLS=http://host.docker.internal:18100,http://api:8000,http://memorybank-api-1:8000,https://memlayer.loc/api\n"
        "MEMLAYER_RETRY_ATTEMPTS=10\n"
    )
    template = (
        f"MEMORYBANK_API_KEY=\n"
        f"MEMLAYER_API_URL={PRODUCTION_API_URL}\n"
        f"MEMLAYER_EXTRA_URLS={LOCAL_EXTRA_URLS}\n"
        f"MEMLAYER_RETRY_ATTEMPTS=2\n"
    )

    merged = merge_env_text(existing, template)

    assert "MEMORYBANK_API_KEY=secret" in merged
    assert f"MEMLAYER_API_URL={PRODUCTION_API_URL}" in merged
    assert f"MEMLAYER_EXTRA_URLS={LOCAL_EXTRA_URLS}" in merged
    assert "MEMLAYER_RETRY_ATTEMPTS=2" in merged


def test_merge_env_text_fills_empty_api_key_from_template() -> None:
    existing = "MEMORYBANK_API_KEY=\nMEMLAYER_API_URL=http://127.0.0.1:18100\n"
    template = f"MEMORYBANK_API_KEY=prod-key\nMEMLAYER_API_URL={PRODUCTION_API_URL}\n"

    merged = merge_env_text(existing, template)

    assert "MEMORYBANK_API_KEY=prod-key" in merged
    assert f"MEMLAYER_API_URL={PRODUCTION_API_URL}" in merged


def test_merge_env_text_preserves_existing_non_empty_api_key() -> None:
    existing = "MEMORYBANK_API_KEY=custom-key\n"
    template = "MEMORYBANK_API_KEY=prod-key\n"

    merged = merge_env_text(existing, template)

    assert "MEMORYBANK_API_KEY=custom-key" in merged
    assert "MEMORYBANK_API_KEY=prod-key" not in merged


def test_apply_env_secret_seed_uses_memorybank_api_key(monkeypatch) -> None:
    monkeypatch.setenv("MEMORYBANK_API_KEY", "prod-key")

    seeded = apply_env_secret_seed("MEMORYBANK_API_KEY=\nMEMLAYER_API_URL=https://api.memlayer.ru\n")

    assert "MEMORYBANK_API_KEY=prod-key" in seeded


def test_merge_project_config_preserves_existing_project_identity() -> None:
    existing = {
        "project_id": "8bc076cc-300e-481c-9215-f0e24364d81d",
        "tenant_id": "tenant-1",
        "preferred_url": "http://old:18100",
    }
    generated = {
        "preferred_url": PRODUCTION_API_URL,
        "local_fallback_url": LOCAL_API_URL,
    }

    merged = merge_project_config(existing, generated)

    assert merged["project_id"] == "8bc076cc-300e-481c-9215-f0e24364d81d"
    assert merged["tenant_id"] == "tenant-1"
    assert merged["preferred_url"] == PRODUCTION_API_URL
