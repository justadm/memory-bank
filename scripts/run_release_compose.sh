#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 IMAGE_ID OPERATION" >&2
  echo "Operations: rollout-api, migrate-head" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/release_lock.sh
source "${ROOT_DIR}/scripts/release_lock.sh"
IMAGE_ID="$1"
OPERATION="$2"
LOCK_DIR="$(memlayer_release_lock_path)"
LOCK_TOKEN=""
LOCK_ACQUIRED=0
OVERRIDE_FILE=""

if [[ ! "${IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "image ID must be an immutable sha256 digest" >&2
  exit 2
fi

case "${OPERATION}" in
  rollout-api|migrate-head)
    ;;
  *)
    echo "unsupported release Compose operation: ${OPERATION}" >&2
    exit 2
    ;;
esac

cleanup() {
  if [[ -n "${OVERRIDE_FILE}" ]]; then
    rm -f "${OVERRIDE_FILE}"
  fi
  if [[ "${LOCK_ACQUIRED}" -eq 1 ]]; then
    memlayer_release_lock_release "${LOCK_DIR}" "${LOCK_TOKEN}" || true
  fi
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "${OPERATION}" == "rollout-api" ]]; then
  LOCK_TOKEN="${MEMLAYER_RELEASE_LOCK_TOKEN:-}"
  SUPERVISOR_PID="${MEMLAYER_RELEASE_SUPERVISOR_PID:-}"
  if [[ ! "${SUPERVISOR_PID}" =~ ^[1-9][0-9]*$ ]] ||
     [[ "${SUPERVISOR_PID}" != "${PPID}" ]] ||
     [[ "${LOCK_TOKEN}" != rollout:"${SUPERVISOR_PID}":* ]] ||
     ! memlayer_release_lock_assert_owner "${LOCK_DIR}" "${LOCK_TOKEN}"; then
    echo "rollout-api requires the active rollout supervisor lock" >&2
    exit 1
  fi
else
  LOCK_TOKEN="migrate:$$:${IMAGE_ID}"
  trap '' HUP INT TERM
  if ! memlayer_release_lock_acquire "${LOCK_DIR}" "${LOCK_TOKEN}"; then
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    echo "another release Compose operation is already active" >&2
    exit 1
  fi
  LOCK_ACQUIRED=1
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
fi

OVERRIDE_FILE="$(
  mktemp "${TMPDIR:-/tmp}/memlayer-release-compose.XXXXXX"
)"
chmod 600 "${OVERRIDE_FILE}"
printf 'services:\n  api:\n    image: %s\n' "${IMAGE_ID}" >"${OVERRIDE_FILE}"

case "${OPERATION}" in
  rollout-api)
    COMPOSE_ARGUMENTS=(
      up -d --no-build --force-recreate --no-deps api
    )
    ;;
  migrate-head)
    RUNNING_IMAGE_ID="$(
      docker inspect --format '{{.Image}}' memlayer-api
    )"
    if [[ ! "${RUNNING_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
      echo "running API container has no immutable image identity" >&2
      exit 1
    fi
    if [[ "${RUNNING_IMAGE_ID}" != "${IMAGE_ID}" ]]; then
      echo "migration image digest does not match running API container" >&2
      exit 1
    fi
    COMPOSE_ARGUMENTS=(
      exec -T api alembic upgrade head
    )
    ;;
esac

cd "${ROOT_DIR}"
docker compose \
  --env-file .env \
  -f deploy/msk/docker-compose.yml \
  -f "${OVERRIDE_FILE}" \
  "${COMPOSE_ARGUMENTS[@]}"
