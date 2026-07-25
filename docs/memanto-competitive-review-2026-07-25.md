# Memanto Competitive Review

Date: 2026-07-25

## Scope

This note records the product and engineering lessons from a source review of
`moorcheh-ai/memanto`. It is a competitive reference, not an adoption decision.

## Confirmed Strengths

Memanto packages long-term memory into a clear three-operation interface:

```text
remember -> persist a memory
recall   -> retrieve raw relevant memories
answer   -> synthesize an answer grounded in retrieved memory
```

Its strongest product advantage over the current MemLayer workflow is agent
onboarding. The `connect` layer has an agent registry, installs managed
instructions and skills, and can update or remove its own integration.

Other useful ideas:

- first-class provenance and confidence;
- temporal recall such as `as-of` and `changed-since`;
- explicit conflict handling and versioning;
- portable memory export/import;
- local and managed deployment profiles;
- a small, agent-friendly command surface.

## Important Boundaries

The Memanto repository is MIT licensed, but the on-prem retrieval engine is
delivered separately as `moorcheh/server:latest`. The server source and license
are not present in the Memanto repository. The local setup also uses an
embedding model through Ollama or a cloud embedding provider. Therefore the
claims "100% open source" and "no indexing pipeline" should not be treated as
verified properties of the complete runtime.

The generated agent instruction is intentionally aggressive: it requires
memory reads before work and proactive writes for every meaningful event. That
can improve adoption, but it can also produce write spam and encourage agents
to treat retrieved memory as truth.

MemLayer keeps the stricter boundary:

```text
Git, runtime, and authoritative APIs -> source of truth
MemLayer                            -> context, evidence, and retrieval
Agent                               -> must verify freshness and authority
```

## Accepted Product Direction

The first MemLayer adoption release will include:

- Codex-only project connector;
- project-local managed instructions and skill;
- connection manifest with safe update and uninstall behavior;
- dry-run by default;
- provenance and confidence as first-class memory fields;
- temporal validity and immutable semantic revisions;
- `as-of`, `changed-since`, and revision-history reads.

Deferred:

- Claude Code, Cursor, and other agent connectors;
- OKF export/import;
- replacing the MemLayer retrieval backend with Moorcheh.

## Reusable Lesson

Memanto should be treated primarily as an onboarding and workflow reference.
The immediate opportunity is not to replace MemLayer storage or retrieval. It
is to make MemLayer safer and easier to connect to a project while improving
the trustworthiness and temporal meaning of stored memory.
