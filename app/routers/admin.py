import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.memory_repository import MemoryRepository
from app.repositories.metrics_repository import MetricsRepository
from app.schemas.admin import (
    ImportConflictListResponse,
    ImportProjectSummaryListResponse,
    ObservabilitySummaryResponse,
)
from app.services.admin_observability_service import AdminObservabilityService


router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_observability_service(db: Session = Depends(get_db)) -> AdminObservabilityService:
    return AdminObservabilityService(MetricsRepository(db), MemoryRepository(db), get_settings())


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
def get_observability_summary(
    service: AdminObservabilityService = Depends(get_admin_observability_service),
) -> ObservabilitySummaryResponse:
    return ObservabilitySummaryResponse(**service.get_summary())


@router.get("/import-conflicts", response_model=ImportConflictListResponse)
def get_import_conflicts(
    project_id: uuid.UUID | None = None,
    limit: int = 20,
    service: AdminObservabilityService = Depends(get_admin_observability_service),
) -> ImportConflictListResponse:
    return ImportConflictListResponse(**service.get_import_conflicts(project_id=project_id, limit=limit))


@router.get("/imports/summary", response_model=ImportProjectSummaryListResponse)
def get_import_summaries(
    limit: int = 20,
    service: AdminObservabilityService = Depends(get_admin_observability_service),
) -> ImportProjectSummaryListResponse:
    return ImportProjectSummaryListResponse(**service.get_import_summaries(limit=limit))
