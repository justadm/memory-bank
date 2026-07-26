# MemLayer Temporal Memory API

## Current and historical reads

Current list, search, relevant context, duplicate checks, imports, graph nodes,
metrics, and project counts use one predicate:

```text
valid_from <= now
AND (valid_to IS NULL OR valid_to > now)
AND archived = false
```

Explicit `as_of` reads additionally require `history_available=true`. Legacy
rows that were already archived before migration have
`history_available=false` and fail closed for temporal history.

## Semantic writes

- `POST /memory` creates a current revision and one project change event.
- `POST /memory/{id}/revise` closes the current revision, creates one
  successor, inherits graph links, and emits one `revised` event.
- `POST /memory/{id}/archive` closes the current validity interval and emits
  one `archived` event.
- `POST /memory/{id}/restore` creates a successor from a historical source in
  the same chain, closes the current leaf when needed, and emits one
  `restored` event.
- `GET /memory/{id}/history` returns a tenant-authorized linear chain.
- `PATCH /memory/{id}` is a deprecated compatibility path that delegates to
  immutable revision with reason `legacy PATCH compatibility`.

Identity, validity, actor, archive state, usage counters, and service-owned
metadata are not client-writable through revision payloads.

## Change feed

`GET /memory/changes?project_id=...` returns committed events ordered by
`sequence`, independent of `occurred_at`. `cursor` and `after_sequence` are
exclusive. Signed cursors are bound to project, tenant, feed epoch, and a
non-negative checkpoint not beyond the committed high watermark.

Production startup requires a non-default
`MEMORY_CHANGE_CURSOR_SIGNING_KEY`.

## Connector boundary

`memlayer connect codex` installs only the reviewed project-local connector
artifacts. The connection manifest is untrusted input and is validated against
the released artifact registry before disconnect. `.env.memlayer`, snapshots,
offline queues, and the `.gitignore` guard remain preserved on disconnect.
