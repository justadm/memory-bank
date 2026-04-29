import uuid

from pydantic import BaseModel, Field, model_validator

from app.models.enums import MemoryLinkType, MemoryType
from app.schemas.projects import ProjectCreate, ProjectResponse


class ProjectImportEvent(BaseModel):
    title: str = Field(default="Initial project import", max_length=255)
    content: str = Field(default="Imported existing project into MemoryBank.", min_length=1)
    source_agent: str = Field(default="memorybank-import-agent", max_length=100)
    importance: int = Field(default=3, ge=1, le=5)
    metadata: dict = Field(default_factory=lambda: {"import_type": "initial_project_scan"})


class ProjectImportEntry(BaseModel):
    ref: str = Field(min_length=1, max_length=100)
    type: MemoryType
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)
    source_agent: str | None = Field(default="memorybank-import-agent", max_length=100)
    importance: int = Field(default=3, ge=1, le=5)
    metadata: dict = Field(default_factory=dict)


class ProjectImportLink(BaseModel):
    from_ref: str = Field(min_length=1, max_length=100)
    to_ref: str = Field(min_length=1, max_length=100)
    type: MemoryLinkType
    strength: float = Field(default=1.0, ge=0.0)
    created_by_agent: str | None = Field(default="memorybank-import-agent", max_length=100)
    metadata: dict = Field(default_factory=dict)


class ProjectImportRequest(BaseModel):
    project: ProjectCreate | None = None
    project_id: uuid.UUID | None = None
    import_event: ProjectImportEvent = Field(default_factory=ProjectImportEvent)
    entries: list[ProjectImportEntry] = Field(default_factory=list)
    links: list[ProjectImportLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_project_source(self) -> "ProjectImportRequest":
        if bool(self.project) == bool(self.project_id):
            raise ValueError("Provide exactly one of project or project_id")
        return self


class ProjectImportResponse(BaseModel):
    project: ProjectResponse
    import_event_id: uuid.UUID
    entries_created: int
    links_created: int
    entry_refs: dict[str, uuid.UUID]
