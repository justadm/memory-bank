from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from scripts.run_guarded_migration_drill import (
    MigrationDrillError,
    build_child_environment,
    run_guarded_migration_drill,
    validate_disposable_database_url,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_disposable_database_url_rejects_external_and_mismatched_targets() -> None:
    valid = (
        "postgresql+psycopg://memlayer_migration_drill_user:"
        "synthetic-password@db:5432/memlayer_migration_drill_db"
    )
    validate_disposable_database_url(valid)

    invalid = [
        valid.replace("@db:", "@localhost:"),
        valid.replace("@db:", "@db.example.com:"),
        valid.replace("postgresql+psycopg", "sqlite"),
        valid.replace("memlayer_migration_drill_db", "memory_bank"),
        valid.replace("memlayer_migration_drill_user", "memory_user"),
        valid + "?sslmode=require",
    ]
    for database_url in invalid:
        with pytest.raises(MigrationDrillError):
            validate_disposable_database_url(database_url)


def test_child_environment_is_allowlisted_and_disables_default_env_discovery() -> None:
    source = {
        "PATH": "/usr/bin",
        "HOME": "/tmp/home",
        "DOCKER_HOST": "unix:///tmp/docker.sock",
        "DATABASE_URL": "postgresql://production",
        "MEMLAYER_API_KEY": "secret",
        "POSTGRES_PASSWORD": "secret",
        "HTTPS_PROXY": "https://user:password@example.invalid",
        "COMPOSE_FILE": "production.yml",
    }

    child = build_child_environment(source, cwd=Path("/tmp/drill"))

    assert child == {
        "PATH": "/usr/bin",
        "HOME": "/tmp/home",
        "DOCKER_HOST": "unix:///tmp/docker.sock",
        "PWD": "/tmp/drill",
        "COMPOSE_DISABLE_ENV_FILE": "1",
    }


def test_runner_uses_isolated_compose_context_and_synthetic_env_file(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path, dict[str, str]]] = []

    def fake_run(command, *, cwd, env, check, timeout):
        assert check is True
        assert timeout > 0
        cwd_path = Path(cwd)
        env_path = Path(command[command.index("--env-file") + 1])
        compose_path = Path(command[command.index("--file") + 1])
        assert cwd_path == env_path.parent
        assert cwd_path != REPO_ROOT
        assert not cwd_path.is_relative_to(REPO_ROOT)
        assert compose_path == REPO_ROOT / "deploy/test/docker-compose.migration.yml"
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
        env_text = env_path.read_text()
        assert "MEMLAYER_REPO_ROOT=" + str(REPO_ROOT) in env_text
        assert "DATABASE_URL=postgresql+psycopg://" in env_text
        assert "production" not in env_text
        assert "secret-parent-value" not in env_text
        assert env == {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "PWD": str(cwd_path),
            "COMPOSE_DISABLE_ENV_FILE": "1",
        }
        calls.append((list(command), cwd_path, dict(env)))
        return subprocess.CompletedProcess(command, 0)

    run_guarded_migration_drill(
        repo_root=REPO_ROOT,
        target="20260725_0005",
        fixture_profile="connector",
        run_command=fake_run,
        parent_environment={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "DATABASE_URL": "postgresql://production",
            "MEMLAYER_API_KEY": "secret-parent-value",
        },
        temporary_parent=tmp_path,
    )

    assert len(calls) == 2
    prefix = calls[0][0][:10]
    assert prefix[:2] == ["docker", "compose"]
    assert "--project-name" in prefix
    assert prefix[prefix.index("--project-name") + 1].startswith("memlayer_migration_drill_")
    assert calls[0][0][:10] == calls[1][0][:10]
    assert calls[0][0][10:] == [
        "up",
        "--build",
        "--abort-on-container-exit",
        "--exit-code-from",
        "migration",
    ]
    assert calls[1][0][10:] == [
        "down",
        "--volumes",
        "--remove-orphans",
        "--rmi",
        "local",
    ]


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(1, ["docker"]),
        subprocess.TimeoutExpired(["docker"], timeout=1),
        KeyboardInterrupt(),
    ],
)
def test_runner_always_attempts_cleanup(tmp_path: Path, failure: BaseException) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if command[-1] == "migration":
            raise failure
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(type(failure)):
        run_guarded_migration_drill(
            repo_root=REPO_ROOT,
            target="20260725_0005",
            fixture_profile="connector",
            run_command=fake_run,
            parent_environment={"PATH": "/usr/bin", "HOME": "/tmp"},
            temporary_parent=tmp_path,
        )

    assert calls[-1][-5:] == [
        "down",
        "--volumes",
        "--remove-orphans",
        "--rmi",
        "local",
    ]


def test_runner_reports_primary_and_cleanup_failures(tmp_path: Path) -> None:
    calls = []

    def fail_both(command, **kwargs):
        calls.append(command)
        if "up" in command:
            raise subprocess.CalledProcessError(1, command)
        raise subprocess.CalledProcessError(2, command)

    with pytest.raises(ExceptionGroup) as exc_info:
        run_guarded_migration_drill(
            repo_root=REPO_ROOT,
            target="20260725_0005",
            fixture_profile="connector",
            run_command=fail_both,
            parent_environment={"PATH": "/usr/bin"},
            temporary_parent=tmp_path,
        )

    assert len(exc_info.value.exceptions) == 2
    assert calls[-1][-5:] == [
        "down",
        "--volumes",
        "--remove-orphans",
        "--rmi",
        "local",
    ]


def test_runner_rejects_target_profile_mismatch_before_compose(tmp_path: Path) -> None:
    with pytest.raises(MigrationDrillError, match="target"):
        run_guarded_migration_drill(
            repo_root=REPO_ROOT,
            target="head",
            fixture_profile="connector",
            run_command=lambda *args, **kwargs: None,
            temporary_parent=tmp_path,
        )
