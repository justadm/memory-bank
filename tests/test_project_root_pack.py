from __future__ import annotations

from pathlib import Path

from scripts.install_memlayer_project_pack import (
    MANAGED_END,
    MANAGED_START,
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
        "http://127.0.0.1:18100",
        "https://memlayer.loc/api",
        "https://memlayer.loc/api",
    )

    assert config["project_name"] == "ExampleProject"
    assert config["project_root"] == str(project_root)
    assert config["preferred_url"] == "http://127.0.0.1:18100"
    assert config["human_preferred_url"] == "https://memlayer.loc/api"
    assert config["existing_entry_mode"] == "update"
    assert config["recommended_search_mode"] == "hybrid"


def test_install_for_project_creates_pack_files(tmp_path: Path) -> None:
    project_root = tmp_path / "SampleProject"
    project_root.mkdir()

    result = install_for_project(
        project_root,
        preferred_url="http://127.0.0.1:18100",
        local_url="https://memlayer.loc/api",
        human_url="https://memlayer.loc/api",
        dry_run=False,
    )

    assert result["agents"] == "created"
    assert (project_root / "AGENTS.md").exists()
    assert (project_root / "MEMLAYER.md").exists()
    assert (project_root / ".env.memlayer.example").exists()
    assert (project_root / ".env.memlayer").exists()
    assert (project_root / "memlayer.config.json").exists()
    assert (project_root / "memlayer_api.sh").exists()
    assert (project_root / "memlayer_watchdog.sh").exists()
    assert (project_root / "memlayer_recover.sh").exists()
    assert (project_root / "memlayer_context.sh").exists()
    assert (project_root / "memlayer_write.sh").exists()
    assert (project_root / "memlayer_sync.sh").exists()
    assert (project_root / "memlayer_snapshot_pull.sh").exists()
    assert (project_root / "memlayer.snapshot.json").exists()
    assert (project_root / "memlayer.snapshot.md").exists()
    assert (project_root / "memlayer.offline.log.md").exists()
    assert (project_root / "memlayer.offline.queue.jsonl").exists()
    assert (project_root / "memlayer_api.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_watchdog.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_recover.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_context.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_write.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_sync.sh").stat().st_mode & 0o111
    assert (project_root / "memlayer_snapshot_pull.sh").stat().st_mode & 0o111
    context_text = (project_root / "memlayer_context.sh").read_text(encoding="utf-8")
    assert "REFRESH_MODE" in context_text
    assert 'print_snapshot' in context_text
    assert 'print_local_query_context' in context_text
    assert 'matched_items' in context_text
    assert 'memlayer_snapshot_pull.sh' in context_text
    api_text = (project_root / "memlayer_api.sh").read_text(encoding="utf-8")
    assert "host.docker.internal:18100" in api_text
    assert 'http://api:8000' in api_text
    assert 'http://memorybank-api-1:8000' in api_text
    assert 'doctor' in api_text


def test_install_for_project_merges_existing_agents_file(tmp_path: Path) -> None:
    project_root = tmp_path / "ExistingProject"
    project_root.mkdir()
    agents_path = project_root / "AGENTS.md"
    agents_path.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")

    result = install_for_project(
        project_root,
        preferred_url="http://127.0.0.1:18100",
        local_url="https://memlayer.loc/api",
        human_url="https://memlayer.loc/api",
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
    local_env_path = project_root / ".env.memlayer"
    local_env_path.write_text("MEMORYBANK_API_KEY=secret\n", encoding="utf-8")

    install_for_project(
        project_root,
        preferred_url="http://127.0.0.1:18100",
        local_url="https://memlayer.loc/api",
        human_url="https://memlayer.loc/api",
        dry_run=False,
    )

    local_env = local_env_path.read_text(encoding="utf-8")
    assert "MEMORYBANK_API_KEY=secret" in local_env
    assert "MEMLAYER_API_URL=http://127.0.0.1:18100" in local_env
    assert "MEMLAYER_EXTRA_URLS=http://host.docker.internal:18100,http://api:8000,http://memorybank-api-1:8000,https://memlayer.loc/api" in local_env


def test_merge_env_text_appends_missing_keys_without_overwriting_existing_values() -> None:
    existing = "MEMORYBANK_API_KEY=secret\nMEMLAYER_API_URL=http://custom:8000\n"
    template = "MEMORYBANK_API_KEY=\nMEMLAYER_API_URL=http://127.0.0.1:18100\nMEMLAYER_EXTRA_URLS=http://api:8000\n"

    merged = merge_env_text(existing, template)

    assert "MEMORYBANK_API_KEY=secret" in merged
    assert "MEMLAYER_API_URL=http://custom:8000" in merged
    assert "MEMLAYER_EXTRA_URLS=http://api:8000" in merged


def test_merge_project_config_preserves_existing_project_identity() -> None:
    existing = {
        "project_id": "8bc076cc-300e-481c-9215-f0e24364d81d",
        "tenant_id": "tenant-1",
        "preferred_url": "http://old:18100",
    }
    generated = {
        "preferred_url": "http://127.0.0.1:18100",
        "local_fallback_url": "https://memlayer.loc/api",
    }

    merged = merge_project_config(existing, generated)

    assert merged["project_id"] == "8bc076cc-300e-481c-9215-f0e24364d81d"
    assert merged["tenant_id"] == "tenant-1"
    assert merged["preferred_url"] == "http://127.0.0.1:18100"
