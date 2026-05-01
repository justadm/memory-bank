# Memory Bank MVP

Простой сервис памяти для агентных сценариев на FastAPI и PostgreSQL.

## Что уже есть

- healthcheck `GET /health`
- CRUD для проектов
- CRUD для памяти, архивирование и листинг
- связи между записями и простой подграф
- поиск по памяти с PostgreSQL FTS и fallback для SQLite-тестов
- rebuild endpoint для `search_vector` и более полноценный PostgreSQL stored FTS runtime
- task logs и базовая eval/experiment analytics summary
- встроенный evaluator endpoint для rule-based оценки использования памяти
- встроенный metrics overview endpoint для observability без внешнего dashboard
- admin observability snapshot для быстрого production-style обзора состояния сервиса
- endpoint `POST /memory/relevant` с учётом usage/access logs
- maintenance endpoint для архивации устаревшей памяти
- опциональное auto-linking новых записей через bag-of-words similarity
- встроенный `memorybank_sdk` и пример memory-aware агента
- structured project import endpoint для первичного наполнения MemoryBank
- memory quality layer с hard gate для ручной записи и soft review для import flow
- decision authority hints и typed context builder для agent retrieval
- metadata-based conflict resolution flow for competing decisions
- lifecycle maintenance pass with dry-run support
- compaction preview/apply flow for summarizing stale low-value clusters
- operator review queues summary and console actions for conflicts/compaction
- local semantic duplicate detection in memory quality layer
- operator quality-review actions from API and console
- richer review/process metrics in `metrics/overview` and dashboard
- Docker, Alembic и базовые API-тесты

## Быстрый старт

1. Скопировать `.env.example` в `.env`.
2. Запустить `docker compose up --build`.
3. Применить миграции: `docker compose exec api alembic upgrade head`.
4. Открыть `http://localhost:18100/docs` для API или `http://localhost:18100/console/` для встроенной консоли MemLayer.

Для локальных агентов, CLI и automation wrapper-ов теперь рекомендуется:

- sandbox-friendly default: `http://127.0.0.1:18100`
- escalated or browser-friendly fallback: `https://memlayer.loc/api`

Встроенная консоль MemLayer уже умеет:
- работать с same-origin API по умолчанию
- хранить локальный API key
- показывать auth/scopes/tenant status через `GET /auth/me`
- управлять `tenant_id` у проектов
- переключать `lexical / semantic / hybrid` режимы memory search
- показывать import summaries через `GET /admin/imports/summary`
- синхронизировать разделы с URL внутри `/console/`, например `/console/projects` и `/console/memory`
- показывать graph pane выбранной memory entry через `GET /memory/{id}/graph`
- создавать и удалять links прямо из graph pane через `POST /memory-links` и `DELETE /memory-links/{id}`
- открывать связанные import projects из dashboard/review одним действием
- запускать inline reimport project scan из console через `POST /imports/reimport-project` для проектов с `metadata.source_path`
- делать bulk reimport по видимым imported projects прямо из console
- видеть summary результата последнего import/reimport прямо в UI
- редактировать `metadata` у memory entries при create/update

Для отдельного домена вроде `memlayer.loc` console теперь поддерживает root-hosted режим:
- пользовательские страницы могут быть красивыми, например `/`, `/projects`, `/memory`, `/review`, `/settings`
- в этом режиме frontend автоматически использует API через same-origin prefix `/api`
- внутренний `/console/*` namespace при этом остаётся полезным для embedded-режима внутри самого FastAPI приложения

Локальный nginx/vhost можно переключить так, чтобы:
- `https://memlayer.loc/` открывал console root
- `https://memlayer.loc/projects` и другие разделы были UI-маршрутами
- `https://memlayer.loc/api/*` проксировалось в backend API

`docker-compose.yml` уже содержит healthcheck для PostgreSQL, поэтому `api` стартует после готовности БД.

Для формальной локальной проверки API-тестов можно использовать:

```bash
docker compose exec api pytest
```

## Project Root Pack

Для внешних проектных репозиториев теперь есть готовый MemLayer root-pack, который можно положить в корень каждого проекта, чтобы локальные AI-агенты автоматически видели правила работы с общей памятью.

Состав pack:

