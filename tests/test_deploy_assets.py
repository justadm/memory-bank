from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


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


def test_standard_msk_build_propagates_and_verifies_git_revision():
    compose = (ROOT / "deploy/msk/docker-compose.yml").read_text(encoding="utf-8")
    helper = subprocess.run(
        [str(ROOT / "scripts/deploy_msk_prepare.sh")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "GIT_REVISION: ${GIT_REVISION:?" in compose
    assert 'export GIT_REVISION="$(git rev-parse HEAD)"' in helper
    assert "scripts/build_release_image.sh msk-api" in helper
    assert 'docker tag "msk-api:${GIT_REVISION}-candidate" msk-api:latest' in helper
