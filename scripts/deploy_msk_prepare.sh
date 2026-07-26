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

  5. After release approval, promote the verified candidate and start:
     docker tag "msk-api:\${GIT_REVISION}-candidate" msk-api:latest
     docker compose --env-file .env -f deploy/msk/docker-compose.yml up -d --no-build --force-recreate --no-deps api

  6. Run migrations:
     docker compose --env-file .env -f deploy/msk/docker-compose.yml exec -T api alembic upgrade head

  7. Install nginx samples:
     deploy/msk/nginx/api.memlayer.ru.conf
     deploy/msk/nginx/adm.memlayer.ru.conf

  8. Validate local runtime:
     curl -sS http://127.0.0.1:18120/health
EOF
