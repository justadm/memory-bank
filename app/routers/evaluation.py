from fastapi import APIRouter

from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.services.evaluator_service import EvaluatorService


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate_memory_usage(payload: EvaluationRequest) -> EvaluationResponse:
    return EvaluatorService.evaluate(payload)

