
# MVP Memory Bank

## Цель MVP

Сделать простой сервис памяти для агентов:

* агент может записывать факты, решения, задачи и артефакты;
* агент может получать релевантный контекст перед выполнением задачи;
* память имеет связи между записями;
* есть базовый механизм устаревания;
* всё запускается через Docker.

---

# 1. Архитектура MVP

## Минимальный стек

* **Backend:** Python + FastAPI
* **DB:** PostgreSQL
* **ORM:** SQLAlchemy / SQLModel
* **Migrations:** Alembic
* **Search:** сначала PostgreSQL full-text search
* **Docker:** docker-compose
* **Опционально позже:** pgvector, Redis, Qdrant

---

## Сервисы в Docker

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
    env_file:
      - .env

  db:
    image: postgres:16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: memory_bank
      POSTGRES_USER: memory_user
      POSTGRES_PASSWORD: memory_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

# 2. Основные сущности

## Типы памяти

```text
decision  — архитектурные решения
task      — задачи
artifact  — файлы, код, документы
event     — события, логи, взаимодействия агентов
note      — обычная заметка
```

## Типы связей

```text
depends_on
related_to
created_after
affects
derived_from
blocks
resolves
```

---

# 3. Схема БД

## Таблица `memory_entries`

Главная таблица памяти.

```sql
CREATE TABLE memory_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    type VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,

    source_agent VARCHAR(100),
    project_id UUID,

    importance INTEGER NOT NULL DEFAULT 3,
    usage_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    last_used_at TIMESTAMP,

    archived BOOLEAN NOT NULL DEFAULT false,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    search_vector tsvector
);
```

### Поля

| Поле            | Назначение                 |
| --------------- | -------------------------- |
| `id`            | ID записи                  |
| `type`          | тип памяти                 |
| `title`         | короткий заголовок         |
| `content`       | основное содержимое        |
| `source_agent`  | кто создал запись          |
| `project_id`    | принадлежность к проекту   |
| `importance`    | ручная важность от 1 до 5  |
| `usage_count`   | сколько раз использовалась |
| `last_used_at`  | последнее использование    |
| `archived`      | архивирована ли запись     |
| `metadata`      | любые доп. данные          |
| `search_vector` | полнотекстовый поиск       |

---

## Таблица `memory_links`

Связи между записями.

```sql
CREATE TABLE memory_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    from_entry_id UUID NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,
    to_entry_id UUID NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,

    type VARCHAR(50) NOT NULL,
    strength FLOAT NOT NULL DEFAULT 1.0,

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    created_by_agent VARCHAR(100),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE(from_entry_id, to_entry_id, type)
);
```

### Пример

```text
Task A depends_on Decision B
Artifact X derived_from Decision Y
Event Z affects Task A
```

---

## Таблица `memory_access_logs`

Логи использования памяти.

```sql
CREATE TABLE memory_access_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    entry_id UUID NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,

    agent_id VARCHAR(100),
    task_context TEXT,

    accessed_at TIMESTAMP NOT NULL DEFAULT now(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

Нужна для:

* подсчёта использования;
* отладки;
* понимания, какие записи реально помогают агентам.

---

## Таблица `projects`

Для группировки памяти по проектам.

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(255) NOT NULL,
    description TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

---

# 4. Индексы

```sql
CREATE INDEX idx_memory_entries_type
ON memory_entries(type);

CREATE INDEX idx_memory_entries_project_id
ON memory_entries(project_id);

CREATE INDEX idx_memory_entries_archived
ON memory_entries(archived);

CREATE INDEX idx_memory_entries_created_at
ON memory_entries(created_at);

CREATE INDEX idx_memory_entries_last_used_at
ON memory_entries(last_used_at);

CREATE INDEX idx_memory_entries_metadata
ON memory_entries USING GIN(metadata);

CREATE INDEX idx_memory_entries_search_vector
ON memory_entries USING GIN(search_vector);

CREATE INDEX idx_memory_links_from
ON memory_links(from_entry_id);

CREATE INDEX idx_memory_links_to
ON memory_links(to_entry_id);

