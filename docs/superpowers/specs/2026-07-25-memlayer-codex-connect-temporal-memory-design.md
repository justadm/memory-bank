# MemLayer Codex Connect and Temporal Memory Design

Status: review amendment applied; pending final approval

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

## Review Amendment Coverage

The 2026-07-25 implementation-readiness review is incorporated into this
document through:

1. a centralized current-memory predicate and index contract;
2. a complete root-pack ownership matrix and secret-neutral connector mode;
3. an idempotent tenant-safe project registration endpoint;
4. an append-only change-event model with stable cursor pagination;
5. immutable revision identity, graph, actor, provenance, and restore rules;
6. separate doctor authorization and verified-read/write states.

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
./memlayer connect codex --project-root PATH --apply --register-project --tenant-id TENANT
./memlayer connect codex --project-root PATH --apply --register-project --project-id UUID
./memlayer disconnect codex --project-root PATH
./memlayer disconnect codex --project-root PATH --apply
./memlayer doctor --project-root PATH
```

Rules:

- `connect` and `disconnect` are dry-run by default.
- `--apply` is required for filesystem mutation.
- global installation is unsupported and fails explicitly.
- `connect --apply` without `--register-project` installs local files but
  performs no network write.
- `--register-project` is an explicit live action that creates or resolves
  project identity; it does not import repository content.
- `--register-project` is invalid without `--apply`.
- `--tenant-id` selects an allowed tenant when credentials do not resolve one
  unambiguously.
- `--project-id` explicitly binds an existing authorized project after a name
  conflict; config `project_id` is used when the flag is omitted.
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
- calls the secret-neutral connector mode of the root-pack installer;
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
  "connector_identity": "d8399b69-82ff-46ec-8e03-1930f1c84735",
  "project_id": null,
  "root_pack_version": 1,
  "installed_at": "2026-07-25T00:00:00Z",
  "managed_files": [
    {
      "path": "AGENTS.md",
      "ownership": "managed_section",
      "created_by_connector": false,
      "content_sha256": "sha256:..."
    },
    {
      "path": ".agents/skills/memlayer/SKILL.md",
      "ownership": "whole_file",
      "created_by_connector": true,
      "content_sha256": "sha256:..."
    },
    {
      "path": ".memlayer/.env.memlayer",
      "ownership": "user_owned",
      "created_by_connector": false,
      "content_sha256": null
    }
  ]
}
```

The manifest contains no API keys, environment values, raw memory, repository
content, or tenant secrets.

Each managed-file record stores whether the connector created the file or
adopted a matching pre-existing artifact. Disconnect removes only
connector-created material or an explicitly managed section/line that the
connector inserted. A pre-existing matching line is recorded as unowned and is
never removed.

### Root-Pack Ownership Matrix

The connector cannot call the current root-pack installer in its unrestricted
mode. The installer first gains a connector mode that disables secret seeding,
legacy relocation, and unconditional file replacement.

Ownership modes:

- `managed_section`: hash and manage only content between stable sentinels;
- `managed_line`: hash and manage one exact line;
- `whole_file`: hash the complete file bytes;
- `managed_keys`: hash only the canonical JSON values of declared keys;
- `create_if_absent`: create a runtime file once and never overwrite it;
- `user_owned`: create a safe empty skeleton if absent, then never read,
  overwrite, hash, or delete it.

The complete connector ownership matrix is:

| Path | Ownership | Connect/update behavior | Disconnect behavior |
| --- | --- | --- | --- |
| `AGENTS.md` | `managed_section` | Upsert the sentinel block only when its prior managed hash matches | Remove only the unchanged managed block |
| `.gitignore` | `managed_line` | Add the exact `.memlayer/` line once | Remove only the exact connector-added line when safe |
| `.agents/skills/memlayer/SKILL.md` | `whole_file` | Create or replace only when the recorded whole-file hash matches | Delete only when the hash matches |
| `.memlayer/MEMLAYER.md` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/.env.memlayer.example` | `whole_file` | Create or hash-guarded replace; contains no key | Delete only when the hash matches |
| `.memlayer/memlayer.config.json` | `managed_keys` | Merge generated keys; preserve unknown keys; hash the managed subset | Remove managed keys only; preserve the file when other keys remain |
| `.memlayer/memlayer_api.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_watchdog.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_recover.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_launchd_install.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_context.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_write.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_sync.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_snapshot_pull.sh` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/memlayer_payload.py` | `whole_file` | Create or hash-guarded replace | Delete only when the hash matches |
| `.memlayer/.env.memlayer` | `user_owned` | Create mode `0600` with an empty key only when absent | Always preserve |
| `.memlayer/memlayer.snapshot.json` | `create_if_absent` | Create an empty snapshot only when absent | Delete only if connector-created and still at its initial hash |
| `.memlayer/memlayer.snapshot.md` | `create_if_absent` | Create an empty snapshot only when absent | Delete only if connector-created and still at its initial hash |
| `.memlayer/memlayer.offline.log.md` | `create_if_absent` | Create an empty log only when absent | Delete only if connector-created and still at its initial hash |
| `.memlayer/memlayer.offline.queue.jsonl` | `create_if_absent` | Create an empty queue only when absent | Delete only if connector-created, empty, and at its initial hash |

The managed config keys are the root-pack schema version, project name, project
root, connector identity, API URLs, retry policy, read/write defaults, and
recommended search settings. `project_id` and `tenant_id` are identity keys:
registration may set them atomically, but normal reconnect never replaces a
different non-empty value.

The connection manifest is the control file and is not included in its own
`managed_files` array because a file cannot carry a stable hash of itself. It
is schema-validated, written atomically after successful apply, and deleted
last after successful disconnect. Invalid or unrecognized manifest content is
a conflict, not a reset signal.

The connector never copies an API key from process environment into
`.env.memlayer`. Existing legacy top-level MemLayer files are reported by
doctor but are not moved or deleted by `connect`; migration is a separate
explicit operation.

### Ownership and Disconnect

Managed-section files are edited only between stable sentinels. Whole-file
artifacts are removed only when their current hash matches the recorded
managed hash.

If a user modified a managed whole file, `disconnect` reports a conflict and
leaves it untouched. Existing non-MemLayer content in `AGENTS.md` is always
preserved.

A changed managed section, managed line, or managed-key subset is also a
conflict. Reconnect and disconnect preserve the user version and report the
expected and actual hashes without printing file content. There is no
force-reset flag in the first release.

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

## Project Registration Contract

The existing plain `POST /projects` remains unchanged. Connector registration
uses a dedicated idempotent endpoint:

```http
POST /projects/resolve
```

Request:

```json
{
  "agent": "codex",
  "connector_identity": "d8399b69-82ff-46ec-8e03-1930f1c84735",
  "project_name": "example-project",
  "tenant_id": "tenant-42",
  "existing_project_id": null
}
```

Rules:

- `connector_identity` is a random UUID generated locally on first connect and
  persisted in the manifest before the network request;
- the server stores connector bindings in a separate
  `project_connector_identities` table;
- the unique identity is `(agent, normalized_tenant_key,
  connector_identity)`;
- `normalized_tenant_key` is the authenticated tenant id or an internal global
  sentinel and is never accepted directly from the request;
- tenant-restricted credentials with one tenant may omit `tenant_id`;
- credentials with multiple tenants must provide an allowed `tenant_id`;
- unrestricted credentials may explicitly select a tenant or use global scope;
- the endpoint requires `write` scope.

A project's tenant scope becomes immutable after its first connector binding
or memory entry. Cross-tenant project movement requires a separate
admin-approved migration and is outside this release.

The binding table contains:

```text
id
agent
normalized_tenant_key
connector_identity
project_id
created_at
```

`POST /projects/resolve` performs one transaction:

