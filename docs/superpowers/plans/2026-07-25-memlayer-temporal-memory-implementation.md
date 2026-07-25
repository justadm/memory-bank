# MemLayer Temporal Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class provenance, confidence, immutable revisions, historical reads, and a complete project-scoped sequence change feed without changing tenant boundaries or losing current-read correctness.

**Architecture:** Temporal identity lives in first-class `memory_entries` columns. One repository predicate defines current and as-of visibility for every reader. Semantic writes go through one revision service and emit one event in the same transaction through a per-project locked feed-state row. Existing operational updates remain in place behind a narrow service-owned allowlist.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, SQLite test compatibility, pytest.

## Global Constraints

- Complete the Codex connector plan through its project-identity migration before applying this plan; this plan's migration starts at revision `20260725_0006`.
- Keep every committed checkpoint green. Red TDD states may exist locally but not on `main`.
- Use one injected, timezone-aware server clock value per semantic transaction.
- Do not infer historical revisions for legacy rows.
- Do not use `updated_at` or `occurred_at` as a change-feed checkpoint.
- Never accept actor, tenant, successor, validity, or service-owned metadata from ordinary clients.
- Do not expose raw evidence, secrets, API keys, customer payloads, or private identifiers in metadata, events, cursors, or logs.
- Do not deploy or migrate production as part of this plan.

---

### Task 1: Add Temporal Models, Constraints, and Backfill Migration

**Files:**
- Modify: `app/models/enums.py`
- Modify: `app/models/memory_entry.py`
- Modify: `app/models/__init__.py`
- Create: `app/models/memory_change_feed.py`
- Create: `alembic/versions/20260725_0006_temporal_memory.py`
- Modify: `scripts/run_guarded_migration_drill.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_temporal_models.py`

**Interfaces:**
- Produces: `MemoryProvenance`, `MemoryChangeEventKind`, temporal entry columns, `MemoryChangeFeedState`, and `MemoryChangeEvent`.
- Consumes: project identity migration revision `20260725_0005`.

- [ ] **Step 1: Write failing model tests**

Cover:

```python
def test_memory_entry_defaults_to_unspecified_current_revision(db_session):
    entry = make_memory_entry()
    db_session.add(entry)
    db_session.flush()

    assert entry.provenance is MemoryProvenance.unspecified
    assert entry.confidence is None
    assert entry.valid_from is not None
    assert entry.valid_to is None
    assert entry.supersedes_id is None
    assert entry.history_available is True
```

Also assert confidence rejects values outside `0.0..1.0`, `valid_to <= valid_from` fails, self-superseding fails, and a second successor for one predecessor violates the unique constraint.

- [ ] **Step 2: Run the focused tests and confirm failure**

```bash
.venv313/bin/pytest tests/test_temporal_models.py -q
```

Expected: missing enums/models/columns fail.

- [ ] **Step 3: Add enums and SQLAlchemy models**

Add:

```python
class MemoryProvenance(str, Enum):
    unspecified = "unspecified"
    explicit_statement = "explicit_statement"
    observed = "observed"
    inferred = "inferred"
    corrected = "corrected"
    validated = "validated"
    imported = "imported"


class MemoryChangeEventKind(str, Enum):
    created = "created"
    revised = "revised"
    archived = "archived"
    restored = "restored"
```

`MemoryEntry` gains `provenance`, `confidence`, `valid_from`, `valid_to`,
`supersedes_id`, and `history_available`. `MemoryChangeFeedState` is keyed by
`project_id`; `MemoryChangeEvent` is keyed by `(project_id, sequence)` and
includes `feed_epoch`, `event_kind`, `occurred_at`,
`normalized_tenant_key`, `entry_id`, `previous_entry_id`, `actor`, and
`reason`. Model metadata defines the SQLite full current/as-of support index;
the Alembic migration defines the PostgreSQL partial/current and as-of indexes.