- `AGENTS.md` — создаётся или безопасно дополняется managed-секцией MemLayer
- `MEMLAYER.md` — подробная инструкция для агента по read/write/import workflow
- `memlayer_api.sh` — локальный helper для чтения и записи в MemLayer с automatic fallback `localhost -> memlayer.loc`
- `memlayer_context.sh` — snapshot-first helper для pre-task чтения: сначала локальный snapshot, live MemLayer только по явному refresh
- `memlayer_watchdog.sh` — быстрый runtime-check для случаев после сна, ребута или flaky localhost-доступа
- `memlayer_recover.sh` — локальный recovery helper для рестарта dockerized MemLayer API из проектного корня
- `memlayer_snapshot_pull.sh` — выгружает локальный snapshot контекста из MemLayer в проектный корень
- `memlayer.snapshot.md` / `memlayer.snapshot.json` — offline-readable snapshot для sandboxed агентов
- `memlayer.offline.log.md` — локальный журнал несинхронизированного прогресса, если live MemLayer временно недоступен
- `.env.memlayer` — локальный override-файл для `MEMORYBANK_API_KEY` и timeout helper-скрипта
- `.env.memlayer.example` — переменные окружения для подключения к MemLayer
- `memlayer.config.json` — машинно-читаемый проектный конфиг для агентов и tool wrappers

Installer:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/install_memlayer_project_pack.py \
  --projects-root /Users/just/projects
```

Полезные режимы:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/install_memlayer_project_pack.py \
  --projects-root /Users/just/projects \
  --names max,APUAI \
  --dry-run
```

Installer не затирает пользовательский текст в уже существующих `AGENTS.md`: он только добавляет или обновляет managed-блок между маркерами `MEMLAYER_ROOT_PACK`.
Если в проекте уже есть `.env.memlayer`, installer его сохраняет и не перезаписывает.
Importer теперь также умеет поднимать doc-driven handoff проекты: `docs/*.md` и `mvp-handoff/*.md` превращаются в `artifact` entries, backlog `EPIC-*` headings импортируются как `task`, а product/architecture decisions вроде staged LLM pipeline, schema-first runtime и local `.loc` constraints поднимаются в память автоматически.
`memlayer_api.sh` теперь делает короткие retry/backoff попытки на localhost перед fallback на `memlayer.loc`, а `memlayer_watchdog.sh` даёт готовую быструю проверку `health + runtime self-check`.
Если сам runtime действительно просел, `memlayer_recover.sh` умеет перезапустить `api` через `docker compose restart api`, а watchdog можно перевести в auto-recover режим через `.env.memlayer`.
Если в агентной сессии недоступны вообще оба endpoint'а, root-pack теперь даёт нормальный pre-task fallback: агент читает `./memlayer_context.sh`, который по умолчанию использует локальный snapshot и не блокирует старт задачи на flaky runtime. Когда нужен живой refresh, можно явно вызвать `./memlayer_context.sh --refresh "query"` или `./memlayer_snapshot_pull.sh`.
Для import hygiene появился admin endpoint `GET /admin/projects/duplicates`: он группирует проекты по `name + source_path` и помогает быстро заметить accidental duplicate rows до того, как они начнут мешать в UI и retrieval.

## Runtime Smoke

Для быстрого operational smoke-check теперь есть отдельный сценарий `health -> import -> search -> relevant`:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/runtime_smoke_check.py \
  --project-root /Users/just/projects/router \
  --existing-project-id a1507c13-2397-41de-807b-f5d18d88a9d1 \
  --query "no-disconnect router"
```

Он:

- проверяет `/health`
- пытается прочитать `/auth/me`
- при необходимости делает reimport проекта в режиме `update`
- запускает `GET /admin/runtime/self-check`
- делает follow-up `search`
- делает follow-up `relevant`

Для лёгкой read-only проверки есть endpoint:

```bash
curl -sS 'http://127.0.0.1:18100/admin/runtime/self-check?search_query=architecture&limit=5' \
  -H 'Authorization: Bearer ops-admin-key'