1. resolve and authorize tenant scope;
2. lock or insert the connector identity;
3. if the binding exists, return its project without mutation;
4. if `existing_project_id` is supplied, verify access and bind that project;
5. otherwise check accessible projects with the same normalized name;
6. if a name match exists without a binding, return conflict and require the
   caller to retry with an explicit `existing_project_id`;
7. if no match exists, create one project and bind it;
8. return the resolved project.

Response:

```json
{
  "status": "created",
  "project_id": "20f0ee72-d962-48d5-8857-0213a187ba98",
  "connector_identity": "d8399b69-82ff-46ec-8e03-1930f1c84735",
  "tenant_id": "tenant-42"
}
```

`status` is `created`, `resolved`, or `bound_existing`. Concurrent retries are
serialized by the unique constraint and return the winning binding. A timeout
is retried with the same connector identity. The connector writes `project_id`
to config and manifest only after a separate authenticated
`GET /projects/{project_id}` read-back succeeds; a failed request never creates
a second local identity.

No absolute source path, repository content, API key, or environment value is
sent by project registration.

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
api_reachable
auth_authenticated
live_read_authorized
live_read_verified
live_write_authorized
live_write_verified
snapshot_ready
queue_pending
```

Meanings:

- `local_connected`: manifest and all owned local artifacts are consistent;
- `live_identity_ready`: project id is present and its authenticated read-back
  matches connector identity and tenant;
- `api_reachable`: health endpoint responded;
- `auth_authenticated`: `/auth/me` confirms the configured credential;
- `live_read_authorized`: scopes permit reads;
- `live_read_verified`: the bound project was read successfully;
- `live_write_authorized`: scopes permit writes;
- `live_write_verified`: tri-state evidence of a recent write plus read-back;
- `snapshot_ready`: snapshot is valid and within the configured age limit;
- `queue_pending`: count of valid unsynchronized queue records is greater than
  zero.

`live_read_authorized` and `live_write_authorized` come only from authenticated
scope inspection. `live_read_verified` requires a successful project read-back.
`live_write_verified` is a tri-state value:

- `true`: a referenced prior write receipt is still fresh and its target can
  be read back;
- `false`: a prior explicit write attempt failed;
- `unknown`: no verifiable prior write receipt is available.

The last write-check summary is stored as an operational, non-hashed config
key. It includes status, operation, attempted timestamp, target id when one
exists, successful read-back timestamp when applicable, and an opaque local
receipt id, but no payload, response body, or secret. Connector registration
and root-pack write helpers record `success` only after write plus target
read-back; a failed explicit attempt records `failed`. It expires after 24
hours. Doctor repeats the target read-back before returning `true`; a fresh
failed attempt without a later success is `false`; an expired or missing record
is `unknown`. Doctor never performs a canary write, registration, cleanup, or
any other mutation. Health alone proves only `api_reachable`.

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

Allowed `kind` values are:

```text
source_inspection
test_run
runtime_health
read_back
external_api_read
human_approval
```

Provenance authorization:

- `unspecified`, `explicit_statement`, `observed`, `inferred`, and `corrected`
  require `write` scope;
- `imported` requires `import` or `admin` scope and is set through the import
  service;
- `validated` requires `validate` or `admin` scope.

For `validated`, the API validates the evidence schema, rejects unknown fields,
applies a shared fail-closed scanner extracted from the current import masking
patterns and expanded with authorization headers, private-key markers, common
API-key prefixes, password assignments, and forbidden raw-output keys. It then
records the authenticated actor in the change event. Passing this deterministic
scan means "authorized, structured, and privacy-attested"; it is not a
mathematical proof that no sensitive datum exists.

The event actor is a server-derived safe principal identifier matching
`[A-Za-z0-9._:-]{1,100}`. It is never an API key, display name, email address,
or client-provided actor string.

Clients cannot submit service-owned metadata such as `quality`,
`review_history`, review flags, conflict sets, or import-run counters. Those
keys are rejected rather than silently removed.

Top-level `confidence` is the caller's evidence confidence. The existing
`metadata.quality.confidence` remains a read-only system heuristic during the
compatibility period and is exposed in new code as
`quality.assessment_confidence`. It never populates or overrides top-level
`confidence`.

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

## Current and Historical Read Semantics

At an injected or database-consistent time `t`, the current-memory predicate
is:

```text
valid_from <= t
AND (valid_to IS NULL OR valid_to > t)
AND archived = false
```

The predicate is centralized in the repository and is the default for:

- memory list with `archived` omitted or `false`;
- lexical, semantic, and hybrid search;
- relevant-memory and context building;
- duplicate and semantic-duplicate detection;
- decision authority checks;
- auto-link candidate selection;
- import match and active import-event reuse;
- compaction and hygiene candidates;
- lifecycle jobs;
- current-memory metrics and admin summaries.

History, revision-chain reads, explicit `as_of`, and explicit
`archived=true` administration do not use the default current view.
`archived=true` returns archived closures only; it does not expose superseded
rows. Superseded rows are available through history, direct id lookup, and
authorized historical reads.

Historical `as_of` evaluates the validity interval and does not apply the
row's present-day `archived` flag. This is required because archive closes the
interval and then marks the same row archived; a query for a time before that
closure must still see the row.

`GET /memory/{id}` returns that exact revision even when it is no longer
current. Its response includes:

```text
is_current
valid_from
valid_to
supersedes_id
successor_id
```

This prevents a historical citation from silently resolving to different
content. Clients that need the current state use normal search/list or follow
`successor_id`.

Database constraints and indexes:

- unique index on non-null `supersedes_id`, enforcing one direct successor;
- index on `(project_id, valid_from, valid_to)`, supporting `as_of`;
- PostgreSQL partial index on `(project_id, type, created_at DESC)` where
  `archived=false AND valid_to IS NULL`, supporting current reads;
- SQLite full index on `(project_id, archived, valid_to, valid_from)` with the
  same predicate applied by the repository.

Current and historical metrics are reported separately. A superseded row never
increments current-memory counts and is never archived again by lifecycle
maintenance.

Legacy metadata fields such as `valid_from`, `valid_until`, and
`supersedes_entry_id` remain compatibility diagnostics only. The new
first-class columns are authoritative for temporal filtering and lineage.

## Revision Semantics

Client-changeable semantic fields:

- type;
- title;
- content;
- source agent;
- importance;
- provenance;
- confidence;
- user-controlled metadata.

Immutable identity and scope fields:

- entry id;
- project id;
- tenant scope;
- created-at timestamp of an existing revision;
- validity and successor fields, which are server-controlled.

Project tenant changes are rejected after the project has a connector binding
or any memory row. This makes the inherited tenant scope stable without
silently reassigning historical memory.

A semantic revision runs in one transaction:

1. lock and authorize the current active entry;
2. reject revision of an entry that already has a successor;
3. derive `actor` from the authenticated principal and require a bounded,
   privacy-safe `reason`;
4. take one injected server clock value and set `old.valid_to` to it;
5. create a new entry with the same `project_id`, `valid_from` equal to that
   clock value, and `supersedes_id=old.id`;
6. preserve project and tenant scope;
7. rebuild system-owned quality and conflict metadata for the new content;
8. copy graph relations according to the inheritance policy below;
9. create the new search representation and one change event;
10. return the new entry and revision metadata.

Ordinary callers cannot provide `valid_from` for a revision. Backdated initial
creation is restricted to `import` or `admin` scope. Revision requires `write`
scope; cross-project movement is not a revision and is unsupported in the
first release.

Metadata policy:

- client-owned metadata is copied and then patched;
- system-owned operational keys are rejected in a generic request;
- quality and decision-conflict metadata is recomputed;
- review history remains attached to the revision it reviewed;
- import counters/history are copied only when ImportService initiates the
  revision for an import event.

Graph-link inheritance policy:

- retain every historical link unchanged;
- for each incoming or outgoing link on the old revision, create one link with
  the new revision substituted only on the revised side;
- preserve opposite endpoint, type, strength, and creating agent;
- add `inherited_from_link_id`, `inherited_at`, and `revision_id` metadata;
- do not chase or retarget a successor of the opposite endpoint;
- skip an already-existing identical link;
- roll back the entire revision if link inheritance fails.

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
uses a dedicated restore operation that creates a new current revision instead
of reopening the old row. A superseded or archived entry cannot be revised
through the normal revision endpoint.

Restore selects historical source content but preserves a linear chain:

1. find and lock the chain's current leaf, or its archived leaf when the chain
   has no current entry;
2. close that leaf when it is current;
3. create the restored entry with `supersedes_id` pointing to that leaf, not
   to the older source revision;
4. record `restored_from_entry_id` in the change event;
5. inherit links from the closed leaf under the same graph policy.

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

`valid_from` defaults to the server clock. A client-supplied value requires
`import` or `admin` scope.

### Revise

```http
POST /memory/{id}/revise
```

Request:

```json
{
  "changes": {
    "title": "Updated title",
    "content": "Updated content",
    "provenance": "corrected",
    "confidence": 0.85
  },
  "metadata_patch": {
    "evidence": ["sanitized-read-back"]
  },
  "reason": "Corrected after authoritative read-back."
}
```

`reason` is required, limited to 500 characters, scanned for forbidden secret
markers, and recorded in the change event. `actor` is derived from the
authenticated principal under the safe actor-id rule, never accepted from the
payload. The response returns the new entry, superseded id, actor, reason, and
revision timestamp.

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
GET /memory/changes?project_id=...&changed_since=...&limit=...
GET /memory/changes?project_id=...&cursor=...&limit=...
```

