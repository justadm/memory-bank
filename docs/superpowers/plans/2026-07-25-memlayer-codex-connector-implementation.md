# MemLayer Codex Connector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reversible, project-local, dry-run-first `memlayer connect codex` workflow with safe root-pack adoption, idempotent project registration, and read-only readiness diagnostics.

**Architecture:** A new `memlayer_connector` package owns the artifact registry, untrusted-manifest validation, adoption planning, filesystem apply/disconnect, and doctor checks. The existing root-pack installer becomes a compatibility wrapper over that package. Server-side project identity uses a dedicated binding table and idempotent resolve endpoint; no repository content is uploaded by connect.

**Tech Stack:** Python 3.11+, pathlib, dataclasses, Pydantic, FastAPI, SQLAlchemy, Alembic, httpx, pytest.

## Global Constraints

- Codex is the only supported agent in this release.
- Connect and disconnect are dry-run by default; filesystem changes require `--apply`.
- Project registration requires `--apply --register-project` and performs no repository import.
- No global Codex settings may be read or changed.
- `.memlayer/.env.memlayer` is user-owned: never read for adoption, hashed, overwritten, deleted, or seeded from process environment.
- The manifest is untrusted input; only canonical allowlisted relative paths below the project root may be touched.
- Existing runtime snapshots, queues, and logs are preserved during disconnect.
- Existing root-pack adoption must finish a complete read-only inventory before the first write.
- No production deployment belongs to this plan.

---

### Task 1: Define the Connector Artifact Registry

**Files:**
- Create: `memlayer_connector/__init__.py`
- Create: `memlayer_connector/artifacts.py`
- Create: `templates/project_root_pack/memlayer_skill.md.tmpl`
- Test: `tests/test_connector_artifacts.py`

**Interfaces:**
- Produces: `OwnershipMode`, `ArtifactSpec`, `RenderContext`, `artifact_registry()`, `render_artifact()`.
- Consumes: existing templates under `templates/project_root_pack/`.

- [ ] **Step 1: Write failing registry coverage tests**

```python
from pathlib import PurePosixPath

from memlayer_connector.artifacts import OwnershipMode, RenderContext, artifact_registry


def test_codex_registry_covers_every_connector_artifact(tmp_path):
    context = RenderContext(
        project_name="demo",
        project_root=tmp_path,
        preferred_url="https://api.memlayer.ru",
        local_url="http://127.0.0.1:18100",
        human_url="https://api.memlayer.ru",
    )
    registry = artifact_registry(agent="codex", root_pack_version=1, context=context)

    assert PurePosixPath("AGENTS.md") in registry
    assert registry[PurePosixPath("AGENTS.md")].ownership is OwnershipMode.MANAGED_SECTION
    assert registry[PurePosixPath(".memlayer/.env.memlayer")].ownership is OwnershipMode.USER_OWNED
    assert registry[PurePosixPath(".memlayer/memlayer.offline.queue.jsonl")].ownership is OwnershipMode.CREATE_IF_ABSENT
    assert PurePosixPath(".agents/skills/memlayer/SKILL.md") in registry
    assert all(not path.is_absolute() and ".." not in path.parts for path in registry)
```

- [ ] **Step 2: Run the test and confirm the missing module failure**

Run:

```bash
.venv313/bin/pytest tests/test_connector_artifacts.py -q
```

Expected: collection fails because `memlayer_connector.artifacts` does not exist.

- [ ] **Step 3: Implement the typed registry**

Add these public definitions:

```python
class OwnershipMode(str, Enum):
    MANAGED_SECTION = "managed_section"
    MANAGED_LINE = "managed_line"
    WHOLE_FILE = "whole_file"
    MANAGED_KEYS = "managed_keys"
    CREATE_IF_ABSENT = "create_if_absent"
    USER_OWNED = "user_owned"


@dataclass(frozen=True)
class RenderContext:
    project_name: str
    project_root: Path
    preferred_url: str
    local_url: str
    human_url: str


@dataclass(frozen=True)
class ArtifactSpec:
    path: PurePosixPath
    ownership: OwnershipMode
    template_name: str | None
    executable: bool = False
    managed_keys: tuple[str, ...] = ()
    preserve_on_disconnect: bool = False
    expected_sha256: str | None = None
```