```

## Memory Quality Layer

MemLayer теперь делает базовую quality-оценку при `POST /memory` и `PATCH /memory/{id}`.

- ручная запись может быть отклонена с `422`, если запись выглядит слишком слабой или placeholder-like
- import flow не блокируется: слабые записи сохраняются, но получают `metadata.quality_review_required=true`
- quality-метаданные сохраняются прямо в `metadata.quality`

Сейчас quality layer проверяет:

- слишком короткий контент
- placeholder content вроде `todo` или `tbd`
- отсутствие title для более структурных типов памяти
- отсутствие evidence-like metadata для `decision`, `constraint`, `risk`, `artifact`
- возможный дубликат внутри проекта
- semantic duplicate candidates внутри проекта через local hashed embeddings

`POST /imports/project-scan` дополнительно возвращает:

- `quality_review_required_count`

Это позволяет импортёрам и UI быстро видеть, сколько записей стоит вручную пересмотреть после scan/reimport.

Semantic duplicate detection сейчас работает без внешней vector DB:

- близкие по смыслу записи получают `metadata.quality.semantic_duplicate_risk=true`
- quality metadata включает `semantic_similarity_max` и `semantic_duplicate_candidates`
- очень близкие duplicate-case записи могут быть отклонены тем же `422` quality gate

## Decision Authority

После переноса первых практичных идей из `memlayer_next_stage_pack` MemLayer теперь умеет базово размечать решения на уровне metadata:

- новые `decision` entries по умолчанию получают `metadata.decision_status=active`
- если новая decision конфликтует с уже активной direction внутри проекта, запись получает:
  - `metadata.requires_review=true`
  - `metadata.decision_conflicts=[...]`

Пока это metadata-based слой без тяжёлой миграции схемы, поэтому он хорошо встраивается в текущий MVP/runtime и не ломает существующие import/search flows.

## Conflict Resolution

Поверх decision authority теперь есть первый рабочий human-in-the-loop flow для конфликтующих решений.

Новые admin endpoints:

- `GET /admin/decision-conflicts`
- `POST /admin/decision-conflicts/resolve`

Поддерживаемые actions:

- `supersede`
- `reject_new`
- `keep_both`
- `needs_changes`

Что делает resolution:

- обновляет `decision_status`
- меняет `requires_review` / `review_status`
- пишет `review_history`
- для `supersede` связывает записи через `supersedes_entry_id` и `deprecated_by_entry_id`
- для `reject_new` архивирует новое решение

## Lifecycle

Из `memlayer_next_stage_pack` я пока перенёс безопасный управляемый lifecycle-pass, а не бесконечный background worker.

Новый endpoint:

- `POST /maintenance/lifecycle/run`

Что он умеет:

- снижать `metadata.quality.score` у старых low-value `note` / `event`
- помечать старые review-required записи как `metadata.review_overdue=true`
- архивировать слабые stale entries по threshold-правилам
- удалять старые weak links по `strength`

Поддерживается `dry_run`, поэтому оператор может сначала посмотреть кандидатов, а потом уже применить pass по-настоящему.

## Compaction

Следующий перенесённый слой из `memlayer_next_stage_pack` — operator-driven compaction.

Новые endpoints:

- `POST /maintenance/compaction/preview`
- `POST /maintenance/compaction/apply`

Что делает preview:

- ищет stale low-value entries внутри проекта
- группирует их в простые topic-clusters по token overlap
- предлагает `suggested_title` и `suggested_content` для summary entry

Что делает apply:

- создаёт summary memory entry
- связывает исходные записи с summary через `derived_from` link с `metadata.compaction=true`
- помечает исходники `metadata.compacted_into_entry_id`
- при включённом `archive_originals` архивирует исходные записи

## Review Queues

Для операторского слоя теперь есть единый summary endpoint:

- `GET /admin/review-queues/summary`

Он собирает в одном ответе:

- `import_conflicts_count`
- `decision_conflicts_count`
- `review_overdue_count`
- `quality_review_required_count`
- `compaction_candidate_clusters_count`
- `compaction_candidate_entries_count`

И дополнительно возвращает preview-списки:

- `review_overdue_items`
- `quality_review_required_items`
- `compaction_candidates`

Встроенная MemLayer console теперь использует этот слой в `dashboard` и `review`:

- показывает decision conflicts отдельно от import conflicts
- показывает overdue review и quality review queues
- показывает compaction candidates
- умеет делать `supersede` / `reject_new` для decision conflicts
- умеет запускать `apply compaction` прямо из review UI
- умеет закрывать quality review items через `approve`, `false_positive`, `archive`

Дополнительно появился endpoint:

- `POST /admin/quality-review/resolve`

Поддерживаемые actions:

- `approve`
- `false_positive`
- `archive`
- `needs_changes`

Этот flow:

- обновляет `review_status`
- снимает или оставляет `quality_review_required`
- пишет `review_history`
- для `false_positive` помечает `metadata.quality.false_positive=true`
- для `archive` архивирует запись

## Review Metrics

`GET /metrics/overview` теперь включает не только `memory`, `graph` и `tasks`, но и новые блоки:

- `review`
- `trends`

`review` сейчас даёт:

- `pending_import_conflicts_count`
- `pending_decision_conflicts_count`
- `review_overdue_count`
- `quality_review_required_count`
- `semantic_duplicate_flagged_count`
- `false_positive_count`
- `approved_review_count`
- `archived_after_review_count`
- `compaction_summary_count`
- `compacted_original_count`
- `review_resolution_rate`
- `false_positive_rate`

`trends` сейчас даёт:

- `entries_created_7d`
- `reviews_resolved_7d`
- `duplicate_flags_7d`
- `compactions_applied_7d`

MemLayer console уже использует эти сигналы в dashboard как product-health слой поверх новых review/lifecycle/compaction процессов.

## Context Builder

Вместо плоского retrieval теперь доступен typed context endpoint:

- `POST /context/build`

Он использует существующий retrieval/search path и возвращает buckets:

- `active_decisions`
- `constraints`
- `risks`
- `artifacts`
- `tasks`
- `notes`
- `other`

Результаты дополнительно бустятся по типу памяти, `importance` и decision status, чтобы агенту было проще сначала увидеть реальные решения и ограничения, а не шум.

## Auth

Сервис теперь поддерживает optional API-key auth.

Переменные окружения:

```env
AUTH_ENABLED=true
AUTH_API_KEYS=reader-key:read,agent-write-key:write|import,ops-admin-key:write|import|admin,tenant-agent:tenant-key:read|write|import:tenant-a
```

Поддерживаются два способа передачи ключа:

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

Scope-ы:

- `read` — чтение проектов, памяти, links и search endpoints
- `write` — изменение данных, запись памяти, links, projects, task logs
- `import` — import endpoints
- `admin` — maintenance, metrics, admin observability

Если auth включён, read endpoints тоже требуют API key. Ключи с `write`, `import` или `admin` могут читать данные тоже, а отдельный `read` scope удобен для dashboard/UI и наблюдения без права записи.

Поддерживается tenant-scoped формат ключей:

```env
AUTH_API_KEYS=tenant-agent:tenant-key:read|write|import:tenant-a|tenant-b
```

В таком режиме ключ видит и изменяет только проекты и memory entries, принадлежащие указанным `tenant_id`. Тот же tenant filter теперь применяется и к `task-logs`, `GET /metrics/overview`, `GET /admin/observability/summary`, `GET /admin/import-conflicts`, `GET /admin/imports/summary`.

Если tenant-restricted ключ создаёт проект без явного `tenant_id`, сервис автоматически подставляет единственный доступный tenant. Аналогично `POST /task-logs` автоматически проставляет `metadata.tenant_id`, если ключ ограничен одним tenant.

Если `AUTH_ENABLED=false`, сервис работает как раньше, без обязательной авторизации.

## API Quick Reference

### Memory types

- `decision`
- `task`
- `artifact`
- `event`
- `note`
- `constraint`
- `risk`

### Link types

- `depends_on`
- `related_to`
- `created_after`
- `affects`
- `derived_from`
- `blocks`
- `resolves`

### Core endpoints

- `GET /health`
- `GET /auth/me`
- `GET /console/`
- `POST /projects`
- `GET /projects`
- `GET /projects/{id}`
- `PATCH /projects/{id}`
- `DELETE /projects/{id}`
- `POST /memory`
- `GET /memory`
- `GET /memory/{id}`
- `PATCH /memory/{id}`
- `POST /memory/{id}/archive`
- `GET /memory/search`
- `POST /memory/relevant`
- `POST /context/build`
- `POST /memory-links`
- `GET /memory/{id}/links`
- `GET /memory/{id}/graph`
- `POST /maintenance/archive-stale`
- `POST /maintenance/rebuild-search-vectors`
- `POST /maintenance/lifecycle/run`
- `POST /maintenance/compaction/preview`
- `POST /maintenance/compaction/apply`
- `POST /imports/project-scan`
- `GET /metrics/overview`
- `GET /admin/observability/summary`
- `GET /admin/import-conflicts`
- `GET /admin/decision-conflicts`
- `GET /admin/imports/summary`
- `GET /admin/review-queues/summary`
- `POST /admin/quality-review/resolve`

## curl Examples

Во всех примерах ниже используется дефолтный host port `18100`.

### Проверить health

```bash
curl -sS http://127.0.0.1:18100/health
```

### Узнать активные auth scopes и tenants

```bash
curl -sS http://127.0.0.1:18100/auth/me \
  -H 'Authorization: Bearer tenant-key'
