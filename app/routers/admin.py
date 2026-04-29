from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.admin import ObservabilitySummaryResponse
from app.services.admin_observability_service import AdminObservabilityService


router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_observability_service(db: Session = Depends(get_db)) -> AdminObservabilityService:
    return AdminObservabilityService(MetricsRepository(db), get_settings())


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
def get_observability_summary(
    service: AdminObservabilityService = Depends(get_admin_observability_service),
) -> ObservabilitySummaryResponse:
    return ObservabilitySummaryResponse(**service.get_summary())