This endpoint reads an append-only `memory_change_events` table rather than
inferring changes from `memory_entries.updated_at`.

Event fields:

```text
sequence             monotonic integer primary key
event_kind           created | revised | archived | restored
occurred_at          timezone-aware server timestamp
project_id
normalized_tenant_key server-derived tenant scope at event time
entry_id             resulting or closed entry
previous_entry_id    nullable
actor
reason               nullable, sanitized and bounded
```

Every semantic create, revision, archive, or restore writes exactly one event
in the same transaction as the memory change. Usage counters, access
timestamps, review actions, import-run counters, and other operational updates
do not enter this semantic change feed.

Ordering is `(sequence ASC)`, so equal timestamps cannot drop or reorder
events. `changed_since` is RFC 3339 and exclusive:

```text
occurred_at > changed_since
```

It is allowed only on the first page. The response returns an opaque,
versioned, project-bound cursor containing the last sequence. Subsequent pages
use `sequence > cursor.sequence`; supplying both parameters is a validation
error. `limit` defaults to 100 and is capped at 500. `has_more` and
`next_cursor` are always returned.

Indexes:

- `(project_id, sequence)`;
- `(project_id, occurred_at, sequence)`.

Tenant and project authorization matches normal memory reads. A cursor issued
for another project or tenant is rejected.

