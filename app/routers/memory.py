import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import MemoryType
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_write_access
from app.schemas.memory import (
    MemoryArchiveResponse,
    MemoryCreate,
    MemoryListResponse,
    MemoryRelevantItem,
    MemoryRelevantRequest,
    MemoryRelevantResponse,
    MemoryResponse,
    MemorySearchItem,
    MemorySearchResponse,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService


router = APIRouter(prefix="/memory", tags=["memory"])


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> MemoryResponse:
    return service.create_memory(payload)


@router.get("", response_model=MemoryListResponse)
def list_memory(
    project_id: uuid.UUID | None = None,
    type: MemoryType | None = Query(default=None),
    archived: bool | None = None,
    service: MemoryService = Depends(get_memory_service),
) -> MemoryListResponse:
    return MemoryListResponse(items=service.list_memory(project_id=project_id, memory_type=type, archived=archived))


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(
    query: str,
    project_id: uuid.UUID | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    service: MemoryService = Depends(get_memory_service),
) -> MemorySearchResponse:
    results = service.search_memory(query=query, project_id=project_id, limit=limit)
    return MemorySearchResponse(
        items=[
            MemorySearchItem(
                id=entry.id,
                type=entry.type,
                title=entry.title,
                content_preview=entry.content[:180],
                score=score,
                importance=entry.importance,
                usage_count=entry.usage_count,
            )
            for entry, score in results
        ]
    )


@router.post("/relevant", response_model=MemoryRelevantResponse)
def get_relevant_memory(
    payload: MemoryRelevantRequest,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> MemoryRelevantResponse:
    results = service.get_relevant_memory(payload)
    return MemoryRelevantResponse(
        context=[
            MemoryRelevantItem(
                id=entry.id,
                type=entry.type,
                title=entry.title,
                content=entry.content,
                relevance_score=score,
            )
            for entry, score in results
        ]
    )


@router.get("/{entry_id}", response_model=MemoryResponse)
def get_memory(entry_id: uuid.UUID, service: MemoryService = Depends(get_memory_service)) -> MemoryResponse:
    return service.get_memory(entry_id)


@router.patch("/{entry_id}", response_model=MemoryResponse)
def update_memory(
    entry_id: uuid.UUID,
    payload: MemoryUpdate,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> MemoryResponse:
    return service.update_memory(entry_id, payload)


@router.post("/{entry_id}/archive", response_model=MemoryArchiveResponse)
def archive_memory(
    entry_id: uuid.UUID,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> MemoryArchiveResponse:
    entry = service.archive_memory(entry_id)
    return MemoryArchiveResponse(id=entry.id, archived=entry.archived)
