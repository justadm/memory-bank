from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.access_log import MemoryAccessLog
from app.models.memory_entry import MemoryEntry
from app.models.enums import MemoryType


class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, entry: MemoryEntry) -> MemoryEntry:
        self.db.add(entry)
        self.db.flush()
        self.db.refresh(entry)
        return entry

    def is_postgresql(self) -> bool:
        return bool(self.db.bind and self.db.bind.dialect.name == "postgresql")

    def get(self, entry_id: uuid.UUID) -> MemoryEntry | None:
        return self.db.get(MemoryEntry, entry_id)

    def list(
        self,
        *,
        project_id: uuid.UUID | None = None,
        memory_type: MemoryType | None = None,
        archived: bool | None = None,
    ) -> list[MemoryEntry]:
        stmt = select(MemoryEntry).order_by(MemoryEntry.created_at.desc())
        if project_id:
            stmt = stmt.where(MemoryEntry.project_id == project_id)
        if memory_type:
            stmt = stmt.where(MemoryEntry.type == memory_type)
        if archived is not None:
            stmt = stmt.where(MemoryEntry.archived == archived)
        return list(self.db.scalars(stmt))

    def search(
        self,
        *,
        query: str,
        project_id: uuid.UUID | None = None,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        include_archived: bool = False,
    ) -> list[tuple[MemoryEntry, float]]:
        stmt: Select[tuple[MemoryEntry]] = select(MemoryEntry)
        if not include_archived:
            stmt = stmt.where(MemoryEntry.archived.is_(False))
        if project_id:
            stmt = stmt.where(MemoryEntry.project_id == project_id)
        if types:
            stmt = stmt.where(MemoryEntry.type.in_(types))

        dialect = self.db.bind.dialect.name if self.db.bind else "unknown"
        if dialect == "postgresql":
            ts_query = func.plainto_tsquery("english", query)
            rank = func.ts_rank(MemoryEntry.search_vector, ts_query)
            stmt = (
                stmt.add_columns(rank.label("score"))
                .where(MemoryEntry.search_vector.is_not(None), MemoryEntry.search_vector.op("@@")(ts_query))
                .order_by(rank.desc(), MemoryEntry.created_at.desc())
                .limit(limit)
            )
            return [(entry, float(score or 0.0)) for entry, score in self.db.execute(stmt).all()]

        pattern = f"%{query.strip()}%"
        stmt = (
            stmt.where(or_(MemoryEntry.title.ilike(pattern), MemoryEntry.content.ilike(pattern)))
            .order_by(MemoryEntry.importance.desc(), MemoryEntry.created_at.desc())
            .limit(limit)
        )
        items = list(self.db.scalars(stmt))
        return [(entry, self._fallback_score(entry, query)) for entry in items]

    def _fallback_score(self, entry: MemoryEntry, query: str) -> float:
        haystack = f"{entry.title or ''} {entry.content}".lower()
        words = [part for part in query.lower().split() if part]
        if not words:
            return 0.0
        matched = sum(1 for word in words if word in haystack)
        text_match_score = matched / len(words)
        importance_score = entry.importance / 5
        usage_score = min(1.0, math.log(entry.usage_count + 1, 10))
        recency_score = self._recency_score(entry.updated_at or entry.created_at)
        return text_match_score * 0.6 + importance_score * 0.2 + recency_score * 0.1 + usage_score * 0.1

    def increment_usage(self, entry: MemoryEntry) -> None:
        entry.usage_count += 1
        entry.last_used_at = datetime.now(timezone.utc)
        self.db.add(entry)

    def sync_search_vector(self, entry: MemoryEntry, payload: str) -> None:
        dialect = self.db.bind.dialect.name if self.db.bind else "unknown"
        if dialect == "postgresql":
            self.db.query(MemoryEntry).filter(MemoryEntry.id == entry.id).update(
                {"search_vector": func.to_tsvector("english", payload)},
                synchronize_session=False,
            )
            self.db.flush()
            self.db.refresh(entry)
            return

        entry.search_vector = payload
        self.db.add(entry)
        self.db.flush()
        self.db.refresh(entry)

    def rebuild_search_vectors(self, *, project_id: uuid.UUID | None = None) -> int:
        items = self.list(project_id=project_id, archived=None)
        for item in items:
            payload = f"{item.title or ''} {item.content}".strip()
            self.sync_search_vector(item, payload)
        return len(items)

    def add_access_log(self, log: MemoryAccessLog) -> MemoryAccessLog:
        self.db.add(log)
        self.db.flush()
        self.db.refresh(log)
        return log

    def archive_stale(
        self, *, older_than_days: int, max_usage_count: int, max_importance: int
    ) -> list[MemoryEntry]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        stmt = select(MemoryEntry).where(
            MemoryEntry.archived.is_(False),
            MemoryEntry.created_at < cutoff,
            MemoryEntry.usage_count <= max_usage_count,
            MemoryEntry.importance <= max_importance,
            ~((MemoryEntry.type == MemoryType.decision) & (MemoryEntry.importance >= 4)),
        )
        items = list(self.db.scalars(stmt))
        for item in items:
            item.archived = True
            self.db.add(item)
        return items

    @staticmethod
    def _recency_score(moment: datetime | None) -> float:
        if not moment:
            return 0.0
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - moment).days, 0)
        return max(0.0, 1 - min(age_days / 365, 1))
