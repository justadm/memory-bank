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
3. Start stack:

```bash
cd /opt/memlayer
docker compose --env-file .env -f deploy/msk/docker-compose.yml up -d --build
docker compose --env-file .env -f deploy/msk/docker-compose.yml exec -T api alembic upgrade head
```

4. Install nginx samples into:
- `/etc/nginx/sites-available/memlayer.ru`
- `/etc/nginx/sites-available/api.memlayer.ru`
- `/etc/nginx/sites-available/adm.memlayer.ru`

5. Enable them via symlink in `/etc/nginx/sites-enabled`
6. Run:

```bash
sudo nginx -t
sudo nginx -s reload
```

7. Verify:

```bash
curl -sS http://127.0.0.1:18120/health
curl -sS https://api.memlayer.ru/health
curl -sS https://adm.memlayer.ru/api/health
```

## Optional second auth layer for `adm.memlayer.ru`

If you want an nginx-level barrier in front of the embedded admin console, prepare a Basic Auth file and snippet on `msk`:

```bash
cd /opt/memlayer
sudo ./scripts/prepare_msk_admin_basic_auth.sh opsadmin
```

This writes:

- `/etc/nginx/.htpasswd-memlayer-admin`
- `/etc/nginx/snippets/memlayer_adm_basic_auth.conf`

Then uncomment this line in `/etc/nginx/sites-available/adm.memlayer.ru`:

```nginx
include /etc/nginx/snippets/memlayer_adm_basic_auth.conf;
```

And reload nginx:

```bash
sudo nginx -t
sudo nginx -s reload
```
