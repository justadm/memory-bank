import os
from pathlib import Path
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
ROLLBACK_REVISION = "b" * 40
CANDIDATE_IMAGE_ID = "sha256:" + ("c" * 64)
ROLLBACK_IMAGE_ID = "sha256:" + ("d" * 64)


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

    assert "build:" not in compose
    assert "image: ${MEMLAYER_API_IMAGE:?" in compose
    assert "up -d --build" not in deploy_notes
    assert "docker compose up --build" not in deploy_notes
    assert "scripts/build_release_image.sh msk-api" in deploy_notes
    assert "scripts/rollout_release_image.sh msk-api" in deploy_notes
    assert 'export GIT_REVISION="$(git rev-parse HEAD)"' in helper
    assert "scripts/build_release_image.sh msk-api" in helper
    assert 'scripts/rollout_release_image.sh msk-api "${GIT_REVISION}"' in helper
    assert "msk-api:latest" not in helper


def test_release_rollout_pins_candidate_digest_and_reads_back_rollback():
    content = (ROOT / "scripts/rollout_release_image.sh").read_text(encoding="utf-8")

    assert "scripts/verify_release_image.sh" in content
    assert "CANDIDATE_IMAGE_ID" in content
    assert "ROLLBACK_IMAGE_ID" in content
    assert "ROLLBACK_TAG" in content
    assert 'docker tag "${ROLLBACK_IMAGE_ID}" "${ROLLBACK_TAG}"' in content
    assert "rollback tag read-back mismatch" in content
    assert 'MEMLAYER_API_IMAGE="${image_id}"' in content
    assert 'deploy_image "${CANDIDATE_IMAGE_ID}" "${REVISION}"' in content
    assert "up -d --no-build --force-recreate --no-deps api" in content
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
            printf '%s|%s\\n' "${MEMLAYER_API_IMAGE:-}" "$*" >>"${FAKE_DOCKER_LOG}"

            if [ "$1" = "run" ]; then
              exit 0
            fi
            if [ "$1" = "tag" ]; then
              exit 0
            fi
            if [ "$1" = "compose" ]; then
              printf '%s' "${MEMLAYER_API_IMAGE}" >"${FAKE_STATE}"
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
    }
    return env, log_path, state_path


def test_release_rollout_deploys_candidate_by_immutable_image_id(tmp_path):
    env, log_path, state_path = _fake_release_runtime(tmp_path)

    result = subprocess.run(
        [str(ROOT / "scripts/rollout_release_image.sh"), "msk-api", REVISION],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert state_path.read_text(encoding="utf-8") == CANDIDATE_IMAGE_ID
    log = log_path.read_text(encoding="utf-8")
    assert log.count("|run ") == 2
    assert f"|tag {ROLLBACK_IMAGE_ID} msk-api:rollback-{ROLLBACK_REVISION}" in log
    assert (
        f"{CANDIDATE_IMAGE_ID}|compose --env-file .env "
        "-f deploy/msk/docker-compose.yml up -d --no-build "
        "--force-recreate --no-deps api"
    ) in log


def test_release_rollout_restores_read_back_image_after_failed_health(tmp_path):
    env, _, state_path = _fake_release_runtime(tmp_path)
    env["FAIL_CANDIDATE_HEALTH"] = "1"

    result = subprocess.run(
        [str(ROOT / "scripts/rollout_release_image.sh"), "msk-api", REVISION],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "rollback completed" in result.stderr
    assert state_path.read_text(encoding="utf-8") == ROLLBACK_IMAGE_ID
