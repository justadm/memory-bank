from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass

from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository


TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9_+-]+")


@dataclass
class SemanticDuplicateCandidate:
    entry_id: uuid.UUID
    title: str | None
    similarity: float

    def as_metadata(self) -> dict:
        return {
            "entry_id": str(self.entry_id),
            "title": self.title,
            "similarity": self.similarity,
        }


class LocalEmbeddingService:
    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        tokens = [token.lower() for token in TOKEN_RE.findall(text)]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            vec[int(digest, 16) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vec)) or 1.0
        return [value / norm for value in vec]

    @staticmethod
    def cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))


class SemanticDuplicateService:
    def __init__(self, memory_repository: MemoryRepository, embedder: LocalEmbeddingService | None = None):
        self.memory_repository = memory_repository
        self.embedder = embedder or LocalEmbeddingService()

    def find_candidates(
        self,
        *,
        project_id: uuid.UUID | None,
        title: str | None,
        content: str,
        existing_entry_id: uuid.UUID | None = None,
        threshold: float = 0.72,
        limit: int = 3,
    ) -> list[SemanticDuplicateCandidate]:
        if project_id is None:
            return []
        source_embedding = self.embedder.embed(f"{title or ''} {content}".strip())
        candidates: list[SemanticDuplicateCandidate] = []
        for entry in self.memory_repository.list(project_id=project_id, archived=False):
            if existing_entry_id and entry.id == existing_entry_id:
                continue
            similarity = self.embedder.cosine(
                source_embedding,
                self.embedder.embed(f"{entry.title or ''} {entry.content}".strip()),
            )
            if similarity >= threshold:
                candidates.append(
                    SemanticDuplicateCandidate(
                        entry_id=entry.id,
                        title=entry.title,
                        similarity=round(float(similarity), 3),
                    )
                )
        candidates.sort(key=lambda item: item.similarity, reverse=True)
        return candidates[:limit]
