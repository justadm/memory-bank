import uuid
from collections import deque

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink


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

    def delete(self, link: MemoryLink) -> None:
        self.db.delete(link)

    def get_for_entry(self, entry_id: uuid.UUID) -> tuple[list[MemoryLink], list[MemoryLink]]:
        outgoing = list(
            self.db.scalars(select(MemoryLink).where(MemoryLink.from_entry_id == entry_id).order_by(MemoryLink.created_at))
        )
        incoming = list(
            self.db.scalars(select(MemoryLink).where(MemoryLink.to_entry_id == entry_id).order_by(MemoryLink.created_at))
        )
        return outgoing, incoming

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

        nodes = list(self.db.scalars(select(MemoryEntry).where(MemoryEntry.id.in_(visited))))
        edges = list(self.db.scalars(select(MemoryLink).where(MemoryLink.id.in_(edge_ids))))
        return nodes, edges

