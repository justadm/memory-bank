# MemLayer

Shared memory layer for agent workflows, operator review queues, and project imports.

MemLayer is a FastAPI + PostgreSQL service that keeps decisions, constraints, risks, artifacts, task logs, and retrieval paths in one operational memory contour. It is designed for agent loops that need more than a transient prompt buffer: search, relevant context, imports, quality gates, lifecycle cleanup, compaction, and operator visibility.

Russian documentation lives in [README_RU.md](/Users/just/apps/memory.bank/README_RU.md).

## What is included

- project CRUD and project-scoped memory storage
- memory CRUD, archive flows, and graph links
- lexical, semantic, and hybrid retrieval
- PostgreSQL full-text search with rebuild support
- `POST /memory/relevant` with usage-aware retrieval
- structured project import and reimport
- quality gate, semantic duplicate detection, and review queues
- decision authority, conflict resolution, lifecycle, and compaction
- metrics, task logs, evaluation endpoints, and runtime self-check
- embedded admin console
- hidden `.memlayer/` project pack for external repositories

## Quick start

1. Copy `.env.example` to `.env`.
2. Start the stack:

```bash
docker compose up --build -d
```

3. Apply migrations:

```bash
docker compose exec api alembic upgrade head
```

4. Open:
- API docs: `http://127.0.0.1:18100/docs`
- Embedded console: `http://127.0.0.1:18100/console/`

## Main endpoints

- `GET /health`
- `GET /projects`
- `POST /projects`
- `GET /memory/search`
- `POST /memory/relevant`
- `POST /memory`
- `POST /imports/project-scan`
- `POST /imports/reimport-project`
- `GET /metrics/overview`
- `GET /admin/runtime/self-check`

## Runtime self-check example

```bash
curl -sS 'http://127.0.0.1:18100/admin/runtime/self-check?search_query=architecture&limit=5' \
  -H 'Authorization: Bearer YOUR_API_KEY'
```

## Public deployment

Production entry points currently used on `msk`:

- [memlayer.ru](https://memlayer.ru) — public landing page
- [memlayer.ru/api](https://memlayer.ru/api) — static API examples
- [api.memlayer.ru](https://api.memlayer.ru/health) — production API
- `adm.memlayer.ru` — embedded admin console, intentionally not linked from the public landing page

Deployment assets are in:

- [deploy/msk/docker-compose.yml](/Users/just/apps/memory.bank/deploy/msk/docker-compose.yml)
- [deploy/msk/nginx](/Users/just/apps/memory.bank/deploy/msk/nginx)
- [README_DEPLOY.md](/Users/just/apps/memory.bank/README_DEPLOY.md)

## Project root pack

External repositories can be prepared for MemLayer with a hidden `.memlayer/` pack. It keeps agent instructions, runtime helpers, local snapshots, and offline queue files out of the project root.

Installer:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/install_memlayer_project_pack.py \
  --projects-root /Users/just/projects
```

What the pack provides:

- `.memlayer/memlayer_context.sh` — snapshot-first pre-task read path
- `.memlayer/memlayer_api.sh` — endpoint ladder + doctor mode
- `.memlayer/memlayer_write.sh` — live write or offline queue fallback
- `.memlayer/memlayer_sync.sh` — replay queued writes
- `.memlayer/memlayer_snapshot_pull.sh` — refresh local snapshots
- `.memlayer/memlayer_watchdog.sh` — health and self-check probe
- `.memlayer/memlayer_recover.sh` — local recovery helper

## Verification

Run the test suite:

```bash
.venv313/bin/pytest
```

For containerized API verification:

```bash
docker compose exec api pytest
```
