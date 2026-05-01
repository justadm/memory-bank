import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_admin_access
from app.services.lifecycle_service import LifecycleService
from app.services.memory_service import MemoryService


router = APIRouter(prefix="/maintenance", tags=["maintenance"], dependencies=[Depends(require_admin_access)])


class ArchiveStaleRequest(BaseModel):
    older_than_days: int = Field(ge=1)
    max_usage_count: int = Field(ge=0)
    max_importance: int = Field(ge=1, le=5)


class ArchiveStaleResponse(BaseModel):
    archived_count: int
    archived_ids: list[str]


class RebuildSearchVectorsRequest(BaseModel):
    project_id: uuid.UUID | None = None


class RebuildSearchVectorsResponse(BaseModel):
    rebuilt_count: int


class LifecycleRunRequest(BaseModel):
    stale_days: int = Field(default=21, ge=1)
    review_overdue_days: int = Field(default=14, ge=1)
    weak_link_days: int = Field(default=30, ge=1)
    low_quality_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    weak_link_strength_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    decay_amount: float = Field(default=0.03, ge=0.0, le=1.0)
    dry_run: bool = False


class LifecycleRunResponse(BaseModel):
    quality_decayed_count: int
    review_overdue_marked_count: int
    archived_count: int
    weak_links_deleted_count: int
    archived_ids: list[str]
    review_overdue_ids: list[str]
    weak_link_ids: list[str]
    dry_run: bool


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


def get_lifecycle_service(db: Session = Depends(get_db)) -> LifecycleService:
    return LifecycleService(MemoryRepository(db), LinkRepository(db))


@router.post("/archive-stale", response_model=ArchiveStaleResponse)
def archive_stale(payload: ArchiveStaleRequest, service: MemoryService = Depends(get_memory_service)) -> ArchiveStaleResponse:
    items = service.archive_stale(
        older_than_days=payload.older_than_days,
        max_usage_count=payload.max_usage_count,
        max_importance=payload.max_importance,
    )
    return ArchiveStaleResponse(archived_count=len(items), archived_ids=[str(item.id) for item in items])


@router.post("/rebuild-search-vectors", response_model=RebuildSearchVectorsResponse)
def rebuild_search_vectors(
    payload: RebuildSearchVectorsRequest,
    service: MemoryService = Depends(get_memory_service),
) -> RebuildSearchVectorsResponse:
    rebuilt_count = service.rebuild_search_vectors(project_id=payload.project_id)
    return RebuildSearchVectorsResponse(rebuilt_count=rebuilt_count)


@router.post("/lifecycle/run", response_model=LifecycleRunResponse)
def run_lifecycle(
    payload: LifecycleRunRequest,
    service: LifecycleService = Depends(get_lifecycle_service),
) -> LifecycleRunResponse:
    result = service.run(
        stale_days=payload.stale_days,
        review_overdue_days=payload.review_overdue_days,
        weak_link_days=payload.weak_link_days,
        low_quality_threshold=payload.low_quality_threshold,
        weak_link_strength_threshold=payload.weak_link_strength_threshold,
        decay_amount=payload.decay_amount,
        dry_run=payload.dry_run,
    )
    return LifecycleRunResponse(
        quality_decayed_count=result.quality_decayed_count,
        review_overdue_marked_count=result.review_overdue_marked_count,
        archived_count=result.archived_count,
        weak_links_deleted_count=result.weak_links_deleted_count,
        archived_ids=[str(item) for item in result.archived_ids],
        review_overdue_ids=[str(item) for item in result.review_overdue_ids],
        weak_link_ids=[str(item) for item in result.weak_link_ids],
        dry_run=result.dry_run,
    )
