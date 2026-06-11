# Revision Evidence Templates

MemLayer stores operational memory, but agents also need a small machine-readable contract for risky work. These templates define that contract without adding a new runtime dependency.

## Templates

- `revision_pass.v0` is the pre-action gate. Use it before deploys, reimports, cleanup, CRM writes, key/scope changes, or customer-data mutation.
- `post_action_evidence.v0` is the read-back record. Use it after the action to prove what changed, what did not change, what was verified, and where evidence was written.

## Files

- [docs/schemas/revision_pass.v0.schema.json](/Users/just/apps/memory.bank/docs/schemas/revision_pass.v0.schema.json)
- [docs/schemas/post_action_evidence.v0.schema.json](/Users/just/apps/memory.bank/docs/schemas/post_action_evidence.v0.schema.json)
- [docs/examples/revision_pass.v0.example.json](/Users/just/apps/memory.bank/docs/examples/revision_pass.v0.example.json)
- [docs/examples/post_action_evidence.v0.example.json](/Users/just/apps/memory.bank/docs/examples/post_action_evidence.v0.example.json)

## Agent Rules

1. For production writes, `approved_in_current_thread` must be true in the post-action evidence.
2. Do not include credentials, tokens, raw webhooks, raw customer payloads, or full private API responses.
3. Evidence should contain command labels, result summaries, counts, commit IDs, health checks, and read-back facts.
4. A `GO` revision decision must list allowed changes, forbidden changes, required verification, and rollback behavior.
5. A post-action record must state both what changed and what explicitly did not change.

## MemLayer Usage

Store completed template instances as `artifact` or `task_log` memory entries. Keep the schema version in both the JSON body and metadata so retrieval can filter by version:

```json
{
  "type": "artifact",
  "title": "Production reimport evidence",
  "content": "{...post_action_evidence.v0...}",
  "metadata": {
    "schema_version": "post_action_evidence.v0",
    "artifact": "local.agent.post_action_evidence.v0",
    "source": "agent"
  }
}
```

These contracts are intentionally local-first. A later API layer can validate them server-side, but agents can already use the examples as strict working shapes.
