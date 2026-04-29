"""Add task_logs table for evaluation and experiment analytics."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_0003"
down_revision = "20260429_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()
    json_default = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("experiment_id", sa.Text(), nullable=True),
        sa.Column("group_name", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("used_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("memory_entries_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("result_quality_score", sa.Float(), nullable=True),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consistency_score", sa.Float(), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", json_type, nullable=False, server_default=json_default),
    )
    op.create_index("idx_task_logs_experiment_id", "task_logs", ["experiment_id"])
    op.create_index("idx_task_logs_group_name", "task_logs", ["group_name"])
    op.create_index("idx_task_logs_agent_id", "task_logs", ["agent_id"])
    op.create_index("idx_task_logs_created_at", "task_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_task_logs_created_at", table_name="task_logs")
    op.drop_index("idx_task_logs_agent_id", table_name="task_logs")
    op.drop_index("idx_task_logs_group_name", table_name="task_logs")
    op.drop_index("idx_task_logs_experiment_id", table_name="task_logs")
    op.drop_table("task_logs")
