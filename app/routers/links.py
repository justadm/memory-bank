import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_write_access
from app.schemas.links import GraphEdge, GraphNode, GraphResponse, LinkCreate, LinkResponse, MemoryLinksResponse
from app.services.memory_service import MemoryService


router = APIRouter(tags=["links"])


def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    return MemoryService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


@router.post("/memory-links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: LinkCreate,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> LinkResponse:
    return service.create_link(payload)


@router.delete("/memory-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    link_id: uuid.UUID,
    service: MemoryService = Depends(get_memory_service),
    _principal=Depends(require_write_access),
) -> Response:
    service.delete_link(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memory/{entry_id}/links", response_model=MemoryLinksResponse)
def get_links(entry_id: uuid.UUID, service: MemoryService = Depends(get_memory_service)) -> MemoryLinksResponse:
    outgoing, incoming = service.get_links(entry_id)
    return MemoryLinksResponse(outgoing=outgoing, incoming=incoming)


@router.get("/memory/{entry_id}/graph", response_model=GraphResponse)
def get_graph(entry_id: uuid.UUID, depth: int = 1, service: MemoryService = Depends(get_memory_service)) -> GraphResponse:
    nodes, edges = service.get_graph(entry_id, depth)
    return GraphResponse(
        nodes=[GraphNode(id=node.id, type=node.type.value, title=node.title) for node in nodes],
        edges=[GraphEdge.model_validate({"from": edge.from_entry_id, "to": edge.to_entry_id, "type": edge.type.value}) for edge in edges],
    )
