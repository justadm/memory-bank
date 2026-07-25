from __future__ import annotations

import uuid
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.project import Project
from app.models.project_connector_identity import ProjectConnectorIdentity
from app.repositories.project_repository import ProjectRepository
from app.schemas.projects import ProjectResolveRequest, ProjectResolveResponse
from app.security import AuthPrincipal, ensure_tenant_access, resolve_tenant_for_create


class ProjectConnectorService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def resolve(
        self,
        payload: ProjectResolveRequest,
        *,
        principal: AuthPrincipal,
    ) -> ProjectResolveResponse:
        tenant_id = resolve_tenant_for_create(principal, payload.tenant_id)
        normalized_tenant_key = tenant_id or "__global__"
        binding = self.repository.get_connector_identity(
            agent=payload.agent,
            normalized_tenant_key=normalized_tenant_key,
            connector_identity=payload.connector_identity,
            lock=True,
        )
        if binding:
            project = self.repository.get(binding.project_id)
            if not project:
                raise HTTPException(status_code=409, detail={"code": "binding_target_missing"})
            return self._response(project, payload, "resolved")

        if payload.existing_project_id:
            project = self.repository.get(payload.existing_project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            self._ensure_project_tenant(project, tenant_id, principal)
            action: Literal["created", "bound_existing"] = "bound_existing"
        else:
            existing = self.repository.find_by_name_and_tenant(payload.project_name, tenant_id)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "existing_project_requires_explicit_id", "project_id": str(existing.id)},
                )
            metadata = {"tenant_id": tenant_id} if tenant_id else {}
            project = Project(name=payload.project_name, metadata_=metadata)
            self.repository.create(project)
            action = "created"

        binding = ProjectConnectorIdentity(
            agent=payload.agent,
            normalized_tenant_key=normalized_tenant_key,
            connector_identity=payload.connector_identity,
            project_id=project.id,
        )
        self.repository.db.add(binding)
        try:
            self.repository.db.flush()
        except IntegrityError as exc:
            self.repository.db.rollback()
            winner = self.repository.get_connector_identity(
                agent=payload.agent,
                normalized_tenant_key=normalized_tenant_key,
                connector_identity=payload.connector_identity,
            )
            if winner:
                winner_project = self.repository.get(winner.project_id)
                if winner_project:
                    return self._response(winner_project, payload, "resolved")
            raise HTTPException(status_code=409, detail={"code": "connector_identity_race"}) from exc
        return self._response(project, payload, action)

    @staticmethod
    def _ensure_project_tenant(project: Project, tenant_id: str | None, principal: AuthPrincipal) -> None:
        ensure_tenant_access(principal, project.tenant_id)
        if tenant_id is not None and project.tenant_id != tenant_id:
            raise HTTPException(status_code=409, detail={"code": "project_tenant_mismatch"})

    @staticmethod
    def _response(project: Project, payload: ProjectResolveRequest, action: str) -> ProjectResolveResponse:
        return ProjectResolveResponse(
            project_id=project.id,
            status=action,
            agent=payload.agent,
            connector_identity=payload.connector_identity,
            tenant_id=project.tenant_id,
        )
