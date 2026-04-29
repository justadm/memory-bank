from __future__ import annotations

from app.schemas.evaluation import (
    EvaluationBatchRequest,
    EvaluationBatchResponse,
    EvaluationBatchSummary,
    EvaluationRequest,
    EvaluationResponse,
)


MEMORY_REFERENCE_MARKERS = [
    "based on memory",
    "according to memory",
    "previous decision",
    "past decision",
    "existing decision",
    "memory says",
    "из памяти",
    "согласно памяти",
    "прошлое решение",
    "предыдущее решение",
    "ранее было решено",
]

CONFLICT_MARKERS = [
    "ignore previous",
    "contradicts previous",
    "despite previous decision",
    "игнорируем предыдущее",
    "противоречит прошлому",
]


class EvaluatorService:
    @staticmethod
    def evaluate(payload: EvaluationRequest) -> EvaluationResponse:
        task = EvaluatorService._normalize(payload.task)
        answer = EvaluatorService._normalize(payload.answer)
        reasoning = EvaluatorService._normalize(payload.reasoning)
        memory = payload.memory or []

        combined = f"{task}\n{answer}\n{reasoning}"
        used_memory = len(memory) > 0
        referenced_memory = any(marker in combined for marker in MEMORY_REFERENCE_MARKERS)
        possible_conflict = any(marker in combined for marker in CONFLICT_MARKERS)

        memory_titles = [EvaluatorService._normalize(item.title or "") for item in memory]
        memory_keywords_hit = sum(1 for title in memory_titles if title and title in combined)
        likely_influenced = referenced_memory or memory_keywords_hit > 0

        notes: list[str] = []
        if not used_memory:
            notes.append("Memory was not provided or not fetched.")
        if used_memory and not likely_influenced:
            notes.append("Memory was fetched, but answer does not clearly reference it.")
        if possible_conflict:
            notes.append("Possible conflict with previous memory detected.")
        if used_memory and likely_influenced and not possible_conflict:
            notes.append("Memory appears to be used meaningfully.")

        score = 0.4
        if used_memory:
            score += 0.2
        if referenced_memory:
            score += 0.2
        if likely_influenced:
            score += 0.2
        if possible_conflict:
            score -= 0.3
        score = max(0.0, min(1.0, score))

        consistency = 1.0
        if possible_conflict:
            consistency = 0.4
        elif used_memory and not likely_influenced:
            consistency = 0.7

        return EvaluationResponse(
            used_memory=used_memory,
            memory_entries_count=len(memory),
            referenced_memory_in_answer=referenced_memory,
            likely_influenced_decision=likely_influenced,
            possible_conflict=possible_conflict,
            quality_score=round(score, 3),
            consistency_score=round(consistency, 3),
            notes=notes,
        )

    @staticmethod
    def evaluate_batch(payload: EvaluationBatchRequest) -> EvaluationBatchResponse:
        results = [EvaluatorService.evaluate(item) for item in payload.items]
        total = len(results)
        if total == 0:
            return EvaluationBatchResponse(
                items=[],
                summary=EvaluationBatchSummary(
                    total_items=0,
                    used_memory_rate=0.0,
                    avg_quality_score=0.0,
                    avg_consistency_score=0.0,
                    conflict_rate=0.0,
                ),
            )

        return EvaluationBatchResponse(
            items=results,
            summary=EvaluationBatchSummary(
                total_items=total,
                used_memory_rate=round(sum(1 for item in results if item.used_memory) / total, 4),
                avg_quality_score=round(sum(item.quality_score for item in results) / total, 4),
                avg_consistency_score=round(sum(item.consistency_score for item in results) / total, 4),
                conflict_rate=round(sum(1 for item in results if item.possible_conflict) / total, 4),
            ),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").lower()
