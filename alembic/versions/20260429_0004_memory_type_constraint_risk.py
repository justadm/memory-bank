"""Add constraint and risk memory types."""

from alembic import op


revision = "20260429_0004"
down_revision = "20260429_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE memorytype ADD VALUE IF NOT EXISTS 'constraint'")
        op.execute("ALTER TYPE memorytype ADD VALUE IF NOT EXISTS 'risk'")


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted.
    pass
