#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 IMAGE_REPOSITORY GIT_REVISION" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_REPOSITORY="$1"
REVISION="$2"
CANDIDATE_IMAGE="${IMAGE_REPOSITORY}:${REVISION}-candidate"
HEALTH_URL="${MEMLAYER_HEALTH_URL:-http://127.0.0.1:18120/health}"
COMPOSE=(
  docker compose
  --env-file .env
  -f deploy/msk/docker-compose.yml
)

if [[ ! "${REVISION}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "revision must be a 40-character lowercase Git SHA" >&2
  exit 2
fi

if [[ "$(git -C "${ROOT_DIR}" rev-parse --verify HEAD)" != "${REVISION}" ]]; then
  echo "checkout HEAD does not match approved revision" >&2
  exit 1
fi

if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain --untracked-files=all)" ]]; then
  echo "release rollout requires a clean Git worktree" >&2
  exit 1
fi

cd "${ROOT_DIR}"
"${ROOT_DIR}/scripts/verify_release_image.sh" "${CANDIDATE_IMAGE}" "${REVISION}"

CANDIDATE_IMAGE_ID="$(
  docker image inspect --format '{{.Id}}' "${CANDIDATE_IMAGE}"
)"
if [[ ! "${CANDIDATE_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "candidate image has no immutable sha256 identity" >&2
  exit 1
fi

ROLLBACK_IMAGE_ID="$(
  docker inspect --format '{{.Image}}' memlayer-api
)"
if [[ ! "${ROLLBACK_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "running API container has no immutable rollback image identity" >&2
  exit 1
fi

ROLLBACK_REVISION="$(
  docker image inspect \
    --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
    "${ROLLBACK_IMAGE_ID}"
)"
if [[ ! "${ROLLBACK_REVISION}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "rollback image has no valid Git revision label" >&2
  exit 1
fi

"${ROOT_DIR}/scripts/verify_release_image.sh" \
  "${ROLLBACK_IMAGE_ID}" \
  "${ROLLBACK_REVISION}"

ROLLBACK_TAG="${IMAGE_REPOSITORY}:rollback-${ROLLBACK_REVISION}"
docker tag "${ROLLBACK_IMAGE_ID}" "${ROLLBACK_TAG}"
ROLLBACK_TAG_IMAGE_ID="$(
  docker image inspect --format '{{.Id}}' "${ROLLBACK_TAG}"
)"
if [[ "${ROLLBACK_TAG_IMAGE_ID}" != "${ROLLBACK_IMAGE_ID}" ]]; then
  echo "rollback tag read-back mismatch" >&2
  exit 1
fi

wait_for_health() {
  local _
  for _ in {1..30}; do
    if curl --fail --silent --show-error --max-time 3 "${HEALTH_URL}" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "API health check did not recover" >&2
  return 1
}

deploy_image() {
  local image_id="$1"
  local expected_revision="$2"
  local running_image_id
  local running_revision

  MEMLAYER_API_IMAGE="${image_id}" \
    "${COMPOSE[@]}" up -d --no-build --force-recreate --no-deps api || return 1

  running_image_id="$(
    docker inspect --format '{{.Image}}' memlayer-api
  )" || return 1
  if [[ "${running_image_id}" != "${image_id}" ]]; then
    echo "running image digest mismatch" >&2
    return 1
  fi

  running_revision="$(
    docker inspect \
      --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
      memlayer-api
  )" || return 1
  if [[ "${running_revision}" != "${expected_revision}" ]]; then
    echo "running image revision mismatch" >&2
    return 1
  fi

  wait_for_health
}

rollback_release() {
  echo "candidate rollout failed; restoring verified rollback image" >&2
  if ! deploy_image "${ROLLBACK_IMAGE_ID}" "${ROLLBACK_REVISION}"; then
    echo "rollback failed; manual recovery is required" >&2
    return 1
  fi
  echo "rollback completed" >&2
}

if ! deploy_image "${CANDIDATE_IMAGE_ID}" "${REVISION}"; then
  rollback_release || exit 2
  exit 1
fi

echo "release rollout passed"
echo "revision=${REVISION}"
echo "image_id=${CANDIDATE_IMAGE_ID}"
echo "rollback_tag=${ROLLBACK_TAG}"
echo "rollback_image_id=${ROLLBACK_IMAGE_ID}"
