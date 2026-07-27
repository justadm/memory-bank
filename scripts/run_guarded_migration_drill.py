#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from urllib.parse import urlsplit


ALLOWED_CHILD_ENVIRONMENT = (
    "PATH",
    "HOME",
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_CONFIG",
    "XDG_RUNTIME_DIR",
    "TMPDIR",
)
PROFILE_TARGETS = {
    "connector": {"20260725_0005"},
    "temporal": {"20260725_0006", "head"},
}
MIGRATION_DRILL_GIT_REVISION = "0" * 40


class MigrationDrillError(RuntimeError):
    pass


def validate_disposable_database_url(database_url: str) -> None:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"}:
        raise MigrationDrillError("migration drill requires PostgreSQL")
    if parsed.hostname != "db" or parsed.port not in {None, 5432}:
        raise MigrationDrillError("migration drill database host must be the isolated Compose service")
    if not (parsed.username or "").startswith("memlayer_migration_drill_"):
        raise MigrationDrillError("migration drill database user is not synthetic")
    if not parsed.password:
        raise MigrationDrillError("migration drill database password is required")
    if not parsed.path.removeprefix("/").startswith("memlayer_migration_drill_"):
        raise MigrationDrillError("migration drill database name is not synthetic")
    if parsed.query or parsed.fragment:
        raise MigrationDrillError("migration drill database URL may not contain options")


def build_child_environment(source: Mapping[str, str], *, cwd: Path) -> dict[str, str]:
    child = {key: source[key] for key in ALLOWED_CHILD_ENVIRONMENT if source.get(key)}
    child["PWD"] = str(cwd)
    child["COMPOSE_DISABLE_ENV_FILE"] = "1"
    return child


def _write_env_file(path: Path, values: Mapping[str, str]) -> None:
    for key, value in values.items():
        if "\n" in key or "\n" in value or "\r" in key or "\r" in value:
            raise MigrationDrillError("migration environment values must be single-line")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise MigrationDrillError("migration environment file permissions are not 0600")


def _validate_profile_target(*, target: str, fixture_profile: str) -> None:
    allowed = PROFILE_TARGETS.get(fixture_profile)
    if allowed is None:
        raise MigrationDrillError(f"unsupported fixture profile: {fixture_profile}")
    if target not in allowed:
        raise MigrationDrillError(
            f"target {target!r} is not allowed for fixture profile {fixture_profile!r}"
        )


def run_guarded_migration_drill(
    *,
    repo_root: Path,
    target: str,
    fixture_profile: str,
    run_command: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    parent_environment: Mapping[str, str] | None = None,
    temporary_parent: Path | None = None,
) -> None:
    repo_root = repo_root.resolve(strict=True)
    _validate_profile_target(target=target, fixture_profile=fixture_profile)
    compose_file = repo_root / "deploy/test/docker-compose.migration.yml"
    if not compose_file.is_file():
        raise MigrationDrillError(f"missing migration Compose file: {compose_file}")

    parent = temporary_parent.resolve() if temporary_parent else None
    if parent and (parent == repo_root or parent.is_relative_to(repo_root)):
        raise MigrationDrillError("temporary migration directory must be outside the repository")

    run_id = secrets.token_hex(8)
    project_name = f"memlayer_migration_drill_{run_id}"
    database_name = f"memlayer_migration_drill_{run_id}"
    database_user = f"memlayer_migration_drill_user_{run_id}"
    database_password = secrets.token_urlsafe(24)
    database_url = (
        f"postgresql+psycopg://{database_user}:{database_password}"
        f"@db:5432/{database_name}"
    )
    validate_disposable_database_url(database_url)

    with tempfile.TemporaryDirectory(
        prefix="memlayer_migration_drill_",
        dir=str(parent) if parent else None,
    ) as temporary_directory:
        temp_dir = Path(temporary_directory).resolve()
        if temp_dir == repo_root or temp_dir.is_relative_to(repo_root):
            raise MigrationDrillError("temporary migration directory resolved inside repository")
        env_path = temp_dir / "compose.env"
        _write_env_file(
            env_path,
            {
                "MEMLAYER_REPO_ROOT": str(repo_root),
                "POSTGRES_DB": database_name,
                "POSTGRES_USER": database_user,
                "POSTGRES_PASSWORD": database_password,
                "DATABASE_URL": database_url,
                "GIT_REVISION": MIGRATION_DRILL_GIT_REVISION,
                "MIGRATION_TARGET": target,
                "MIGRATION_FIXTURE_PROFILE": fixture_profile,
            },
        )
        compose_prefix = [
            "docker",
            "compose",
            "--project-name",
            project_name,
            "--project-directory",
            str(temp_dir),
            "--env-file",
            str(env_path),
            "--file",
            str(compose_file),
        ]
        child_env = build_child_environment(
            parent_environment if parent_environment is not None else os.environ,
            cwd=temp_dir,
        )
        primary_error: BaseException | None = None
        try:
            run_command(
                [
                    *compose_prefix,
                    "up",
                    "--build",
                    "--abort-on-container-exit",
                    "--exit-code-from",
                    "migration",
                ],
                cwd=temp_dir,
                env=child_env,
                check=True,
                timeout=900,
            )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                run_command(
                    [
                        *compose_prefix,
                        "down",
                        "--volumes",
                        "--remove-orphans",
                        "--rmi",
                        "local",
                    ],
                    cwd=temp_dir,
                    env=child_env,
                    check=True,
                    timeout=120,
                )
            except BaseException as cleanup_error:
                if primary_error is None:
                    raise
                raise ExceptionGroup(
                    "migration drill and cleanup both failed",
                    [primary_error, cleanup_error],
                ) from primary_error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run MemLayer migrations only against an isolated disposable PostgreSQL service."
    )
    parser.add_argument("--target", required=True, choices=["20260725_0005", "20260725_0006", "head"])
    parser.add_argument("--fixture-profile", required=True, choices=sorted(PROFILE_TARGETS))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_guarded_migration_drill(
        repo_root=Path(__file__).resolve().parents[1],
        target=args.target,
        fixture_profile=args.fixture_profile,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