`artifact_registry()` must return the complete ownership matrix from the design. `render_artifact()` must render bytes deterministically and must raise `ValueError` for unsupported agent/version combinations.
`expected_sha256` is computed from the managed bytes rendered for the validated
context; it is `None` for user-owned and create-if-absent runtime artifacts.

- [ ] **Step 4: Add deterministic hash and historical-release tests**

```python
def test_registry_expected_hashes_are_deterministic_for_same_context(tmp_path):
    context = make_context(tmp_path)
    first = artifact_registry("codex", 1, context)
    second = artifact_registry("codex", 1, context)

    assert {
        path: spec.expected_sha256 for path, spec in first.items()
    } == {
        path: spec.expected_sha256 for path, spec in second.items()
    }
```

Keep versioned released template bytes or template identifiers keyed by
`(agent, root_pack_version, path)`. Render current and prior released templates
with the same validated `RenderContext`, then compute `expected_sha256`.
Project-specific values therefore change the rendered hash without weakening
historical-template matching. Never compare a dynamic artifact against a
single project-independent rendered hash.

- [ ] **Step 5: Run focused and existing root-pack tests**

Run:

```bash
.venv313/bin/pytest tests/test_connector_artifacts.py tests/test_project_root_pack.py -q
```

Expected: both files pass.

- [ ] **Step 6: Commit**

```bash
git add memlayer_connector templates/project_root_pack/memlayer_skill.md.tmpl tests/test_connector_artifacts.py
git commit -m "Add Codex connector artifact registry"
```

### Task 2: Validate Untrusted Manifests and Project Paths

**Files:**
- Create: `memlayer_connector/manifest.py`
- Test: `tests/test_connector_manifest.py`

**Interfaces:**
- Consumes: `ArtifactSpec` registry from Task 1.
- Produces: `ManifestRecord`, `ConnectionManifest`, `load_validated_manifest()`, `safe_project_path()`, `write_manifest_atomic()`.

- [ ] **Step 1: Write path-escape and ownership-forgery tests**

```python
@pytest.mark.parametrize("unsafe", ["/etc/passwd", "../AGENTS.md", ".", "", "a\\b"])
def test_manifest_rejects_unsafe_paths(tmp_path, unsafe):
    payload = valid_manifest_payload(tmp_path)
    payload["managed_files"][0]["path"] = unsafe

    with pytest.raises(ManifestConflict):
        validate_manifest(payload, project_root=tmp_path, registry=make_registry(tmp_path))


def test_manifest_cannot_change_registry_ownership(tmp_path):
    payload = valid_manifest_payload(tmp_path)
    payload["managed_files"][0]["ownership"] = "whole_file"

    with pytest.raises(ManifestConflict, match="ownership"):
        validate_manifest(payload, project_root=tmp_path, registry=make_registry(tmp_path))
```

- [ ] **Step 2: Run the tests and confirm the missing API failure**

Run:

```bash
.venv313/bin/pytest tests/test_connector_manifest.py -q
```

Expected: import failure for `memlayer_connector.manifest`.

- [ ] **Step 3: Implement strict manifest models**

Use Pydantic with `extra="forbid"`:

```python
class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    ownership: OwnershipMode
    created_by_connector: bool
    content_sha256: str | None


class ConnectionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    agent: Literal["codex"]
    project_root: str
    connector_identity: UUID
    project_id: UUID | None
    root_pack_version: Literal[1]
    installed_at: datetime
    managed_files: list[ManifestRecord]
```

`safe_project_path()` must:

1. reject absolute, empty, dot, parent, backslash, NUL, duplicate, and non-registry paths;
2. compare canonical `project_root` with the CLI root;
3. use `lstat()` on existing components and reject symlinks;
4. ensure the resolved parent remains below the canonical root.

Validation must reconstruct ownership from the registry and reject missing or extra records.

- [ ] **Step 4: Add symlink and connector-identity tests**