CREATE INDEX idx_memory_links_type
ON memory_links(type);
```

---

# 5. API MVP

## Healthcheck

```http
GET /health
```

Ответ:

```json
{
  "status": "ok"
}
```

---

# Memory API

## Добавить запись

```http
POST /memory
```

Тело:

```json
{
  "type": "decision",
  "title": "Use PostgreSQL for MVP",
  "content": "For MVP we will use PostgreSQL instead of Neo4j to reduce complexity.",
  "source_agent": "planner-agent",
  "project_id": "uuid",
  "importance": 4,
  "metadata": {
    "tags": ["architecture", "database"]
  }
}
```

Ответ:

```json
{
  "id": "uuid",
  "type": "decision",
  "title": "Use PostgreSQL for MVP",
  "created_at": "2026-04-29T10:00:00Z"
}
```

---

## Получить запись

```http
GET /memory/{id}
```

Ответ:

```json
{
  "id": "uuid",
  "type": "decision",
  "title": "Use PostgreSQL for MVP",
  "content": "...",
  "importance": 4,
  "usage_count": 2,
  "created_at": "...",
  "last_used_at": "...",
  "metadata": {}
}
```

---

## Обновить запись

```http
PATCH /memory/{id}
```

Тело:

```json
{
  "title": "Updated title",
  "content": "Updated content",
  "importance": 5,
  "metadata": {
    "tags": ["backend", "db"]
  }
}
```

---

## Архивировать запись

```http
POST /memory/{id}/archive
```

Ответ:

```json
{
  "id": "uuid",
  "archived": true
}
```

---

## Поиск памяти

```http
GET /memory/search?query=postgresql architecture&project_id=uuid&limit=10
```

Ответ:

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "decision",
      "title": "Use PostgreSQL for MVP",
      "content_preview": "For MVP we will use PostgreSQL...",
      "score": 0.87,
      "importance": 4,
      "usage_count": 5
    }
  ]
}
```

---

## Получить релевантную память для агента

```http
POST /memory/relevant
```

Тело:

```json
{
  "query": "Implement database layer for memory bank",
  "project_id": "uuid",
  "agent_id": "backend-agent",
  "types": ["decision", "artifact", "task"],
  "limit": 8
}
```

Ответ:

```json
{
  "context": [
    {
      "id": "uuid",
      "type": "decision",
      "title": "Use PostgreSQL for MVP",
      "content": "For MVP we will use PostgreSQL instead of Neo4j...",
      "relevance_score": 0.91
    }
  ]
}
```

При вызове этого endpoint:

* увеличивается `usage_count`;
* обновляется `last_used_at`;
* создаётся запись в `memory_access_logs`.

---

# Links API

## Создать связь

```http
POST /memory-links
```

Тело:

```json
{
  "from_entry_id": "uuid",
  "to_entry_id": "uuid",
  "type": "depends_on",
  "strength": 1.0,
  "created_by_agent": "planner-agent",
  "metadata": {}
}
```

---

## Получить связи записи

```http
GET /memory/{id}/links
```

Ответ:

```json
{
  "outgoing": [
    {
      "id": "uuid",
      "to_entry_id": "uuid",
      "type": "depends_on",
      "strength": 1.0
    }
  ],
  "incoming": [
    {
      "id": "uuid",
      "from_entry_id": "uuid",
      "type": "affects",
      "strength": 0.8
    }
  ]
}
```

---

## Получить подграф

```http
GET /memory/{id}/graph?depth=2
```

Ответ:

```json
{
  "nodes": [
    {
      "id": "uuid",
      "type": "decision",
      "title": "Use PostgreSQL"
    }
  ],
  "edges": [
    {
      "from": "uuid",
      "to": "uuid",
      "type": "depends_on"
    }
  ]
}
```

---

# Projects API

## Создать проект

```http
POST /projects
```

```json
{
  "name": "Memory Bank MVP",
  "description": "Simple memory layer for agents"
}
```

---

## Получить проекты

```http
GET /projects
```

---

# Maintenance API

## Архивировать устаревшую память

```http
POST /maintenance/archive-stale
```

Тело:

```json
{
  "older_than_days": 30,
  "max_usage_count": 0,
  "max_importance": 2
}
```

Логика:

```text
archive if:
- created_at older than N days
- usage_count <= max_usage_count
- importance <= max_importance
```

---

# 6. Формула релевантности MVP

Без ML и векторных баз.

```text
final_score =
  text_match_score * 0.6
  + importance_score * 0.2
  + recency_score * 0.1
  + usage_score * 0.1
```

Где:

```text
text_match_score — PostgreSQL full-text rank
importance_score — importance / 5
recency_score — чем свежее, тем выше
usage_score — log(usage_count + 1)
```

---

