import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import MemoryType
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_read_access, require_write_access
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
    principal=Depends(require_write_access),
) -> MemoryResponse:
    return service.create_memory(payload, principal=principal)


@router.get("", response_model=MemoryListResponse)
def list_memory(
    project_id: uuid.UUID | None = None,
    type: MemoryType | None = Query(default=None),
    archived: bool | None = None,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemoryListResponse:
    return MemoryListResponse(items=service.list_memory(project_id=project_id, memory_type=type, archived=archived, principal=principal))


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(
    query: str,
    project_id: uuid.UUID | None = None,
    mode: Literal["lexical", "semantic", "hybrid"] = Query(default="hybrid"),
    limit: int = Query(default=10, ge=1, le=50),
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemorySearchResponse:
    results = service.search_memory(query=query, project_id=project_id, limit=limit, mode=mode, principal=principal)
    return MemorySearchResponse(
        items=[
            MemorySearchItem(
                id=match.entry.id,
                type=match.entry.type,
                title=match.entry.title,
                content_preview=match.entry.content[:180],
                score=match.score,
                lexical_score=match.lexical_score,
                semantic_score=match.semantic_score,
                match_mode=match.match_mode,
                importance=match.entry.importance,
                usage_count=match.entry.usage_count,
            )
            for match in results
        ]
    )


@router.post("/relevant", response_model=MemoryRelevantResponse)
def get_relevant_memory(
    payload: MemoryRelevantRequest,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryRelevantResponse:
    results = service.get_relevant_memory(payload, principal=principal)
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
def get_memory(
    entry_id: uuid.UUID,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemoryResponse:
    return service.get_memory(entry_id, principal=principal)


@router.patch("/{entry_id}", response_model=MemoryResponse)
def update_memory(
    entry_id: uuid.UUID,
    payload: MemoryUpdate,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryResponse:
    return service.update_memory(entry_id, payload, principal=principal)


@router.post("/{entry_id}/archive", response_model=MemoryArchiveResponse)
def archive_memory(
    entry_id: uuid.UUID,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryArchiveResponse:
    entry = service.archive_memory(entry_id, principal=principal)
    return MemoryArchiveResponse(id=entry.id, archived=entry.archived)