```python
def test_manifest_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / ".memlayer").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ManifestConflict, match="symlink"):
        safe_project_path(tmp_path, PurePosixPath(".memlayer/MEMLAYER.md"), registry_paths())


def test_manifest_identity_must_match_config(tmp_path):
    manifest = make_manifest(tmp_path, connector_identity=uuid4())
    config = {"connector_identity": str(uuid4())}

    with pytest.raises(ManifestConflict, match="connector_identity"):
        validate_manifest_identity(manifest, config=config)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv313/bin/pytest tests/test_connector_manifest.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add memlayer_connector/manifest.py tests/test_connector_manifest.py
git commit -m "Validate connector manifests as untrusted input"
```

### Task 3: Plan Adoption, Connect, and Disconnect

**Files:**
- Create: `memlayer_connector/service.py`
- Test: `tests/test_connector_service.py`

**Interfaces:**
- Consumes: artifact registry and validated manifest.
- Produces: `ConnectorAction`, `ConnectorPlan`, `ConnectorService.plan_connect()`, `apply_connect()`, `plan_disconnect()`, `apply_disconnect()`.

- [ ] **Step 1: Write failing manifest-less adoption tests**

```python
def test_matching_manifestless_pack_is_adopted_without_rewrite(tmp_path):
    seed_current_pack(tmp_path)
    before = snapshot_bytes(tmp_path)

    plan = connector_service(tmp_path).plan_connect()

    assert plan.conflicts == []
    assert any(action.kind == "adopt" for action in plan.actions)
    assert snapshot_bytes(tmp_path) == before


def test_unknown_managed_block_fails_before_any_write(tmp_path):
    (tmp_path / "AGENTS.md").write_text(
        "<!-- MEMLAYER_ROOT_PACK:START -->\nuser content\n"
        "<!-- MEMLAYER_ROOT_PACK:END -->\n",
        encoding="utf-8",
    )

    plan = connector_service(tmp_path).plan_connect()

    assert plan.ready is False
    assert plan.conflicts[0].code == "unknown_managed_section"
```

- [ ] **Step 2: Run the tests and confirm the missing service failure**

Run:

```bash
.venv313/bin/pytest tests/test_connector_service.py -q
```

Expected: import failure for `memlayer_connector.service`.

- [ ] **Step 3: Implement plan-only inventory**

Public action types:

```python
ActionKind = Literal[
    "create", "adopt", "upgrade", "update_managed_section",
    "update_managed_keys", "preserve", "remove", "conflict"
]


@dataclass(frozen=True)
class ConnectorAction:
    kind: ActionKind
    path: str
    ownership: OwnershipMode
    reason: str


@dataclass(frozen=True)
class ConnectorPlan:
    operation: Literal["connect", "disconnect"]
    project_root: str
    actions: tuple[ConnectorAction, ...]
    conflicts: tuple[ConnectorConflict, ...]

    @property
    def ready(self) -> bool:
        return not self.conflicts
```

Inventory all registry paths before producing a writable plan. Existing whole files and managed sections must match current or historical released hashes. Existing runtime state is preserved and adopted as unowned. Malformed sentinels or unknown content create conflicts.

- [ ] **Step 4: Implement atomic apply**

`apply_connect(plan)` must reject non-ready or stale plans, write temporary files in the same directory, `fsync`, replace atomically, set executable modes, and write the manifest last. On failure, restore prior bytes for files changed in this apply and report unresolved rollback paths.

`apply_disconnect(plan)` must recalculate safe paths and registry hashes, preserve `.env.memlayer`, runtime files, and `.gitignore`, remove only unchanged connector-exclusive templates or the unchanged managed `AGENTS.md` section, then remove the manifest last.

- [ ] **Step 5: Add stale-plan and preserve-on-disconnect tests**

