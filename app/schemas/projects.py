import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tenant_id: str | None = Field(default=None, max_length=100)
    metadata: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    tenant_id: str | None = Field(default=None, max_length=100)
    metadata: dict | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    tenant_id: str | None = None
    metadata: dict = Field(validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime


class ProjectResolveRequest(BaseModel):
    agent: str = Field(pattern="^codex$")
    connector_identity: uuid.UUID
    project_name: str = Field(min_length=1, max_length=255)
    existing_project_id: uuid.UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=100)


class ProjectResolveResponse(BaseModel):
    project_id: uuid.UUID
    status: str
    agent: str
    connector_identity: uuid.UUID
    tenant_id: str | None


class ProjectConnectorBindingResponse(BaseModel):
    project_id: uuid.UUID
    agent: str
    connector_identity: uuid.UUID
    tenant_id: str | None
    bound: bool
