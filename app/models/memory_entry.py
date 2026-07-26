import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.sql.sqltypes import Text as SqlText

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MemoryProvenance, MemoryType


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
    provenance: Mapped[MemoryProvenance] = mapped_column(
        Enum(MemoryProvenance, native_enum=False), default=MemoryProvenance.unspecified, nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("memory_entries.id", ondelete="RESTRICT"), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False
    )
    search_vector: Mapped[str | None] = mapped_column(SqlText().with_variant(TSVECTOR, "postgresql"), nullable=True)

    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)", name="ck_memory_confidence"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="ck_memory_valid_interval"),
        CheckConstraint("supersedes_id IS NULL OR supersedes_id <> id", name="ck_memory_no_self_successor"),
        Index(
            "uq_memory_single_successor",
            "supersedes_id",
            unique=True,
            sqlite_where=text("supersedes_id IS NOT NULL"),
            postgresql_where=text("supersedes_id IS NOT NULL"),
        ),
        Index(
            "idx_memory_entries_temporal_current",
            "project_id",
            "valid_from",
            "valid_to",
            "archived",
        ),
        Index(
            "idx_memory_entries_temporal_as_of",
            "project_id",
            "history_available",
            "valid_from",
            "valid_to",
        ),
    )

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