```python
def test_apply_rejects_file_changed_after_plan(tmp_path):
    service = connector_service(tmp_path)
    plan = service.plan_connect()
    (tmp_path / "AGENTS.md").write_text("changed after plan\n", encoding="utf-8")

    with pytest.raises(ConnectorConflict, match="stale"):
        service.apply_connect(plan)


def test_disconnect_preserves_runtime_and_env(tmp_path):
    service = connected_project(tmp_path)
    queue = tmp_path / ".memlayer/memlayer.offline.queue.jsonl"
    env = tmp_path / ".memlayer/.env.memlayer"
    queue.write_text('{"pending":true}\n', encoding="utf-8")
    env.write_text("MEMORYBANK_API_KEY=secret\n", encoding="utf-8")

    service.apply_disconnect(service.plan_disconnect())

    assert queue.exists()
    assert env.read_text(encoding="utf-8") == "MEMORYBANK_API_KEY=secret\n"
```

- [ ] **Step 6: Run connector tests**

Run:

```bash
.venv313/bin/pytest tests/test_connector_artifacts.py tests/test_connector_manifest.py tests/test_connector_service.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add memlayer_connector/service.py tests/test_connector_service.py
git commit -m "Add safe root-pack adoption and disconnect"
```

### Task 4: Add Idempotent Project Registration

**Files:**
- Create: `app/models/project_connector_identity.py`
- Create: `alembic/versions/20260725_0005_project_connector_identity.py`
- Create: `deploy/test/docker-compose.migration.yml`
- Create: `scripts/run_guarded_migration_drill.py`
- Create: `app/services/project_connector_service.py`
- Modify: `app/models/__init__.py`
- Modify: `app/repositories/project_repository.py`
- Modify: `app/schemas/projects.py`
- Modify: `app/routers/projects.py`
- Modify: `app/services/memory_service.py`
- Test: `tests/test_api.py`
- Test: `tests/test_migration_drill_guard.py`

**Interfaces:**
- Produces: `ProjectResolveRequest`, `ProjectResolveResponse`, `ProjectConnectorService.resolve()`, `POST /projects/resolve`.
- Consumes: existing authentication and tenant-resolution functions.

- [ ] **Step 1: Write failing API idempotency and tenant tests**

```python
def test_project_resolve_is_idempotent(client):
    payload = {
        "agent": "codex",
        "connector_identity": "d8399b69-82ff-46ec-8e03-1930f1c84735",
        "project_name": "demo",
    }

    first = client.post("/projects/resolve", json=payload)
    second = client.post("/projects/resolve", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["project_id"] == second.json()["project_id"]


def test_project_resolve_rejects_ambiguous_name(client):
    create_project(client, name="demo")
    response = client.post("/projects/resolve", json=resolve_payload(name="demo"))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "existing_project_requires_explicit_id"
```

- [ ] **Step 2: Run targeted tests and confirm 404**

Run:

```bash
.venv313/bin/pytest tests/test_api.py -k "project_resolve" -q
```

Expected: endpoint tests fail with 404.

- [ ] **Step 3: Add binding model and migration**

Model fields:

```python
class ProjectConnectorIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_connector_identities"
    __table_args__ = (
        UniqueConstraint(
            "agent", "normalized_tenant_key", "connector_identity",
            name="uq_project_connector_identity",
        ),
    )

    agent: Mapped[str]
    normalized_tenant_key: Mapped[str]
    connector_identity: Mapped[uuid.UUID]
    project_id: Mapped[uuid.UUID]
```

Migration `20260725_0005` creates the table, unique constraint, project foreign key with `CASCADE`, and an index on `project_id`.

- [ ] **Step 4: Implement transactional resolve**

```python
def resolve(
    self,
    payload: ProjectResolveRequest,
    *,
    principal: AuthPrincipal,
) -> tuple[ProjectConnectorIdentity, Literal["created", "resolved", "bound_existing"]]:
    ...
```

Resolve tenant through `resolve_tenant_for_create()`. Normalize global scope to
`__global__`. Never auto-bind a same-name project. Explicit
`existing_project_id` must pass tenant authorization.

Create the binding inside `Session.begin_nested()` and flush inside that
savepoint. On the unique-race `IntegrityError`, roll back only the nested
transaction, expire the failed pending objects, and reselect the winner in the
still-usable outer transaction. Do not query through a failed session and do
not roll back unrelated work owned by the caller. Add a test that forces the
losing flush and proves the subsequent read succeeds without
`PendingRollbackError`.

