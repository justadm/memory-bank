import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.metrics_repository import MetricsRepository
from app.security import require_admin_access
from app.schemas.metrics import MetricsOverviewResponse
from app.services.metrics_service import MetricsService


router = APIRouter(prefix="/metrics", tags=["metrics"], dependencies=[Depends(require_admin_access)])


def get_metrics_service(db: Session = Depends(get_db)) -> MetricsService:
    return MetricsService(MetricsRepository(db))


@router.get("/overview", response_model=MetricsOverviewResponse)
def get_metrics_overview(
    project_id: uuid.UUID | None = None,
    agent_id: str | None = None,
    experiment_id: str | None = None,
    service: MetricsService = Depends(get_metrics_service),
) -> MetricsOverviewResponse:
    return MetricsOverviewResponse(**service.get_overview(project_id=project_id, agent_id=agent_id, experiment_id=experiment_id))
