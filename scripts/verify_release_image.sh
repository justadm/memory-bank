#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 IMAGE EXPECTED_GIT_REVISION" >&2
  exit 2
fi

IMAGE="$1"
EXPECTED_GIT_REVISION="$2"

if [[ ! "${EXPECTED_GIT_REVISION}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "expected revision must be a 40-character lowercase Git SHA" >&2
  exit 2
fi

ACTUAL_GIT_REVISION="$(
  docker image inspect \
    --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
    "${IMAGE}"
)"

if [[ "${ACTUAL_GIT_REVISION}" != "${EXPECTED_GIT_REVISION}" ]]; then
  echo "release image revision mismatch" >&2
  exit 1
fi

docker run --rm --network none --user 0:0 --entrypoint sh "${IMAGE}" -eu -c '
  test ! -e /app/.env
  test ! -e /app/backups
  test -f /app/app/main.py
'

echo "release image verification passed"
