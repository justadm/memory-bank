from fastapi import APIRouter

from app.schemas.evaluation import (
    EvaluationBatchRequest,
    EvaluationBatchResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from app.services.evaluator_service import EvaluatorService


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate_memory_usage(payload: EvaluationRequest) -> EvaluationResponse:
    return EvaluatorService.evaluate(payload)


@router.post("/evaluate-batch", response_model=EvaluationBatchResponse)
def evaluate_memory_usage_batch(payload: EvaluationBatchRequest) -> EvaluationBatchResponse:
    return EvaluatorService.evaluate_batch(payload)
