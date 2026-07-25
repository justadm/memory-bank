# Temporal Memory Dogfood Evidence

Date: 2026-07-25

Sanitized local evidence from the isolated test database and synthetic API fixtures:

- Temporal schema migration `20260725_0006` upgraded legacy rows, created zero-history feed state, downgraded, and upgraded again on disposable SQLite state.
- Full API and model checks cover defaults, confidence/interval/successor constraints, provenance/evidence privacy boundaries, current versus as-of search, immutable revision history, archive/restore, and signed exclusive change cursors.
- Semantic revision closes the previous validity interval, creates one successor, and emits one revised event; operational reads do not claim write verification.
- No production database, deployment, external project, API key, repository payload, or customer data was used.
