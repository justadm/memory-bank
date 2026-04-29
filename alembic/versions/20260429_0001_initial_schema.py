"""Initial schema for Memory Bank MVP."""

from alembic import op
import sqlalchemy as sa


revision = "20260429_0001"
down_revision = None
branch_labels = None
depends_on = None


memory_type_enum = sa.Enum("decision", "task", "artifact", "event", "note", name="memorytype")
link_type_enum = sa.Enum(
    "depends_on",
    "related_to",
    "created_after",
    "affects",
    "derived_from",
    "blocks",
    "resolves",
    name="memorylinktype",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    memory_type_enum.create(bind, checkfirst=True)
    link_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("type", memory_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_agent", sa.String(length=100), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("search_vector", sa.Text(), nullable=True),
    )

    op.create_table(
        "memory_links",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("from_entry_id", sa.Uuid(), sa.ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_entry_id", sa.Uuid(), sa.ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", link_type_enum, nullable=False),
        sa.Column("strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_agent", sa.String(length=100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("from_entry_id", "to_entry_id", "type", name="uq_memory_link"),
    )

    op.create_table(
        "memory_access_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("entry_id", sa.Uuid(), sa.ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(length=100), nullable=True),
        sa.Column("task_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_index("idx_memory_entries_type", "memory_entries", ["type"])
    op.create_index("idx_memory_entries_project_id", "memory_entries", ["project_id"])
    op.create_index("idx_memory_entries_archived", "memory_entries", ["archived"])
    op.create_index("idx_memory_entries_created_at", "memory_entries", ["created_at"])
    op.create_index("idx_memory_entries_last_used_at", "memory_entries", ["last_used_at"])
    op.create_index("idx_memory_entries_metadata", "memory_entries", ["metadata"])
    op.create_index("idx_memory_entries_search_vector", "memory_entries", ["search_vector"])
    op.create_index("idx_memory_links_from", "memory_links", ["from_entry_id"])
    op.create_index("idx_memory_links_to", "memory_links", ["to_entry_id"])
    op.create_index("idx_memory_links_type", "memory_links", ["type"])


def downgrade() -> None:
    op.drop_index("idx_memory_links_type", table_name="memory_links")
    op.drop_index("idx_memory_links_to", table_name="memory_links")
    op.drop_index("idx_memory_links_from", table_name="memory_links")
    op.drop_index("idx_memory_entries_search_vector", table_name="memory_entries")
    op.drop_index("idx_memory_entries_metadata", table_name="memory_entries")
    op.drop_index("idx_memory_entries_last_used_at", table_name="memory_entries")
    op.drop_index("idx_memory_entries_created_at", table_name="memory_entries")
    op.drop_index("idx_memory_entries_archived", table_name="memory_entries")
    op.drop_index("idx_memory_entries_project_id", table_name="memory_entries")
    op.drop_index("idx_memory_entries_type", table_name="memory_entries")
    op.drop_table("memory_access_logs")
    op.drop_table("memory_links")
    op.drop_table("memory_entries")
    op.drop_table("projects")
    bind = op.get_bind()
    link_type_enum.drop(bind, checkfirst=True)
    memory_type_enum.drop(bind, checkfirst=True)