Existing memory rows do not receive fabricated historical events. The endpoint
returns `history_complete_from`, equal to the change-feed migration timestamp.
A `changed_since` value earlier than that timestamp returns a validation error
with `history_complete_from`, rather than implying a complete feed.

### PATCH Compatibility

Rollout is staged:

1. before temporal schema activation, existing `PATCH` remains unchanged;
2. when revisions activate, semantic `PATCH` delegates internally to the same
   revision transaction and returns deprecation headers;
3. compatibility revisions use the authenticated actor and the server reason
   `legacy PATCH compatibility`;
4. `project_id`, tenant, validity, and successor changes are rejected
   immediately rather than delegated;
5. migrate console, SDK, import/reimport, compaction, and root-pack callers;
6. reject semantic `PATCH` with a conflict response that points to `/revise`;
7. retain only explicit operational service updates until a versioned API
   cleanup is approved.

## Error Handling

- invalid project root: fail before mutation;
- unsupported agent: fail with supported list containing only `codex`;
- modified managed file: conflict, preserve file;
- missing project id: local connection may succeed, live readiness remains
  false;
- missing API key for registration: fail before network write;
- ambiguous existing project name: conflict requiring explicit project id;
- connector identity already bound in another tenant: not found or forbidden
  without revealing that binding;