# 7. Структура проекта

```text
memory-bank/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   │
│   ├── models/
│   │   ├── memory_entry.py
│   │   ├── memory_link.py
│   │   ├── project.py
│   │   └── access_log.py
│   │
│   ├── schemas/
│   │   ├── memory.py
│   │   ├── links.py
│   │   └── projects.py
│   │
│   ├── routers/
│   │   ├── memory.py
│   │   ├── links.py
│   │   ├── projects.py
│   │   └── maintenance.py
│   │
│   ├── services/
│   │   ├── memory_service.py
│   │   ├── search_service.py
│   │   ├── graph_service.py
│   │   └── scoring_service.py
│   │
│   └── repositories/
│       ├── memory_repository.py
│       ├── link_repository.py
│       └── project_repository.py
│
├── alembic/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
├── .env.example
└── README.md
```

---

# 8. Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

# 9. `requirements.txt`

```txt
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
alembic
pydantic
pydantic-settings
python-dotenv
pytest
httpx
```

---

# 10. `.env.example`

```env
DATABASE_URL=postgresql://memory_user:memory_password@db:5432/memory_bank
APP_ENV=development
API_PORT=8000
```

---

# 11. Этапы разработки

## Этап 0. Подготовка

Цель: поднять пустой проект в Docker.

Задачи:

* создать структуру проекта;
* настроить FastAPI;
* настроить PostgreSQL;
* добавить Dockerfile;
* добавить docker-compose;
* добавить `/health`.

Критерий готовности:

```bash
docker compose up --build
```

И:

```http
GET http://localhost:8000/health
```

возвращает:

```json
{"status": "ok"}
```

---

## Этап 1. Базовая БД и миграции

Цель: создать таблицы.

Задачи:

* подключить SQLAlchemy;
* настроить Alembic;
* создать модели:

  * `Project`
  * `MemoryEntry`
  * `MemoryLink`
  * `MemoryAccessLog`
* создать первую миграцию;
* добавить индексы.

Критерий готовности:

```bash
docker compose exec api alembic upgrade head
```

создаёт все таблицы в PostgreSQL.

---

## Этап 2. CRUD для проектов

Цель: уметь создавать рабочие пространства.

API:

```text
POST /projects
GET /projects
GET /projects/{id}
PATCH /projects/{id}
DELETE /projects/{id}
```

Критерий готовности:

* можно создать проект;
* можно получить список проектов;
* memory entries можно привязывать к `project_id`.

---

## Этап 3. CRUD для памяти

Цель: базовая запись и чтение памяти.

API:

```text
POST /memory
GET /memory/{id}
PATCH /memory/{id}
POST /memory/{id}/archive
GET /memory
```

Критерий готовности:

* агент может записать память;
* агент может прочитать память;
* можно фильтровать по:

  * `project_id`
  * `type`
  * `archived`.

---

## Этап 4. Связи между записями

Цель: добавить графовую логику без графовой БД.

API:

```text
POST /memory-links
GET /memory/{id}/links
DELETE /memory-links/{id}
GET /memory/{id}/graph?depth=1
```

Критерий готовности:

* можно связать две записи;
* можно получить входящие и исходящие связи;
* можно получить простой подграф.

---

## Этап 5. Поиск

Цель: найти релевантные записи по тексту.

Задачи:

* добавить PostgreSQL full-text search;
* обновлять `search_vector`;
* реализовать `/memory/search`.

API:

```text
GET /memory/search?query=...&project_id=...&limit=10
```

Критерий готовности:

* поиск находит записи по `title` и `content`;
* архивные записи по умолчанию не возвращаются.

---

## Этап 6. Endpoint для агентов

Цель: сделать основной сценарий использования.

API:

```text
POST /memory/relevant
```

Этот endpoint должен:

1. принять задачу агента;
2. найти релевантные записи;
3. отсортировать по итоговому score;
4. увеличить `usage_count`;
5. обновить `last_used_at`;
6. записать лог доступа.

Критерий готовности:

* агент получает готовый контекст;
* использование памяти фиксируется.

---

## Этап 7. Архивация и забывание

Цель: базовый lifecycle памяти.

API:

```text
POST /maintenance/archive-stale
```

Логика:

```text
Архивировать записи, которые:
- старше N дней;
- почти не использовались;
- имеют низкую importance;
- не являются decision с importance >= 4.
```

Критерий готовности:

* старые неважные записи архивируются;
* важные решения остаются активными.

