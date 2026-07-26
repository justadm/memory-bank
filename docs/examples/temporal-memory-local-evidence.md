# Temporal Memory Local Evidence

Date: 2026-07-26

Scope: isolated branch and worktree, synthetic fixtures only.

Verified locally:

- SQLite tests create schema only through `Base.metadata.create_all()`.
- The complete unit/API suite covers provenance boundaries, temporal
  visibility, immutable revision chains, graph-link inheritance, archive and
  restore guards, semantic PATCH compatibility, import revision behavior,
  sequence cursors, metrics, connector lifecycle, and query-inventory lint.
- The guarded migration runner provisions an isolated PostgreSQL container
  with a generated synthetic URL, no exposed port, no persistent volume, no
  repository `.env`, and unconditional cleanup.
- PostgreSQL migration profile performs `0004 -> head -> 0004 -> head`, checks
  active and legacy-archived backfill, partial indexes, feed-state creation,
  single-successor race rejection, concurrent successor conflict handling,
  concurrent feed allocation, and sequence ordering with deliberately
  out-of-order timestamps.
- No production database, API write, deploy, rollout, project registration,
  repository import, or push is part of this evidence.

Production remains a separate approval-gated package.
