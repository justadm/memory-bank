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

RELEASE_LOCK_DIR="$(memlayer_release_lock_path)"
RELEASE_LOCK_TOKEN="rollout:$$:${REVISION}"
RELEASE_LOCK_ACQUIRED=0
MUTATION_STATE_DIR=""
MUTATION_MARKER=""
RELEASE_SUCCEEDED=0

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

mutation_started() {
  [[ -n "${MUTATION_MARKER}" && -f "${MUTATION_MARKER}" ]]
}

cleanup_mutation_state() {
  local cleanup_failed=0

  if [[ -n "${MUTATION_MARKER}" ]]; then
    rm -f "${MUTATION_MARKER}" || cleanup_failed=1
  fi
  if [[ -n "${MUTATION_STATE_DIR}" && -d "${MUTATION_STATE_DIR}" ]]; then
    rmdir "${MUTATION_STATE_DIR}" || cleanup_failed=1
  fi
  MUTATION_MARKER=""
  MUTATION_STATE_DIR=""
  unset MEMLAYER_RELEASE_MUTATION_MARKER
  return "${cleanup_failed}"
}

finish_after_failure() {
  local exit_code="$1"
  local final_exit_code="${exit_code}"
  local rollback_failed=0

  # Rollback must not be interrupted after the mutation boundary.
  trap - EXIT
  trap '' HUP INT TERM
  if [[ "${RELEASE_SUCCEEDED}" -ne 1 ]] && mutation_started; then
    if ! rollback_release; then
      final_exit_code=2
      rollback_failed=1
    fi
  fi
  if ! cleanup_mutation_state; then
    echo "release mutation marker cleanup failed; manual cleanup is required" >&2
    final_exit_code=2
  fi
  if [[ "${rollback_failed}" -eq 1 ]]; then
    echo "release lock retained after failed rollback" >&2
  elif ! release_rollout_lock; then
    final_exit_code=2
  fi
  trap - EXIT HUP INT TERM
  exit "${final_exit_code}"
}

install_failure_traps() {
  trap 'finish_after_failure $?' EXIT
  trap 'finish_after_failure 129' HUP
  trap 'finish_after_failure 130' INT
  trap 'finish_after_failure 143' TERM
}

acquire_release_lock() {
  install_failure_traps
  trap '' HUP INT TERM
  if ! memlayer_release_lock_acquire \
    "${RELEASE_LOCK_DIR}" \
    "${RELEASE_LOCK_TOKEN}"; then
    install_failure_traps
    echo "another release Compose operation is already active" >&2
    return 1
  fi
  RELEASE_LOCK_ACQUIRED=1
  export MEMLAYER_RELEASE_LOCK_TOKEN="${RELEASE_LOCK_TOKEN}"
  export MEMLAYER_RELEASE_SUPERVISOR_PID="$$"
  install_failure_traps
}

prepare_mutation_state() {
  trap '' HUP INT TERM
  if ! MUTATION_STATE_DIR="$(
    umask 077
    mktemp -d "${TMPDIR:-/tmp}/memlayer-release-mutation.XXXXXX"
  )"; then
    install_failure_traps
    echo "failed to create private release mutation state" >&2
    return 1
  fi
  if [[ ! -d "${MUTATION_STATE_DIR}" || -L "${MUTATION_STATE_DIR}" ]]; then
    install_failure_traps
    echo "failed to create private release mutation state" >&2
    return 1
  fi
  MUTATION_MARKER="${MUTATION_STATE_DIR}/started"
  export MEMLAYER_RELEASE_MUTATION_MARKER="${MUTATION_MARKER}"
  install_failure_traps
}

acquire_release_lock
prepare_mutation_state
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
    MEMLAYER_RELEASE_MUTATION_MARKER="${MUTATION_MARKER}" \
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

deploy_image "${CANDIDATE_IMAGE_ID}" "${REVISION}"
RELEASE_SUCCEEDED=1
if ! cleanup_mutation_state; then
  echo "release mutation marker cleanup failed; manual cleanup is required" >&2
  release_rollout_lock || true
  trap - EXIT HUP INT TERM
  exit 2
fi
release_rollout_lock
trap - EXIT HUP INT TERM

echo "release rollout passed"
echo "revision=${REVISION}"
echo "image_id=${CANDIDATE_IMAGE_ID}"
echo "rollback_tag=${ROLLBACK_TAG}"
echo "rollback_image_id=${ROLLBACK_IMAGE_ID}"
