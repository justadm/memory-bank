import os
from pathlib import Path
import shlex
import stat
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
ROLLBACK_REVISION = "b" * 40
CANDIDATE_IMAGE_ID = "sha256:" + ("c" * 64)
ROLLBACK_IMAGE_ID = "sha256:" + ("d" * 64)
OTHER_IMAGE_ID = "sha256:" + ("e" * 64)


def test_basic_auth_deploy_assets_exist():
    snippet = ROOT / "deploy" / "msk" / "nginx" / "snippets" / "adm.memlayer.basic-auth.conf.example"
    helper = ROOT / "scripts" / "prepare_msk_admin_basic_auth.sh"
    assert snippet.exists()
    assert helper.exists()


def test_basic_auth_helper_has_expected_targets():
    helper = (ROOT / "scripts" / "prepare_msk_admin_basic_auth.sh").read_text(encoding="utf-8")
    assert "openssl passwd -apr1" in helper
    assert "chgrp www-data" in helper
    assert "chmod 640" in helper
    assert "/etc/nginx/.htpasswd-memlayer-admin" in helper
    assert "/etc/nginx/snippets/memlayer_adm_basic_auth.conf" in helper


def test_docker_build_context_excludes_production_backups():
    def patterns(path: Path) -> set[str]:
        return {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

    assert "backups/" in patterns(ROOT / ".dockerignore")
    assert "backups/" in patterns(ROOT / ".gitignore")


def test_docker_build_context_excludes_environment_files():
    patterns = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".env" in patterns
    assert ".env.*" in patterns
    assert "!.env.example" in patterns


def test_release_dockerfiles_require_revision_labels():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG GIT_REVISION" in content
    assert "^[0-9a-f]{40}$" in content
    assert 'org.opencontainers.image.revision="${GIT_REVISION}"' in content


def test_release_builder_uses_exact_clean_git_archive():
    content = (ROOT / "scripts/build_release_image.sh").read_text(encoding="utf-8")

    assert "status --porcelain --untracked-files=all" in content
    assert 'archive --format=tar "${REVISION}"' in content
    assert 'IMAGE="${IMAGE_REPOSITORY}:${REVISION}-candidate"' in content
    assert "--platform" in content
    assert "--no-cache" in content
    assert "scripts/verify_release_image.sh" in content
    assert "APPROVED_IMAGE_ID" in content
    assert content.index('APPROVED_IMAGE_ID="$(') < content.index(
        '"${ROOT_DIR}/scripts/verify_release_image.sh"'
    )
    assert '"${APPROVED_IMAGE_ID}" \\\n  "${REVISION}"' in content
    assert "CANDIDATE_TAG_IMAGE_ID_AFTER" in content
    assert "candidate tag changed during verification" in content
    assert not (ROOT / "deploy/msk/Dockerfile.offline-rebase").exists()


def test_release_image_verifier_checks_revision_and_sensitive_paths():
    content = (ROOT / "scripts/verify_release_image.sh").read_text(encoding="utf-8")

    assert "org.opencontainers.image.revision" in content
    assert "40-character lowercase Git SHA" in content
    assert "--user 0:0" in content
    assert "--network none" in content
    assert "test ! -e /app/.env" in content
    assert "test ! -e /app/backups" in content


def test_standard_msk_release_uses_archive_builder_and_digest_rollout():
    compose = (ROOT / "deploy/msk/docker-compose.yml").read_text(encoding="utf-8")
    deploy_notes = (ROOT / "README_DEPLOY.md").read_text(encoding="utf-8")
    helper = subprocess.run(
        [str(ROOT / "scripts/deploy_msk_prepare.sh")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    api_service = compose.split("\n  db:\n", maxsplit=1)[0]
    assert "build:" not in api_service
    assert "image:" not in api_service
    assert "up -d --build" not in deploy_notes
    assert "docker compose up --build" not in deploy_notes
    assert "scripts/build_release_image.sh msk-api" in deploy_notes
    assert "scripts/rollout_release_image.sh" in deploy_notes
    assert 'export GIT_REVISION="$(git rev-parse HEAD)"' in helper
    assert "scripts/build_release_image.sh msk-api" in helper
    assert (
        'scripts/rollout_release_image.sh msk-api "${GIT_REVISION}" '
        '"${APPROVED_IMAGE_ID}"'
    ) in helper
    assert "msk-api:latest" not in helper


def test_release_compose_entrypoint_rejects_mutable_image_reference(tmp_path):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\necho called >\"${FAKE_DOCKER_CALLED}\"\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    called = tmp_path / "docker-called"

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            "msk-api:latest",
            "rollout-api",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_CALLED": str(called),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "immutable sha256" in result.stderr
    assert not called.exists()


def test_release_compose_entrypoint_rejects_late_compose_override(tmp_path):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\necho called >\"${FAKE_DOCKER_CALLED}\"\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    called = tmp_path / "docker-called"
    mutable_override = tmp_path / "mutable.yml"
    mutable_override.write_text(
        "services:\n  api:\n    image: msk-api:latest\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            CANDIDATE_IMAGE_ID,
            "-f",
            str(mutable_override),
            "rollout-api",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_CALLED": str(called),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert not called.exists()


def test_migrate_head_rejects_running_image_mismatch(tmp_path):
    fake_docker = tmp_path / "docker"
    docker_log = tmp_path / "docker.log"
    fake_docker.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            set -eu
            printf '%s\\n' "$*" >>"${{FAKE_DOCKER_LOG}}"
            if [ "$1" = "inspect" ]; then
              printf '%s\\n' "{ROLLBACK_IMAGE_ID}"
              exit 0
            fi
            exit 0
            """
        ),
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            CANDIDATE_IMAGE_ID,
            "migrate-head",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(docker_log),
            "MEMLAYER_RELEASE_TEST_MODE": "1",
            "MEMLAYER_RELEASE_LOCK_DIR": str(tmp_path / "release.lock"),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "does not match running API container" in result.stderr
    log = docker_log.read_text(encoding="utf-8")
    assert "inspect --format {{.Image}} memlayer-api" in log
    assert "compose " not in log
    assert not (tmp_path / "release.lock").exists()


def test_migrate_head_binds_running_image_and_holds_release_lock(tmp_path):
    fake_docker = tmp_path / "docker"
    docker_log = tmp_path / "docker.log"
    captured_override = tmp_path / "override.yml"
    lock_dir = tmp_path / "release.lock"
    fake_docker.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            set -eu
            printf '%s\\n' "$*" >>"${{FAKE_DOCKER_LOG}}"
            if [ "$1" = "inspect" ]; then
              printf '%s\\n' "{CANDIDATE_IMAGE_ID}"
              exit 0
            fi
            if [ "$1" = "compose" ]; then
              test -d "${{MEMLAYER_RELEASE_LOCK_DIR}}"
              override_file=""
              shift
              while [ "$#" -gt 0 ]; do
                if [ "$1" = "-f" ]; then
                  shift
                  override_file="$1"
                fi
                shift
              done
              cp "${{override_file}}" "${{CAPTURED_OVERRIDE}}"
              exit 0
            fi
            exit 2
            """
        ),
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            CANDIDATE_IMAGE_ID,
            "migrate-head",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_LOG": str(docker_log),
            "CAPTURED_OVERRIDE": str(captured_override),
            "MEMLAYER_RELEASE_TEST_MODE": "1",
            "MEMLAYER_RELEASE_LOCK_DIR": str(lock_dir),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    log = docker_log.read_text(encoding="utf-8")
    assert "inspect --format {{.Image}} memlayer-api" in log
    assert " exec -T api alembic upgrade head" in log
    assert f"image: {CANDIDATE_IMAGE_ID}" in captured_override.read_text(
        encoding="utf-8"
    )
    compose_line = next(
        line for line in log.splitlines() if line.startswith("compose ")
    )
    compose_args = shlex.split(compose_line)
    override_paths = [
        Path(compose_args[index + 1])
        for index, value in enumerate(compose_args[:-1])
        if value == "-f"
    ]
    assert len(override_paths) == 2
    assert "XXXXXX" not in override_paths[-1].name
    assert not override_paths[-1].exists()
    assert not lock_dir.exists()


def test_release_compose_rejects_concurrent_operation(tmp_path):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\necho called >\"${FAKE_DOCKER_CALLED}\"\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    called = tmp_path / "docker-called"
    lock_dir = tmp_path / "release.lock"
    lock_dir.mkdir()

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            CANDIDATE_IMAGE_ID,
            "migrate-head",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_CALLED": str(called),
            "MEMLAYER_RELEASE_TEST_MODE": "1",
            "MEMLAYER_RELEASE_LOCK_DIR": str(lock_dir),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "already active" in result.stderr
    assert not called.exists()


def test_rollout_api_rejects_replayed_owner_token(tmp_path):
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\necho called >\"${FAKE_DOCKER_CALLED}\"\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    called = tmp_path / "docker-called"
    lock_dir = tmp_path / "release.lock"
    lock_dir.mkdir(mode=0o700)
    replayed_token = f"rollout:99999:{REVISION}"
    owner = lock_dir / "owner"
    owner.write_text(f"{replayed_token}\n", encoding="utf-8")
    owner.chmod(0o600)

    result = subprocess.run(
        [
            str(ROOT / "scripts/run_release_compose.sh"),
            CANDIDATE_IMAGE_ID,
            "rollout-api",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "FAKE_DOCKER_CALLED": str(called),
            "MEMLAYER_RELEASE_TEST_MODE": "1",
            "MEMLAYER_RELEASE_LOCK_DIR": str(lock_dir),
            "MEMLAYER_RELEASE_LOCK_TOKEN": replayed_token,
            "MEMLAYER_RELEASE_SUPERVISOR_PID": "99999",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "active rollout supervisor lock" in result.stderr
    assert not called.exists()


def test_release_lock_uses_private_permissions(tmp_path):
    lock_dir = tmp_path / "release.lock"
    token = f"migrate:{os.getpid()}:{CANDIDATE_IMAGE_ID}"
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source scripts/release_lock.sh; "
                "memlayer_release_lock_acquire \"$LOCK_DIR\" \"$LOCK_TOKEN\""
            ),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "LOCK_DIR": str(lock_dir),
            "LOCK_TOKEN": token,
        },
        check=True,
    )

    assert result.returncode == 0
    assert stat.S_IMODE(lock_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((lock_dir / "owner").stat().st_mode) == 0o600
    (lock_dir / "owner").unlink()
    lock_dir.rmdir()


def test_production_release_lock_path_ignores_environment_override(tmp_path):
    custom_lock = tmp_path / "bypass.lock"
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                "source scripts/release_lock.sh; "
                "memlayer_release_lock_path"
            ),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "MEMLAYER_RELEASE_LOCK_DIR": str(custom_lock),
            "MEMLAYER_RELEASE_TEST_MODE": "0",
        },
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "/tmp/memlayer-release-compose.lock"


def test_retired_msk_documents_do_not_contain_build_rollout_commands():
    paths = [
        ROOT / "docs/superpowers/specs/2026-05-26-memlayer-msk-deploy-design.md",
        ROOT / "docs/superpowers/plans/2026-05-26-memlayer-msk-deploy.md",
    ]

    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "up -d --build" not in content
        assert "scripts/rollout_release_image.sh" in content


def test_release_rollout_pins_candidate_digest_and_reads_back_rollback():
    content = (ROOT / "scripts/rollout_release_image.sh").read_text(encoding="utf-8")
    compose_entrypoint = (ROOT / "scripts/run_release_compose.sh").read_text(
        encoding="utf-8"
    )

    assert "scripts/verify_release_image.sh" in content
    assert "APPROVED_IMAGE_ID" in content
    assert "candidate tag does not match approved image digest" in content
    assert "CANDIDATE_IMAGE_ID" in content
    assert "ROLLBACK_IMAGE_ID" in content
    assert "ROLLBACK_TAG" in content
    assert 'docker tag "${ROLLBACK_IMAGE_ID}" "${ROLLBACK_TAG}"' in content
    assert "rollback tag read-back mismatch" in content
    assert "scripts/run_release_compose.sh" in content
    assert 'deploy_image "${CANDIDATE_IMAGE_ID}" "${REVISION}"' in content
    assert "rollout-api" in content
    assert "up -d --no-build --force-recreate --no-deps api" in compose_entrypoint
    assert "running image digest mismatch" in content
    assert "org.opencontainers.image.revision" in content
    assert "rollback_release" in content


def _fake_release_runtime(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "docker.log"
    state_path = tmp_path / "running-image"
    state_path.write_text(ROLLBACK_IMAGE_ID, encoding="utf-8")

    docker = bin_dir / "docker"
    docker.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            printf '%s\\n' "$*" >>"${FAKE_DOCKER_LOG}"
            if [ "${REQUIRE_RELEASE_LOCK_FOR_DOCKER:-0}" = "1" ]; then
              test -f "${MEMLAYER_RELEASE_LOCK_DIR}/owner"
            fi

            if [ "$1" = "run" ]; then
              exit 0
            fi
            if [ "$1" = "tag" ]; then
              exit 0
            fi
            if [ "$1" = "compose" ]; then
              override_file=""
              shift
              while [ "$#" -gt 0 ]; do
                if [ "$1" = "-f" ]; then
                  shift
                  override_file="$1"
                fi
                shift
              done
              release_image="$(
                sed -n 's/^    image: //p' "${override_file}"
              )"
              if [ "${FAIL_ROLLBACK_COMPOSE:-0}" = "1" ] &&
                 [ "${release_image}" = "${FAKE_ROLLBACK_ID}" ]; then
                exit 1
              fi
              printf '%s' "${release_image}" >"${FAKE_STATE}"
              if [ -n "${SIGNAL_ON_CANDIDATE:-}" ] &&
                 [ "${release_image}" = "${FAKE_CANDIDATE_ID}" ]; then
                kill "-${SIGNAL_ON_CANDIDATE}" "${MEMLAYER_ROLLOUT_SUPERVISOR_PID}"
              fi
              if [ -n "${SIGNAL_ON_ROLLBACK:-}" ] &&
                 [ "${release_image}" = "${FAKE_ROLLBACK_ID}" ]; then
                kill "-${SIGNAL_ON_ROLLBACK}" "${MEMLAYER_ROLLOUT_SUPERVISOR_PID}"
              fi
              exit 0
            fi
            if [ "$1" = "inspect" ]; then
              state="$(cat "${FAKE_STATE}")"
              case "$3" in
                *'.Image'*) printf '%s\\n' "${state}" ;;
                *'org.opencontainers.image.revision'*)
                  if [ "${state}" = "${FAKE_CANDIDATE_ID}" ]; then
                    printf '%s\\n' "${FAKE_REVISION}"
                  else
                    printf '%s\\n' "${FAKE_ROLLBACK_REVISION}"
                  fi
                  ;;
                *) exit 2 ;;
              esac
              exit 0
            fi
            if [ "$1" = "image" ] && [ "$2" = "inspect" ]; then
              format="$4"
              image="$5"
              case "${format}" in
                *'.Id'*)
                  case "${image}" in
                    *rollback-*) printf '%s\\n' "${FAKE_ROLLBACK_ID}" ;;
                    *) printf '%s\\n' "${FAKE_CANDIDATE_ID}" ;;
                  esac
                  ;;
                *'org.opencontainers.image.revision'*)
                  case "${image}" in
                    "${FAKE_ROLLBACK_ID}") printf '%s\\n' "${FAKE_ROLLBACK_REVISION}" ;;
                    *) printf '%s\\n' "${FAKE_REVISION}" ;;
                  esac
                  ;;
                *) exit 2 ;;
              esac
              exit 0
            fi
            exit 2
            """
        ),
        encoding="utf-8",
    )
    docker.chmod(0o755)

    git = bin_dir / "git"
    git.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            case "$*" in
              *"rev-parse --verify HEAD") printf '%s\\n' "${FAKE_REVISION}" ;;
              *"status --porcelain --untracked-files=all") exit 0 ;;
              *) exit 2 ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    git.chmod(0o755)

    curl = bin_dir / "curl"
    curl.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            state="$(cat "${FAKE_STATE}")"
            if [ "${FAIL_CANDIDATE_HEALTH:-0}" = "1" ] &&
               [ "${state}" = "${FAKE_CANDIDATE_ID}" ]; then
              if [ "${PROBE_MIGRATION_DURING_HEALTH:-0}" = "1" ] &&
                 [ ! -f "${MIGRATION_PROBE_RESULT}" ]; then
                set +e
                "${RELEASE_COMPOSE_SCRIPT}" \
                  "${FAKE_CANDIDATE_ID}" \
                  migrate-head >/dev/null 2>&1
                printf '%s' "$?" >"${MIGRATION_PROBE_RESULT}"
                set -e
              fi
              exit 22
            fi
            exit 0
            """
        ),
        encoding="utf-8",
    )
    curl.chmod(0o755)

    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_DOCKER_LOG": str(log_path),
        "FAKE_STATE": str(state_path),
        "FAKE_REVISION": REVISION,
        "FAKE_ROLLBACK_REVISION": ROLLBACK_REVISION,
        "FAKE_CANDIDATE_ID": CANDIDATE_IMAGE_ID,
        "FAKE_ROLLBACK_ID": ROLLBACK_IMAGE_ID,
        "REQUIRE_RELEASE_LOCK_FOR_DOCKER": "1",
        "MEMLAYER_RELEASE_TEST_MODE": "1",
        "MEMLAYER_RELEASE_LOCK_DIR": str(tmp_path / "release.lock"),
    }
    return env, log_path, state_path


