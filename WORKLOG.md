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
- Reviewed `/Users/just/apps/memorybank_eval_pack` and pulled its most practical backend extension into the core service: `task_logs` plus a basic analytics summary API.
- Switched Docker host ports to less conflict-prone configurable defaults (`18100` for API, `15432` for Postgres) while keeping internal container ports standard.
- Added an embedded evaluator endpoint inspired by `memorybank_eval_pack` for rule-based memory-usage assessment.
- Added a built-in metrics overview API so the service can expose key memory/graph/task observability data without requiring an external dashboard first.
- Extended the eval layer with batch evaluation and task-log import flow so evaluation payloads and experiment logs can move in larger chunks.
- Upgraded the embedded SDK so `MemoryAwareAgent` can automatically evaluate completed runs and write `task_logs` without extra orchestration code.
- Reviewed `/Users/just/apps/memorybank_production_addons` and used its observability direction to add a lightweight admin summary endpoint instead of dragging in the entire production stack.
- Reviewed `/Users/just/apps/Importer.md` and started aligning the API with a real import-agent workflow: structured project import plus explicit `constraint` and `risk` memory types.
- Continued the `Importer.md` direction into the embedded SDK so project-import agents can call the import flow directly and use a ready-made example importer script.
- Added conservative decision conflict detection to the import flow and introduced a local project-import CLI with `--dry-run`, so repository scanning is reusable and safer before writing to Memory Bank.
- Extended the importer to batch-import child projects from a directory and added an admin endpoint for reviewing import conflicts after those scans.
- Live verification uncovered two runtime integration issues: the SDK helper initially missed the `detect_conflicts` flag, and the Dockerized PostgreSQL runtime needed the `20260429_0004` enum migration before real project imports could succeed.
- After fixing that path, successfully batch-imported the real local projects `/Users/just/projects/APUAI` and `/Users/just/projects/max`; the live `/admin/import-conflicts` endpoint currently reports no detected conflicts for those imports.
- Continued by deepening importer heuristics for Node.js, Go, and monorepo-style repositories and added an admin import summary view so operators can review what has already been imported, not just where conflicts happened.
- Updated `roadmap.md` into a status-oriented checklist (`готово / частично / не начато`) and documented the near-term plan directly in the roadmap.
- Added re-import modes for project scans (`create`, `skip`, `update`) so repeated imports can avoid duplicates or refresh previously imported entries in place.
- Closed another roadmap-docs gap by extending `README.md` with an API quick reference, explicit memory/link type lists, `curl` examples, and the formal Docker test command.
- Added an optional API-key auth layer with `write`, `import`, and `admin` scopes, protected critical routes, updated the SDK/CLI/examples to read `MEMORYBANK_API_KEY`, and covered the security flow with API tests.
- Added a practical semantic layer without external services: `lexical / semantic / hybrid` search modes, local token-expansion scoring, and support for the same mode in `/memory/relevant`.