```python
try:
    with self.repository.db.begin_nested():
        project, binding = self._create_project_and_binding(...)
        self.repository.db.flush()
except IntegrityError:
    self.repository.db.expire_all()
    binding = self.repository.get_connector_binding(...)
    if binding is None:
        raise
```

Both project and binding creation belong to the savepoint so the losing race
cannot leave an orphan project.

- [ ] **Step 5: Freeze tenant scope after first binding or memory**

Update `ProjectService.update_project()` so a changed `tenant_id` returns `409 project_tenant_scope_locked` when the project has either a connector binding or at least one memory entry.

- [ ] **Step 6: Add the guarded migration runner**

`scripts/run_guarded_migration_drill.py` accepts only a repository migration
target and fixture profile. It must not accept a database URL. It generates a
unique Compose project name and synthetic database credentials, starts
`deploy/test/docker-compose.migration.yml` without published ports or
persistent volumes, runs Alembic and assertions inside the isolated network,
and executes `down --volumes --remove-orphans` from `finally`, including on
timeout or failed assertions.

Tests mock the subprocess boundary and prove:

- external database URL flags and environment overrides are rejected;
- compose project and database names carry a random
  `memlayer_migration_drill_` prefix;
- cleanup runs after success, migration failure, timeout, and interruption;
- connector profile performs `base -> 20260725_0005 -> 20260429_0004 ->
  20260725_0005`;
- no production `.env` file or configured `DATABASE_URL` is read.

- [ ] **Step 7: Run API and guarded migration tests**

Run:

```bash
.venv313/bin/pytest tests/test_api.py -k "project_resolve or tenant_scope_locked" -q
python3 scripts/run_guarded_migration_drill.py --target 20260725_0005 --fixture-profile connector
```

Expected: tests pass and the isolated PostgreSQL migration round trip succeeds.

- [ ] **Step 8: Commit**

```bash
git add app/models app/repositories/project_repository.py app/schemas/projects.py app/routers/projects.py app/services alembic/versions/20260725_0005_project_connector_identity.py deploy/test/docker-compose.migration.yml scripts/run_guarded_migration_drill.py tests/test_api.py tests/test_migration_drill_guard.py
git commit -m "Add idempotent connector project identity"
```

### Task 5: Add CLI and Registration Client

**Files:**
- Create: `memlayer_connector/client.py`
- Create: `memlayer_connector/cli.py`
- Create: `memlayer`
- Modify: `memorybank_sdk/client.py`
- Test: `tests/test_connector_cli.py`
- Test: `tests/test_sdk.py`

**Interfaces:**
- Consumes: `ConnectorService`, `POST /projects/resolve`.
- Produces: `memlayer connect codex`, `memlayer disconnect codex`, JSON/text summaries, `MemoryBankClient.resolve_project()`.

- [ ] **Step 1: Write failing dry-run and explicit-registration tests**

```python
def test_connect_is_dry_run_by_default(tmp_path, capsys):
    code = main(["connect", "codex", "--project-root", str(tmp_path), "--json"])

    assert code == 0
    assert not (tmp_path / ".memlayer").exists()
    assert json.loads(capsys.readouterr().out)["mode"] == "dry_run"


def test_register_requires_apply(tmp_path, capsys):
    code = main([
        "connect", "codex", "--project-root", str(tmp_path),
        "--register-project", "--json",
    ])

    assert code == 2
    assert "requires --apply" in capsys.readouterr().err
```

- [ ] **Step 2: Run targeted tests and confirm missing CLI**

Run:

```bash
.venv313/bin/pytest tests/test_connector_cli.py tests/test_sdk.py -q
```

Expected: connector CLI tests fail before implementation.

- [ ] **Step 3: Add SDK resolve method**

```python
def resolve_project(
    self,
    *,
    agent: Literal["codex"],
    connector_identity: str,
    project_name: str,
    tenant_id: str | None = None,
    existing_project_id: str | None = None,
) -> dict[str, Any]:
    return self._request("POST", "/projects/resolve", json={...})
```

- [ ] **Step 4: Implement CLI parsing and execution**

