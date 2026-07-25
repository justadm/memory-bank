from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectConnectorIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_connector_identities"
    __table_args__ = (
        UniqueConstraint(
            "agent",
            "normalized_tenant_key",
            "connector_identity",
            name="uq_project_connector_identity",
        ),
    )

    agent: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_tenant_key: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_identity: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
