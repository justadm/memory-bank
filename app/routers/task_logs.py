from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.task_log_repository import TaskLogRepository
from app.schemas.task_logs import TaskLogCreate, TaskLogListResponse, TaskLogResponse, TaskLogSummaryResponse
from app.services.task_log_service import TaskLogService


router = APIRouter(prefix="/task-logs", tags=["task-logs"])


def get_task_log_service(db: Session = Depends(get_db)) -> TaskLogService:
    return TaskLogService(TaskLogRepository(db))


@router.post("", response_model=TaskLogResponse, status_code=201)
def create_task_log(
    payload: TaskLogCreate,
    service: TaskLogService = Depends(get_task_log_service),
) -> TaskLogResponse:
    return service.create_task_log(payload)


@router.get("", response_model=TaskLogListResponse)
def list_task_logs(
    agent_id: str | None = None,
    experiment_id: str | None = None,
    service: TaskLogService = Depends(get_task_log_service),
) -> TaskLogListResponse:
    return TaskLogListResponse(items=service.list_task_logs(agent_id=agent_id, experiment_id=experiment_id))


@router.get("/summary", response_model=TaskLogSummaryResponse)
def get_task_log_summary(
    agent_id: str | None = None,
    experiment_id: str | None = None,
    service: TaskLogService = Depends(get_task_log_service),
) -> TaskLogSummaryResponse:
    return TaskLogSummaryResponse(**service.get_summary(agent_id=agent_id, experiment_id=experiment_id))