```

### Создать проект

```bash
curl -sS -X POST http://127.0.0.1:18100/projects \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Memory Bank MVP",
    "description": "Simple memory layer for agents"
  }'
```

### Добавить запись в память

```bash
curl -sS -X POST http://127.0.0.1:18100/memory \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "decision",
    "title": "Use PostgreSQL for MVP",
    "content": "For MVP we will use PostgreSQL instead of Neo4j to reduce complexity.",
    "source_agent": "planner-agent",
    "importance": 4,
    "metadata": {
      "tags": ["architecture", "database"]
    }
  }'
```

Если запись не проходит quality gate, API вернёт `422` с полем `detail.quality`.

### Получить релевантный контекст для агента

```bash
curl -sS -X POST http://127.0.0.1:18100/memory/relevant \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Implement database layer for memory bank",
    "agent_id": "backend-agent",
    "types": ["decision", "artifact", "task"],
    "limit": 8
  }'
```

### Собрать typed context для агента

```bash
curl -sS -X POST http://127.0.0.1:18100/context/build \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "database runtime",
    "project_id": "PROJECT_UUID",
    "scope": "project",
    "mode": "hybrid",
    "limit": 8
  }'
```

### Выполнить полнотекстовый поиск

```bash
curl -sS 'http://127.0.0.1:18100/memory/search?query=postgresql%20architecture&limit=10'
```

### Создать связь между записями

```bash
curl -sS -X POST http://127.0.0.1:18100/memory-links \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "from_entry_id": "FROM_UUID",
    "to_entry_id": "TO_UUID",
    "type": "depends_on",
    "strength": 1.0,
    "created_by_agent": "planner-agent"
  }'
