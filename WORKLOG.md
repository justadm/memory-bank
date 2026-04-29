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

### Notes

- This file will be appended as implementation continues so later turns remain auditable.
- The working directory currently is not an initialized Git repository, so change tracking is file-based rather than Git-based for now.