The top-level `memlayer` file is an executable Python launcher that calls `memlayer_connector.cli.main()`. `--json` output contains `status`, `mode`, `operation`, `project_root`, `actions`, `conflicts`, and readiness or registration data.

Registration flow:

1. apply local connector plan;
2. read API key only inside the narrow client boundary;
3. call resolve with manifest connector identity;
4. read back `GET /projects/{id}`;
5. atomically update identity keys in config and manifest;
6. store a sanitized successful write-check summary.

- [ ] **Step 5: Test timeout retry identity reuse and no import**

```python
def test_registration_retry_reuses_connector_identity(tmp_path, fake_client):
    fake_client.resolve_side_effects = [TimeoutError(), {"project_id": PROJECT_ID}]

    result = run_connect_apply_register(tmp_path, fake_client)

    assert fake_client.connector_identities == [result.connector_identity] * 2
    assert fake_client.import_calls == []
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv313/bin/pytest tests/test_connector_cli.py tests/test_sdk.py tests/test_api.py -k "connector or project_resolve" -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add memlayer memlayer_connector/cli.py memlayer_connector/client.py memorybank_sdk/client.py tests/test_connector_cli.py tests/test_sdk.py
git commit -m "Add MemLayer Codex connector CLI"
```

### Task 6: Implement Read-Only Doctor

**Files:**
- Create: `memlayer_connector/doctor.py`
- Modify: `memlayer_connector/cli.py`
- Test: `tests/test_connector_doctor.py`

**Interfaces:**
- Produces: `DoctorReport`, `DoctorService.check()`, `memlayer doctor`.
- Consumes: validated manifest, artifact registry, config, API health/auth/project read-back.

- [ ] **Step 1: Write failing readiness-separation tests**

```python
def test_write_scope_is_authorized_not_verified(tmp_path, fake_api):
    fake_api.health_result = {"status": "ok"}
    fake_api.auth_result = {"authenticated": True, "scopes": ["read", "write"]}
    fake_api.project_result = {"id": PROJECT_ID}

    report = doctor(tmp_path, fake_api).check()

    assert report.api_reachable is True
    assert report.live_read_authorized is True
    assert report.live_read_verified is True
    assert report.live_write_authorized is True
    assert report.live_write_verified == "unknown"
```

- [ ] **Step 2: Run and confirm missing doctor**

Run:

```bash
.venv313/bin/pytest tests/test_connector_doctor.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement independent readiness dimensions**

```python
@dataclass(frozen=True)
class DoctorReport:
    local_connected: bool
    live_identity_ready: bool
    api_reachable: bool
    auth_authenticated: bool
    live_read_authorized: bool
    live_read_verified: bool
    live_write_authorized: bool
    live_write_verified: Literal["true", "false", "unknown"]
    snapshot_ready: bool
    queue_pending: int
    findings: tuple[DoctorFinding, ...]
```

Doctor must never invoke a write method. A fresh successful write-check must be at most 24 hours old and its target GET must succeed before `true`. A fresh failed check without a later success is `false`.

- [ ] **Step 4: Add invalid manifest, stale snapshot, queue, and redaction tests**

Assert that doctor reports each independently and that serialized output never contains API-key values, env contents, memory payloads, or response bodies.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv313/bin/pytest tests/test_connector_doctor.py tests/test_connector_manifest.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add memlayer_connector/doctor.py memlayer_connector/cli.py tests/test_connector_doctor.py
git commit -m "Add read-only MemLayer connector doctor"
```

### Task 7: Route Existing Root-Pack Callers Through Connector Mode

**Files:**
- Modify: `scripts/install_memlayer_project_pack.py`
- Modify: `scripts/onboard_memlayer_project.py`
- Modify: `tests/test_project_root_pack.py`
- Modify: `tests/test_onboard_memlayer_project.py`
- Modify: `README.md`
- Modify: `README_RU.md`

**Interfaces:**
- Consumes: connector artifact registry and service.
- Produces: compatibility wrapper preserving current script arguments while using secret-neutral planning for connector calls.

- [ ] **Step 1: Add regression tests for secret-neutral connector mode**

