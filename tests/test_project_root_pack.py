from __future__ import annotations

from pathlib import Path

from scripts.install_memlayer_project_pack import (
    MANAGED_END,
    MANAGED_START,
    build_project_config,
    install_for_project,
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
    assert (project_root / "memlayer.config.json").exists()


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