def test_release_rollout_deploys_candidate_by_immutable_image_id(tmp_path):
    env, log_path, state_path = _fake_release_runtime(tmp_path)

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert state_path.read_text(encoding="utf-8") == CANDIDATE_IMAGE_ID
    log = log_path.read_text(encoding="utf-8")
    assert log.count("run ") == 2
    assert f"tag {ROLLBACK_IMAGE_ID} msk-api:rollback-{ROLLBACK_REVISION}" in log
    assert "compose --env-file .env -f deploy/msk/docker-compose.yml -f " in log
    assert (
        " up -d --no-build "
        "--force-recreate --no-deps api"
    ) in log


def test_release_lock_handoff_cannot_be_interrupted_by_handled_signal(tmp_path):
    env, _, state_path = _fake_release_runtime(tmp_path)
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    fake_mkdir = bin_dir / "mkdir"
    fake_mkdir.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            /bin/mkdir "$@"
            kill -TERM "${PPID}"
            """
        ),
        encoding="utf-8",
    )
    fake_mkdir.chmod(0o755)

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert state_path.read_text(encoding="utf-8") == CANDIDATE_IMAGE_ID
    assert not Path(env["MEMLAYER_RELEASE_LOCK_DIR"]).exists()


def test_release_mutation_state_handoff_cannot_be_interrupted(tmp_path):
    env, _, state_path = _fake_release_runtime(tmp_path)
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    fake_mktemp = bin_dir / "mktemp"
    fake_mktemp.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            case " $* " in
              *" -d "*)
                result="$(/usr/bin/mktemp "$@")"
                kill -TERM "${MEMLAYER_RELEASE_SUPERVISOR_PID}"
                printf '%s\\n' "${result}"
                ;;
              *) exec /usr/bin/mktemp "$@" ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    fake_mktemp.chmod(0o755)

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert state_path.read_text(encoding="utf-8") == CANDIDATE_IMAGE_ID
    assert not Path(env["MEMLAYER_RELEASE_LOCK_DIR"]).exists()


def test_release_rollout_restores_read_back_image_after_failed_health(tmp_path):
    env, _, state_path = _fake_release_runtime(tmp_path)
    env["FAIL_CANDIDATE_HEALTH"] = "1"

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "rollback completed" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID


def test_release_rollout_does_not_rollback_before_mutation_marker(tmp_path):
    env, log_path, state_path = _fake_release_runtime(tmp_path)
    bin_dir = Path(env["PATH"].split(os.pathsep)[0])
    fake_mktemp = bin_dir / "mktemp"
    fake_mktemp.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            set -eu
            case " $* " in
              *" -d "*) exec /usr/bin/mktemp "$@" ;;
              *) exit 1 ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    fake_mktemp.chmod(0o755)

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "restoring verified rollback image" not in result.stderr
    assert "manual recovery is required" not in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID
    assert "compose " not in log_path.read_text(encoding="utf-8")
    assert not Path(env["MEMLAYER_RELEASE_LOCK_DIR"]).exists()


@pytest.mark.parametrize("signal_name", ["HUP", "INT", "TERM"])
def test_release_rollout_ignores_repeated_signal_during_rollback(
    tmp_path,
    signal_name,
):
    env, _, state_path = _fake_release_runtime(tmp_path)
    env["FAIL_CANDIDATE_HEALTH"] = "1"
    env["SIGNAL_ON_ROLLBACK"] = signal_name

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "rollback completed" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID
    assert not Path(env["MEMLAYER_RELEASE_LOCK_DIR"]).exists()


def test_release_rollout_retains_lock_after_failed_rollback(tmp_path):
    env, _, state_path = _fake_release_runtime(tmp_path)
    env["FAIL_CANDIDATE_HEALTH"] = "1"
    env["FAIL_ROLLBACK_COMPOSE"] = "1"

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "rollback failed; manual recovery is required" in result.stderr
    assert "release lock retained after failed rollback" in result.stderr
    assert state_path.read_text(encoding="utf-8") == CANDIDATE_IMAGE_ID
    assert Path(env["MEMLAYER_RELEASE_LOCK_DIR"]).exists()


def test_release_rollout_blocks_migration_until_health_or_rollback_finishes(
    tmp_path,
):
    env, log_path, state_path = _fake_release_runtime(tmp_path)
    migration_probe = tmp_path / "migration-probe-result"
    env.update(
        {
            "FAIL_CANDIDATE_HEALTH": "1",
            "PROBE_MIGRATION_DURING_HEALTH": "1",
            "MIGRATION_PROBE_RESULT": str(migration_probe),
            "RELEASE_COMPOSE_SCRIPT": str(
                ROOT / "scripts/run_release_compose.sh"
            ),
        }
    )

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert migration_probe.read_text(encoding="utf-8") == "1"
    assert "exec -T api alembic upgrade head" not in log_path.read_text(
        encoding="utf-8"
    )
    assert "rollback completed" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID


def test_release_rollout_rejects_candidate_tag_digest_mismatch(tmp_path):
    env, log_path, state_path = _fake_release_runtime(tmp_path)

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            OTHER_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "candidate tag does not match approved image digest" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID
    assert "compose " not in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("signal_name", "exit_code"),
    [("HUP", 129), ("INT", 130), ("TERM", 143)],
)
def test_release_rollout_restores_read_back_image_after_signal(
    tmp_path,
    signal_name,
    exit_code,
):
    env, _, state_path = _fake_release_runtime(tmp_path)
    env["SIGNAL_ON_CANDIDATE"] = signal_name

    result = subprocess.run(
        [
            str(ROOT / "scripts/rollout_release_image.sh"),
            "msk-api",
            REVISION,
            CANDIDATE_IMAGE_ID,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == exit_code
    assert "rollback completed" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID
