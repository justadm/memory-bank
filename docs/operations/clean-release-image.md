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
`git archive`, builds for `${TARGET_PLATFORM:-linux/amd64}`, and runs the
mandatory verifier against `msk-api:<revision>-candidate`. It never writes the
mutable `latest` tag. The verifier fails unless the OCI revision label matches
and both `/app/.env` and `/app/backups` are absent.

## Rollout Boundary

After approval:

```bash
REVISION="$(git rev-parse HEAD)"
docker tag "msk-api:${REVISION}-candidate" msk-api:latest
docker compose --env-file .env -f deploy/msk/docker-compose.yml \
  up -d --no-build --force-recreate --no-deps api
```

Secret rotation and deletion of older images are separate destructive/security
actions and require separate approval.