- [ ] **Step 4: Write the migration**

Migration `20260725_0006` must:

1. add nullable temporal columns;
2. capture one database-derived `migration_cutover_at`;
3. backfill non-archived rows with `valid_from=created_at`,
   `valid_to=null`, and `history_available=true`;
4. backfill archived rows with `valid_from=created_at`,
   `valid_to=migration_cutover_at`, and `history_available=false`;
5. make required columns non-null;
6. add confidence, interval, self-reference, and single-successor constraints;
7. add PostgreSQL current/as-of indexes;
8. create feed-state and event tables;
9. create one feed-state row with sequence `0` for every existing project;
10. set `down_revision = "20260725_0005"`.

It must not fabricate change events for existing memories.

- [ ] **Step 5: Test models on SQLite and migrations on PostgreSQL**

SQLite tests create schema through `Base.metadata.create_all()` and verify
model constraints, predicates, and API behavior. They do not run the
PostgreSQL-only Alembic chain.

Extend `scripts/run_guarded_migration_drill.py` with
`--fixture-profile temporal`. The runner provisions its own isolated
PostgreSQL and performs:

```text
base -> 20260429_0004
insert active and archived legacy fixtures
upgrade -> head
verify cutover backfill, history markers, constraints, indexes, feed state
downgrade -> 20260429_0004
upgrade -> head
```

The runner uses the same no-external-URL and unconditional-cleanup contract
defined by the connector plan. It exits non-zero on any failed migration or
assertion.

- [ ] **Step 6: Run focused tests and commit**

```bash
.venv313/bin/pytest tests/test_temporal_models.py tests/test_api.py -q
git diff --check
git add app/models alembic/versions/20260725_0006_temporal_memory.py scripts/run_guarded_migration_drill.py tests/test_temporal_models.py tests/test_api.py
git commit -m "Add temporal memory schema"
```

### Task 2: Enforce Provenance, Evidence, Actor, and Metadata Boundaries

**Files:**
- Modify: `app/security.py`
- Modify: `app/schemas/memory.py`
- Create: `app/services/memory_evidence_service.py`
- Modify: `app/services/memory_service.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_memory_evidence.py`

**Interfaces:**
- Produces: `ValidationEvidence`, `MemoryEvidenceService`, `safe_actor_id()`, and service-owned metadata validation.
- Consumes: authenticated `AuthPrincipal` and the new provenance fields.

- [ ] **Step 1: Write failing authorization and privacy tests**

Test that:

- `validated` requires `validate` or `admin`;
- `imported` requires `import` or `admin` and cannot be set by generic create/revise;
- validation evidence rejects unknown keys, raw output keys, authorization headers, private keys, common API-key prefixes, and password assignments;
- service-owned metadata keys are rejected;
- actor is server-derived and matches `[A-Za-z0-9._:-]{1,100}`;
- top-level confidence never copies `metadata.quality.confidence`.

- [ ] **Step 2: Implement strict schemas and the evidence scanner**

Use an extra-forbid Pydantic model:

```python
class ValidationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "source_inspection",
        "test_run",
        "runtime_health",
        "read_back",
        "external_api_read",
        "human_approval",
    ]
    summary: str = Field(min_length=1, max_length=500)
    captured_at: datetime
    redacted: Literal[True]
    contains_sensitive_data: Literal[False]
```

Extract existing import masking patterns into a shared deterministic scanner and extend them with the forbidden markers from the design.

- [ ] **Step 3: Centralize service-owned metadata**

Define one immutable `SERVICE_OWNED_METADATA_KEYS` set. Generic create/update/revise payloads reject these keys; internal services use an explicit operational update method added in Task 7.

- [ ] **Step 4: Enforce provenance scopes**

`MemoryEvidenceService.validate_provenance()` receives provenance, principal, operation source, and metadata. It must reject client attempts to claim `imported`, reject unauthorized `validated`, and require valid evidence for `validated`.

