from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models.enums import MemoryLinkType, MemoryType
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository


@dataclass
class CompactionCluster:
    entry_ids: list[uuid.UUID]
    project_id: uuid.UUID | None
    representative_titles: list[str]
    types: dict[str, int]
    suggested_title: str
    suggested_content: str


class CompactionService:
    def __init__(self, memory_repository: MemoryRepository, link_repository: LinkRepository):
        self.memory_repository = memory_repository
        self.link_repository = link_repository

    def preview(
        self,
        *,
        project_id: uuid.UUID | None = None,
        stale_days: int = 21,
        min_entries: int = 4,
        max_entries: int = 12,
        min_overlap_tokens: int = 2,
    ) -> list[CompactionCluster]:
        candidates = self._candidate_entries(project_id=project_id, stale_days=stale_days)
        return self._build_clusters(
            candidates,
            min_entries=min_entries,
            max_entries=max_entries,
            min_overlap_tokens=min_overlap_tokens,
        )

    def apply(
        self,
        *,
        entry_ids: list[uuid.UUID],
        archive_originals: bool = True,
    ) -> dict:
        entries = [self.memory_repository.get(entry_id) for entry_id in entry_ids]
        items = [entry for entry in entries if entry is not None]
        if len(items) < 2:
            raise ValueError("At least two valid entries are required for compaction")

        summary_payload = self._build_summary(items)
        summary_entry = MemoryEntry(
            type=MemoryType.note,
            title=summary_payload["title"],
            content=summary_payload["content"],
            source_agent="memlayer-compaction",
            project_id=items[0].project_id,
            importance=summary_payload["importance"],
            metadata_=summary_payload["metadata"],
            search_vector=None if self.memory_repository.is_postgresql() else f"{summary_payload['title']} {summary_payload['content']}",
        )
        created = self.memory_repository.create(summary_entry)
        self.memory_repository.sync_search_vector(created, f"{created.title or ''} {created.content}".strip())

        linked_ids: list[uuid.UUID] = []
        archived_ids: list[uuid.UUID] = []
        for item in items:
            link = self.link_repository.find_by_pair(item.id, created.id, MemoryLinkType.derived_from)
            if not link:
                self.link_repository.create(
                    MemoryLink(
                        from_entry_id=item.id,
                        to_entry_id=created.id,
                        type=MemoryLinkType.derived_from,
                        strength=1.0,
                        created_by_agent="memlayer-compaction",
                        metadata_={"compaction": True},
                    )
                )
            linked_ids.append(item.id)
            metadata = dict(item.metadata_ or {})
            metadata["compacted_into_entry_id"] = str(created.id)
            metadata["compaction_applied_at"] = datetime.now(timezone.utc).isoformat()
            item.metadata_ = metadata
            if archive_originals:
                item.archived = True
                archived_ids.append(item.id)
            self.memory_repository.db.add(item)

        self.memory_repository.db.flush()
        self.memory_repository.db.refresh(created)
        return {
            "summary_entry_id": created.id,
            "linked_entry_ids": linked_ids,
            "archived_entry_ids": archived_ids,
            "archived_originals": archive_originals,
        }

    def _candidate_entries(self, *, project_id: uuid.UUID | None, stale_days: int) -> list[MemoryEntry]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        items = self.memory_repository.list(project_id=project_id, archived=False)
        candidates: list[MemoryEntry] = []
        for entry in items:
            if entry.type in {MemoryType.decision, MemoryType.constraint, MemoryType.risk}:
                continue
            if entry.importance > 3 or entry.usage_count > 1:
                continue
            if isinstance(entry.metadata_, dict) and entry.metadata_.get("compaction"):
                continue
            anchor_time = entry.last_used_at or entry.created_at
            if anchor_time.tzinfo is None:
                anchor_time = anchor_time.replace(tzinfo=timezone.utc)
            if anchor_time >= cutoff:
                continue
            candidates.append(entry)
        return candidates

    def _build_clusters(
        self,
        entries: list[MemoryEntry],
        *,
        min_entries: int,
        max_entries: int,
        min_overlap_tokens: int,
    ) -> list[CompactionCluster]:
        remaining = list(entries)
        clusters: list[CompactionCluster] = []
        while remaining:
            seed = remaining.pop(0)
            seed_tokens = self._tokens(seed)
            cluster = [seed]
            leftovers: list[MemoryEntry] = []
            for candidate in remaining:
                overlap = len(seed_tokens & self._tokens(candidate))
                if candidate.project_id == seed.project_id and overlap >= min_overlap_tokens and len(cluster) < max_entries:
                    cluster.append(candidate)
                else:
                    leftovers.append(candidate)
            remaining = leftovers
            if len(cluster) >= min_entries:
                clusters.append(self._cluster_from_entries(cluster))
        return clusters

    def _cluster_from_entries(self, entries: list[MemoryEntry]) -> CompactionCluster:
        types = Counter(item.type.value for item in entries)
        titles = [item.title for item in entries if item.title][:10]
        summary = self._build_summary(entries)
        return CompactionCluster(
            entry_ids=[item.id for item in entries],
            project_id=entries[0].project_id,
            representative_titles=titles,
            types=dict(types),
            suggested_title=summary["title"],
            suggested_content=summary["content"],
        )

    def _build_summary(self, entries: list[MemoryEntry]) -> dict:
        types = Counter(item.type.value for item in entries)
        titles = [item.title for item in entries if item.title][:10]
        body = "\n".join(f"- {item.type.value}: {item.title or item.content[:80]}" for item in entries[:25])
        return {
            "title": f"Compacted memory summary: {', '.join(types.keys())}",
            "content": (
                "This entry summarizes a cluster of related memory entries.\n\n"
                f"Entry count: {len(entries)}\n"
                f"Types: {dict(types)}\n\n"
                "Representative items:\n"
                f"{body}\n\n"
                "Original entries are linked with derived_from and marked as compacted."
            ),
            "importance": max([item.importance for item in entries] + [3]),
            "metadata": {
                "compaction": True,
                "source_entry_ids": [str(item.id) for item in entries],
                "representative_titles": titles,
            },
        }

    @staticmethod
    def _tokens(entry: MemoryEntry) -> set[str]:
        text = f"{entry.title or ''} {entry.content}".lower()
        tokens = {token.strip(".,:;!?()[]{}") for token in text.split()}
        return {token for token in tokens if len(token) >= 4}
