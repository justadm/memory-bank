#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_guarded_migration_drill import MigrationDrillError, validate_disposable_database_url


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_revision(engine: sa.Engine) -> str | None:
    with engine.connect() as connection:
        return connection.scalar(sa.text("SELECT version_num FROM alembic_version"))


def _assert_revision(engine: sa.Engine, expected: str) -> None:
    actual = _current_revision(engine)
    if actual != expected:
        raise AssertionError(f"expected Alembic revision {expected}, got {actual}")


def _insert_temporal_legacy_fixtures(engine: sa.Engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    project_id = uuid.uuid4()
    active_id = uuid.uuid4()
    archived_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO projects (id, name, description, created_at, updated_at, metadata)
                VALUES (:id, 'migration-drill', NULL, :now, :now, '{}'::jsonb)
                """
            ),
            {"id": project_id, "now": now},
        )
        for entry_id, title, archived in (
            (active_id, "active-fixture", False),
            (archived_id, "archived-fixture", True),
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO memory_entries (
                        id, type, title, content, source_agent, project_id, importance,
                        usage_count, created_at, updated_at, last_used_at, archived,
                        metadata, search_vector
                    )
                    VALUES (
                        :id, 'note', :title, 'synthetic fixture', 'migration-drill',
                        :project_id, 3, 0, :now, :now, NULL, :archived, '{}'::jsonb, NULL
                    )
                    """
                ),
                {
                    "id": entry_id,
                    "title": title,
                    "project_id": project_id,
                    "now": now,
                    "archived": archived,
                },
            )
    return project_id, active_id, archived_id


def _assert_connector_profile(config: Config, engine: sa.Engine, target: str) -> None:
    command.upgrade(config, target)
    _assert_revision(engine, "20260725_0005")
    with engine.connect() as connection:
        assert connection.scalar(
            sa.text(
                """
                SELECT count(*) FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'project_connector_identities'
                """
            )
        ) == 1
    command.downgrade(config, "20260429_0004")
    _assert_revision(engine, "20260429_0004")
    command.upgrade(config, target)
    _assert_revision(engine, "20260725_0005")


def _assert_temporal_state(
    engine: sa.Engine,
    *,
    project_id: uuid.UUID,
    active_id: uuid.UUID,
    archived_id: uuid.UUID,
) -> None:
    with engine.connect() as connection:
        active = connection.execute(
            sa.text(
                """
                SELECT provenance, valid_from, valid_to, history_available
                FROM memory_entries WHERE id = :id
                """
            ),
            {"id": active_id},
        ).one()
        archived = connection.execute(
            sa.text(
                """
                SELECT provenance, valid_from, valid_to, history_available
                FROM memory_entries WHERE id = :id
                """
            ),
            {"id": archived_id},
        ).one()
        assert active.provenance == "unspecified"
        assert active.valid_from is not None
        assert active.valid_to is None
        assert active.history_available is True
        assert archived.provenance == "unspecified"
        assert archived.valid_from is not None
        assert archived.valid_to is not None
        assert archived.history_available is False
        assert connection.scalar(
            sa.text(
                "SELECT count(*) FROM memory_change_feed_states WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        ) == 1
        index_names = set(
            connection.scalars(
                sa.text(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = 'memory_entries'
                    """
                )
            )
        )
        assert {
            "idx_memory_entries_temporal_current",
            "idx_memory_entries_temporal_as_of",
            "uq_memory_single_successor",
        } <= index_names


def _assert_temporal_profile(config: Config, engine: sa.Engine, target: str) -> None:
    command.upgrade(config, "20260429_0004")
    _assert_revision(engine, "20260429_0004")
    project_id, active_id, archived_id = _insert_temporal_legacy_fixtures(engine)
    command.upgrade(config, target)
    _assert_revision(engine, "20260725_0006")
    _assert_temporal_state(
        engine,
        project_id=project_id,
        active_id=active_id,
        archived_id=archived_id,
    )
    command.downgrade(config, "20260429_0004")
    _assert_revision(engine, "20260429_0004")
    command.upgrade(config, target)
    _assert_revision(engine, "20260725_0006")
    _assert_temporal_state(
        engine,
        project_id=project_id,
        active_id=active_id,
        archived_id=archived_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--fixture-profile", required=True, choices=["connector", "temporal"])
    args = parser.parse_args()

    if os.environ.get("MEMLAYER_MIGRATION_DRILL") != "1":
        raise MigrationDrillError("migration profile requires the disposable drill marker")
    database_url = os.environ.get("DATABASE_URL", "")
    validate_disposable_database_url(database_url)
    parsed = urlsplit(database_url)
    if parsed.hostname != "db":
        raise MigrationDrillError("migration profile database is not isolated")

    config = _alembic_config(database_url)
    engine = sa.create_engine(database_url)
    try:
        if args.fixture_profile == "connector":
            _assert_connector_profile(config, engine, args.target)
        else:
            _assert_temporal_profile(config, engine, args.target)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
