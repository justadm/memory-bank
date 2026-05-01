from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository
from app.services.search_service import SearchMatch


@dataclass
class ContextItem:
    id: str
    type: str
    title: str | None
    content: str
    score: float
    importance: int
    decision_status: str | None
    project_id: str | None
    metadata: dict[str, Any]


class ContextBuilderService:
    TYPE_WEIGHTS = {
        "decision": 1.35,
        "constraint": 1.3,
        "risk": 1.2,
        "artifact": 1.0,
        "task": 0.9,
        "note": 0.7,
        "event": 0.55,
    }

    def __init__(self, memory_repository: MemoryRepository):
        self.memory_repository = memory_repository

    def build_from_search_results(self, items: list[SearchMatch], *, limit: int = 12) -> dict[str, Any]:
        context_items = [self._to_context_item(item.entry, item.score) for item in items]
        return self.build(context_items, limit=limit)

    def build(self, items: list[ContextItem], *, limit: int = 12) -> dict[str, Any]:
        ranked = sorted(items, key=self.boost_score, reverse=True)[:limit]
        buckets = {
            "active_decisions": [],
            "constraints": [],
            "risks": [],
            "artifacts": [],
            "tasks": [],
            "notes": [],
            "other": [],
        }
        mapping = {
            "decision": "active_decisions",
            "constraint": "constraints",
            "risk": "risks",
            "artifact": "artifacts",
            "task": "tasks",
            "note": "notes",
        }
        for item in ranked:
            bucket = mapping.get(item.type, "other")
            if item.type == "decision" and item.decision_status not in {None, "active", "approved"}:
                bucket = "other"
            buckets[bucket].append(
                {
                    "id": item.id,
                    "type": item.type,
                    "title": item.title,
                    "content": item.content,
                    "score": self.boost_score(item),
                    "importance": item.importance,
                    "project_id": item.project_id,
                }
            )
        return {
            "context_version": "v2",
            "summary": {
                "total_items": len(ranked),
                "decisions": len(buckets["active_decisions"]),
                "constraints": len(buckets["constraints"]),
                "risks": len(buckets["risks"]),
                "artifacts": len(buckets["artifacts"]),
            },
            "context": buckets,
            "agent_instructions": [
                "Respect active_decisions first.",
                "Do not violate constraints.",
                "Check risks before implementation.",
                "Use artifacts as implementation references.",
            ],
        }

    def boost_score(self, item: ContextItem) -> float:
        score = item.score * self.TYPE_WEIGHTS.get(item.type, 1.0)
        score += min(item.importance, 5) * 0.03
        if item.type == "decision" and item.decision_status in {"active", "approved"}:
            score += 0.12
        if item.metadata.get("review_status") == "approved":
            score += 0.08
        return round(min(score, 1.0), 4)

    @staticmethod
    def _to_context_item(entry: MemoryEntry, score: float) -> ContextItem:
        metadata = dict(entry.metadata_ or {})
        return ContextItem(
            id=str(entry.id),
            type=entry.type.value,
            title=entry.title,
            content=entry.content,
            score=score,
            importance=entry.importance,
            decision_status=metadata.get("decision_status"),
            project_id=str(entry.project_id) if entry.project_id else None,
            metadata=metadata,
        )
