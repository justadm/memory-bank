"""Convert search_vector to PostgreSQL tsvector and rebuild search index."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("idx_memory_entries_search_vector", table_name="memory_entries")
    op.execute(
        """
        ALTER TABLE memory_entries
        ALTER COLUMN search_vector TYPE tsvector
        USING to_tsvector(
            'english',
            coalesce(search_vector, concat_ws(' ', coalesce(title, ''), content))
        )
        """
    )
    op.execute(
        """
        UPDATE memory_entries
        SET search_vector = to_tsvector('english', concat_ws(' ', coalesce(title, ''), content))
        """
    )
    op.create_index(
        "idx_memory_entries_search_vector",
        "memory_entries",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("idx_memory_entries_search_vector", table_name="memory_entries")
    op.alter_column(
        "memory_entries",
        "search_vector",
        type_=sa.Text(),
        postgresql_using="search_vector::text",
    )
    op.create_index("idx_memory_entries_search_vector", "memory_entries", ["search_vector"])
