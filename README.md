# Memory Bank MVP

Простой сервис памяти для агентных сценариев на FastAPI и PostgreSQL.

## Что уже есть

- healthcheck `GET /health`
- CRUD для проектов
- CRUD для памяти, архивирование и листинг
- связи между записями и простой подграф
- поиск по памяти с PostgreSQL FTS и fallback для SQLite-тестов
- endpoint `POST /memory/relevant` с учётом usage/access logs
- maintenance endpoint для архивации устаревшей памяти
- Docker, Alembic и базовые API-тесты

## Быстрый старт

1. Скопировать `.env.example` в `.env`.
2. Запустить `docker compose up --build`.
3. Применить миграции: `docker compose exec api alembic upgrade head`.
4. Открыть `http://localhost:8000/docs`.

`docker-compose.yml` уже содержит healthcheck для PostgreSQL, поэтому `api` стартует после готовности БД.

## Журнал

Ход реализации фиксируется в [WORKLOG.md](/Users/just/apps/memory.bank/WORKLOG.md).

## Примечание по драйверу БД

Проект использует `psycopg` v3 (`postgresql+psycopg://...`) вместо `psycopg2-binary`, чтобы установка зависимостей не требовала системного `pg_config`.
