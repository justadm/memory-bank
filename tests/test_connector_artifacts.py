from pathlib import Path, PurePosixPath

import pytest

from memlayer_connector.artifacts import OwnershipMode, RenderContext, artifact_registry, render_artifact


def make_context(tmp_path: Path) -> RenderContext:
    return RenderContext(
        project_name="demo",
        project_root=tmp_path,
        preferred_url="https://api.memlayer.ru",
        local_url="http://127.0.0.1:18100",
        human_url="https://api.memlayer.ru",
    )


def test_codex_registry_covers_every_connector_artifact(tmp_path: Path) -> None:
    registry = artifact_registry("codex", 1, make_context(tmp_path))

    assert registry[PurePosixPath("AGENTS.md")].ownership is OwnershipMode.MANAGED_SECTION
    assert registry[PurePosixPath(".gitignore")].ownership is OwnershipMode.MANAGED_LINE
    assert registry[PurePosixPath(".memlayer/.env.memlayer")].ownership is OwnershipMode.USER_OWNED
    assert registry[PurePosixPath(".memlayer/memlayer.offline.queue.jsonl")].ownership is OwnershipMode.CREATE_IF_ABSENT
    assert registry[PurePosixPath(".agents/skills/memlayer/SKILL.md")].ownership is OwnershipMode.WHOLE_FILE
    assert all(not path.is_absolute() and ".." not in path.parts for path in registry)


def test_registry_hashes_are_deterministic_and_context_specific(tmp_path: Path) -> None:
    first_context = make_context(tmp_path)
    second_context = make_context(tmp_path)
    first = artifact_registry("codex", 1, first_context)
    second = artifact_registry("codex", 1, second_context)
    assert {path: spec.expected_sha256 for path, spec in first.items()} == {
        path: spec.expected_sha256 for path, spec in second.items()
    }

    changed = artifact_registry("codex", 1, RenderContext("other", tmp_path, first_context.preferred_url, first_context.local_url, first_context.human_url))
    assert first[PurePosixPath(".memlayer/MEMLAYER.md")].expected_sha256 != changed[PurePosixPath(".memlayer/MEMLAYER.md")].expected_sha256


def test_user_owned_env_is_not_rendered(tmp_path: Path) -> None:
    spec = artifact_registry("codex", 1, make_context(tmp_path))[PurePosixPath(".memlayer/.env.memlayer")]
    assert spec.expected_sha256 is None
    with pytest.raises(ValueError, match="user-owned"):
        render_artifact(spec, make_context(tmp_path))


def test_unsupported_agent_and_version_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported agent"):
        artifact_registry("cursor", 1, make_context(tmp_path))
    with pytest.raises(ValueError, match="unsupported root-pack"):
        artifact_registry("codex", 2, make_context(tmp_path))
