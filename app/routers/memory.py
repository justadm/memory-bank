import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import MemoryType
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_read_access, require_write_access
from app.schemas.memory import (
    MemoryArchiveResponse,
    MemoryChangesResponse,
    MemoryHistoryResponse,
    MemoryRestoreRequest,
    MemoryRevisionResponse,
    MemoryReviseRequest,
    MemoryCreate,
    MemoryListResponse,
    MemoryRelevantItem,
    MemoryRelevantRequest,
    MemoryRelevantResponse,
    MemoryResponse,
    MemorySearchItem,
    MemorySearchResponse,
    SearchScope,
    MemoryUpdate,
)
from app.services.memory_service import MemoryService
from app.services.memory_change_service import MemoryChangeService
from app.services.memory_revision_service import MemoryRevisionService


router = APIRouter(prefix="/memory", tags=["memory"])


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


def get_revision_service(db: Session = Depends(get_db)) -> MemoryRevisionService:
    return MemoryRevisionService(MemoryRepository(db), ProjectRepository(db))


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryResponse:
    return service.create_memory(payload, principal=principal, operation_source="api")


@router.get("", response_model=MemoryListResponse)
def list_memory(
    project_id: uuid.UUID | None = None,
    type: MemoryType | None = Query(default=None),
    archived: bool | None = None,
    as_of: datetime | None = None,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemoryListResponse:
    return MemoryListResponse(items=service.list_memory(project_id=project_id, memory_type=type, archived=archived, as_of=as_of, principal=principal))


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(
    query: str,
    project_id: uuid.UUID | None = None,
    scope: SearchScope = Query(default="project"),
    mode: Literal["lexical", "semantic", "hybrid"] = Query(default="hybrid"),
    limit: int = Query(default=10, ge=1, le=50),
    as_of: datetime | None = None,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemorySearchResponse:
    results = service.search_memory(
        query=query,
        project_id=project_id,
        scope=scope,
        limit=limit,
        mode=mode,
        principal=principal,
        as_of=as_of,
    )
    return MemorySearchResponse(
        items=[
            MemorySearchItem(
                id=match.entry.id,
                type=match.entry.type,
                title=match.entry.title,
                project_id=match.entry.project_id,
                project_name=match.entry.project.name if match.entry.project else None,
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


@router.get("/changes", response_model=MemoryChangesResponse)
def get_memory_changes(
    project_id: uuid.UUID,
    cursor: str | None = None,
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> MemoryChangesResponse:
    project = service.project_repository.get(project_id)
    if not project:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    payload = MemoryChangeService(service.memory_repository.db).list_changes(
        project=project,
        principal=principal,
        cursor=cursor,
        after_sequence=after_sequence,
        limit=limit,
    )
    return MemoryChangesResponse(
        items=[
            {
                "project_id": item.project_id,
                "sequence": item.sequence,
                "feed_epoch": item.feed_epoch,
                "event_kind": item.event_kind.value,
                "occurred_at": item.occurred_at,
                "entry_id": item.entry_id,
                "previous_entry_id": item.previous_entry_id,
                "actor": item.actor,
                "reason": item.reason,
            }
            for item in payload["items"]
        ],
        **{key: payload[key] for key in ("has_more", "next_cursor", "committed_high_watermark", "feed_epoch", "feed_started_at")},
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
                project_id=entry.project_id,
                project_name=entry.project.name if entry.project else None,
                content=entry.content,
                relevance_score=score,
            )
            for entry, score in results
        ]
    )


@router.post("/{entry_id}/revise", response_model=MemoryRevisionResponse)
def revise_memory(
    entry_id: uuid.UUID,
    payload: MemoryReviseRequest,
    service: MemoryRevisionService = Depends(get_revision_service),
    principal=Depends(require_write_access),
) -> MemoryRevisionResponse:
    created, old, reason = service.revise(entry_id, payload, principal=principal)
    from app.schemas.memory import MemoryResponse
    return MemoryRevisionResponse(
        entry=MemoryResponse.model_validate(created),
        superseded_id=old.id,
        actor=__import__("app.security", fromlist=["safe_actor_id"]).safe_actor_id(principal),
        reason=reason,
        revised_at=created.valid_from,
    )


@router.get("/{entry_id}/history", response_model=MemoryHistoryResponse)
def memory_history(
    entry_id: uuid.UUID,
    service: MemoryRevisionService = Depends(get_revision_service),
    principal=Depends(require_read_access),
) -> MemoryHistoryResponse:
    return MemoryHistoryResponse(items=[MemoryResponse.model_validate(item) for item in service.history(entry_id, principal=principal)])


@router.post("/{entry_id}/restore", response_model=MemoryResponse)
def restore_memory(
    entry_id: uuid.UUID,
    payload: MemoryRestoreRequest,
    service: MemoryRevisionService = Depends(get_revision_service),
    principal=Depends(require_write_access),
) -> MemoryResponse:
    return MemoryResponse.model_validate(service.restore(entry_id, payload, principal=principal))


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
    response: Response,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryResponse:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'</memory/{entry_id}/revise>; rel="successor"'
    return service.update_memory(entry_id, payload, principal=principal, operation_source="api")


@router.post("/{entry_id}/archive", response_model=MemoryArchiveResponse)
def archive_memory(
    entry_id: uuid.UUID,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_write_access),
) -> MemoryArchiveResponse:
    entry = service.archive_memory(entry_id, principal=principal)
    return MemoryArchiveResponse(id=entry.id, archived=entry.archived)
