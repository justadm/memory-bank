# Codex Connector Dogfood Evidence

Date: 2026-07-25

This record contains only sanitized local synthetic-project evidence. No API key, response body, temporary path, repository content, or production identifier is included.

## Checks

- Dry-run `connect codex`: exit `0`; 20 planned actions; synthetic project remained unchanged.
- First local `connect codex --apply`: exit `0`; managed pack applied and manifest written.
- Reconnect `connect codex --apply`: exit `0`; 14 released artifacts adopted without conflict; user-owned and runtime files preserved.
- `doctor`: exit `0`; local connection detected; API reachability/read authorization were reported independently; live project identity was not claimed before registration; write verification remained `unknown`; the initial snapshot was reported stale.
- Manifest-less adoption: manifest removal was followed by a conflict-free dry-run and apply; released artifacts were recognized as adoptable.
- Safe disconnect: exit `0`; a user-owned environment value, a pending queue record, `.gitignore`, and unrelated `AGENTS.md` content remained; the manifest was removed.

## Boundary

All checks used a temporary synthetic project and local read-only health/auth checks only. No project registration, repository import, production API call, deployment, or production mutation was performed.
