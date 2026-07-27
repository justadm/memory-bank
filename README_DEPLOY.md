# Deployment Notes

Primary design spec:

- `docs/superpowers/specs/2026-05-26-memlayer-msk-deploy-design.md`

## MSK runtime target

- runtime root: `/opt/memlayer`
- API domain: `api.memlayer.ru`
- admin console domain: `adm.memlayer.ru`
- host API bind: `127.0.0.1:18120 -> 8000`

## Repository deploy artifacts

- env template: `deploy/msk/.env.example`
- compose file: `deploy/msk/docker-compose.yml`
- nginx sample vhosts:
  - `deploy/msk/nginx/memlayer.ru.conf`
  - `deploy/msk/nginx/api.memlayer.ru.conf`
  - `deploy/msk/nginx/adm.memlayer.ru.conf`
  - `deploy/msk/nginx/snippets/adm.memlayer.basic-auth.conf.example`
- public static site:
  - `deploy/msk/site/index.html`
  - `deploy/msk/site/api/index.html`
  - `deploy/msk/site/styles.css`
  - `deploy/msk/site/site.js`
- prep helper: `scripts/deploy_msk_prepare.sh`

## Expected server flow

1. Put repo checkout into `/opt/memlayer`
2. Create `/opt/memlayer/.env` from `deploy/msk/.env.example`
3. Build the exact committed revision through the archive-based release builder:

```bash
cd /opt/memlayer
export GIT_REVISION="$(git rev-parse HEAD)"
scripts/build_release_image.sh msk-api
```

Record the builder's `approved_image_id=sha256:...` output in the release
approval. Do not recompute or substitute that value during rollout.

Do not invoke Compose with its `--build` flag for a release. That bypasses the
clean Git archive boundary and does not provide an immutable image identity.

4. After release approval, deploy the verified candidate by immutable
`sha256` image ID:

```bash
export APPROVED_IMAGE_ID="sha256:<approved-image-id>"
scripts/rollout_release_image.sh \
  msk-api \
  "${GIT_REVISION}" \
  "${APPROVED_IMAGE_ID}"
```

The rollout script first proves the candidate tag still resolves to the
approval-bound image ID. It then creates and reads back a rollback tag for the
currently running image, deploys by immutable image ID, reads the running image
ID and OCI revision back from the container, checks health, and restores the
verified rollback image on failures or termination signals.

The base production Compose file intentionally defines neither `image` nor
`build` for the API service. It cannot start or replace that service by itself.
All approved API Compose operations must use
`scripts/run_release_compose.sh`, which rejects mutable image references and
creates a temporary override containing the validated immutable image ID.
The rollout supervisor takes one fixed host-local lock before its first Docker
inspection and holds it through candidate mutation, image/revision read-back,
health validation, and any rollback. Migration uses the same lock. Before
`migrate-head`, the entrypoint reads the running `memlayer-api` image ID and
fails unless it exactly matches the approved ID supplied by the operator.
The Compose wrapper records the mutation boundary immediately before candidate
replacement. Pre-boundary failures only clean up temporary state; post-boundary
failures restore the verified rollback image. Repeated handled signals cannot
interrupt rollback or release the lock before rollback verification finishes.
A failed rollback retains the lock and requires manual recovery before any
later release or migration.

### Stale release lock recovery

`SIGKILL`, host loss, or a forced shell termination can leave
`/tmp/memlayer-release-compose.lock`. Treat it as active until both conditions
are checked:

1. no `rollout_release_image.sh`, `run_release_compose.sh`, or migration
   process is running;
2. the PID encoded in the lock's `owner` file is not running.

Only after that read-only verification, and with explicit operational approval,
remove the `owner` file and then the empty lock directory. Never remove an
active lock to force a rollout.

### Trust boundary

The release scripts enforce the canonical operator workflow; they are not an
authorization boundary against the Unix account that already controls Docker.
That deployment account is trusted. A hostile or compromised Docker-authorized
process can always bypass shell wrappers with direct Docker commands. Preventing
that requires an OS-level boundary such as a restricted service, forced command,
or narrowly scoped privileged helper and is a separate rollout hardening step.

5. After separate migration approval, run migrations against the running image:

```bash
export RUNNING_IMAGE_ID="$(docker inspect --format '{{.Image}}' memlayer-api)"
scripts/run_release_compose.sh "${RUNNING_IMAGE_ID}" \
  migrate-head
```

6. Install nginx samples into:
- `/etc/nginx/sites-available/memlayer.ru`
- `/etc/nginx/sites-available/api.memlayer.ru`
- `/etc/nginx/sites-available/adm.memlayer.ru`

7. Enable them via symlink in `/etc/nginx/sites-enabled`
8. Run:

```bash
sudo nginx -t
sudo nginx -s reload
```

9. Verify:

```bash
curl -sS http://127.0.0.1:18120/health
curl -sS https://api.memlayer.ru/health
curl -sS https://adm.memlayer.ru/api/health
```

## Optional second auth layer for `adm.memlayer.ru`

Live `msk` status: enabled. Unauthenticated requests to `https://adm.memlayer.ru/` and `https://adm.memlayer.ru/api/health` should return `401`.

If you want an nginx-level barrier in front of the embedded admin console, prepare a Basic Auth file and snippet on `msk`:

```bash
cd /opt/memlayer
sudo ./scripts/prepare_msk_admin_basic_auth.sh opsadmin
```

This writes:

- `/etc/nginx/.htpasswd-memlayer-admin`
- `/etc/nginx/snippets/memlayer_adm_basic_auth.conf`

The htpasswd file must be readable by nginx workers. On Ubuntu nginx usually runs as `www-data`, so the expected file mode is:

```bash
sudo chgrp www-data /etc/nginx/.htpasswd-memlayer-admin
sudo chmod 640 /etc/nginx/.htpasswd-memlayer-admin
```

Then enable the auth barrier in `/etc/nginx/sites-available/adm.memlayer.ru`. For configs based on the current repository sample, uncomment this include:

```nginx
include /etc/nginx/snippets/memlayer_adm_basic_auth.conf;
```

For the current live `msk` vhost, the equivalent active lines are:

```nginx
auth_basic "MemLayer Admin";
auth_basic_user_file /etc/nginx/.htpasswd-memlayer-admin;
```

And reload nginx:

```bash
sudo nginx -t
sudo nginx -s reload
```
