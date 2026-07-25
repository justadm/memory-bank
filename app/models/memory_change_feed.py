from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MemoryChangeEventKind


class MemoryChangeFeedState(TimestampMixin, Base):
    __tablename__ = "memory_change_feed_states"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    feed_epoch: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MemoryChangeEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "memory_change_events"
    __table_args__ = (Index("uq_memory_change_event_sequence", "project_id", "sequence", unique=True),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    feed_epoch: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    event_kind: Mapped[MemoryChangeEventKind] = mapped_column(
        Enum(MemoryChangeEventKind, native_enum=False), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    normalized_tenant_key: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    previous_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
