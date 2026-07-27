#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 IMAGE_REPOSITORY GIT_REVISION APPROVED_IMAGE_ID" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/release_lock.sh
source "${ROOT_DIR}/scripts/release_lock.sh"
IMAGE_REPOSITORY="$1"
REVISION="$2"
APPROVED_IMAGE_ID="$3"
CANDIDATE_IMAGE="${IMAGE_REPOSITORY}:${REVISION}-candidate"
HEALTH_URL="${MEMLAYER_HEALTH_URL:-http://127.0.0.1:18120/health}"

if [[ ! "${REVISION}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "revision must be a 40-character lowercase Git SHA" >&2
  exit 2
fi

if [[ ! "${APPROVED_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "approved image ID must be an immutable sha256 digest" >&2
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

ROLLBACK_TRAP_ARMED=0
RELEASE_LOCK_DIR="$(memlayer_release_lock_path)"
RELEASE_LOCK_TOKEN="rollout:$$:${REVISION}"
RELEASE_LOCK_ACQUIRED=0

release_rollout_lock() {
  if [[ "${RELEASE_LOCK_ACQUIRED}" -ne 1 ]]; then
    return
  fi
  memlayer_release_lock_release \
    "${RELEASE_LOCK_DIR}" \
    "${RELEASE_LOCK_TOKEN}" || {
      echo "release lock ownership changed; manual cleanup is required" >&2
      return 1
    }
  RELEASE_LOCK_ACQUIRED=0
  unset MEMLAYER_RELEASE_LOCK_TOKEN
  unset MEMLAYER_RELEASE_SUPERVISOR_PID
}

cleanup_after_exit() {
  local exit_code="$1"

  trap - EXIT HUP INT TERM
  release_rollout_lock || exit 2
  exit "${exit_code}"
}

cleanup_after_signal() {
  local exit_code="$1"

  trap - EXIT HUP INT TERM
  release_rollout_lock || exit 2
  exit "${exit_code}"
}

install_cleanup_traps() {
  trap 'cleanup_after_exit $?' EXIT
  trap 'cleanup_after_signal 129' HUP
  trap 'cleanup_after_signal 130' INT
  trap 'cleanup_after_signal 143' TERM
}

disarm_rollback_traps() {
  ROLLBACK_TRAP_ARMED=0
  install_cleanup_traps
}

rollback_after_exit() {
  local exit_code="$1"

  if [[ "${ROLLBACK_TRAP_ARMED}" -ne 1 ]]; then
    exit "${exit_code}"
  fi
  disarm_rollback_traps
  if ! rollback_release; then
    release_rollout_lock || true
    exit 2
  fi
  release_rollout_lock || exit 2
  trap - EXIT HUP INT TERM
  exit "${exit_code}"
}

rollback_after_signal() {
  local exit_code="$1"

  disarm_rollback_traps
  if ! rollback_release; then
    release_rollout_lock || true
    exit 2
  fi
  release_rollout_lock || exit 2
  trap - EXIT HUP INT TERM
  exit "${exit_code}"
}

acquire_release_lock() {
  install_cleanup_traps
  trap '' HUP INT TERM
  if ! memlayer_release_lock_acquire \
    "${RELEASE_LOCK_DIR}" \
    "${RELEASE_LOCK_TOKEN}"; then
    install_cleanup_traps
    echo "another release Compose operation is already active" >&2
    return 1
  fi
  RELEASE_LOCK_ACQUIRED=1
  export MEMLAYER_RELEASE_LOCK_TOKEN="${RELEASE_LOCK_TOKEN}"
  export MEMLAYER_RELEASE_SUPERVISOR_PID="$$"
  install_cleanup_traps
}

arm_rollback_traps() {
  ROLLBACK_TRAP_ARMED=1
  trap 'rollback_after_exit $?' EXIT
  trap 'rollback_after_signal 129' HUP
  trap 'rollback_after_signal 130' INT
  trap 'rollback_after_signal 143' TERM
}

acquire_release_lock
cd "${ROOT_DIR}"

CANDIDATE_TAG_IMAGE_ID="$(
  docker image inspect --format '{{.Id}}' "${CANDIDATE_IMAGE}"
)"
if [[ ! "${CANDIDATE_TAG_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "candidate image has no immutable sha256 identity" >&2
  exit 1
fi
if [[ "${CANDIDATE_TAG_IMAGE_ID}" != "${APPROVED_IMAGE_ID}" ]]; then
  echo "candidate tag does not match approved image digest" >&2
  exit 1
fi

CANDIDATE_IMAGE_ID="${APPROVED_IMAGE_ID}"
"${ROOT_DIR}/scripts/verify_release_image.sh" \
  "${CANDIDATE_IMAGE_ID}" \
  "${REVISION}"

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

  MEMLAYER_ROLLOUT_SUPERVISOR_PID="$$" \
    "${ROOT_DIR}/scripts/run_release_compose.sh" \
    "${image_id}" \
    rollout-api || return 1

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

arm_rollback_traps
deploy_image "${CANDIDATE_IMAGE_ID}" "${REVISION}"
disarm_rollback_traps
release_rollout_lock
trap - EXIT HUP INT TERM

echo "release rollout passed"
echo "revision=${REVISION}"
echo "image_id=${CANDIDATE_IMAGE_ID}"
echo "rollback_tag=${ROLLBACK_TAG}"
echo "rollback_image_id=${ROLLBACK_IMAGE_ID}"
