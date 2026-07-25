# MemLayer Codex Connect and Temporal Memory Design

Status: approved product design

Date: 2026-07-25

## Problem

MemLayer already provides project-scoped storage, retrieval, root-pack helpers,
offline queues, quality review, imports, task logs, and production operations.
Its main adoption gap is that project onboarding is exposed through several
scripts and copied helper files instead of one reversible agent connection
contract.

Memory entries also lack first-class provenance, confidence, and validity
intervals. An in-place content update destroys the previous state, so MemLayer
cannot answer what was believed at a past point in time.

## Goals

1. Connect a project to Codex through one dry-run-first command.
2. Install only project-local managed files.
3. Make updates and disconnects ownership-aware and non-destructive.
4. Store provenance and confidence as validated database fields.
5. Preserve semantic history through immutable revisions.
6. Support project-scoped `as-of`, `changed-since`, and history reads.
7. Preserve current project, tenant, privacy, quality-review, and offline
   behavior.

## Non-Goals

- global Codex configuration changes;
- Claude Code, Cursor, or other agent integrations;
- automatic project-content upload during `connect`;
- OKF export/import;
- replacement of PostgreSQL, lexical search, semantic search, or the current
  MemLayer API;
- reconstruction of historical states that predate the migration;
- production deployment as part of the implementation branch.

## Product Boundary

```text
Git, runtime, authoritative APIs -> source of truth
MemLayer                         -> retrieved context and evidence
Codex                            -> verifies authority and freshness
```

The connector must not install instructions that declare memory authoritative.
The Codex skill must explicitly preserve this boundary.

## User-Facing Commands

The repository exposes a top-level `memlayer` executable backed by a focused
Python CLI module.

```text
./memlayer connect codex --project-root PATH
./memlayer connect codex --project-root PATH --apply
./memlayer connect codex --project-root PATH --apply --register-project
./memlayer disconnect codex --project-root PATH
./memlayer disconnect codex --project-root PATH --apply
./memlayer doctor --project-root PATH
```

Rules:

- `connect` and `disconnect` are dry-run by default.
- `--apply` is required for filesystem mutation.
- global installation is unsupported and fails explicitly.
- `connect --apply` installs local files but performs no network write.
- `--register-project` is an explicit live action that creates or resolves
  project identity; it does not import repository content.
- repository import remains the separate onboarding/import flow.
- text output is human-readable; `--json` provides a stable machine contract.
- non-zero exit status indicates conflict, invalid state, or failed readiness.

## Connector Architecture

### CLI Layer

The CLI parses commands and renders text or JSON. It contains no file mutation
logic.

### Connector Service

The connector service:

- resolves and validates the project root;
- calls the existing root-pack installer;
- installs the Codex skill;
- upserts the managed `AGENTS.md` section;
- writes the connection manifest;
- computes a dry-run action list;
- delegates optional project registration to a narrow client boundary.

### Manifest

Path:

```text
.memlayer/connection-manifest.json
```

Required fields:

```json
{
  "schema_version": 1,
  "agent": "codex",
  "project_root": "/absolute/project/path",
  "project_id": null,
  "root_pack_version": 1,
  "installed_at": "2026-07-25T00:00:00Z",
  "managed_files": [
    {
      "path": "AGENTS.md",
      "ownership": "managed_section",
      "content_sha256": "sha256:..."
    },
    {
      "path": ".agents/skills/memlayer/SKILL.md",
      "ownership": "whole_file",
      "content_sha256": "sha256:..."
    }
  ]
}
```

The manifest contains no API keys, environment values, raw memory, repository
content, or tenant secrets.

### Ownership and Disconnect

Managed-section files are edited only between stable sentinels. Whole-file
artifacts are removed only when their current hash matches the recorded
managed hash.

If a user modified a managed whole file, `disconnect` reports a conflict and
leaves it untouched. Existing non-MemLayer content in `AGENTS.md` is always
preserved.

### Codex Skill

Path:

```text
.agents/skills/memlayer/SKILL.md
```

The skill instructs Codex to:

- read snapshot-first project context before meaningful work;
- use `project_id` and `source_agent=codex`;
- distinguish memory from source of truth;
- avoid secrets, customer data, raw logs, and unsupported claims;
- use offline queue fallback;
- write decisions, constraints, risks, artifacts, and task outcomes;
- verify live outcomes through authoritative sources;
- run doctor when auth, routing, or project identity is unclear.

It must not require a write for every conversational turn.

## Doctor Contract