- [ ] **Step 5: Run tests and commit**

```bash
.venv313/bin/pytest tests/test_memory_evidence.py tests/test_api.py -q
git diff --check
git add app/security.py app/schemas/memory.py app/services/memory_evidence_service.py app/services/memory_service.py tests/test_memory_evidence.py tests/test_api.py
git commit -m "Enforce memory provenance boundaries"
```

### Task 3: Centralize Current and Historical Visibility

**Files:**
- Modify: `app/repositories/memory_repository.py`
- Modify: `app/repositories/project_repository.py`
- Modify: `app/services/search_service.py`
- Modify: `app/services/semantic_search_service.py`
- Modify: `app/services/context_builder_service.py`
- Modify: `app/services/semantic_duplicate_service.py`
- Modify: `app/services/decision_authority_service.py`
- Modify: `app/services/auto_link_service.py`
- Modify: `app/services/import_service.py`
- Modify: `app/services/compaction_service.py`
- Modify: `app/services/memory_hygiene_service.py`
- Modify: `app/services/lifecycle_service.py`
- Modify: `app/repositories/metrics_repository.py`
- Modify: `app/services/admin_observability_service.py`
- Create: `docs/current-memory-query-inventory.json`
- Create: `scripts/lint_memory_query_inventory.py`
- Create: `tests/test_memory_query_inventory.py`
- Create: `tests/test_temporal_visibility.py`

**Interfaces:**
- Produces: `MemoryRepository.current_predicate(at)`, `historical_predicate(at)`, and current-by-default repository methods.
- Consumes: first-class validity columns from Task 1.

- [ ] **Step 1: Create the tracked query inventory and failing lint test**

`scripts/lint_memory_query_inventory.py` parses Python AST under `app/` and
finds every statement that both references `MemoryEntry` and performs a
database query or mutation through `select`, `query`, `get`, `execute`,
`scalars`, `update`, or `delete`. Each detected statement gets a stable key:

```text
relative_path : qualified_function : normalized_ast_sha256
```

Line numbers are diagnostic only and are not part of identity. Store the
reviewed set in `docs/current-memory-query-inventory.json`:

```json
{
  "schema_version": 1,
  "queries": [
    {
      "key": "app/repositories/memory_repository.py:MemoryRepository.list:<sha256>",
      "classification": "current-view",
      "required_guard": "current_predicate",
      "owner": "MemoryRepository.list"
    }
  ]
}
```

Allowed classifications are `current-view`, `historical-view`,
`exact-id-view`, and `operational-row-update`. `--write` creates or refreshes
the inventory only after explicit review; normal `--check` compares the exact
detected key set and exits non-zero for missing, extra, or duplicate entries.

`tests/test_memory_query_inventory.py` invokes `--check`. Before inventory
population it must fail and list every unclassified query.

- [ ] **Step 2: Write failing boundary tests**

Create fixtures with:

- current entry: `valid_from <= t`, `valid_to=None`, not archived;
- future entry;
- superseded entry;
- archived closure;
- historical entry that was active before archive.

Assert current list/search/relevant/context/duplicates/import-match/auto-link/
compaction/lifecycle/metrics/project entry counts/admin summaries exclude
non-current rows. Assert `as_of` includes a native historical row active at
that instant even when it is now archived. Assert a legacy archived row with
`history_available=false` is excluded both before and after
`migration_cutover_at`.

- [ ] **Step 3: Add repository predicates**

```python
@staticmethod
def current_predicate(at: datetime):
    return and_(
        MemoryEntry.valid_from <= at,
        or_(MemoryEntry.valid_to.is_(None), MemoryEntry.valid_to > at),
        MemoryEntry.archived.is_(False),
    )


@staticmethod
def historical_predicate(at: datetime):
    return and_(
        MemoryEntry.history_available.is_(True),
        MemoryEntry.valid_from <= at,
        or_(MemoryEntry.valid_to.is_(None), MemoryEntry.valid_to > at),
    )
```

