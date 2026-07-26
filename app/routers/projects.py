import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.project_repository import ProjectRepository
from app.security import require_read_access, require_write_access
from app.schemas.projects import (
    ProjectConnectorBindingResponse,
    ProjectCreate,
    ProjectResolveRequest,
    ProjectResolveResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_connector_service import ProjectConnectorService
from app.services.memory_service import ProjectService


router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


def get_project_connector_service(db: Session = Depends(get_db)) -> ProjectConnectorService:
    return ProjectConnectorService(ProjectRepository(db))


@router.post("/resolve", response_model=ProjectResolveResponse)
def resolve_project(
    payload: ProjectResolveRequest,
    response: Response,
    service: ProjectConnectorService = Depends(get_project_connector_service),
    principal=Depends(require_write_access),
) -> ProjectResolveResponse:
    result = service.resolve(payload, principal=principal)
    if result.status == "created":
        response.status_code = status.HTTP_201_CREATED
    return result


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
    principal=Depends(require_write_access),
) -> ProjectResponse:
    return service.create_project(payload, principal=principal)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    service: ProjectService = Depends(get_project_service),
    principal=Depends(require_read_access),
) -> list[ProjectResponse]:
    return service.list_projects(principal=principal)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    principal=Depends(require_read_access),
) -> ProjectResponse:
    return service.get_project(project_id, principal=principal)


@router.get(
    "/{project_id}/connector-binding",
    response_model=ProjectConnectorBindingResponse,
)
def verify_project_connector_binding(
    project_id: uuid.UUID,
    agent: str,
    connector_identity: uuid.UUID,
    tenant_id: str | None = None,
    service: ProjectConnectorService = Depends(get_project_connector_service),
    principal=Depends(require_read_access),
) -> ProjectConnectorBindingResponse:
    return service.verify_binding(
        project_id=project_id,
        agent=agent,
        connector_identity=connector_identity,
        tenant_id=tenant_id,
        principal=principal,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
    principal=Depends(require_write_access),
) -> ProjectResponse:
    return service.update_project(project_id, payload, principal=principal)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    principal=Depends(require_write_access),
) -> Response:
    service.delete_project(project_id, principal=principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
