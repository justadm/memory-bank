# Clean Release Image

Release images are built from an exact Git archive, not from the mutable working
tree. The Dockerfile pins the Python base image, requires a full Git revision
label, and copies only the committed archive filtered through `.dockerignore`.

## Preconditions

- The checkout is clean and at the approved Git revision.
- Package repositories are reachable from the build host.
- The existing API image has a rollback tag.

## Build

```bash
scripts/build_release_image.sh msk-api
```

The builder refuses a dirty worktree, exports the exact `HEAD` through
`git archive`, performs a no-cache build for
`${TARGET_PLATFORM:-linux/amd64}`, and runs the
mandatory verifier against `msk-api:<revision>-candidate`. It never writes the
mutable `latest` tag. The verifier fails unless the OCI revision label matches
and both `/app/.env` and `/app/backups` are absent.
Its final `approved_image_id=sha256:...` output is the immutable identity that
must be recorded in the release approval. The builder resolves that image ID
before verification, verifies the immutable ID itself, and then confirms the
candidate tag still resolves to the same ID before printing it.

## Rollout Boundary

After approval:

```bash
REVISION="$(git rev-parse HEAD)"
APPROVED_IMAGE_ID="sha256:<approved-image-id>"
scripts/rollout_release_image.sh \
  msk-api \
  "${REVISION}" \
  "${APPROVED_IMAGE_ID}"
```

The rollout rejects the candidate if its current tag no longer resolves to the
approval-bound image ID. Before changing the container, it captures the current
image ID and revision, creates
`msk-api:rollback-<revision>`, verifies that rollback image with the same
revision/sensitive-path checks as the candidate, and reads the tag back to
prove it resolves to the captured image. Compose receives the candidate image
ID through `scripts/run_release_compose.sh`. The base production Compose file
contains neither an API `image` nor an API `build` directive, so it cannot
replace the API service directly. The entrypoint accepts only a full
`sha256:...` image ID and writes that literal ID to a temporary, mode-0600
Compose override. The rollout supervisor takes a fixed host-local lock before
its first Docker interaction and holds it across candidate verification,
mutation, read-back, health validation, and automatic rollback.
The Compose wrapper creates a private mutation marker immediately before the
first candidate `compose up`. Failures before that marker use cleanup-only
handling and do not recreate the running API. Failures after it enter rollback.
Once rollback starts, handled `HUP`, `INT`, and `TERM` signals are ignored until
the rollback image, revision, and health have been read back and the lock can be
released safely. A failed rollback retains the lock and requires the documented
manual recovery procedure before any later release or migration.
`migrate-head` uses the same lock, reads `memlayer-api`'s current container
image ID, and rejects any mismatch before `exec`. A test-only lock path override
is accepted only when `MEMLAYER_RELEASE_TEST_MODE=1`; production ignores it.
The rollout helper additionally verifies that its immediate parent PID is the
supervisor PID recorded in the lock owner token, so the on-disk token is not a
replayable value for an unrelated process by accident. This is
defense-in-depth, not authorization against the trusted Docker deployment
account: that account can create its own parent process or invoke Docker
directly. Enforcing hostile same-user isolation requires an OS-level
service/forced-command/privilege boundary. The lock directory and owner file
use `0700`/`0600` permissions.

`SIGKILL` or host loss can leave a stale lock. Follow the read-only process/PID
checks in `README_DEPLOY.md` before an explicitly approved removal; never delete
the lock while a release or migration process is active.

After startup, the script reads back both the running container image ID and
the OCI revision label, then checks health. A mismatch or failed health check
causes an automatic rollout of the verified rollback image and a second
digest/revision/health read-back. `HUP`, `INT`, `TERM`, and unexpected shell
exit after the mutation boundary use the same rollback path.

Secret rotation and deletion of older images are separate destructive/security
actions and require separate approval.
