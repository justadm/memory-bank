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
- endpoint `POST /memory/relevant` с учётом usage/access logs
- maintenance endpoint для архивации устаревшей памяти
- опциональное auto-linking новых записей через bag-of-words similarity
- встроенный `memorybank_sdk` и пример memory-aware агента
- Docker, Alembic и базовые API-тесты

## Быстрый старт

1. Скопировать `.env.example` в `.env`.
2. Запустить `docker compose up --build`.
3. Применить миграции: `docker compose exec api alembic upgrade head`.
4. Открыть `http://localhost:18100/docs` или свой `HOST_API_PORT`.

`docker-compose.yml` уже содержит healthcheck для PostgreSQL, поэтому `api` стартует после готовности БД.

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

## SDK и Example Agent

В репозитории есть встроенный минимальный SDK для агентных сценариев:

```python
from memorybank_sdk import MemoryBankClient

with MemoryBankClient("http://localhost:8000") as client:
    health = client.health()
    print(health)
```

И пример агента:

```bash
PYTHONPATH=$PWD .venv313/bin/python examples/simple_agent.py
```

Он следует циклу:

```text
READ -> ACT -> WRITE -> LINK
```

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

Он возвращает сводку по:

- памяти: `total_entries`, `active_entries`, `archived_entries`, `reuse_rate`, `orphan_rate`
- графу: `total_links`, `avg_link_strength`
- task logs: `total_tasks`, `memory_usage_rate`, `avg_duration_seconds`, `avg_quality_score`

Можно фильтровать по `project_id` для memory/graph и по `agent_id` / `experiment_id` для task logs.

## Журнал

Ход реализации фиксируется в [WORKLOG.md](/Users/just/apps/memory.bank/WORKLOG.md).

## Примечание по драйверу БД

Проект использует `psycopg` v3 (`postgresql+psycopg://...`) вместо `psycopg2-binary`, чтобы установка зависимостей не требовала системного `pg_config`.
