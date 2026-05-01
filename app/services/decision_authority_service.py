from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository


@dataclass
class DecisionConflict:
    entry_id: uuid.UUID
    conflicts_with_entry_id: uuid.UUID
    reason: str
    severity: str = "medium"

    def as_metadata(self) -> dict:
        return {
            "entry_id": str(self.entry_id),
            "conflicts_with_entry_id": str(self.conflicts_with_entry_id),
            "reason": self.reason,
            "severity": self.severity,
        }


class DecisionAuthorityService:
    NEGATION_PAIRS = [
        ("postgres", "mongo"),
        ("postgresql", "mongodb"),
        ("sqlite", "postgres"),
        ("fastapi", "django"),
        ("qdrant", "pgvector"),
        ("neo4j", "postgres"),
        ("kafka", "redis"),
    ]

    def __init__(self, memory_repository: MemoryRepository):
        self.memory_repository = memory_repository

    def enrich_metadata(
        self,
        *,
        entry_id: uuid.UUID | None,
        memory_type: MemoryType,
        project_id: uuid.UUID | None,
        title: str | None,
        content: str,
        metadata: dict,
    ) -> dict:
        enriched = dict(metadata)
        if memory_type != MemoryType.decision:
            return enriched

        enriched.setdefault("decision_status", "active")
        conflicts = self.detect_conflicts(
            entry_id=entry_id,
            project_id=project_id,
            title=title,
            content=content,
        )
        if conflicts:
            enriched["requires_review"] = True
            enriched["decision_conflicts"] = [item.as_metadata() for item in conflicts]
        else:
            enriched.pop("decision_conflicts", None)
        return enriched

    def detect_conflicts(
        self,
        *,
        entry_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
        title: str | None,
        content: str,
    ) -> list[DecisionConflict]:
        if project_id is None:
            return []

        text_new = f"{title or ''} {content}".lower()
        conflicts: list[DecisionConflict] = []
        existing = self.memory_repository.list(project_id=project_id, memory_type=MemoryType.decision, archived=False)
        for old in existing:
            if entry_id and old.id == entry_id:
                continue
            old_status = (old.metadata_ or {}).get("decision_status")
            if old_status not in {None, "active", "approved"}:
                continue
            text_old = f"{old.title or ''} {old.content}".lower()
            for left, right in self.NEGATION_PAIRS:
                if (left in text_new and right in text_old) or (right in text_new and left in text_old):
                    conflicts.append(
                        DecisionConflict(
                            entry_id=entry_id or uuid.uuid4(),
                            conflicts_with_entry_id=old.id,
                            reason=f"Technology direction conflict: {left} vs {right}",
                            severity="high",
                        )
                    )
                    break
            else:
                if self._looks_like_supersession(text_new, text_old):
                    conflicts.append(
                        DecisionConflict(
                            entry_id=entry_id or uuid.uuid4(),
                            conflicts_with_entry_id=old.id,
                            reason="Possible supersession of an existing active decision",
                            severity="medium",
                        )
                    )
        return conflicts

    def supersede_metadata(self, *, old_entry_id: uuid.UUID, new_entry_id: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "old": {
                "decision_status": "superseded",
                "deprecated_by_entry_id": str(new_entry_id),
                "valid_until": now,
            },
            "new": {
                "decision_status": "active",
                "supersedes_entry_id": str(old_entry_id),
                "valid_from": now,
                "requires_review": False,
            },
        }

    @staticmethod
    def _looks_like_supersession(text_new: str, text_old: str) -> bool:
        overlap = set(text_new.split()) & set(text_old.split())
        if len(overlap) < 4:
            return False
        return any(marker in text_new for marker in ("instead", "switch", "replace", "migrate", "замен", "перей"))