```python
def test_connector_mode_does_not_seed_environment_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMORYBANK_API_KEY", "must-not-be-copied")

    install_for_project(
        tmp_path,
        preferred_url=PRODUCTION_API_URL,
        local_url=LOCAL_API_URL,
        human_url=PRODUCTION_API_URL,
        dry_run=False,
        connector_mode=True,
    )

    assert "must-not-be-copied" not in (tmp_path / ".memlayer/.env.memlayer").read_text()
```

- [ ] **Step 2: Run the regression and confirm it fails**

Run:

```bash
.venv313/bin/pytest tests/test_project_root_pack.py -k "connector_mode" -q
```

Expected: failure because the argument and behavior do not exist.

- [ ] **Step 3: Refactor the installer**

Keep legacy explicit installer behavior compatible for existing callers, but make `connector_mode=True` delegate to `ConnectorService`. Remove direct file-write duplication from new connector paths. `onboard_memlayer_project.py` must not silently switch to connector registration or import semantics.

- [ ] **Step 4: Document commands and boundaries**

Document:

```text
./memlayer connect codex --project-root PATH
./memlayer connect codex --project-root PATH --apply
./memlayer connect codex --project-root PATH --apply --register-project
./memlayer doctor --project-root PATH
./memlayer disconnect codex --project-root PATH --apply
```

State explicitly that connect does not import repository content and that `.env.memlayer` remains user-owned.

- [ ] **Step 5: Run root-pack, onboarding, SDK, and full suites**

Run:

```bash
.venv313/bin/pytest tests/test_project_root_pack.py tests/test_onboard_memlayer_project.py tests/test_connector_cli.py tests/test_connector_doctor.py tests/test_sdk.py -q
.venv313/bin/pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/install_memlayer_project_pack.py scripts/onboard_memlayer_project.py tests/test_project_root_pack.py tests/test_onboard_memlayer_project.py README.md README_RU.md
git commit -m "Integrate connector with root-pack workflows"
```

### Task 8: Run Local Connector Dogfood and Prepare Review Evidence

**Files:**
- Create: `docs/examples/codex-connector-dogfood.md`
- Modify: `WORKLOG.md`

**Interfaces:**
- Consumes: completed connector CLI and local API.
- Produces: privacy-safe local evidence only.

- [ ] **Step 1: Create a temporary synthetic project**

Run:

```bash
project_root="$(mktemp -d)/connector-demo"
mkdir -p "$project_root"
printf '# Demo\n' > "$project_root/README.md"
./memlayer connect codex --project-root "$project_root" --json
```

Expected: dry-run JSON with no filesystem changes.

- [ ] **Step 2: Apply, reconnect, and run doctor**

Run:

```bash
./memlayer connect codex --project-root "$project_root" --apply --json
./memlayer connect codex --project-root "$project_root" --apply --json
./memlayer doctor --project-root "$project_root" --json
```

Expected: first apply creates managed artifacts, second apply is idempotent, and doctor separates local/live readiness.

- [ ] **Step 3: Exercise adoption and safe disconnect**

Remove only the generated manifest from the synthetic project, run dry-run connect to confirm adoption, restore by apply, add one queue record, and disconnect. Verify the queue, `.env.memlayer`, `.gitignore`, and unrelated `AGENTS.md` content remain.

- [ ] **Step 4: Record sanitized evidence**

`docs/examples/codex-connector-dogfood.md` records command names, exit codes, action counts, and file-preservation assertions. It contains no temporary absolute path, API key, response body, or repository content.

- [ ] **Step 5: Run final verification**

Run:

```bash
.venv313/bin/pytest
git diff --check
git status --short
```

Expected: suite passes, diff check succeeds, and only intended documentation changes remain.

- [ ] **Step 6: Commit**

```bash
git add docs/examples/codex-connector-dogfood.md WORKLOG.md
git commit -m "Document Codex connector dogfood evidence"
```

## Completion Gate

The connector plan is complete only when all eight task commits are green, a temporary-project dogfood proves adoption and preservation, and no production project or server was mutated. Production rollout requires a separate reviewed plan and explicit approval.