Normalize and validate timezone-aware `at` once. Default reads use a single injected time per service operation.

- [ ] **Step 4: Route every current consumer through the predicate**

Refactor each inventoried query. Administrative `archived=true`, direct id, history, and explicit `as_of` use dedicated paths and must not accidentally inherit current filtering.
`ProjectRepository.list_with_entry_counts(*, at)` must apply the same current
predicate inside its outer join so project/admin counts cannot include
superseded or future rows.

- [ ] **Step 5: Enforce guards and refresh the reviewed inventory**

For each inventory row, the linter also verifies:

```text
current-view           -> enclosing function calls current_predicate
historical-view        -> enclosing function calls historical_predicate
exact-id-view          -> lookup is keyed by entry id and does not feed a current summary
operational-row-update -> owner is present in a hardcoded internal allowlist
```

After refactoring, run `--write`, review the JSON diff, then run `--check`.
Any new or structurally changed direct query produces a new AST fingerprint
and fails until a reviewer classifies it. Comments alone never satisfy the
test.

- [ ] **Step 6: Run tests and commit**

```bash
python3 scripts/lint_memory_query_inventory.py --check
.venv313/bin/pytest tests/test_memory_query_inventory.py tests/test_temporal_visibility.py tests/test_api.py tests/test_importer.py -q
git diff --check
git add app/repositories app/services docs/current-memory-query-inventory.json scripts/lint_memory_query_inventory.py tests/test_memory_query_inventory.py tests/test_temporal_visibility.py tests/test_api.py tests/test_importer.py
git commit -m "Apply temporal visibility to memory reads"
```

### Task 4: Implement the Sequence Change Feed

**Files:**
- Modify: `app/config.py`
- Create: `app/repositories/memory_change_repository.py`
- Create: `app/services/memory_change_service.py`
- Modify: `app/schemas/memory.py`
- Modify: `app/routers/memory.py`
- Modify: `app/services/memory_service.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_memory_change_feed.py`

**Interfaces:**
- Produces: `MemoryChangeRepository.append()`, `MemoryChangeService.list_changes()`, opaque cursor codec, and `GET /memory/changes`.
- Consumes: project feed-state row and the same database transaction as semantic writes.

- [ ] **Step 1: Write failing ordering and cursor tests**

Cover:

- first page starts after exclusive `after_sequence`;
- cursor and `after_sequence` together fail;
- cursor project, tenant, or epoch mismatch fails;
- event order follows sequence when timestamps are equal or deliberately out of order;
- limit is `1..500`, default `100`;
- high watermark never includes an uncommitted lower event;
- operational updates emit no event.

- [ ] **Step 2: Implement event allocation**

Within the caller's transaction:

1. ensure a feed-state row exists for projects created after the migration,
   using conflict-safe insert semantics;
2. lock the project's `MemoryChangeFeedState` using `SELECT ... FOR UPDATE` on
   PostgreSQL;
3. serialize SQLite tests with the transaction strategy documented in the
   repository;
4. allocate `sequence = committed_sequence + 1`;
5. insert the event;
6. update `committed_sequence`;
7. flush without committing.

The service must reject event creation outside a semantic write transaction.

- [ ] **Step 3: Implement the signed opaque cursor**

Add a dedicated `MEMORY_CHANGE_CURSOR_SIGNING_KEY` setting. Production startup
fails closed when the change endpoint is enabled without a non-default key;
tests inject a deterministic key. Do not reuse an API key or expose the cursor
key through settings output.

Encode versioned canonical JSON as base64url and append an HMAC-SHA256 signature:

```json
{
  "v": 1,
  "project_id": "...",
  "tenant_key": "...",
  "feed_epoch": "...",
  "sequence": 42
}
```

