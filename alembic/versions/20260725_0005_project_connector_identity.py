"""Add idempotent project connector identities."""

from alembic import op
import sqlalchemy as sa


revision = "20260725_0005"
down_revision = "20260429_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_connector_identities",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("agent", sa.String(length=50), nullable=False),
        sa.Column("normalized_tenant_key", sa.String(length=255), nullable=False),
        sa.Column("connector_identity", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "agent",
            "normalized_tenant_key",
            "connector_identity",
            name="uq_project_connector_identity",
        ),
    )
    op.create_index(
        "idx_project_connector_identity_project_id",
        "project_connector_identities",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_project_connector_identity_project_id",
        table_name="project_connector_identities",
    )
    op.drop_table("project_connector_identities")
