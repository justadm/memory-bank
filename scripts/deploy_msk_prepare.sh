#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-/opt/memlayer}"

cat <<EOF
MemLayer MSK deploy prep

Local repo root: ${ROOT_DIR}
Target server path: ${TARGET_DIR}

Expected next steps on msk:
  1. Create target directory:
     sudo mkdir -p ${TARGET_DIR}
     sudo chown -R \$(whoami):\$(whoami) ${TARGET_DIR}

  2. Put repo checkout into ${TARGET_DIR}

  3. Create ${TARGET_DIR}/.env from:
     ${ROOT_DIR}/deploy/msk/.env.example

  4. Build and verify the API image:
     cd ${TARGET_DIR}
     export GIT_REVISION="\$(git rev-parse HEAD)"
     scripts/build_release_image.sh msk-api
     # Record approved_image_id from the verified builder output in the release approval.

  5. After release approval, deploy the verified immutable image:
     export APPROVED_IMAGE_ID="sha256:<approved-image-id>"
     scripts/rollout_release_image.sh msk-api "\${GIT_REVISION}" "\${APPROVED_IMAGE_ID}"

  6. Run migrations:
     RUNNING_IMAGE_ID="\$(docker inspect --format '{{.Image}}' memlayer-api)"
     scripts/run_release_compose.sh "\${RUNNING_IMAGE_ID}" \\
       migrate-head

  7. Install nginx samples:
     deploy/msk/nginx/api.memlayer.ru.conf
     deploy/msk/nginx/adm.memlayer.ru.conf

  8. Validate local runtime:
     curl -sS http://127.0.0.1:18120/health
EOF
