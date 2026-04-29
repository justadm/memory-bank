import uuid

from app.models.memory_entry import MemoryEntry
from app.models.enums import MemoryType
from app.repositories.memory_repository import MemoryRepository
from app.services.scoring_service import ScoringService


class SearchService:
    def __init__(self, memory_repository: MemoryRepository):
        self.memory_repository = memory_repository

    def search(
        self,
        *,
        query: str,
        project_id: uuid.UUID | None = None,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        include_archived: bool = False,
    ) -> list[tuple[MemoryEntry, float]]:
        matches = self.memory_repository.search(
            query=query,
            project_id=project_id,
            limit=limit,
            types=types,
            include_archived=include_archived,
        )
        rescored = [
            (entry, ScoringService.calculate_final_score(entry, text_match_score)) for entry, text_match_score in matches
        ]
        return sorted(rescored, key=lambda item: item[1], reverse=True)[:limit]