```

### Получить подграф памяти

```bash
curl -sS 'http://127.0.0.1:18100/memory/ENTRY_UUID/graph?depth=2'
```

### Архивировать устаревшую память

```bash
curl -sS -X POST http://127.0.0.1:18100/maintenance/archive-stale \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "older_than_days": 30,
    "max_usage_count": 0,
    "max_importance": 2
  }'
```

### Запустить lifecycle pass в dry-run режиме

```bash
curl -sS -X POST http://127.0.0.1:18100/maintenance/lifecycle/run \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "dry_run": true,
    "stale_days": 21,
    "review_overdue_days": 14,
    "weak_link_days": 30,
    "low_quality_threshold": 0.35,
    "weak_link_strength_threshold": 0.35
  }'
```

### Посмотреть compaction candidates

```bash
curl -sS -X POST http://127.0.0.1:18100/maintenance/compaction/preview \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "PROJECT_UUID",
    "stale_days": 21,
    "min_entries": 4,
    "max_entries": 12,
    "min_overlap_tokens": 2
  }'
```

### Применить compaction cluster

```bash
curl -sS -X POST http://127.0.0.1:18100/maintenance/compaction/apply \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "entry_ids": ["ENTRY_UUID_1", "ENTRY_UUID_2", "ENTRY_UUID_3", "ENTRY_UUID_4"],
    "archive_originals": true
  }'
```

### Импортировать проект в Memory Bank

```bash
curl -sS -X POST http://127.0.0.1:18100/imports/project-scan \
  -H 'Authorization: Bearer agent-write-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "project": {
      "name": "Imported Project",
      "description": "Imported from existing repository"
    },
    "entries": [
      {
        "ref": "decision-db",
        "type": "decision",
        "title": "Use PostgreSQL as primary database",
        "content": "Project uses PostgreSQL as the primary database service in docker-compose.",
        "importance": 4
      },
      {
        "ref": "artifact-compose",
        "type": "artifact",
        "title": "docker-compose.yml",
        "content": "Defines api and db services.",
        "importance": 4
      }
    ],
    "links": [
      {
        "from_ref": "artifact-compose",
        "to_ref": "decision-db",
        "type": "derived_from",
        "strength": 0.8
      }
    ],
    "detect_conflicts": true,
    "existing_entry_mode": "update"
  }'
