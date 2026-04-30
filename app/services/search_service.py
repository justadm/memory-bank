import uuid
from dataclasses import dataclass
from typing import Literal

from app.models.memory_entry import MemoryEntry
from app.models.enums import MemoryType
from app.repositories.memory_repository import MemoryRepository
from app.services.scoring_service import ScoringService
from app.services.semantic_search_service import SemanticSearchService


@dataclass
class SearchMatch:
    entry: MemoryEntry
    score: float
    lexical_score: float | None
    semantic_score: float | None
    match_mode: Literal["lexical", "semantic", "hybrid"]


class SearchService:
    def __init__(self, memory_repository: MemoryRepository):
        self.memory_repository = memory_repository

    def search(
        self,
        *,
        query: str,
        project_id: uuid.UUID | None = None,
        project_ids: list[uuid.UUID] | None = None,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        include_archived: bool = False,
        mode: Literal["lexical", "semantic", "hybrid"] = "hybrid",
    ) -> list[SearchMatch]:
        lexical_matches = self.memory_repository.search(
            query=query,
            project_id=project_id,
            project_ids=project_ids,
            limit=max(limit * 3, 20),
            types=types,
            include_archived=include_archived,
        )
        if mode == "lexical":
            return [
                SearchMatch(
                    entry=entry,
                    score=ScoringService.calculate_final_score(entry, lexical_score),
                    lexical_score=lexical_score,
                    semantic_score=None,
                    match_mode="lexical",
                )
                for entry, lexical_score in lexical_matches[:limit]
            ]

        candidates = self.memory_repository.list(
            project_id=project_id,
            project_ids=project_ids,
            memory_type=types[0] if types and len(types) == 1 else None,
            archived=False if not include_archived else None,
        )
        if types and len(types) > 1:
            candidates = [item for item in candidates if item.type in types]

        lexical_by_id = {entry.id: lexical_score for entry, lexical_score in lexical_matches}
        semantic_scored = []
        for entry in candidates:
            semantic_score = SemanticSearchService.semantic_score(query, entry)
            lexical_score = lexical_by_id.get(entry.id, 0.0)
            if mode == "semantic":
                combined = semantic_score
            else:
                combined = semantic_score * 0.45 + lexical_score * 0.55
            if combined <= 0:
                continue
            semantic_scored.append(
                SearchMatch(
                    entry=entry,
                    score=ScoringService.calculate_final_score(entry, combined),
                    lexical_score=lexical_score if mode == "hybrid" else None,
                    semantic_score=semantic_score,
                    match_mode=mode,
                )
            )

        semantic_scored.sort(key=lambda item: item.score, reverse=True)
        return semantic_scored[:limit]
