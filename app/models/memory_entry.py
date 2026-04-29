import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.sql.sqltypes import Text as SqlText

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MemoryType


class MemoryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_entries"

    type: Mapped[MemoryType] = mapped_column(Enum(MemoryType, native_enum=False), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    importance: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    search_vector: Mapped[str | None] = mapped_column(SqlText().with_variant(TSVECTOR, "postgresql"), nullable=True)

    project = relationship("Project", back_populates="memory_entries")
    outgoing_links = relationship(
        "MemoryLink",
        back_populates="from_entry",
        foreign_keys="MemoryLink.from_entry_id",
        cascade="all, delete-orphan",
    )
    incoming_links = relationship(
        "MemoryLink",
        back_populates="to_entry",
        foreign_keys="MemoryLink.to_entry_id",
        cascade="all, delete-orphan",
    )
    access_logs = relationship("MemoryAccessLog", back_populates="entry", cascade="all, delete-orphan")
