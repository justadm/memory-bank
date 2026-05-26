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
- Reviewed the neighboring `/Users/just/apps/memorybank-admin` project and confirmed that the future migration target should be its static `frontend/` shell rather than the older Streamlit prototype.
- Continued the auth track into tenant-aware RBAC hardening: clarified that read endpoints require auth when enabled, documented tenant-scoped API key format, fixed project updates so `tenant_id` survives metadata patches, and closed an import path that had not forwarded the current principal into the import event creation step.
- Added regression coverage for tenant-preserving project updates and tenant-scoped import authorization.
- Extended tenant-aware RBAC into observability: tenant-scoped keys now automatically stamp `task_logs` with `tenant_id` and only see their own `task_logs`, metrics, admin summaries, import conflict lists, and import summaries.
- Added `GET /auth/me` so the future in-repo admin/frontend shell can discover whether auth is enabled, whether the current request is authenticated, and which scopes/tenants are attached to the current API key.
- Started the actual frontend migration from `/Users/just/apps/memorybank-admin/frontend` into this repository: mounted the transferred static shell at `/console/`, switched the console brand to `MemLayer`, pointed it at same-origin API by default, and added local API-key support plus `/auth/me`-driven auth awareness so the embedded UI can function against secured environments.
- Continued adapting the embedded MemLayer console to real backend capabilities: exposed editable `tenant_id` in project forms/tables, surfaced auth/scopes/tenant chips directly in the shell, and added `lexical / semantic / hybrid` search mode controls for the memory workspace.
- Extended the embedded console with import visibility as well: dashboard and review screens now surface `/admin/imports/summary` so recent imports and conflict-heavy projects are visible without leaving the main shell.
- Reworked console navigation into real SPA-style routes under `/console/*`: dashboard/projects/memory/review/settings now push browser history and survive reloads via backend index fallback instead of staying on a single static URL.
- Added dual-mode console routing for the upcoming `memlayer.loc` switch: embedded mode still uses `/console/*`, while root-hosted mode can expose clean URLs like `/projects` and automatically redirects frontend API calls to same-origin `/api`.
- Switched the local `memlayer.loc` nginx vhost over to the new root-hosted MemLayer console shape: `/api/*` proxies to backend API, while `/`, `/projects`, `/memory`, `/review`, and `/settings` proxy to the console SPA. Rebuilt the Dockerized API runtime and verified the new behavior through `curl --resolve ... https://memlayer.loc/...` checks. Automatic `/etc/hosts` insertion was blocked by local system permissions, so hostname resolution may still need one manual host entry on the machine.
- Added a first graph pane to the memory workspace in the embedded/root-hosted MemLayer console: selected entries now load `/memory/{id}/graph` with configurable depth and show connected nodes plus edges directly in the operator UI.
- Added a reusable MemLayer project-root pack for external repositories: template-driven `AGENTS.md` integration, `MEMLAYER.md`, `.env.memlayer.example`, and `memlayer.config.json`, plus an installer script that can safely fan this pack out across `/Users/just/projects` without overwriting user-authored agent guidance.
- Hardened the project-root pack for flaky local agent sessions: every external project can now receive a root-level `memlayer_api.sh` helper that reads `memlayer.config.json`, tries localhost first, and automatically retries through `https://memlayer.loc/api` on network failure. The installer also seeds `.env.memlayer` without overwriting an existing local secret file, and the AGENTS/MEMLAYER guidance now explicitly points agents to the helper instead of raw `curl`.
- Upgraded the project importer for doc-centric handoff repositories: `docs/*.md` and `mvp-handoff/*.md` are now imported as first-class artifacts, backlog `EPIC-*` markdown headings become task entries, and product signals such as pre-build positioning, staged LLM pipeline, schema-first runtime, anonymous-session V1, `.loc` local-domain constraints, and structured-output risks can be derived directly from the handoff docs. Also taught the import flow to reuse an existing project by `source_path` or project name instead of always creating another project row.
- Added another operational hardening pass for flaky local agent sessions: `memlayer_api.sh` now retries localhost with a short backoff before falling back to `https://memlayer.loc/api`, the root-pack exposes a direct runtime self-check example, and a new `memlayer_watchdog.sh` script gives external projects a one-command `health + /admin/runtime/self-check` probe after sleep, reboot, or transient localhost failures.
- Added project-list hygiene visibility to the admin layer: duplicate projects are now grouped by `name + source_path` through `GET /admin/projects/duplicates`, and the embedded console dashboard surfaces duplicate groups so accidental repeated imports are visible before manual cleanup is needed.
- Added an explicit recovery path for external project helpers: along with `memlayer_api.sh` retries and `memlayer_watchdog.sh`, the root-pack now installs `memlayer_recover.sh`, which can restart the dockerized MemLayer API from the project root. Watchdog can be switched into auto-recover mode through `.env.memlayer` on machines where restarting the shared runtime is acceptable.
- Added an offline-readable fallback for sandboxed agents: every external project can now receive `memlayer_snapshot_pull.sh`, `memlayer.snapshot.md/json`, and `memlayer.offline.log.md`. The snapshot pull helper stores a locally readable context export from `POST /context/build`, while agents can keep working against the snapshot and append unsynced notes to the offline log when both live endpoints are temporarily unavailable. The import CLI now also persists `project_id` back into `memlayer.config.json` so later snapshot pulls can stay project-scoped.
- Switched the root-pack pre-task read path to snapshot-first instead of live-first. `memlayer_context.sh` now reads the local snapshot immediately and only touches live MemLayer on explicit `--refresh`, which fixes the core sandbox pain point where agents were blocked from reading context before a task even started.
- Added runtime-context discovery to the external-project helper itself. `memlayer_api.sh` now has an endpoint ladder plus `doctor` mode, so agents can distinguish “MemLayer is down” from “this sandbox/container cannot reach localhost and should use host.docker.internal or api:8000 instead.”
- Taught the root-pack installer to merge new connection defaults into existing `.env.memlayer` files instead of leaving older minimal env files stuck without `MEMLAYER_API_URL` / `MEMLAYER_EXTRA_URLS`. This keeps local overrides and secrets intact while still upgrading older projects like `BuildGuard` to the new connectivity profile.
- Fixed a subtle but important root-pack regression: installer was rewriting `memlayer.config.json` without preserving `project_id`, which silently downgraded later snapshot pulls from project-scoped retrieval back to global retrieval. `BuildGuard` was the first clear symptom because its cached context started pulling `router/openvpn` memories into product work.
- Reduced project-root clutter by changing the external-project layout to `AGENTS.md` in the root plus a dedicated `.memlayer/` directory for all helpers, env files, snapshots, queues, and config. The installer now also adds `.memlayer/` to `.gitignore` and migrates older root-level MemLayer files into that hidden directory.
- Updated the import CLI for the same hidden-layout migration: `persist_project_id(...)` now resolves `.memlayer/memlayer.config.json` first, so imported projects like `lk.loc` keep their scoped MemLayer identity without relying on the old root-level config path.
- Added a real offline write path for sandboxed agents. `memlayer_write.sh` now queues failed write payloads into `memlayer.offline.queue.jsonl` and mirrors a human-readable note into `memlayer.offline.log.md`, while `memlayer_sync.sh` can replay that queue later once live MemLayer becomes reachable again.
- Tightened the operator ergonomics of the offline write path: queued writes now use a separate short retry budget (`MEMLAYER_WRITE_RETRY_ATTEMPTS`) through an explicit internal override, so agents fall into the offline queue quickly instead of inheriting the full long-form endpoint discovery loop from `.env.memlayer`.
- Added an operational hardening layer around local MemLayer usage: a new `scripts/runtime_smoke_check.py` verifies `health -> import -> search -> relevant`, `GET /admin/runtime/self-check` provides a lightweight read-only runtime check after reboots or deploys, and then the agent-facing defaults were corrected back to localhost-first because sandboxed agents were repeatedly escalating just to read MemLayer through `https://memlayer.loc/api`.
- Extended retrieval beyond a single repository by adding `scope=project|related|global` to memory search/relevant flows. `related` scope now expands through `project.metadata.related_projects`, and the API responses include source `project_id` / `project_name` so agents can reuse neighboring-project solutions without losing provenance.
- Added a smart default retrieval ladder to `MemoryAwareAgent`: the SDK now tries `project -> related -> global` automatically and only expands when the current scope returns too little context. The used scopes are written back into memory/task-log metadata as `retrieval_scopes_used`, making cross-project retrieval behavior observable instead of implicit.
- Expanded the console graph/import UX in one pass: links can now be created and deleted directly from the graph pane, import summaries/conflicts expose project-opening actions, the graph gained a simple visual canvas, and the topbar controls were tightened by removing the global refresh button and shrinking locale/theme toggles.
- Added a true inline reimport flow: backend now exposes `POST /imports/reimport-project`, which rebuilds a project scan payload from `metadata.source_path` and replays it against an existing project; the console surfaces this as `Reimport project` actions in project/import views.
- Finished the broader import-operator pass in the console: added bulk reimport for visible import summaries, surfaced the last import/reimport result as a compact UI summary, and exposed editable metadata JSON fields in memory create/update forms so operators can curate entries without dropping to raw API calls.
- Started the first real Memory Quality Layer so MemLayer can reject obviously weak manual entries before they pollute the graph. Added a reusable quality assessment service with basic heuristics for placeholder content, too-short text, missing evidence, and possible same-project duplicates, and now persist the assessment under `metadata.quality`.
- Wired the quality layer into `POST /memory` and `PATCH /memory/{id}` as a hard gate: manual create/update can now return `422` with structured quality details when an entry looks too weak to keep.
- Kept the import path intentionally softer: `POST /imports/project-scan` and reimport/update flows now bypass hard rejection, but weak imported entries are marked with `metadata.quality_review_required=true` and the response surfaces `quality_review_required_count` so operators can review noisy imports instead of silently accepting them.
- Initial verification found two regressions that were then fixed: the first heuristic was too aggressive for short draft-like notes, and repeated imports were accidentally failing on duplicate import events because the quality gate was applied too strictly there as well. After narrowing those cases, the full local suite passes again with `58 passed`.
- Reviewed `/Users/just/apps/memlayer_next_stage_pack` and chose not to copy it wholesale. Instead, extracted the first two highest-value pieces that fit the current architecture without forcing a big schema migration: metadata-based decision authority and a typed context builder endpoint.
- Added `DecisionAuthorityService` and integrated it into the normal memory write path. New `decision` entries now default to `metadata.decision_status=active`, and conflicting technology-direction decisions inside the same project are automatically marked with `metadata.requires_review=true` plus a structured `metadata.decision_conflicts` payload.
- Added `POST /context/build`, which reuses the existing search pipeline and turns flat retrieval into typed buckets (`active_decisions`, `constraints`, `risks`, `artifacts`, `tasks`, `notes`, `other`) with lightweight score boosting by memory type, importance, and decision status.
- Added SDK support for the new typed context flow via `MemoryBankClient.build_context(...)` and covered the backend behavior with API tests for default decision status, conflict marking, and context bucket shaping.
- Verified the integrated next-stage subset with the full local suite; result: `60 passed`.
- Continued the next-stage extraction with a metadata-based conflict-resolution flow instead of introducing a new `memory_conflicts` table immediately. This keeps the workflow compatible with the current schema while still enabling real operator decisions on competing architecture directions.
- Added `GET /admin/decision-conflicts`, which flattens pending `metadata.decision_conflicts` into an admin review queue, and `POST /admin/decision-conflicts/resolve`, which supports `supersede`, `reject_new`, `keep_both`, and `needs_changes`.
- Resolution actions now update `decision_status`, `requires_review`, `review_status`, `review_history`, and for supersession also wire `supersedes_entry_id` / `deprecated_by_entry_id`. Rejecting the new decision archives it immediately so retrieval stops surfacing it as a live choice.
- Covered the new flow with API tests for conflict listing, superseding an old decision, and rejecting a new conflicting decision before running the full suite again.
- Continued the next-stage extraction with a lifecycle maintenance pass, but intentionally kept it operator-triggered instead of introducing a background daemon immediately. This fits the current architecture better and is safer for early-stage runtime operations.
- Added `LifecycleService` plus `POST /maintenance/lifecycle/run` with `dry_run` support. The pass now decays quality for stale low-value `note` / `event` entries, marks overdue review items with `metadata.review_overdue=true`, archives weak stale entries below a configurable threshold, and cleans up weak old links.
- Covered the lifecycle pass with API tests for both dry-run preview behavior and real application behavior, including review-overdue marking, stale entry archiving, and weak-link deletion.
- Verified the integrated lifecycle subset with the full local suite; result: `64 passed`.
- Continued the next-stage extraction with an operator-driven compaction workflow instead of introducing new compaction tables or a scheduler first. This keeps the feature useful immediately while staying compatible with the current schema.
- Added `CompactionService` plus `POST /maintenance/compaction/preview` and `POST /maintenance/compaction/apply`. Preview detects stale low-value clusters by simple topic-token overlap, while apply creates a summary entry, links originals to it with `derived_from` + `metadata.compaction=true`, marks `metadata.compacted_into_entry_id`, and optionally archives the originals.
- Covered the compaction flow with an API test that exercises the full preview/apply cycle and verifies the resulting summary metadata, outgoing links, and archived originals.
- Verified the integrated compaction subset with the full local suite; result: `65 passed`.
- Continued by making the new quality/conflict/lifecycle/compaction mechanisms truly operator-visible. Added `GET /admin/review-queues/summary`, which aggregates counts and preview items for import conflicts, decision conflicts, overdue review, quality-review-required entries, and compaction candidates into one payload.
- Extended the embedded MemLayer console to consume the new summary on both dashboard and review screens. The UI now shows separate decision-conflict queues, overdue review items, quality-review-required entries, and compaction candidates instead of collapsing everything into the older import-conflicts-only view.
- Added direct UI actions for the new workflows: console operators can now resolve a decision conflict via `supersede` or `reject_new`, and can trigger `apply compaction` for a suggested cluster without leaving the review screen.
- Covered the new admin summary endpoint plus frontend asset wiring in API tests and re-ran the full local suite; result: `66 passed`.
- Continued into semantic duplicate detection so the quality layer can catch near-duplicate knowledge, not just exact duplicates or low-value placeholders. Added a local hashed-embedding service that compares entries within the same project without requiring pgvector or any external vector store.
- Integrated the semantic duplicate signal into `MemoryQualityService`: close matches now populate `metadata.quality.semantic_duplicate_risk`, `semantic_similarity_max`, and `semantic_duplicate_candidates`, which means duplicate-like entries naturally flow into the existing review queues. Extremely close duplicates can now be rejected by the normal quality gate.
- Added API tests for both the soft semantic-duplicate review path and the hard rejection path for almost identical entries before running the full suite again.
- Continued the operator loop by adding explicit quality-review actions instead of leaving review queues as read-only signals. Added `POST /admin/quality-review/resolve`, which supports `approve`, `false_positive`, `archive`, and `needs_changes`.
- Quality-review resolution now updates `review_status`, `quality_review_required`, `review_history`, and in the false-positive path also marks `metadata.quality.false_positive=true` so the system keeps an auditable record of operator overrides. Archiving through this route now works as a first-class review outcome as well.
- Extended the embedded MemLayer console review screen so operators can approve a reviewed item, mark a semantic duplicate warning as false positive, or archive a low-value item directly from the quality-review queue.
- Covered the new quality-review resolution flow with API tests and re-ran the full local suite; result: `70 passed`.
- Continued toward product-level observability by expanding `GET /metrics/overview` with a new `review` block and a lightweight `trends` block. This makes false-positive rate, semantic-duplicate pressure, compaction yield, and review resolution behavior visible without stitching together multiple admin endpoints manually.
- Added review metrics such as pending import/decision conflicts, overdue review, quality-review-required count, semantic duplicate flags, false positives, review resolution rate, and compaction counts. Added trend metrics for entries created in the last 7 days, reviews resolved in the last 7 days, duplicate flags in the last 7 days, and compactions applied in the last 7 days.
- Wired the new review/process metrics into the embedded MemLayer dashboard so operators can see these product-health signals directly in the console alongside the older memory/graph/task metrics.
- Extended importer heuristics beyond public `docs/` handoff repositories: hidden `.docs/*.md`, `COMMITS.md`, and `openspec/config.yaml` are now imported as first-class signals as well. This lets MemLayer extract spec-driven workflow notes, commit-policy guidance, Bitrix24-list MVP decisions, admin-only delivery constraints, SharePoint historical-source constraints, and personal-data attachment risks from process-heavy internal repositories like `lk.loc`.
- Verified the new importer path with focused tests, then used it to prepare a richer reimport path for `/Users/just/projects/ofs/lk.loc` so its project-scoped snapshot can graduate from a single source marker to real decisions, constraints, risks, and process notes.
- Hardened the external-project runtime helpers for machine restarts and sleep/wake recovery. `memlayer_recover.sh` now defaults to `docker compose up -d` and waits for `/health` with a bounded timeout, so it can revive a fully stopped MemLayer stack instead of only restarting an already-running API container.
- Added a new root-pack helper `memlayer_launchd_install.sh` that installs a macOS `launchd` agent under `~/Library/LaunchAgents`. This gives projects a one-command way to auto-start the shared MemLayer Docker stack at login and retry periodically while Docker Desktop is still coming up.
- Built a first consolidated inventory document for the `msk` server in `docs/msk-server-inventory-2026-05-26.md`. It captures the currently visible project roots, active Docker contours, nginx-routed domains, the special `jstun` remote root under `/opt/jstun`, and the main runbook-like source files that currently act as the operational truth for that host.
- Continued the `msk` host inventory with the second-pass routing matrix the user requested. The same document now contains a domain-level table mapping hostnames to nginx config files, upstream ports, confirmed docker/runtime contours, known project roots, and an explicit `active / legacy / unclear` status so the next operational pass can focus on unresolved roots and legacy ingress.
- Published a convenience copy of the `msk` inventory directly onto the server as `/home/opsadmin/SERVER_INVENTORY.md` so other bots can read a stable local path without first locating this repository.
- Prepared the first public deployment design for running MemLayer on `msk` under `api.memlayer.ru` and `adm.memlayer.ru` as an isolated `/opt/memlayer` Docker Compose stack with its own PostgreSQL, host-nginx ingress, auth enabled from day one, and host port `127.0.0.1:18120` confirmed free during the design pass.
- Started implementation of the `msk` deployment path by adding repository-native production artifacts: a dedicated `deploy/msk/docker-compose.yml` instead of an override (to avoid inherited development DB port publishing), a production `.env` template, nginx vhost samples for `api.memlayer.ru` and `adm.memlayer.ru`, and a small deploy-prep helper script plus an expanded `README_DEPLOY.md`.
- While bringing the first real stack up on `msk`, found a concrete production compose bug: the DB service was still taking fallback credentials because compose-time variable substitution did not reliably consume the root `.env` from this nested file layout. Switched the production compose to a simpler `env_file`-driven DB config and updated deploy commands to use `docker compose --env-file .env ...` explicitly.
- Continued the real `msk` rollout after that fix: created `/opt/memlayer`, cloned the current repo there, generated a production `.env`, and brought up the dedicated MemLayer stack successfully. The corrected stack now responds locally on `http://127.0.0.1:18120/health`, `openapi.json` is reachable, and Alembic migrations reached head against the dedicated PostgreSQL volume.
- Installed temporary `80`-only nginx vhosts for `api.memlayer.ru` and `adm.memlayer.ru` on `msk`, verified nginx syntax/reload, and confirmed local host-header routing to the new stack works. The current external blocker is DNS: `certbot` failed with `NXDOMAIN` for both subdomains, so the final HTTPS vhosts and public smoke checks are waiting on real public DNS records for `api.memlayer.ru` and `adm.memlayer.ru`.