```

В ответе import flow теперь есть `quality_review_required_count`, а слабые импортированные записи получают флаг `metadata.quality_review_required=true` вместо жёсткого отказа.

### Посмотреть pending decision conflicts

```bash
curl -sS 'http://127.0.0.1:18100/admin/decision-conflicts?limit=20' \
  -H 'Authorization: Bearer ops-admin-key'
```

### Разрешить decision conflict через supersede

```bash
curl -sS -X POST http://127.0.0.1:18100/admin/decision-conflicts/resolve \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "entry_id": "NEW_DECISION_UUID",
    "conflicts_with_entry_id": "OLD_DECISION_UUID",
    "action": "supersede",
    "resolution": "New decision replaces the previous direction.",
    "resolved_by": "ops-admin"
  }'
```

### Посмотреть unified review queues summary

```bash
curl -sS 'http://127.0.0.1:18100/admin/review-queues/summary?limit=10' \
  -H 'Authorization: Bearer ops-admin-key'
```

### Закрыть quality review item

```bash
curl -sS -X POST http://127.0.0.1:18100/admin/quality-review/resolve \
  -H 'Authorization: Bearer ops-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "entry_id": "ENTRY_UUID",
    "action": "false_positive",
    "resolution": "This semantic duplicate warning is acceptable.",
    "resolved_by": "ops-admin"
  }'
```

## Auto-linking

Можно включить автоматическое создание `related_to` связей после `POST /memory`:

```env
AUTO_LINK_ON_CREATE=true
AUTO_LINK_MIN_SIMILARITY=0.35
AUTO_LINK_SEARCH_LIMIT=20
AUTO_LINK_MAX_LINKS=5
```

Фича вдохновлена подходом из `memorybank_agent_pack` и работает без внешних embeddings-сервисов.

## Full-Text Search

Для PostgreSQL проект теперь использует stored `search_vector` и отдельную миграцию до `tsvector`.

После массовых правок или импорта данных можно вручную пересобрать поисковые векторы:

```bash
curl -X POST http://localhost:8000/maintenance/rebuild-search-vectors \
  -H 'Content-Type: application/json' \
  -d '{}'
```

## Hybrid Search

Поиск теперь поддерживает три режима:

- `lexical` — текущий FTS / text-match путь
- `semantic` — локальный semantic-ish token similarity с query expansion
- `hybrid` — смешанный режим по умолчанию

Это доступно в:

- `GET /memory/search?query=...&mode=hybrid`
- `POST /memory/relevant` через поле `search_mode`

Также доступен retrieval scope:

- `scope=project` — только текущий проект
- `scope=related` — текущий проект плюс соседние проекты из `project.metadata.related_projects`
- `scope=global` — поиск по всей доступной памяти

Это особенно полезно для агентных сценариев, когда решение может уже лежать в соседнем репозитории, но при этом мы не хотим сразу проваливаться в глобальный шум.

## SDK и Example Agent

В репозитории есть встроенный минимальный SDK для агентных сценариев:

```python
from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient

with MemoryBankClient(DEFAULT_MEMORYBANK_URL) as client:
    health = client.health()
    print(health)
    related = client.search_memory(
        "vpn routing fix",
        project_id="PROJECT_UUID",
        scope="related",
        mode="hybrid",
    )
    print(related["items"])
```

SDK теперь также умеет вызывать structured import flow:

```python
from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient

with MemoryBankClient(DEFAULT_MEMORYBANK_URL) as client:
    result = client.import_project_scan(
        project={"name": "Imported Project"},
        entries=[
            {"ref": "decision-db", "type": "decision", "content": "Use PostgreSQL."},
            {"ref": "risk-secrets", "type": "risk", "content": "Never store api_key=..."},
        ],
        links=[
            {"from_ref": "risk-secrets", "to_ref": "decision-db", "type": "affects"},
        ],
    )
    print(result["entries_created"])
```

И пример агента:

```bash
PYTHONPATH=$PWD .venv313/bin/python examples/simple_agent.py
```

И пример импортёра:

```bash
PYTHONPATH=$PWD MEMORYBANK_URL=http://127.0.0.1:18100 .venv313/bin/python examples/project_importer.py
```

И CLI-импорт локального проекта:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/import_project_cli.py \
  --project-root /path/to/project \
  --memorybank-url http://127.0.0.1:18100 \
  --dry-run
```

