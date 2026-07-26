import uuid
from collections import deque
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import MemoryLinkType
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.repositories.memory_repository import MemoryRepository


class LinkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, link: MemoryLink) -> MemoryLink:
        self.db.add(link)
        self.db.flush()
        self.db.refresh(link)
        return link

    def get(self, link_id: uuid.UUID) -> MemoryLink | None:
        return self.db.get(MemoryLink, link_id)

    def find_by_pair(
        self, from_entry_id: uuid.UUID, to_entry_id: uuid.UUID, link_type: MemoryLinkType
    ) -> MemoryLink | None:
        stmt = select(MemoryLink).where(
            MemoryLink.from_entry_id == from_entry_id,
            MemoryLink.to_entry_id == to_entry_id,
            MemoryLink.type == link_type,
        )
        return self.db.scalar(stmt)

    def delete(self, link: MemoryLink) -> None:
        self.db.delete(link)

    def list_weak_links(self, *, older_than: datetime, strength_threshold: float) -> list[MemoryLink]:
        stmt = select(MemoryLink).where(
            MemoryLink.strength < strength_threshold,
            MemoryLink.created_at < older_than,
        )
        return list(self.db.scalars(stmt))

    def get_for_entry(self, entry_id: uuid.UUID) -> tuple[list[MemoryLink], list[MemoryLink]]:
        outgoing = list(
            self.db.scalars(select(MemoryLink).where(MemoryLink.from_entry_id == entry_id).order_by(MemoryLink.created_at))
        )
        incoming = list(
            self.db.scalars(select(MemoryLink).where(MemoryLink.to_entry_id == entry_id).order_by(MemoryLink.created_at))
        )
        return outgoing, incoming

    def inherit_for_revision(
        self,
        *,
        previous_entry_id: uuid.UUID,
        revision_entry_id: uuid.UUID,
        inherited_at: datetime,
    ) -> list[MemoryLink]:
        outgoing, incoming = self.get_for_entry(previous_entry_id)
        created: list[MemoryLink] = []
        seen: set[tuple[uuid.UUID, uuid.UUID, MemoryLinkType]] = set()
        for original, outgoing_side in [
            *((item, True) for item in outgoing),
            *((item, False) for item in incoming),
        ]:
            from_id = revision_entry_id if outgoing_side else original.from_entry_id
            to_id = original.to_entry_id if outgoing_side else revision_entry_id
            if from_id == to_id:
                continue
            key = (from_id, to_id, original.type)
            if key in seen or self.find_by_pair(*key):
                continue
            seen.add(key)
            metadata = dict(original.metadata_ or {})
            metadata.update(
                {
                    "inherited_from_link_id": str(original.id),
                    "inherited_at": inherited_at.astimezone(timezone.utc).isoformat(),
                    "revision_id": str(revision_entry_id),
                }
            )
            link = MemoryLink(
                from_entry_id=from_id,
                to_entry_id=to_id,
                type=original.type,
                strength=original.strength,
                created_by_agent=original.created_by_agent,
                metadata_=metadata,
            )
            self.db.add(link)
            created.append(link)
        self.db.flush()
        return created

    def get_graph(self, entry_id: uuid.UUID, depth: int) -> tuple[list[MemoryEntry], list[MemoryLink]]:
        visited = {entry_id}
        queue = deque([(entry_id, 0)])
        edge_ids: set[uuid.UUID] = set()

        while queue:
            current_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            links = list(
                self.db.scalars(
                    select(MemoryLink).where(
                        or_(MemoryLink.from_entry_id == current_id, MemoryLink.to_entry_id == current_id)
                    )
                )
            )
            for link in links:
                edge_ids.add(link.id)
                for next_id in (link.from_entry_id, link.to_entry_id):
                    if next_id not in visited:
                        visited.add(next_id)
                        queue.append((next_id, current_depth + 1))

        nodes = list(
            self.db.scalars(
                select(MemoryEntry).where(
                    MemoryEntry.id.in_(visited),
                    MemoryRepository.current_predicate(),
                )
            )
        )
        edges = list(self.db.scalars(select(MemoryLink).where(MemoryLink.id.in_(edge_ids))))
        return nodes, edges