Doctor performs read-only checks:

- manifest validity;
- managed-section and skill integrity;
- root-pack version;
- `.memlayer` config validity;
- project name, root, and `project_id` consistency;
- API endpoint health;
- auth status without exposing keys;
- offline queue count and JSON validity;
- snapshot availability and age;
- source-agent configuration;
- readiness state.

Readiness is reported separately:

```text
local_connected
live_identity_ready
live_read_ready
live_write_ready
snapshot_ready
queue_pending
```

Doctor must not claim live readiness from a health check alone.

## Provenance and Confidence Model

Add the enum `MemoryProvenance`:

```text
unspecified
explicit_statement
observed
inferred
corrected
validated
imported
```

Add fields to `memory_entries`:

```text
provenance   enum, non-null, default unspecified
confidence   float, nullable, range 0.0 through 1.0
valid_from   timezone-aware timestamp, non-null
valid_to     timezone-aware timestamp, nullable
supersedes_id UUID, nullable self-reference
```

Constraints:

- `valid_to` must be later than `valid_from`;
- `supersedes_id` cannot equal the entry id;
- one entry can have at most one direct successor;
- `confidence` is evidence confidence, not retrieval relevance;
- `validated` requires privacy-safe validation evidence in
  `metadata.validation_evidence`;
- omitted confidence remains `null`; agents must not invent precision.

The validation evidence contract is:

```json
{
  "kind": "read_back",
  "summary": "Sanitized read-back confirmed the expected state.",
  "captured_at": "2026-07-25T10:00:00Z",
  "redacted": true,
  "contains_sensitive_data": false
}
```

`kind`, `summary`, and `captured_at` are required. `summary` is bounded to 500
characters. Raw command output, credentials, customer payloads, and secret
identifiers are forbidden. `contains_sensitive_data` must be `false`;
`redacted=true` records that the summary was intentionally minimized.

Existing rows are backfilled as:

```text
provenance = unspecified
confidence = null
valid_from = created_at
valid_to = null
supersedes_id = null
```

This records only the state known at migration time. Earlier historical states
are not inferred.

## Revision Semantics

Semantic fields:

- type;
- title;
- content;
- source agent;
- project;
- importance;
- provenance;
- confidence;
- user-controlled metadata.

A semantic revision runs in one transaction:

1. lock and authorize the current active entry;
2. reject revision of an entry that already has a successor;
3. set `old.valid_to` to the injected clock value;
4. create a new entry with `supersedes_id=old.id`;
5. preserve project and tenant scope;
6. copy graph relations to the new revision with inherited-link metadata;
7. create the new search representation;
8. return the new entry and revision metadata.

Operational fields such as usage counters and access timestamps remain mutable
in place. Existing service-owned metadata may also be updated in place only
through a central allowlist used by quality review, conflict review, lifecycle,
and import-run services. The initial allowlist covers:

- `quality`;
- `quality_review_required`;
- `review_overdue`;
- `review_status`;
- `review_history`;
- `requires_review`;
- `import_runs_count`;
- `last_imported_at`;
- `import_history`;
- `import_conflicts`;
- `decision_conflicts`;
- decision-review linkage and status fields maintained by the conflict
  resolution service.

Generic memory `PATCH` cannot claim service ownership of those keys. Any
metadata change outside the operational allowlist creates a semantic revision.

Archiving closes the active validity interval. Restoring historical content
creates a new revision instead of reopening the old row.

## API Contract

### Create

`POST /memory` accepts optional:

```json
{
  "provenance": "observed",
  "confidence": 0.9,
  "valid_from": "2026-07-25T10:00:00Z"
}
```

`valid_from` defaults to the server clock.

### Revise

```http
POST /memory/{id}/revise
```

The request contains changed semantic fields and an optional reason. The
response returns the new entry, the superseded id, and revision timestamp.

### History

```http
GET /memory/{id}/history
```

Returns the ordered linear revision chain visible to the authenticated
principal.

### As-Of Retrieval

Add optional `as_of` to:

- `GET /memory/search`;
- `POST /memory/relevant`.

An entry is active at time `t` when:

```text
valid_from <= t AND (valid_to IS NULL OR valid_to > t)
```

### Changed-Since

```http
GET /memory/changes?project_id=...&changed_since=...
```

Returns created, superseded, and validity-ended revisions ordered by event
time. Tenant and project authorization matches normal memory reads.

### PATCH Compatibility

Rollout is staged:

1. add revision endpoints while existing `PATCH` remains functional;
2. return deprecation diagnostics when `PATCH` changes semantic fields;
3. migrate console, SDK, and root-pack callers;
4. reject semantic `PATCH` updates with a conflict response that points to
   `/revise`;
5. retain only operational updates on the old path until a versioned API
   cleanup is approved.

## Error Handling

- invalid project root: fail before mutation;
- unsupported agent: fail with supported list containing only `codex`;
- modified managed file: conflict, preserve file;
- missing project id: local connection may succeed, live readiness remains
  false;
- missing API key for registration: fail before network write;
- invalid confidence or temporal interval: validation error;
- stale revision target: conflict with current successor id;
- cross-project or cross-tenant revision: forbidden;
- partial filesystem mutation: write through temporary files and atomic
  replacement, then report any unresolved rollback item;
- failed registration never removes a successful local installation.

## Testing Strategy

### Connector Unit Tests

- dry-run produces actions without writes;
- apply preserves existing `AGENTS.md`;
- repeated connect is idempotent;
- manifest contains no secrets;
- disconnect removes unchanged managed artifacts;
- disconnect preserves user-modified skill files;
- unsupported/global agent modes fail closed;
- registration is never called without the explicit flag.

### Doctor Tests

- each readiness dimension is independent;
- HTTP health without auth does not imply write readiness;
- stale snapshot and invalid queue are reported;
- no API key value appears in text or JSON output.

### Model and Migration Tests

- PostgreSQL and SQLite-compatible model behavior;
- existing-row backfill;
- enum and confidence constraints;
- self-reference and single-successor constraints;
- downgrade safety on a disposable database.

### Revision Tests

- deterministic injected clock;
- atomic old-close/new-create behavior;
- concurrent second revision loses with conflict;
- graph relations are inherited once;
- project and tenant boundaries are preserved;
- archive and restore produce correct intervals.

### Temporal Retrieval Tests

- exact interval boundaries;
- `as_of` returns the correct historical revision;
- `changed_since` includes creation and closure events;
- archived and superseded entries do not appear as currently active;
- lexical, semantic, and hybrid modes preserve temporal filtering.

### Integration Tests

- connect a temporary Codex project;
- register it against a fake API;
- create, revise, recall as-of, inspect history, and disconnect;
- verify the project worktree contains only expected tracked changes;
- verify no repository content was uploaded by `connect`.

## Rollout

### Stage 1: Documentation and Contracts

Commit this design. After explicit review of the written design, prepare and
commit the implementation plan. No runtime changes.

### Stage 2: Codex Connector

Ship dry-run, apply, manifest, skill, disconnect, and doctor. Dogfood on one
temporary project and one existing low-risk project.

### Stage 3: Provenance Schema

Apply the migration locally, expose fields through API and SDK, and collect
provenance distribution without changing update semantics.

### Stage 4: Revisions and Temporal Reads

Add revision service, history, as-of, and changed-since. Keep semantic PATCH in
diagnostic mode.

### Stage 5: Caller Migration

Move console, SDK, import/reimport, compaction, and project helpers to explicit
revision or operational update paths.

### Stage 6: Enforcement and Production Preparation

Block semantic PATCH, run migration rollback drills, prepare a production
package, and require explicit deploy approval.

### Stage 7: Dogfood and Metrics

Roll out to two or three projects. Measure:

- connector success and conflict rate;
- doctor readiness failures;
- missing provenance rate;
- inferred versus validated distribution;
- revision count and stale-write conflicts;
- as-of and changed-since usage;
- memory retrieval usefulness and review load.

## Deferred Backlog

- Claude Code connector;
- Cursor connector;
- additional agent registry;
- global connector mode;
- OKF export/import;
- migration adapters for Memanto, Mem0, Letta, and Supermemory;
- independent retrieval benchmark against Moorcheh;
- signed and pinned distribution packages.

## Acceptance Criteria

The release is accepted when:

1. a Codex project can be connected and disconnected without touching global
   settings or unrelated files;
2. dry-run predicts every managed filesystem action;
3. doctor distinguishes local, identity, read, write, snapshot, and queue
   readiness;
4. new memories expose validated provenance, confidence, and validity fields;
5. semantic revisions preserve the old state and reject branching races;
6. as-of retrieval returns the correct revision;
7. existing clients remain usable during the documented compatibility window;
8. tests cover privacy, tenant isolation, idempotency, migration, rollback, and
   temporal boundaries;
9. no production deploy or project-content import occurs without separate
   explicit approval.
