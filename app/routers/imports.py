from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import require_import_access
from app.schemas.imports import ProjectImportRequest, ProjectImportResponse
from app.services.import_service import ImportService


router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(require_import_access)])


def get_import_service(db: Session = Depends(get_db)) -> ImportService:
    return ImportService(MemoryRepository(db), ProjectRepository(db), LinkRepository(db))


@router.post("/project-scan", response_model=ProjectImportResponse, status_code=status.HTTP_201_CREATED)
def import_project_scan(
    payload: ProjectImportRequest,
    service: ImportService = Depends(get_import_service),
    principal=Depends(require_import_access),
) -> ProjectImportResponse:
    return ProjectImportResponse(**service.import_project_scan(payload, principal=principal))