Verify the signature with constant-time comparison before decoding. Decode
with strict extra-field rejection. Authorization is repeated from the request
principal. Reject tampering, another project/tenant/epoch, and any negative or
beyond-high-watermark sequence. Cursor text and decoded contents are never
logged.

- [ ] **Step 4: Add endpoint and response contract**

Return:

```python
class MemoryChangePage(BaseModel):
    items: list[MemoryChangeItem]
    has_more: bool
    next_cursor: str | None
    committed_high_watermark: int
    feed_epoch: UUID
    feed_started_at: datetime
```

Register `/memory/changes` before `/{entry_id}` in the router. The query is
strictly:

```text
project_id = requested project
AND feed_epoch = current epoch
AND sequence > checkpoint
AND sequence <= committed high watermark
ORDER BY sequence
```

- [ ] **Step 5: Emit a create event**

Wire only ordinary `POST /memory` in this checkpoint. Event actor and tenant are server-derived; reason is null. Revision/archive/restore events are added with their operations in later tasks.

- [ ] **Step 6: Run tests and commit**

```bash
.venv313/bin/pytest tests/test_memory_change_feed.py tests/test_api.py -q
git diff --check
git add app/config.py app/repositories/memory_change_repository.py app/services/memory_change_service.py app/services/memory_service.py app/schemas/memory.py app/routers/memory.py tests/test_memory_change_feed.py tests/test_api.py
git commit -m "Add sequence memory change feed"
```

### Task 5: Add Immutable Revision and History APIs

**Files:**
- Create: `app/services/memory_revision_service.py`
- Modify: `app/repositories/memory_repository.py`
- Modify: `app/repositories/link_repository.py`
- Modify: `app/schemas/memory.py`
- Modify: `app/routers/memory.py`
- Modify: `app/services/memory_service.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_memory_revisions.py`

**Interfaces:**
- Produces: `MemoryRevisionService.revise()`, `history()`, `POST /memory/{id}/revise`, and `GET /memory/{id}/history`.
- Consumes: evidence validation, current predicate, graph repository, and change feed.

- [ ] **Step 1: Write failing revision tests**

Test deterministic clock, old-close/new-create atomicity, immutable project/tenant/validity fields, stale predecessor conflict, server actor/reason, metadata policy, one revision event, and rollback when link inheritance fails.

- [ ] **Step 2: Add strict revise schemas**

`MemoryReviseRequest` contains `changes`, `metadata_patch`, and required privacy-scanned `reason`. It does not expose `project_id`, tenant, actor, validity, successor, archive state, usage counters, or service metadata.

- [ ] **Step 3: Implement the transactional revision**

`revise()`:

1. locks exact target and authorizes project;
2. proves it is current and has no successor;
3. takes one injected clock value;
4. closes old validity;
5. creates new entry with same project and `supersedes_id=old.id`;
6. recomputes quality/decision metadata;
7. rebuilds search vector;
8. inherits graph links exactly once;
9. appends one `revised` event;
10. returns without an internal commit.

Catch the unique-successor race and return `409` with the current successor id.

- [ ] **Step 4: Implement graph-link inheritance**

Historical links remain unchanged. New links substitute only the revised endpoint, preserve the opposite endpoint/type/strength/creating agent, and add:

```json
{
  "inherited_from_link_id": "...",
  "inherited_at": "...",
  "revision_id": "..."
}
```

Skip an already-identical inherited link.

- [ ] **Step 5: Add direct historical response and history**

`GET /memory/{id}` returns exact revision plus `is_current`, `successor_id`, and temporal fields. History follows the linear predecessor/successor chain, applies tenant authorization to every member, and orders by `valid_from`.

- [ ] **Step 6: Run tests and commit**

```bash
.venv313/bin/pytest tests/test_memory_revisions.py tests/test_api.py -q
git diff --check
git add app/services/memory_revision_service.py app/services/memory_service.py app/repositories app/schemas/memory.py app/routers/memory.py tests/test_memory_revisions.py tests/test_api.py
git commit -m "Add immutable memory revisions"
```

