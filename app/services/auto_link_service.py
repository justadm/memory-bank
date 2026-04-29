from __future__ import annotations

import math
import re

from app.config import Settings
from app.models.enums import MemoryLinkType
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository


class AutoLinkService:
    def __init__(
        self,
        *,
        memory_repository: MemoryRepository,
        link_repository: LinkRepository,
        settings: Settings,
    ):
        self.memory_repository = memory_repository
        self.link_repository = link_repository
        self.settings = settings

    def link_entry(self, entry: MemoryEntry) -> list[MemoryLink]:
        if not self.settings.auto_link_on_create:
            return []

        text = self._compose_text(entry.title, entry.content)
        base_vector = self._embed(text)
        candidates = self.memory_repository.list(
            project_id=entry.project_id,
            archived=False,
        )
        candidates = sorted(
            candidates,
            key=lambda candidate: candidate.created_at,
            reverse=True,
        )[: self.settings.auto_link_search_limit]

        created_links: list[MemoryLink] = []
        for candidate in candidates:
            if candidate.id == entry.id:
                continue

            similarity = self._cosine(base_vector, self._embed(self._compose_text(candidate.title, candidate.content)))
            if similarity < self.settings.auto_link_min_similarity:
                continue

            if self.link_repository.find_by_pair(entry.id, candidate.id, MemoryLinkType.related_to):
                continue

            link = self.link_repository.create(
                MemoryLink(
                    from_entry_id=entry.id,
                    to_entry_id=candidate.id,
                    type=MemoryLinkType.related_to,
                    strength=round(similarity, 4),
                    created_by_agent="auto-linker",
                    metadata_={"method": "simple_bow_cosine"},
                )
            )
            created_links.append(link)

            if len(created_links) >= self.settings.auto_link_max_links:
                break

        return created_links

    @staticmethod
    def _compose_text(title: str | None, content: str) -> str:
        return "\n".join(part for part in [title or "", content] if part)

    @staticmethod
    def _embed(text: str) -> dict[str, float]:
        tokens = re.findall(r"[a-zA-Zа-яА-Я0-9_]{3,}", text.lower())
        vector: dict[str, float] = {}
        for token in tokens:
            vector[token] = vector.get(token, 0.0) + 1.0
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        return {token: value / norm for token, value in vector.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(value * b.get(key, 0.0) for key, value in a.items())
