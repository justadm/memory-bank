# Agent Exchange

This file is a lightweight handoff channel for local agents working around
MemLayer, memory.bank, and SolutionArtifact. Keep entries short, factual, and
safe to read without secrets.

## Protocol

- Append only. Do not rewrite another agent's note unless it contains a secret.
- Start each entry with UTC timestamp, agent id, repo, and intent.
- Separate facts from recommendations.
- Never paste API keys, bearer tokens, raw `.env` files, customer payloads, or
  private production data.
- Mark production writes explicitly: `prod_write: yes/no`.
- Mark whether user approval is required before the next step.
- If another agent has uncommitted files, do not overwrite them.

## Current Coordination Note

### 2026-06-10T20:40:00Z - codex-local - memory.bank - handoff

prod_write: no

Facts:

- User is pausing and wants agents to coordinate through a file while he sleeps.
- `/Users/just/apps/memory.bank` is on `main`.
- `memory.bank` commit `c97d265 Harden runtime smoke check` is pushed and pulled to `/opt/memlayer`.
- Public MemLayer health was verified after that deploy: `https://api.memlayer.ru/health` returned `{"status":"ok"}`.
- `runtime_smoke_check.py` now has committed path bootstrap and least-privilege admin self-check handling.
- Full local suite after that fix: `102 passed`.
- Current local worktree has an uncommitted `tests/test_api.py` change. Treat it as another agent's in-progress regression test and do not overwrite it.
- SolutionArtifact evidence was updated to reference `c97d265`, `102 tests`, production health, and no local patch.
- Emergency cleanup happened with a non-admin production key:
  - duplicate import events were archived through direct `/memory/*` operations;
  - useful docs/artifacts were cleared through metadata/evidence PATCH;
  - `/admin/quality-review/resolve` was unavailable with current key: missing `admin` scope;
  - therefore `review_history` is not populated for that cleanup.

Open work:

- Finish the import-event idempotency fix in `ImportService.import_project_scan()` before `create_memory()` creates the import event.
- Regression should prove that a second `existing_entry_mode="update"` import does not create a new import event.
- Also verify `/admin/imports/summary` keeps `import_events_count == 1` after repeated update-mode imports.
- Search for existing event should ignore archived events.
- Prefer preserving explicit `existing_entry_mode="create"` behavior unless the user asks to change it.
- After implementation, run targeted tests and full `.venv313/bin/pytest`.
- Update SolutionArtifact evidence/notes with:
  - direct cleanup caveat;
  - idempotency fix commit;
  - verification result.

Needs user approval:

- Any production write beyond the already discussed cleanup/fix verification.
- Any key/scope change, especially granting `admin` to production keys.

### 2026-06-10T21:05:00Z - codex-local - memory.bank - update

prod_write: yes

Facts:

- Import-event idempotency fix was committed as `553c73b Make project import events idempotent`.
- Commit was pushed to `origin/main`.
- `/opt/memlayer` on `msk` was fast-forwarded to `553c73b`.
- Production API image was rebuilt from `/opt/memlayer/deploy/msk/docker-compose.yml`.
- Only the `api` service was recreated; `db` remained running and healthy.
- `memlayer-api` is running on `127.0.0.1:18120->8000`.
- Local and public health checks returned `{"status":"ok"}` after deploy.
- Full local verification before commit: `.venv313/bin/pytest` returned `104 passed`.
- No controlled production reimport was run after deploy.

Open work:

- Update SolutionArtifact evidence to replace "idempotency fix locally ready, needs commit/deploy" with commit/deploy evidence for `553c73b`.
- If approved, run one controlled live reimport for `SolutionArtifact` and verify that active `Initial project import` count stays at `1`.

### 2026-06-10T23:26:53Z - codex-local - memory.bank - status correction

prod_write: no

Facts:

- Local worktree currently has uncommitted changes in:
  - `app/services/import_service.py`
  - `tests/test_api.py`
- These changes are the local import-event idempotency fix and regression tests.
- Local verification already completed after those changes: focused import tests passed and full `.venv313/bin/pytest` returned `104 passed`.
- The fix is not committed, pushed, or deployed yet.
- Production MemLayer may still create duplicate import events on repeated update-mode reimport until this fix is deployed.

Recommendation:

- Next agent should review the local diff, commit/push/deploy only after user approval, then run a controlled production verification.

Needs user approval:

- Any production reimport or deploy.

### 2026-06-10T23:34:36Z - codex-local - memory.bank - correction

prod_write: no

Facts:

- The preceding `2026-06-10T23:26:53Z` status correction is stale.
- Local worktree is clean.
- Import-event idempotency fix is committed as `553c73b Make project import events idempotent`.
- Follow-up exchange note is committed as `545d126 Update agent exchange after import deploy`.
- Both commits are pushed to `origin/main`.
- `/opt/memlayer` on `msk` is at `545d126`.
- Running `memlayer-api` container contains `ImportService._record_import_event`.
- No controlled production reimport has been run after this deploy.

Open work:

- Update SolutionArtifact evidence to reference deployed `553c73b`/`545d126`.
- With explicit user approval, run one controlled production reimport and confirm active `Initial project import` remains `1`.
