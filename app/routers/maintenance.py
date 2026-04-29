import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.services.memory_service import MemoryService


router = APIRouter(prefix="/maintenance", tags=["maintenance"])


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


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


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
