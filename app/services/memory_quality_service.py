from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.enums import MemoryType
from app.repositories.memory_repository import MemoryRepository
from app.services.semantic_duplicate_service import SemanticDuplicateService

LOW_VALUE_PHRASES = {
    "todo",
    "tbd",
    "wip",
    "fix later",
    "temporary note",
    "test note",
}

EVIDENCE_KEYS = {"evidence", "files", "commands", "source_path", "service", "tags", "related_issue"}


@dataclass
class MemoryQualityAssessment:
    score: float
    confidence: float
    duplicate_risk: bool
    semantic_duplicate_risk: bool
    semantic_similarity_max: float | None
    semantic_duplicate_candidates: list[dict]
    evidence_present: bool
    review_required: bool
    reject: bool
    flags: list[str]

    def as_metadata(self) -> dict:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "duplicate_risk": self.duplicate_risk,
            "semantic_duplicate_risk": self.semantic_duplicate_risk,
            "semantic_similarity_max": self.semantic_similarity_max,
            "semantic_duplicate_candidates": self.semantic_duplicate_candidates,
            "evidence_present": self.evidence_present,
            "review_required": self.review_required,
            "reject": self.reject,
            "flags": self.flags,
        }


class MemoryQualityService:
    def __init__(self, memory_repository: MemoryRepository):
        self.memory_repository = memory_repository
        self.semantic_duplicate_service = SemanticDuplicateService(memory_repository)

    def assess(
        self,
        *,
        memory_type: MemoryType,
        title: str | None,
        content: str,
        metadata: dict | None,
        project_id: uuid.UUID | None,
        existing_entry_id: uuid.UUID | None = None,
    ) -> MemoryQualityAssessment:
        metadata = metadata or {}
        normalized_title = self._normalize(title or "")
        normalized_content = self._normalize(content)
        flags: list[str] = []

        if len(normalized_content) < 24:
            flags.append("too_short")
        if normalized_content in LOW_VALUE_PHRASES:
            flags.append("placeholder_content")
        if memory_type in {MemoryType.decision, MemoryType.constraint, MemoryType.risk, MemoryType.artifact} and not title:
            flags.append("missing_title")

        evidence_present = any(key in metadata and metadata.get(key) for key in EVIDENCE_KEYS)
        if memory_type in {MemoryType.decision, MemoryType.constraint, MemoryType.risk, MemoryType.artifact} and not evidence_present:
            flags.append("missing_evidence")

        duplicate_risk = self._has_duplicate(
            project_id=project_id,
            normalized_title=normalized_title,
            normalized_content=normalized_content,
            existing_entry_id=existing_entry_id,
        )
        if duplicate_risk:
            flags.append("possible_duplicate")
        semantic_candidates = self.semantic_duplicate_service.find_candidates(
            project_id=project_id,
            title=title,
            content=content,
            existing_entry_id=existing_entry_id,
        )
        semantic_duplicate_risk = bool(semantic_candidates)
        semantic_similarity_max = semantic_candidates[0].similarity if semantic_candidates else None
        if semantic_duplicate_risk:
            flags.append("semantic_duplicate_candidate")

        raw_confidence = metadata.get("confidence")
        if isinstance(raw_confidence, (int, float)):
            confidence = max(0.0, min(float(raw_confidence), 1.0))
        else:
            confidence = 0.7 if evidence_present else 0.45

        text_score = min(len(normalized_content) / 220, 1.0)
        title_score = 1.0 if title else 0.55
        evidence_score = 1.0 if evidence_present else 0.35
        duplicate_penalty = 0.45 if duplicate_risk else 1.0
        semantic_penalty = 0.7 if semantic_duplicate_risk else 1.0
        score = round(
            max(
                0.0,
                min(
                    (text_score * 0.35 + title_score * 0.15 + evidence_score * 0.25 + confidence * 0.25)
                    * duplicate_penalty
                    * semantic_penalty,
                    1.0,
                ),
            ),
            3,
        )
        reject = "placeholder_content" in flags or score < 0.25 or bool(semantic_similarity_max and semantic_similarity_max >= 0.97)
        review_required = bool(flags) or score < 0.55
        return MemoryQualityAssessment(
            score=score,
            confidence=round(confidence, 3),
            duplicate_risk=duplicate_risk,
            semantic_duplicate_risk=semantic_duplicate_risk,
            semantic_similarity_max=semantic_similarity_max,
            semantic_duplicate_candidates=[item.as_metadata() for item in semantic_candidates],
            evidence_present=evidence_present,
            review_required=review_required,
            reject=reject,
            flags=flags,
        )

    def _has_duplicate(
        self,
        *,
        project_id: uuid.UUID | None,
        normalized_title: str,
        normalized_content: str,
        existing_entry_id: uuid.UUID | None,
    ) -> bool:
        if project_id is None:
            return False
        for entry in self.memory_repository.list(project_id=project_id, archived=False):
            if existing_entry_id and entry.id == existing_entry_id:
                continue
            entry_title = self._normalize(entry.title or "")
            entry_content = self._normalize(entry.content)
            if normalized_content and normalized_content == entry_content:
                return True
            if normalized_title and normalized_title == entry_title and normalized_content and normalized_content[:180] == entry_content[:180]:
                return True
        return False

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.lower().strip().split())
