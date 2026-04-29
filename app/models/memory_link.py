import uuid

from sqlalchemy import JSON, Enum, Float, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MemoryLinkType


class MemoryLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_links"
    __table_args__ = (UniqueConstraint("from_entry_id", "to_entry_id", "type", name="uq_memory_link"),)

    from_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    to_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("memory_entries.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[MemoryLinkType] = mapped_column(Enum(MemoryLinkType, native_enum=False), nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_by_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    from_entry = relationship("MemoryEntry", foreign_keys=[from_entry_id], back_populates="outgoing_links")
    to_entry = relationship("MemoryEntry", foreign_keys=[to_entry_id], back_populates="incoming_links")

