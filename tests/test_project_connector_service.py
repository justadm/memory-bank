from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.models.project import Project
from app.models.project_connector_identity import ProjectConnectorIdentity
from app.schemas.projects import ProjectResolveRequest
from app.security import AuthPrincipal
from app.services.project_connector_service import ProjectConnectorService


class _NestedTransaction:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.in_savepoint = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.db.in_savepoint = False
        return False


class _RaceDatabase:
    def __init__(self):
        self.in_savepoint = False
        self.expired = False
        self.flush_calls = 0

    def begin_nested(self):
        return _NestedTransaction(self)

    def add(self, item):
        assert self.in_savepoint

    def flush(self):
        assert self.in_savepoint
        self.flush_calls += 1
        raise IntegrityError("insert", {}, RuntimeError("unique race"))

    def expire_all(self):
        self.expired = True

    def rollback(self):
        raise AssertionError("outer transaction must not be rolled back")


class _RaceRepository:
    def __init__(self):
        self.db = _RaceDatabase()
        self.project = Project(id=uuid.uuid4(), name="winner", metadata_={})
        self.binding = ProjectConnectorIdentity(
            agent="codex",
            normalized_tenant_key="__global__",
            connector_identity=uuid.uuid4(),
            project_id=self.project.id,
        )
        self.binding_reads = 0

    def get_connector_identity(self, **kwargs):
        self.binding_reads += 1
        return None if self.binding_reads == 1 else self.binding

    def find_by_name_and_tenant(self, name, tenant_id):
        return None

    def create(self, project):
        assert self.db.in_savepoint
        project.id = uuid.uuid4()
        return project

    def get(self, project_id):
        return self.project if project_id == self.project.id else None


def test_project_resolve_race_uses_savepoint_and_preserves_outer_transaction() -> None:
    repository = _RaceRepository()
    payload = ProjectResolveRequest(
        agent="codex",
        connector_identity=repository.binding.connector_identity,
        project_name="winner",
    )

    result = ProjectConnectorService(repository).resolve(
        payload,
        principal=AuthPrincipal(name="tester", scopes={"read", "write"}, api_key=""),
    )

    assert result.status == "resolved"
    assert result.project_id == repository.project.id
    assert repository.db.expired is True
    assert repository.db.flush_calls == 1
