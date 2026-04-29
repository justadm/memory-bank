from pydantic import BaseModel, Field


class EvaluationMemoryItem(BaseModel):
    id: str | None = None
    title: str | None = None
    content: str | None = None


class EvaluationRequest(BaseModel):
    task: str = Field(default="")
    memory: list[EvaluationMemoryItem] = Field(default_factory=list)
    reasoning: str = Field(default="")
    answer: str = Field(default="")


class EvaluationResponse(BaseModel):
    used_memory: bool
    memory_entries_count: int
    referenced_memory_in_answer: bool
    likely_influenced_decision: bool
    possible_conflict: bool
    quality_score: float
    consistency_score: float
    notes: list[str]

