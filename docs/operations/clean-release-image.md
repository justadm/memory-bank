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

## Rollout Boundary

After approval:

```bash
REVISION="$(git rev-parse HEAD)"
scripts/rollout_release_image.sh msk-api "${REVISION}"
```

The rollout resolves the candidate to its immutable `sha256` image ID. Before
changing the container, it captures the current image ID and revision, creates
`msk-api:rollback-<revision>`, verifies that rollback image with the same
revision/sensitive-path checks as the candidate, and reads the tag back to
prove it resolves to the captured image. Compose receives the candidate image
ID through `MEMLAYER_API_IMAGE`; mutable tags are not used as runtime identity.

After startup, the script reads back both the running container image ID and
the OCI revision label, then checks health. A mismatch or failed health check
causes an automatic rollout of the verified rollback image and a second
digest/revision/health read-back.

Secret rotation and deletion of older images are separate destructive/security
actions and require separate approval.
