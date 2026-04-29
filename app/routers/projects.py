import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.project_repository import ProjectRepository
from app.security import require_write_access
from app.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.memory_service import ProjectService


router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
    _principal=Depends(require_write_access),
) -> ProjectResponse:
    return service.create_project(payload)


@router.get("", response_model=list[ProjectResponse])
def list_projects(service: ProjectService = Depends(get_project_service)) -> list[ProjectResponse]:
    return service.list_projects()


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: uuid.UUID, service: ProjectService = Depends(get_project_service)) -> ProjectResponse:
    return service.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
    _principal=Depends(require_write_access),
) -> ProjectResponse:
    return service.update_project(project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    service: ProjectService = Depends(get_project_service),
    _principal=Depends(require_write_access),
) -> Response:
    service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
