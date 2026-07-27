#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 IMAGE_REPOSITORY" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_REPOSITORY="$1"
TARGET_PLATFORM="${TARGET_PLATFORM:-linux/amd64}"
REVISION="$(git -C "${ROOT_DIR}" rev-parse --verify HEAD)"
IMAGE="${IMAGE_REPOSITORY}:${REVISION}-candidate"

if [[ ! "${REVISION}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "HEAD is not a full 40-character lowercase Git SHA" >&2
  exit 1
fi

if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain --untracked-files=all)" ]]; then
  echo "release build requires a clean Git worktree" >&2
  exit 1
fi

BUILD_CONTEXT="$(mktemp -d "${TMPDIR:-/tmp}/memlayer-release.XXXXXX")"
trap 'rm -rf "${BUILD_CONTEXT}"' EXIT

git -C "${ROOT_DIR}" archive --format=tar "${REVISION}" \
  | tar -xf - -C "${BUILD_CONTEXT}"

docker build \
  --no-cache \
  --platform "${TARGET_PLATFORM}" \
  --build-arg "GIT_REVISION=${REVISION}" \
  --tag "${IMAGE}" \
  "${BUILD_CONTEXT}"

APPROVED_IMAGE_ID="$(
  docker image inspect --format '{{.Id}}' "${IMAGE}"
)"
if [[ ! "${APPROVED_IMAGE_ID}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "verified image has no immutable sha256 identity" >&2
  exit 1
fi

"${ROOT_DIR}/scripts/verify_release_image.sh" \
  "${APPROVED_IMAGE_ID}" \
  "${REVISION}"

CANDIDATE_TAG_IMAGE_ID_AFTER="$(
  docker image inspect --format '{{.Id}}' "${IMAGE}"
)"
if [[ "${CANDIDATE_TAG_IMAGE_ID_AFTER}" != "${APPROVED_IMAGE_ID}" ]]; then
  echo "candidate tag changed during verification" >&2
  exit 1
fi

echo "revision=${REVISION}"
echo "candidate=${IMAGE}"
echo "approved_image_id=${APPROVED_IMAGE_ID}"
