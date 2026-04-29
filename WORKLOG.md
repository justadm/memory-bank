# Worklog

## 2026-04-29

### Request

- User asked to study `roadmap.md`, start implementation, and record communications, discussions, and actions for later review.

### Decisions

- Started with a full MVP scaffold instead of a minimal hello-world skeleton because the roadmap is already detailed and the repository was empty.
- Added a persistent in-repo journal in this file so progress remains inspectable alongside code changes.
- Kept SQLite fallback support for local tests while preserving PostgreSQL-oriented runtime and migrations for Docker usage.

### Actions

- Reviewed `roadmap.md` end-to-end.
- Created project structure for FastAPI app, Alembic, and tests.
- Implemented configuration, SQLAlchemy models, repositories, services, routers, Docker config, and README.
- Added initial Alembic migration and first API test suite scaffold.
- Tightened session handling, fixed schema serialization for `metadata`, and completed the stale-archive test scenario.
- Switched PostgreSQL driver from `psycopg2-binary` to `psycopg` v3 after install verification showed a Python 3.14 compatibility/build issue with `pg_config`.
- Verification moved to a dedicated Python 3.13 virtualenv because the host default Python 3.14 cannot currently build `pydantic-core` in this stack.
- Ran the full API test suite in `.venv313`; result: `8 passed`.
- Initialized a local Git repository on branch `main` in preparation for public publication.
- Created public GitHub repository `justadm/memory-bank`, connected `origin`, and pushed the initial `main` branch.

### Notes

- This file will be appended as implementation continues so later turns remain auditable.
- Change tracking is now available both in Git and in this file-based journal.

## 2026-04-29 - Iteration 2

### Goal

- Continue development after the initial public push with the next roadmap-aligned improvements.

### Plan

- Improve search data preparation so stored entries carry a normalized searchable payload.
- Extend test coverage for filters, graph traversal, project CRUD, and memory usage logging behavior.

### Actions

- Added normalized `search_vector` payload preparation on memory create/update.
- Expanded API coverage for project CRUD, memory filters, graph traversal, and access-log/usage tracking scenarios.
- Re-ran the test suite in `.venv313`; result: `12 passed`.
- Verified runtime startup through Docker against PostgreSQL.
- Fixed Alembic container import resolution and corrected the initial migration for PostgreSQL enum/JSONB behavior.
- Confirmed live smoke calls for `POST /projects`, `POST /memory`, and `GET /health` against the Dockerized app.
- Added `.dockerignore` and a PostgreSQL healthcheck in `docker-compose.yml` to make container startup lighter and more reliable.
- Reviewed `/Users/just/apps/memorybank_agent_pack` and reused its most practical next-step idea: synchronous auto-linking for newly created memory entries.
- Implemented optional server-side auto-linking on `POST /memory` using bag-of-words cosine similarity and added coverage for it.
- Started an embedded integration layer inside this repository: `memorybank_sdk` plus an example memory-aware agent following `READ -> ACT -> WRITE -> LINK`.
- Verified the embedded SDK layer with imports and tests; total suite status is now `14 passed`.
- Upgraded the search path toward fuller PostgreSQL FTS: stored `search_vector` sync on create/update, rebuild endpoint, and a follow-up migration to `tsvector`.
- Re-ran the suite after the FTS work; total status is now `15 passed`.