---

## Этап 8. Тесты

Минимальный набор:

```text
test_create_project
test_create_memory_entry
test_update_memory_entry
test_archive_memory_entry
test_create_memory_link
test_search_memory
test_get_relevant_memory
test_archive_stale_memory
```

Критерий готовности:

```bash
docker compose exec api pytest
```

все тесты проходят.

---

## Этап 9. Документация

Добавить в README:

* как запустить;
* как создать проект;
* как добавить память;
* как запросить релевантный контекст;
* примеры curl;
* описание типов памяти;
* описание типов связей.

---

# 12. Приоритеты MVP

## Обязательно

```text
Docker
FastAPI
PostgreSQL
Alembic
memory_entries
memory_links
projects
access_logs
POST /memory
POST /memory/relevant
GET /memory/search
GET /memory/{id}/graph
```

## Не обязательно в MVP

```text
Neo4j
Kafka
RabbitMQ
Redis
Vector DB
UI
Auth
multi-tenant access control
```

## Можно добавить после MVP

```text
pgvector
semantic search
agent webhooks
Redis cache
event queue
dashboard
automatic linking
memory summarization
conflict detection
```

---

# 13. Реалистичный план по срокам

## День 1

* структура проекта;
* Docker;
* FastAPI;
* PostgreSQL;
* healthcheck.

## День 2

* SQLAlchemy;
* Alembic;
* модели БД;
* миграции.

## День 3

* CRUD проектов;
* CRUD памяти.

## День 4

* связи;
* подграф;
* базовые тесты.

## День 5

* full-text search;
* endpoint `/memory/search`.

## День 6

* endpoint `/memory/relevant`;
* scoring;
* access logs.

## День 7

* архивация;
* README;
* финальные тесты;
* cleanup.

---

# 14. Главная рекомендация

Я бы делал MVP именно так:

```text
PostgreSQL first.
Graph logic in tables.
No vector DB at start.
No queue at start.
No Neo4j at start.
Everything in Docker.
```

Так ты быстро получишь рабочий Memory Bank, который можно подключить к агенту уже после первой недели.

---

# Статус по roadmap

## Готово

- Цель MVP: базовый Memory Bank для агентов реализован и работает в Docker.
- Архитектура MVP: `FastAPI + PostgreSQL + SQLAlchemy + Alembic + docker-compose + PostgreSQL FTS`.
- Этап 0: структура проекта, Docker, FastAPI, PostgreSQL, `/health`.
- Этап 1: модели, миграции, таблицы, индексы.
- Этап 2: CRUD для проектов.
- Этап 3: CRUD для памяти, фильтры по `project_id`, `type`, `archived`.
- Этап 4: связи, входящие/исходящие links, подграф.
- Этап 5: full-text search, stored `search_vector`, `/memory/search`.
- Этап 6: `/memory/relevant`, scoring, `usage_count`, `last_used_at`, access logs.
- Этап 7: архивация устаревшей памяти.
- Этап 8: тестовый набор закрыт с запасом.
- Обязательные MVP-пункты из раздела приоритетов закрыты.

## Частично

- Этап 9 документации:
  - готово: запуск, Docker, SDK, import flow, admin endpoints, основные возможности.
  - частично: в README ещё стоит добавить более полный набор `curl`-примеров и компактный справочник по memory/link types.
- Формальная Docker-проверка тестов:
  - локальный `pytest` регулярно гоняется и зелёный,
  - но отдельный рутинный сценарий именно `docker compose exec api pytest` ещё не оформлен как постоянный чек.

## Не начато

- UI.
- Auth.
- Multi-tenant access control.
- Redis cache.
- Event queue / workers.
- Semantic search / embeddings / `pgvector`.
- Agent webhooks.
- Memory summarization.

## Что уже сделано сверх roadmap

- SDK для агентов и example scripts.
- Task logs, evaluator, batch evaluation, metrics.
- Auto-linking.
- Import API, CLI, batch directory import.
- Conflict detection.
- Admin observability, import conflicts, import summaries.
- Реальные live imports проектов из `/Users/just/projects/`.

## Ближайший план

- Дополнить README `curl`-примерами и коротким API quick reference.
- Довести повторный import flow для уже известных проектов без дублей.
- Добавить richer import heuristics для сложных monorepo-layouts и mixed stacks.
- Подумать над следующим большим блоком: `auth`, `UI`, либо semantic search.
