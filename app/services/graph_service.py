import uuid

from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.repositories.link_repository import LinkRepository


class GraphService:
    def __init__(self, link_repository: LinkRepository):
        self.link_repository = link_repository

    def get_graph(self, entry_id: uuid.UUID, depth: int) -> tuple[list[MemoryEntry], list[MemoryLink]]:
        return self.link_repository.get_graph(entry_id=entry_id, depth=depth)

