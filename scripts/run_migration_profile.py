#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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


def _assert_temporal_runtime_constraints(
    engine: sa.Engine,
    *,
    project_id: uuid.UUID,
) -> None:
    now = datetime.now(timezone.utc)
    original_id = uuid.uuid4()
    first_successor_id = uuid.uuid4()
    second_successor_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_entries (
                    id, type, title, content, source_agent, project_id, importance,
                    usage_count, created_at, updated_at, last_used_at, archived,
                    metadata, search_vector, provenance, confidence, valid_from,
                    valid_to, history_available, supersedes_id
                )
                VALUES (
                    :id, 'note', 'runtime-original', 'synthetic runtime fixture',
                    'migration-drill', :project_id, 3, 0, :now, :now, NULL, TRUE,
                    '{}'::jsonb, NULL, 'observed', 0.9, :valid_from, :valid_to,
                    TRUE, NULL
                )
                """
            ),
            {
                "id": original_id,
                "project_id": project_id,
                "now": now,
                "valid_from": now - timedelta(minutes=2),
                "valid_to": now - timedelta(minutes=1),
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_entries (
                    id, type, title, content, source_agent, project_id, importance,
                    usage_count, created_at, updated_at, last_used_at, archived,
                    metadata, search_vector, provenance, confidence, valid_from,
                    valid_to, history_available, supersedes_id
                )
                VALUES (
                    :id, 'note', 'runtime-successor', 'synthetic runtime fixture',
                    'migration-drill', :project_id, 3, 0, :now, :now, NULL, FALSE,
                    '{}'::jsonb, NULL, 'observed', 0.9, :now, NULL, TRUE, :previous
                )
                """
            ),
            {
                "id": first_successor_id,
                "project_id": project_id,
                "now": now,
                "previous": original_id,
            },
        )
        try:
            with connection.begin_nested():
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO memory_entries (
                            id, type, title, content, source_agent, project_id,
                            importance, usage_count, created_at, updated_at,
                            last_used_at, archived, metadata, search_vector,
                            provenance, confidence, valid_from, valid_to,
                            history_available, supersedes_id
                        )
                        VALUES (
                            :id, 'note', 'runtime-race', 'synthetic runtime fixture',
                            'migration-drill', :project_id, 3, 0, :now, :now, NULL,
                            FALSE, '{}'::jsonb, NULL, 'observed', 0.9, :now, NULL,
                            TRUE, :previous
                        )
                        """
                    ),
                    {
                        "id": second_successor_id,
                        "project_id": project_id,
                        "now": now,
                        "previous": original_id,
                    },
                )
        except sa.exc.IntegrityError:
            pass
        else:
            raise AssertionError("single-successor race constraint did not fail closed")

        feed_epoch = connection.scalar(
            sa.text(
                "SELECT feed_epoch FROM memory_change_feed_states WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        for sequence, occurred_at in (
            (1, now + timedelta(minutes=1)),
            (2, now - timedelta(minutes=1)),
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO memory_change_events (
                        id, project_id, sequence, feed_epoch, event_kind, occurred_at,
                        normalized_tenant_key, entry_id, previous_entry_id, actor, reason
                    )
                    VALUES (
                        :id, :project_id, :sequence, :feed_epoch, 'revised',
                        :occurred_at, '__global__', :entry_id, :previous_entry_id,
                        'migration-drill', 'synthetic'
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "project_id": project_id,
                    "sequence": sequence,
                    "feed_epoch": feed_epoch,
                    "occurred_at": occurred_at,
                    "entry_id": first_successor_id,
                    "previous_entry_id": original_id,
                },
            )
        connection.execute(
            sa.text(
                "UPDATE memory_change_feed_states SET sequence = 2 WHERE project_id = :project_id"
            ),
            {"project_id": project_id},
        )
        ordered = list(
            connection.scalars(
                sa.text(
                    """
                    SELECT sequence FROM memory_change_events
                    WHERE project_id = :project_id AND feed_epoch = :feed_epoch
                    ORDER BY sequence
                    """
                ),
                {"project_id": project_id, "feed_epoch": feed_epoch},
            )
        )
        assert ordered == [1, 2]

    _assert_concurrent_temporal_writes(
        engine,
        project_id=project_id,
        feed_entry_id=first_successor_id,
    )


def _assert_concurrent_temporal_writes(
    engine: sa.Engine,
    *,
    project_id: uuid.UUID,
    feed_entry_id: uuid.UUID,
) -> None:
    now = datetime.now(timezone.utc)
    predecessor_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO memory_entries (
                    id, type, title, content, source_agent, project_id, importance,
                    usage_count, created_at, updated_at, last_used_at, archived,
                    metadata, search_vector, provenance, confidence, valid_from,
                    valid_to, history_available, supersedes_id
                )
                VALUES (
                    :id, 'note', 'concurrent-predecessor', 'synthetic runtime fixture',
                    'migration-drill', :project_id, 3, 0, :now, :now, NULL, TRUE,
                    '{}'::jsonb, NULL, 'observed', 0.9, :valid_from, :valid_to,
                    TRUE, NULL
                )
                """
            ),
            {
                "id": predecessor_id,
                "project_id": project_id,
                "now": now,
                "valid_from": now - timedelta(minutes=2),
                "valid_to": now - timedelta(minutes=1),
            },
        )

    revision_barrier = threading.Barrier(2)

    def insert_successor(worker: int) -> str:
        try:
            with engine.begin() as connection:
                revision_barrier.wait(timeout=10)
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO memory_entries (
                            id, type, title, content, source_agent, project_id,
                            importance, usage_count, created_at, updated_at,
                            last_used_at, archived, metadata, search_vector,
                            provenance, confidence, valid_from, valid_to,
                            history_available, supersedes_id
                        )
                        VALUES (
                            :id, 'note', :title, 'synthetic concurrent fixture',
                            'migration-drill', :project_id, 3, 0, :now, :now, NULL,
                            FALSE, '{}'::jsonb, NULL, 'observed', 0.9, :now, NULL,
                            TRUE, :previous
                        )
                        """
                    ),
                    {
                        "id": uuid.uuid4(),
                        "title": f"concurrent-successor-{worker}",
                        "project_id": project_id,
                        "now": now + timedelta(seconds=worker),
                        "previous": predecessor_id,
                    },
                )
            return "committed"
        except sa.exc.IntegrityError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        revision_results = list(executor.map(insert_successor, (1, 2)))
    if sorted(revision_results) != ["committed", "conflict"]:
        raise AssertionError(
            f"concurrent single-successor race did not fail closed: {revision_results}"
        )

    sequence_barrier = threading.Barrier(2)

    def allocate_event(worker: int) -> int:
        with engine.begin() as connection:
            sequence_barrier.wait(timeout=10)
            sequence = connection.scalar(
                sa.text(
                    """
                    UPDATE memory_change_feed_states
                    SET sequence = sequence + 1
                    WHERE project_id = :project_id
                    RETURNING sequence
                    """
                ),
                {"project_id": project_id},
            )
            feed_epoch = connection.scalar(
                sa.text(
                    """
                    SELECT feed_epoch FROM memory_change_feed_states
                    WHERE project_id = :project_id
                    """
                ),
                {"project_id": project_id},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO memory_change_events (
                        id, project_id, sequence, feed_epoch, event_kind, occurred_at,
                        normalized_tenant_key, entry_id, previous_entry_id, actor, reason
                    )
                    VALUES (
                        :id, :project_id, :sequence, :feed_epoch, 'revised', :occurred_at,
                        '__global__', :entry_id, NULL, 'migration-drill', :reason
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "project_id": project_id,
                    "sequence": sequence,
                    "feed_epoch": feed_epoch,
                    "occurred_at": now - timedelta(minutes=worker),
                    "entry_id": feed_entry_id,
                    "reason": f"concurrent-worker-{worker}",
                },
            )
            return int(sequence)

    with ThreadPoolExecutor(max_workers=2) as executor:
        allocated = list(executor.map(allocate_event, (1, 2)))
    if sorted(allocated) != [3, 4]:
        raise AssertionError(f"concurrent feed allocation failed: {allocated}")
    with engine.connect() as connection:
        sequence = connection.scalar(
            sa.text(
                """
                SELECT sequence FROM memory_change_feed_states
                WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id},
        )
        if sequence != 4:
            raise AssertionError(f"unexpected feed high watermark: {sequence}")


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
    _assert_temporal_runtime_constraints(engine, project_id=project_id)
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
