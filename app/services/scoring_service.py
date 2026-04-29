import math
from datetime import datetime, timezone

from app.models.memory_entry import MemoryEntry


class ScoringService:
    @staticmethod
    def calculate_final_score(entry: MemoryEntry, text_match_score: float) -> float:
        importance_score = entry.importance / 5
        usage_score = min(1.0, math.log(entry.usage_count + 1, 10))
        recency_score = ScoringService._recency_score(entry.last_used_at or entry.updated_at or entry.created_at)
        return text_match_score * 0.6 + importance_score * 0.2 + recency_score * 0.1 + usage_score * 0.1

    @staticmethod
    def _recency_score(moment: datetime | None) -> float:
        if not moment:
            return 0.0
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - moment).days, 0)
        return max(0.0, 1 - min(age_days / 365, 1))
