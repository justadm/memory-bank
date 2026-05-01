from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository


@dataclass
class LifecycleRunResult:
    quality_decayed_count: int
    review_overdue_marked_count: int
    archived_count: int
    weak_links_deleted_count: int
    archived_ids: list[uuid.UUID]
    review_overdue_ids: list[uuid.UUID]
    weak_link_ids: list[uuid.UUID]
    dry_run: bool


class LifecycleService:
    def __init__(self, memory_repository: MemoryRepository, link_repository: LinkRepository):
        self.memory_repository = memory_repository
        self.link_repository = link_repository

    def run(
        self,
        *,
        stale_days: int = 21,
        review_overdue_days: int = 14,
        weak_link_days: int = 30,
        low_quality_threshold: float = 0.25,
        weak_link_strength_threshold: float = 0.35,
        decay_amount: float = 0.03,
        dry_run: bool = False,
    ) -> LifecycleRunResult:
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=stale_days)
        review_cutoff = now - timedelta(days=review_overdue_days)
        weak_link_cutoff = now - timedelta(days=weak_link_days)

        entries = self.memory_repository.list(archived=None)
        quality_decay_candidates: list[MemoryEntry] = []
        review_overdue_candidates: list[MemoryEntry] = []
        archive_candidates: list[MemoryEntry] = []

        for entry in entries:
            metadata = dict(entry.metadata_ or {})
            quality = metadata.get("quality", {})
            quality_score = float(quality.get("score", 0.0) or 0.0)
            anchor_time = entry.last_used_at or entry.created_at
            if anchor_time and anchor_time.tzinfo is None:
                anchor_time = anchor_time.replace(tzinfo=timezone.utc)
            created_at = entry.created_at
            if created_at and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            if (
                not entry.archived
                and entry.type in {MemoryType.note, MemoryType.event}
                and entry.importance <= 2
                and anchor_time
                and anchor_time < stale_cutoff
            ):
                quality_decay_candidates.append(entry)
                quality_score = max(0.0, quality_score - decay_amount)

            if (
                not entry.archived
                and metadata.get("requires_review") is True
                and created_at
                and created_at < review_cutoff
                and metadata.get("review_overdue") is not True
            ):
                review_overdue_candidates.append(entry)

            if (
                not entry.archived
                and quality_score < low_quality_threshold
                and entry.importance <= 2
                and entry.usage_count <= 1
                and entry.type not in {MemoryType.decision, MemoryType.constraint}
            ):
                archive_candidates.append(entry)

        weak_links = self.link_repository.list_weak_links(
            older_than=weak_link_cutoff,
            strength_threshold=weak_link_strength_threshold,
        )

        if not dry_run:
            for entry in quality_decay_candidates:
                metadata = dict(entry.metadata_ or {})
                quality = dict(metadata.get("quality", {}))
                current_score = float(quality.get("score", 0.0) or 0.0)
                quality["score"] = round(max(0.0, current_score - decay_amount), 3)
                quality["decayed_at"] = now.isoformat()
                metadata["quality"] = quality
                entry.metadata_ = metadata
                self.memory_repository.db.add(entry)

            for entry in review_overdue_candidates:
                metadata = dict(entry.metadata_ or {})
                metadata["review_overdue"] = True
                entry.metadata_ = metadata
                self.memory_repository.db.add(entry)

            archive_ids = {entry.id for entry in archive_candidates}
            for entry in entries:
                if entry.id in archive_ids:
                    entry.archived = True
                    self.memory_repository.db.add(entry)

            for link in weak_links:
                self.link_repository.delete(link)

            self.memory_repository.db.flush()

        return LifecycleRunResult(
            quality_decayed_count=len(quality_decay_candidates),
            review_overdue_marked_count=len(review_overdue_candidates),
            archived_count=len(archive_candidates),
            weak_links_deleted_count=len(weak_links),
            archived_ids=[item.id for item in archive_candidates],
            review_overdue_ids=[item.id for item in review_overdue_candidates],
            weak_link_ids=[item.id for item in weak_links],
            dry_run=dry_run,
        )
