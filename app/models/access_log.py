import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MemoryAccessLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_access_logs"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    entry = relationship("MemoryEntry", back_populates="access_logs")