И batch-импорт нескольких подпроектов из каталога:

```bash
PYTHONPATH=$PWD .venv313/bin/python scripts/import_project_cli.py \
  --projects-directory /Users/just/projects \
  --names max,APUAI \
  --existing-entry-mode update \
  --memorybank-url http://127.0.0.1:18100
```

Он следует циклу:

```text
READ -> ACT -> WRITE -> LINK
```

`MemoryAwareAgent` теперь также может автоматически:

- вызывать evaluator
- логировать `task_logs`
- сохранять `duration_seconds`, `result_quality_score`, `consistency_score`
- использовать smart retrieval default:
  - сначала `scope=project`
  - затем `scope=related`
  - и только при слабом контексте расширяться до `scope=global`

По умолчанию agent protocol считает результат “слабым”, если после project/related retrieval набралось меньше `2` контекстных записей. При этом в metadata памяти и task log теперь пишется `retrieval_scopes_used`, чтобы было видно, насколько далеко агенту пришлось расширять поиск.

## Task Logs и Eval Hooks

Из `memorybank_eval_pack` в ядро сервиса добавлен минимальный слой аналитики:

- `POST /task-logs`
- `POST /task-logs/import`
- `GET /task-logs`
- `GET /task-logs/summary`

Это позволяет логировать агентные задачи и затем считать базовые метрики использования памяти и качества результата.

Также доступен встроенный evaluator endpoint:

- `POST /evaluation/evaluate`
- `POST /evaluation/evaluate-batch`

Он принимает `task`, `memory`, `reasoning`, `answer` и возвращает explainable rule-based оценку того, насколько память действительно повлияла на результат.

Для пакетной оценки можно передать список payload'ов в `POST /evaluation/evaluate-batch` и получить summary по всему набору.

## Metrics API

Для базовой observability без внешнего dashboard доступен:

- `GET /metrics/overview`
- `GET /admin/observability/summary`
- `GET /admin/import-conflicts`
- `GET /admin/imports/summary`

Он возвращает сводку по:

- памяти: `total_entries`, `active_entries`, `archived_entries`, `reuse_rate`, `orphan_rate`
- графу: `total_links`, `avg_link_strength`
- task logs: `total_tasks`, `memory_usage_rate`, `avg_duration_seconds`, `avg_quality_score`

Можно фильтровать по `project_id` для memory/graph и по `agent_id` / `experiment_id` для task logs.

`GET /admin/observability/summary` даёт единый snapshot: environment, recent activity за 24 часа, top agents и top experiments.

`GET /admin/import-conflicts` возвращает импортированные записи, которые были помечены как `requires_review` из-за конфликтующих решений.

`GET /admin/imports/summary` даёт компактную сводку по импортированным проектам: `source_path`, число импортированных entries, число import events, число конфликтов и время последнего импорта.

## Project Import API

Для сценария из `Importer.md` теперь доступен:

- `POST /imports/project-scan`

Он умеет:

- создать новый `project` или использовать существующий `project_id`
- автоматически создать import `event`
- пакетно создать memory entries с `ref`
- пакетно создать связи между ними через `from_ref` / `to_ref`
- базово маскировать строки вида `api_key=...`, `token=...`, `password=...`, `secret=...`
- консервативно помечать конфликтующие `decision` entries как `requires_review=true`
- повторно импортировать проект в режиме `create`, `skip` или `update`

Импортёр теперь дополнительно лучше распознаёт:

- `package.json` и scripts/dependencies
- `go.mod`
- `pnpm-workspace.yaml` и `turbo.json`
- common entrypoints вроде `src/index.ts`, `src/main.ts`, `main.go`, `cmd/server/main.go`
- monorepo/runtime constraints и базовые runtime risks

При включённом conflict detection response также возвращает список найденных конфликтов с `reason` и `confidence`.

Если auth включён, для import flow нужен ключ со scope `import`.

Поддерживаемые типы памяти теперь включают:

- `decision`
- `task`
- `artifact`
- `event`
- `note`
- `constraint`
- `risk`

## Журнал

Ход реализации фиксируется в [WORKLOG.md](/Users/just/apps/memory.bank/WORKLOG.md).

## Примечание по драйверу БД

Проект использует `psycopg` v3 (`postgresql+psycopg://...`) вместо `psycopg2-binary`, чтобы установка зависимостей не требовала системного `pg_config`.