- invalid confidence or temporal interval: validation error;
- unauthorized `imported` or `validated` provenance: forbidden;
- client-supplied service metadata: validation error;
- sensitive validation evidence or revision reason: validation error;
- stale revision target: conflict with current successor id;
- cross-project or cross-tenant revision: forbidden;
- cursor project/tenant mismatch: validation error;
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
- every root-pack path follows the ownership matrix;
- connector mode never reads or seeds an API key;
- modified section, line, managed JSON keys, and whole files fail closed;
- create-if-absent runtime files are not overwritten;
- legacy top-level files are reported but not relocated;
- unsupported/global agent modes fail closed;
- registration is never called without the explicit flag.

### Registration Tests

- first resolve creates one binding and one project;
- repeated and concurrent resolve returns the same project;
- existing `project_id` binds only after tenant authorization;
- ambiguous name returns conflict without creating a project;
- multi-tenant credentials require explicit tenant selection;
- no source path, environment value, or repository content enters the request;
- failed read-back does not write project id to local config or manifest.

### Doctor Tests

- each readiness dimension is independent;
- HTTP health without auth does not imply write readiness;
- write scope yields `live_write_authorized`, not
  `live_write_verified=true`;
- verified status requires a fresh receipt and target read-back;
- stale snapshot and invalid queue are reported;
- no API key value appears in text or JSON output.

### Model and Migration Tests

- PostgreSQL and SQLite-compatible model behavior;
- existing-row backfill;
- enum and confidence constraints;
- provenance scope and validation-evidence constraints;
- service-owned metadata rejection;
- top-level confidence remains independent from quality assessment confidence;
- self-reference and single-successor constraints;
- current and temporal indexes;
- downgrade safety on a disposable database.

### Revision Tests

- deterministic injected clock;
- atomic old-close/new-create behavior;
- concurrent second revision loses with conflict;
- graph relations are inherited once;
- opposite graph endpoints are not silently retargeted;
- actor and reason are recorded from trusted sources;
- project, tenant, and validity identity fields cannot be changed by payload;
- project and tenant boundaries are preserved;
- archive and restore produce correct intervals.

### Temporal Retrieval Tests

- exact interval boundaries;
- ordinary list, all search modes, relevant memory, context, duplicate
  detection, lifecycle, metrics, compaction, import matching, and auto-linking
  exclude superseded revisions;
- `as_of` returns the correct historical revision;
- direct id lookup returns exact historical content and successor metadata;
- `changed_since` and cursor pagination are exclusive, stable, and complete
  across equal timestamps;
- operational updates do not emit semantic change events;
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
4. default reads and every current-memory consumer exclude superseded
   revisions through one repository predicate;
5. connector ownership covers the full root-pack and never seeds or hashes a
   secret-bearing environment file;
6. project registration is tenant-safe, retry-safe, and duplicate-safe;
7. new memories expose authorized provenance, independent confidence, and
   validity fields;
8. validated provenance requires authorized privacy-safe evidence;
9. semantic revisions preserve immutable identity, trusted actor/reason, the
   old state, and reject branching races;
10. as-of retrieval returns the correct revision;
11. change events provide stable project-bound cursor pagination without
    operational-update noise;
12. doctor distinguishes write authorization from verified prior writes;
13. existing clients remain usable during the documented compatibility window;
14. tests cover privacy, tenant isolation, idempotency, migration, rollback,
    temporal boundaries, root-pack ownership, and cursor behavior;
15. no production deploy or project-content import occurs without separate
    explicit approval.
