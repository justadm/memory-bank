"""Add temporal memory fields and project change feeds."""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260725_0006"
down_revision = "20260725_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("memory_entries", sa.Column("provenance", sa.String(length=40), nullable=True))
    op.add_column("memory_entries", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("memory_entries", sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memory_entries", sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memory_entries", sa.Column("history_available", sa.Boolean(), nullable=True))
    op.add_column("memory_entries", sa.Column("supersedes_id", sa.Uuid(), nullable=True))
    migration_cutover_at = bind.scalar(sa.text("SELECT CURRENT_TIMESTAMP"))
    op.execute(sa.text("UPDATE memory_entries SET provenance = 'unspecified' WHERE provenance IS NULL"))
    bind.execute(
        sa.text(
            """
            UPDATE memory_entries
            SET valid_from = created_at,
                valid_to = NULL,
                history_available = TRUE
            WHERE archived = FALSE
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE memory_entries
            SET valid_from = created_at,
                valid_to = :migration_cutover_at,
                history_available = FALSE
            WHERE archived = TRUE
            """
        ),
        {"migration_cutover_at": migration_cutover_at},
    )
    if bind.dialect.name != "sqlite":
        op.alter_column("memory_entries", "provenance", nullable=False)
        op.alter_column("memory_entries", "valid_from", nullable=False)
        op.alter_column("memory_entries", "history_available", nullable=False)
        op.create_foreign_key(
            "fk_memory_entries_supersedes_id",
            "memory_entries",
            "memory_entries",
            ["supersedes_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_check_constraint(
            "ck_memory_confidence",
            "memory_entries",
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
        )
        op.create_check_constraint(
            "ck_memory_valid_interval",
            "memory_entries",
            "valid_to IS NULL OR valid_to > valid_from",
        )
        op.create_check_constraint(
            "ck_memory_no_self_successor",
            "memory_entries",
            "supersedes_id IS NULL OR supersedes_id <> id",
        )
    if bind.dialect.name == "postgresql":
        op.create_index(
            "idx_memory_entries_temporal_current",
            "memory_entries",
            ["project_id", "valid_from"],
            postgresql_where=sa.text("archived = FALSE AND valid_to IS NULL"),
        )
        op.create_index(
            "idx_memory_entries_temporal_as_of",
            "memory_entries",
            ["project_id", "valid_from", "valid_to"],
            postgresql_where=sa.text("history_available = TRUE"),
        )
        op.create_index(
            "uq_memory_single_successor",
            "memory_entries",
            ["supersedes_id"],
            unique=True,
            postgresql_where=sa.text("supersedes_id IS NOT NULL"),
        )
    else:
        op.create_index(
            "idx_memory_entries_temporal_current",
            "memory_entries",
            ["project_id", "valid_from", "valid_to", "archived"],
        )
        op.create_index(
            "idx_memory_entries_temporal_as_of",
            "memory_entries",
            ["project_id", "history_available", "valid_from", "valid_to"],
        )
        op.create_index(
            "uq_memory_single_successor",
            "memory_entries",
            ["supersedes_id"],
            unique=True,
            sqlite_where=sa.text("supersedes_id IS NOT NULL"),
        )

    op.create_table(
        "memory_change_feed_states",
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("feed_epoch", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "memory_change_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("feed_epoch", sa.Uuid(), nullable=False),
        sa.Column("event_kind", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_tenant_key", sa.String(length=255), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column("previous_entry_id", sa.Uuid(), nullable=True),
        sa.Column("restored_from_entry_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "project_id",
            "feed_epoch",
            "sequence",
            name="uq_memory_change_event_sequence",
        ),
    )
    op.create_index("idx_memory_change_events_project_sequence", "memory_change_events", ["project_id", "sequence"])
    project_rows = bind.execute(sa.text("SELECT id FROM projects")).all()
    for row in project_rows:
        op.bulk_insert(
            sa.table(
                "memory_change_feed_states",
                sa.column("project_id", sa.Uuid()),
                sa.column("feed_epoch", sa.Uuid()),
                sa.column("sequence", sa.Integer()),
                sa.column("created_at", sa.DateTime(timezone=True)),
                sa.column("updated_at", sa.DateTime(timezone=True)),
            ),
            [{
                "project_id": uuid.UUID(str(row[0])),
                "feed_epoch": uuid.uuid4(),
                "sequence": 0,
                "created_at": migration_cutover_at,
                "updated_at": migration_cutover_at,
            }],
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("idx_memory_change_events_project_sequence", table_name="memory_change_events")
    op.drop_table("memory_change_events")
    op.drop_table("memory_change_feed_states")
    op.drop_index("uq_memory_single_successor", table_name="memory_entries")
    op.drop_index("idx_memory_entries_temporal_as_of", table_name="memory_entries")
    op.drop_index("idx_memory_entries_temporal_current", table_name="memory_entries")
    if bind.dialect.name != "sqlite":
        op.drop_constraint("ck_memory_no_self_successor", "memory_entries", type_="check")
        op.drop_constraint("ck_memory_valid_interval", "memory_entries", type_="check")
        op.drop_constraint("ck_memory_confidence", "memory_entries", type_="check")
        op.drop_constraint("fk_memory_entries_supersedes_id", "memory_entries", type_="foreignkey")
    op.drop_column("memory_entries", "supersedes_id")
    op.drop_column("memory_entries", "history_available")
    op.drop_column("memory_entries", "valid_to")
    op.drop_column("memory_entries", "valid_from")
    op.drop_column("memory_entries", "confidence")
    op.drop_column("memory_entries", "provenance")
