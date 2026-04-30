import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.memory_repository import MemoryRepository
from app.repositories.metrics_repository import MetricsRepository
from app.security import require_admin_access
from app.schemas.admin import (
    ImportConflictListResponse,
    ImportProjectSummaryListResponse,
    ObservabilitySummaryResponse,
    RuntimeSelfCheckResponse,
)
from app.services.admin_observability_service import AdminObservabilityService


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_access)])


def get_admin_observability_service(db: Session = Depends(get_db)) -> AdminObservabilityService:
    return AdminObservabilityService(MetricsRepository(db), MemoryRepository(db), get_settings())


@router.get("/observability/summary", response_model=ObservabilitySummaryResponse)
def get_observability_summary(
    service: AdminObservabilityService = Depends(get_admin_observability_service),
    principal=Depends(require_admin_access),
) -> ObservabilitySummaryResponse:
    return ObservabilitySummaryResponse(**service.get_summary(principal=principal))


@router.get("/import-conflicts", response_model=ImportConflictListResponse)
def get_import_conflicts(
    project_id: uuid.UUID | None = None,
    limit: int = 20,
    service: AdminObservabilityService = Depends(get_admin_observability_service),
    principal=Depends(require_admin_access),
) -> ImportConflictListResponse:
    return ImportConflictListResponse(**service.get_import_conflicts(project_id=project_id, limit=limit, principal=principal))


@router.get("/imports/summary", response_model=ImportProjectSummaryListResponse)
def get_import_summaries(
    limit: int = 20,
    service: AdminObservabilityService = Depends(get_admin_observability_service),
    principal=Depends(require_admin_access),
) -> ImportProjectSummaryListResponse:
    return ImportProjectSummaryListResponse(**service.get_import_summaries(limit=limit, principal=principal))


@router.get("/runtime/self-check", response_model=RuntimeSelfCheckResponse)
def get_runtime_self_check(
    search_query: str = "architecture",
    project_id: uuid.UUID | None = None,
    limit: int = 5,
    service: AdminObservabilityService = Depends(get_admin_observability_service),
    principal=Depends(require_admin_access),
) -> RuntimeSelfCheckResponse:
    return RuntimeSelfCheckResponse(
        **service.get_runtime_self_check(
            search_query=search_query,
            project_id=project_id,
            limit=limit,
            principal=principal,
        )
    )
