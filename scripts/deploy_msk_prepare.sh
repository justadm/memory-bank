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

  4. Start stack:
     cd ${TARGET_DIR}
     docker compose --env-file .env -f deploy/msk/docker-compose.yml up -d --build

  5. Run migrations:
     docker compose --env-file .env -f deploy/msk/docker-compose.yml exec -T api alembic upgrade head

  6. Install nginx samples:
     deploy/msk/nginx/api.memlayer.ru.conf
     deploy/msk/nginx/adm.memlayer.ru.conf

  7. Validate local runtime:
     curl -sS http://127.0.0.1:18120/health
EOF
