from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Protocol


CONFLICT_KEYWORDS = {
    "postgresql": {"mongodb", "mysql", "neo4j", "arangodb"},
    "fastapi": {"express", "django", "flask"},
    "docker": {"bare metal", "no docker", "kubernetes only"},
    "redis": {"rabbitmq", "kafka"},
}


class MemoryEntryLike(Protocol):
    id: str
    type: str
    title: str | None
    content: str
    project_id: str | None
    metadata: dict


@dataclass
class ConflictCandidate:
    existing_entry_id: str
    new_entry_id: str | None
    reason: str
    confidence: float


class ConflictDetector:
    def detect(self, new_entry: MemoryEntryLike, existing_decisions: Iterable[MemoryEntryLike]) -> list[ConflictCandidate]:
        if new_entry.type != "decision":
            return []

        new_text = normalize(f"{new_entry.title or ''}\n{new_entry.content}")
        conflicts: list[ConflictCandidate] = []

        for old in existing_decisions:
            old_text = normalize(f"{old.title or ''}\n{old.content}")
            if str(old.id) == str(getattr(new_entry, "id", "")):
                continue

            keyword_conflict = self._keyword_conflict(new_text, old_text)
            if keyword_conflict:
                conflicts.append(
                    ConflictCandidate(
                        existing_entry_id=str(old.id),
                        new_entry_id=str(getattr(new_entry, "id", "") or ""),
                        reason=keyword_conflict,
                        confidence=0.85,
                    )
                )
                continue

            if self._same_topic_opposite_action(new_text, old_text):
                conflicts.append(
                    ConflictCandidate(
                        existing_entry_id=str(old.id),
                        new_entry_id=str(getattr(new_entry, "id", "") or ""),
                        reason="Potentially opposite decision on similar topic",
                        confidence=0.65,
                    )
                )

        return conflicts

    def _keyword_conflict(self, new_text: str, old_text: str) -> str | None:
        for chosen, alternatives in CONFLICT_KEYWORDS.items():
            if chosen in old_text:
                for alt in alternatives:
                    if alt in new_text:
                        return f"New decision mentions '{alt}' while existing decision mentions '{chosen}'"
            if chosen in new_text:
                for alt in alternatives:
                    if alt in old_text:
                        return f"New decision mentions '{chosen}' while existing decision mentions '{alt}'"
        return None

    def _same_topic_opposite_action(self, new_text: str, old_text: str) -> bool:
        similarity = SequenceMatcher(None, new_text[:500], old_text[:500]).ratio()
        opposite_terms = [
            ("use", "do not use"),
            ("enable", "disable"),
            ("keep", "remove"),
            ("sync", "async"),
        ]
        has_opposite = any(a in new_text and b in old_text or b in new_text and a in old_text for a, b in opposite_terms)
        return similarity > 0.35 and has_opposite


def normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
