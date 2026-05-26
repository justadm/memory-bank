# MemLayer MSK Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare this repository and deploy MemLayer on `msk` as an isolated stack behind `api.memlayer.ru` and `adm.memlayer.ru`.

**Architecture:** Keep one FastAPI runtime and one PostgreSQL service inside a dedicated Docker Compose stack rooted at `/opt/memlayer`, expose only `127.0.0.1:18120 -> 8000`, and terminate TLS plus host routing in the shared host nginx on `msk`.

**Tech Stack:** FastAPI, PostgreSQL 16, Docker Compose, host nginx, certbot, API-key auth.

---

### Task 1: Add deploy-ready repository artifacts

**Files:**
- Create: `deploy/msk/.env.example`
- Create: `deploy/msk/docker-compose.yml`
- Create: `deploy/msk/nginx/api.memlayer.ru.conf`
- Create: `deploy/msk/nginx/adm.memlayer.ru.conf`
- Create: `scripts/deploy_msk_prepare.sh`
- Modify: `README_DEPLOY.md`
- Modify: `WORKLOG.md`

- [ ] **Step 1: Create production env template**

Add `deploy/msk/.env.example` with production-safe placeholders for API host port, DB credentials, auth keys, and public URLs.

- [ ] **Step 2: Create MSK production compose**

Add `deploy/msk/docker-compose.yml` that:
- binds API to `127.0.0.1:${HOST_API_PORT:-18120}:8000`
- omits any DB host publish
- keeps DB on internal network only
- uses restart policy for both services

- [ ] **Step 3: Add nginx vhost samples**

Create:
- `deploy/msk/nginx/api.memlayer.ru.conf`
- `deploy/msk/nginx/adm.memlayer.ru.conf`

Requirements:
- `api.memlayer.ru` proxies to `127.0.0.1:18120`
- `adm.memlayer.ru` proxies to `127.0.0.1:18120`
- admin vhost includes optional Basic Auth example
- `/api/*` on admin host routes to same backend

- [ ] **Step 4: Add deploy-prep helper**

Create `scripts/deploy_msk_prepare.sh` to document or automate:
- creating `/opt/memlayer`
- copying env template
- copying nginx samples
- expected local verification commands

- [ ] **Step 5: Update deploy docs**

Extend `README_DEPLOY.md` with:
- target domains
- expected root path `/opt/memlayer`
- file list to copy
- exact compose commands
- nginx install locations on `msk`

- [ ] **Step 6: Commit**

```bash
git add deploy/msk README_DEPLOY.md scripts/deploy_msk_prepare.sh WORKLOG.md
git commit -m "Add MSK deployment assets"
```

### Task 2: Validate deploy artifacts locally

**Files:**
- Modify: `tests/test_api.py` if needed
- Modify: `WORKLOG.md`

- [ ] **Step 1: Validate sample configs are syntactically sane**

Run:

```bash
python - <<'PY'
from pathlib import Path
for path in [
    Path("deploy/msk/.env.example"),
    Path("deploy/msk/docker-compose.override.yml"),
    Path("deploy/msk/nginx/api.memlayer.ru.conf"),
    Path("deploy/msk/nginx/adm.memlayer.ru.conf"),
]:
    assert path.exists(), path
print("deploy artifacts present")
PY
```

Expected: `deploy artifacts present`

- [ ] **Step 2: Validate existing app tests still pass**

Run:

```bash
.venv313/bin/pytest
```

Expected: full suite passes

- [ ] **Step 3: Commit doc/test fallout if needed**

```bash
git add WORKLOG.md tests/test_api.py
git commit -m "Validate MSK deployment assets"
```

### Task 3: Provision runtime on `msk`

**Files:**
- Remote create: `/opt/memlayer`
- Remote create: `/opt/memlayer/.env`
- Remote copy: repo checkout or git clone
- Remote copy: nginx samples into staging path

- [ ] **Step 1: Create runtime root on server**

Run:

```bash
ssh msk "sudo mkdir -p /opt/memlayer && sudo chown -R opsadmin:opsadmin /opt/memlayer"
```

Expected: command succeeds

- [ ] **Step 2: Place repository on server**

Preferred:

```bash
ssh msk "git clone git@github.com:justadm/memory-bank.git /opt/memlayer || true"
ssh msk "cd /opt/memlayer && git fetch --all && git checkout main && git pull --ff-only"
```

Expected: current repo content present in `/opt/memlayer`

- [ ] **Step 3: Create production env**

Create `/opt/memlayer/.env` from `deploy/msk/.env.example` with real:
- DB credentials
- auth keys
- public URLs
- `APP_ENV=production`

- [ ] **Step 4: Copy deploy artifacts into place**

Copy or reference:
- compose override
- nginx sample configs

- [ ] **Step 5: Verify remote files**

Run:

```bash
ssh msk "cd /opt/memlayer && ls -lah && sed -n '1,120p' .env"
```

Expected: files present; secrets visually confirmed without printing them into logs more than necessary

### Task 4: Start stack and migrate

**Files:**
- Remote use: `/opt/memlayer/deploy/msk/docker-compose.yml`

- [ ] **Step 1: Start stack**

Run:

```bash
ssh msk "cd /opt/memlayer && docker compose --env-file .env -f deploy/msk/docker-compose.yml up -d --build"
```

Expected: `memlayer-api` and `memlayer-db` start

- [ ] **Step 2: Run migrations**

Run:

```bash
ssh msk "cd /opt/memlayer && docker compose --env-file .env -f deploy/msk/docker-compose.yml exec -T api alembic upgrade head"
```

Expected: migration reaches `head`

- [ ] **Step 3: Verify local runtime**

Run:

```bash
ssh msk "curl -sS http://127.0.0.1:18120/health && echo && curl -sS http://127.0.0.1:18120/openapi.json >/dev/null && echo openapi_ok"
```

Expected:
- `{"status":"ok"}`
- `openapi_ok`

### Task 5: Install nginx vhosts and verify public access

**Files:**
- Remote modify: `/etc/nginx/sites-available/api.memlayer.ru`
- Remote modify: `/etc/nginx/sites-available/adm.memlayer.ru`
- Remote symlink: `/etc/nginx/sites-enabled/*`

- [ ] **Step 1: Install nginx configs**

Copy sample configs into `/etc/nginx/sites-available` and create symlinks in `/etc/nginx/sites-enabled`.

- [ ] **Step 2: Validate and reload nginx**

Run:

```bash
ssh msk "sudo nginx -t && sudo nginx -s reload"
```

Expected: syntax ok and reload successful

- [ ] **Step 3: Issue/refresh TLS**

Run certbot for:
- `api.memlayer.ru`
- `adm.memlayer.ru`

Expected: both hosts serve HTTPS

- [ ] **Step 4: Run public smoke checks**

Run:

```bash
curl -sS https://api.memlayer.ru/health
curl -sS https://adm.memlayer.ru/api/health
```

Expected: both return `{"status":"ok"}`

- [ ] **Step 5: Final manual smoke**

Verify:
- `adm.memlayer.ru` console loads
- API key auth works
- admin runtime self-check works

- [ ] **Step 6: Commit runtime/deploy docs fallout**

```bash
git add README_DEPLOY.md WORKLOG.md
git commit -m "Document live MSK deployment"
```