### Task 6: Add Archive, Restore, and As-Of Reads

**Files:**
- Modify: `app/services/memory_revision_service.py`
- Modify: `app/services/memory_service.py`
- Modify: `app/repositories/memory_repository.py`
- Modify: `app/schemas/memory.py`
- Modify: `app/routers/memory.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_memory_restore.py`

**Interfaces:**
- Produces: temporal archive, `POST /memory/{id}/restore`, and `as_of` search/relevant.
- Consumes: revision chain, historical predicate, and change feed.

- [ ] **Step 1: Write failing archive/restore tests**

Cover interval boundary behavior, archived current exclusion, historical as-of visibility before archive, restore from an older revision, restore pointing to the chain leaf, restore event metadata, and rejection of normal revise on archived/superseded rows.

- [ ] **Step 2: Make archive temporal**

Archive locks the current leaf, takes one clock value, sets `valid_to=clock` and `archived=true`, and appends one `archived` event in the same transaction. Re-archiving a superseded or archived row conflicts.

- [ ] **Step 3: Implement restore**

Restore selects source content but links the new row to the current or archived chain leaf. It copies/inherits under the same revision rules, records `restored_from_entry_id` in the `restored` event, and never reopens an old row.

- [ ] **Step 4: Add as-of request fields**

Add timezone-aware optional `as_of` to search and relevant schemas/routes. Current requests use `current_predicate`; explicit historical requests use `historical_predicate` and do not mutate usage counters unless the existing access-log policy explicitly supports historical reads.

- [ ] **Step 5: Run tests and commit**

```bash
.venv313/bin/pytest tests/test_memory_restore.py tests/test_temporal_visibility.py tests/test_api.py -q
git diff --check
git add app/services app/repositories/memory_repository.py app/schemas/memory.py app/routers/memory.py tests/test_memory_restore.py tests/test_temporal_visibility.py tests/test_api.py
git commit -m "Add temporal archive restore and as-of reads"
```

### Task 7: Separate Semantic Revisions from Operational Updates

**Files:**
- Modify: `app/services/memory_service.py`
- Modify: `app/services/import_service.py`
- Modify: `app/services/compaction_service.py`
- Modify: `app/services/lifecycle_service.py`
- Modify: `app/services/memory_quality_service.py`
- Modify: `app/routers/admin.py`
- Modify: `app/routers/imports.py`
- Modify: `memorybank_sdk/client.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_importer.py`
- Modify: `tests/test_sdk.py`
- Create: `tests/test_memory_update_compatibility.py`

**Interfaces:**
- Produces: `update_operational_fields()`, semantic PATCH compatibility/deprecation behavior, and explicit SDK revision methods.
- Consumes: immutable revision service and service-owned metadata allowlist.

- [ ] **Step 1: Write failing compatibility tests**

Assert:

- semantic PATCH delegates to the revision service and returns deprecation headers;
- `project_id`, tenant, validity, successor, and actor changes fail immediately;
- compatibility reason is exactly `legacy PATCH compatibility`;
- operational updates change no semantic field and emit no change event;
- import counters/history use operational update;
- import content changes create revisions with `imported` provenance;
- SDK exposes `revise_memory`, `restore_memory`, `memory_history`, and `memory_changes`.

- [ ] **Step 2: Implement the operational update boundary**

Only internal services may call:

```python
def update_operational_fields(
    entry: MemoryEntry,
    *,
    fields: Mapping[str, object],
    metadata_patch: Mapping[str, object],
    operation: OperationalUpdateKind,
) -> MemoryEntry:
    ...
```

Validate fields and metadata against the central allowlist. No generic dict passthrough.

- [ ] **Step 3: Delegate semantic PATCH**

