from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.context import ContextBuildRequest, ContextBuildResponse
from app.security import require_read_access
from app.services.context_builder_service import ContextBuilderService
from app.services.memory_service import MemoryService


router = APIRouter(prefix="/context", tags=["context"])


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


@router.post("/build", response_model=ContextBuildResponse)
def build_context(
    payload: ContextBuildRequest,
    service: MemoryService = Depends(get_memory_service),
    principal=Depends(require_read_access),
) -> ContextBuildResponse:
    results = service.search_memory(
        query=payload.query,
        project_id=payload.project_id,
        scope=payload.scope,
        limit=payload.limit,
        mode=payload.mode,
        principal=principal,
    )
    builder = ContextBuilderService(service.memory_repository)
    return ContextBuildResponse.model_validate(builder.build_from_search_results(results, limit=payload.limit))
