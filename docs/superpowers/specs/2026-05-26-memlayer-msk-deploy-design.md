# MemLayer MSK Deployment Design

Дата: 2026-05-26

## Goal

Развернуть публичный MemLayer на `msk` как отдельный production-like contour с собственным Docker Compose stack, отдельным PostgreSQL и отдельными публичными доменами:

- `https://api.memlayer.ru` — API
- `https://adm.memlayer.ru` — admin console

Цель этого дизайна — получить изолированный runtime, который легко перенести на отдельный сервер позже, не смешивая MemLayer с уже перегруженным namespace `justgpt.ru`.

## Why This Shape

`justgpt.ru` уже используется как отдельный product ingress с MCP-path routing и control-plane semantics. Размещение MemLayer под этим namespace усложнит ownership, маршрутизацию и дальнейшую миграцию.

Поэтому целевой shape:

- отдельный product domain: `memlayer.ru`
- отдельный API subdomain: `api.memlayer.ru`
- отдельный admin subdomain: `adm.memlayer.ru`

Это даёт чистый public surface сейчас и не мешает вынести сервис на отдельную машину позже.

## Topology

### Host Layout

На `msk` MemLayer размещается как отдельный runtime root:

- `/opt/memlayer`

Внутри:

- git checkout репозитория `memory.bank`
- production `.env`
- `docker-compose.yml`
- локальный deploy/readme при необходимости

Рекомендованная структура:

```text
/opt/memlayer
  ├── .env
  ├── docker-compose.yml
  ├── README_DEPLOY.md
  ├── backups/
  └── <repo checkout>
```

### Containers

Минимальный stack:

- `memlayer-api`
- `memlayer-db`

Отдельный containerized nginx внутри stack не нужен. На `msk` уже есть устоявшийся host-nginx ingress pattern, и MemLayer лучше встроить в него как новый vhost contour.

### Published Ports

Публикуется только API-контур:

- `127.0.0.1:18120 -> 8000`

Контейнерный `8000` — это внутренний порт FastAPI/uvicorn, не внешний host port.

Проверка на `msk` показала, что host port `18120` на момент дизайна свободен.

PostgreSQL наружу не публикуется.

## Routing Model

### `api.memlayer.ru`

Host nginx проксирует:

- `https://api.memlayer.ru/*` -> `http://127.0.0.1:18120`

Никакой path rewriting не требуется.

### `adm.memlayer.ru`

Host nginx проксирует:

- `https://adm.memlayer.ru/*` -> `http://127.0.0.1:18120`

Admin console работает в root-hosted mode.

Ожидаемый UX:

- `https://adm.memlayer.ru/` — console
- `https://adm.memlayer.ru/projects`
- `https://adm.memlayer.ru/memory`
- `https://adm.memlayer.ru/review`
- `https://adm.memlayer.ru/settings`
- `https://adm.memlayer.ru/api/*` — same backend API

Один FastAPI runtime обслуживает и API, и embedded console.

## Security Model

### API Auth

`api.memlayer.ru` должен быть публично доступен по сети, но не анонимно.

Сразу включается:

- `AUTH_ENABLED=true`

И используются API keys.

Базовый набор ключей:

- `agent-write`: `read|write|import`
- `ops-admin`: `read|write|import|admin`

### Admin Console

`adm.memlayer.ru` не должен быть open-by-default.

Минимальный слой:

- API key внутри console

Рекомендованный дополнительный слой:

- Basic Auth на nginx для `adm.memlayer.ru`

Это даёт второй рубеж поверх application auth.

### Database Exposure

PostgreSQL:

- доступен только внутри docker network
- без host publish
- без прямого публичного ingress

### Secrets

Secrets живут только на сервере:

- `/opt/memlayer/.env`

Они не коммитятся в репозиторий.

## Runtime Configuration

Базовые production-параметры:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://<user>:<pass>@db:5432/<db>
HOST_API_PORT=18120
AUTH_ENABLED=true
AUTH_API_KEYS=<production keys>
MEMORYBANK_URL=https://api.memlayer.ru
```

Для `adm.memlayer.ru` frontend должен использовать same-origin `/api/*`, а не старый `memlayer.loc`.

## Operations

### Deploy Method

Deploy должен быть простым и rollback-friendly:

1. обновить checkout в `/opt/memlayer`
2. обновить `.env` при необходимости
3. `docker compose up -d --build`
4. применить миграции
5. выполнить smoke checks

Rollback:

- возврат к предыдущему commit SHA
- повторный `docker compose up -d --build`

### Health / Smoke

Минимальные runtime checks:

- `GET /health`
- `GET /openapi.json`
- `GET /admin/runtime/self-check`

Плюс прикладной smoke:

- create/read project
- create/read memory
- search
- admin-key self-check
- console login via API key

### Backups

Минимум для первого production-like выноса:

- регулярный `pg_dump`
- сохранение `.env`
- сохранение nginx vhost configs

Полноценная rotation policy и off-host backup не блокируют первый rollout, но должны стать следующим operational шагом.

## Domain Recommendation

Основной выбор:

- использовать `memlayer.ru` family

Итоговая схема:

- `memlayer.ru` — не обязателен для первого этапа
- `api.memlayer.ru` — production API
- `adm.memlayer.ru` — production admin console

На первом rollout можно вообще не публиковать `memlayer.ru`, если нет отдельной маркетинговой/landing задачи.

## Recommended Rollout Sequence

1. Создать runtime root `/opt/memlayer`
2. Разместить там checkout репозитория
3. Подготовить production `.env`
4. Проверить compose-конфигурацию для `HOST_API_PORT=18120`
5. Поднять stack через Docker
6. Применить миграции
7. Проверить local health на `127.0.0.1:18120`
8. Добавить nginx vhost для `api.memlayer.ru`
9. Добавить nginx vhost для `adm.memlayer.ru`
10. Проверить `nginx -t` и reload
11. Выпустить TLS certificates
12. Выполнить public smoke checks

## Risks

### 1. Public Exposure Without Auth

Если забыть включить `AUTH_ENABLED=true`, MemLayer выйдет наружу фактически открытым. Это unacceptable.

### 2. Domain Misbinding

Если console останется привязана к `memlayer.loc` или старому same-origin shape, `adm.memlayer.ru` будет partially broken. Перед deploy нужно проверить host/origin behavior.

### 3. Shared-Host Operational Drift

`msk` уже мультисервисный ingress host. Без явного runbook и фиксированного deploy path MemLayer быстро превратится в ещё один “unclear contour”.

Поэтому вместе с deploy нужно держать:

- deploy doc
- nginx sample configs
- runtime root convention

### 4. Missing Rate Limits / Backup Rotation

Для первого rollout это не блокер, но это первая очередь после запуска.

## Recommendation

Рекомендованная реализация:

- отдельный Compose stack в `/opt/memlayer`
- собственный Postgres
- host nginx как ingress
- `api.memlayer.ru` для API
- `adm.memlayer.ru` для console
- host port `127.0.0.1:18120`
- auth enabled from day one

Это даёт изоляцию, чистый ingress, минимальную сложность для `msk` и лёгкую последующую миграцию на отдельный сервер.