Classify incoming PATCH once. Semantic fields invoke `MemoryRevisionService.revise()` and add deprecation headers; forbidden identity fields reject; purely operational generic PATCH is rejected because only server services own that path.

- [ ] **Step 4: Migrate internal callers**

Import/reimport uses revision for changed semantic content and operational update for run counters. Compaction creates/revises through explicit APIs. Lifecycle and quality review use operational update or temporal archive. No internal caller writes semantic fields in place.

- [ ] **Step 5: Extend the SDK**

Add typed methods for provenance/confidence, revise/history/restore/as-of/changes. Preserve existing method names during compatibility mode and surface deprecation response metadata.

- [ ] **Step 6: Run tests and commit**

```bash
.venv313/bin/pytest tests/test_memory_update_compatibility.py tests/test_api.py tests/test_importer.py tests/test_sdk.py -q
git diff --check
git add app memorybank_sdk tests
git commit -m "Separate memory revisions from operational updates"
```

### Task 8: Add Temporal Metrics, Console Support, and Migration Evidence

**Files:**
- Modify: `app/repositories/metrics_repository.py`
- Modify: `app/services/metrics_service.py`
- Modify: `app/services/admin_observability_service.py`
- Modify: `app/schemas/metrics.py`
- Modify: `app/static/console/app.js`
- Modify: `app/static/console/index.html`
- Modify: `README.md`
- Modify: `README_RU.md`
- Modify: `docs/API.md`
- Modify: `WORKLOG.md`
- Create: `docs/examples/temporal-memory-local-evidence.md`
- Create: `tests/test_temporal_metrics.py`

**Interfaces:**
- Produces: separate current/historical/revision/provenance metrics and operator-visible lineage.
- Consumes: completed temporal APIs and local disposable databases.

- [ ] **Step 1: Write failing metrics tests**

Assert current count excludes archived/superseded rows; historical count includes revisions; provenance distribution, stale-revision conflicts, feed high watermark, and missing provenance rate are separate fields.

- [ ] **Step 2: Implement metrics without changing semantics**

Use repository current/historical predicates. Do not infer old provenance. Console labels must distinguish evidence confidence from quality assessment confidence.

- [ ] **Step 3: Add minimal console lineage**

Expose current/historical status, predecessor/successor ids, provenance, confidence, validity interval, and history navigation. Do not add semantic edit UI in this checkpoint.

- [ ] **Step 4: Run disposable PostgreSQL migration and API drills**

On a disposable PostgreSQL database:

1. migrate legacy schema to head;
2. verify legacy rows are current with unspecified provenance;
3. create, revise, search current, search as-of, archive, restore;
4. page the change feed from sequence `0`;
5. run concurrent stale revision and event-allocation tests;
6. downgrade and upgrade again.

Separately run the full SQLite model/API suite built with
`Base.metadata.create_all()`. Do not run `alembic upgrade` against SQLite.

Record sanitized command names, exit codes, row counts, sequences, and assertion summaries. Do not record content, API keys, project paths, or raw database dumps.

- [ ] **Step 5: Run full verification**

```bash
.venv313/bin/pytest
python3 scripts/lint_memory_query_inventory.py --check
python3 scripts/run_guarded_migration_drill.py --target head --fixture-profile temporal
python3 -m compileall app memorybank_sdk
git diff --check
git status --short
```

Expected: full suite passes and only intended implementation/evidence files remain.

- [ ] **Step 6: Commit**

```bash
git add app README.md README_RU.md docs WORKLOG.md tests/test_temporal_metrics.py
git commit -m "Document temporal memory readiness"
```

## Completion Gate

This plan is complete only when every current-memory consumer uses the central predicate, all semantic operations emit exactly one committed sequence event, out-of-order timestamps cannot skip events, revision races fail closed, migration drills pass on disposable databases, and the full suite is green. Production migration, API deployment, and caller rollout require a separate reviewed production package and explicit approval.
