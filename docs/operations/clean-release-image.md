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
ID through `MEMLAYER_API_IMAGE`; mutable tags are not used as runtime identity.

After startup, the script reads back both the running container image ID and
the OCI revision label, then checks health. A mismatch or failed health check
causes an automatic rollout of the verified rollback image and a second
digest/revision/health read-back. `HUP`, `INT`, `TERM`, and unexpected shell
exit after the mutation boundary use the same rollback path.

Secret rotation and deletion of older images are separate destructive/security
actions and require separate approval.
