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
- Docker, Alembic и базовые API-тесты

## Быстрый старт

1. Скопировать `.env.example` в `.env`.
2. Запустить `docker compose up --build`.
3. Применить миграции: `docker compose exec api alembic upgrade head`.
4. Открыть `http://localhost:18100/docs` или свой `HOST_API_PORT`.

`docker-compose.yml` уже содержит healthcheck для PostgreSQL, поэтому `api` стартует после готовности БД.

Для формальной локальной проверки API-тестов можно использовать:

```bash
docker compose exec api pytest
```

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
- `POST /memory-links`
- `GET /memory/{id}/links`
- `GET /memory/{id}/graph`
- `POST /maintenance/archive-stale`
- `POST /maintenance/rebuild-search-vectors`
- `POST /imports/project-scan`
- `GET /metrics/overview`
- `GET /admin/observability/summary`
- `GET /admin/import-conflicts`
- `GET /admin/imports/summary`

## curl Examples

Во всех примерах ниже используется дефолтный host port `18100`.

### Проверить health

```bash
curl -sS http://127.0.0.1:18100/health
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

## SDK и Example Agent

В репозитории есть встроенный минимальный SDK для агентных сценариев:

```python
from memorybank_sdk import MemoryBankClient

with MemoryBankClient("http://localhost:8000") as client:
    health = client.health()
    print(health)
```

SDK теперь также умеет вызывать structured import flow:

```python
from memorybank_sdk import MemoryBankClient

with MemoryBankClient("http://localhost:18100") as client:
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
