from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.enums import MemoryChangeEventKind, MemoryProvenance
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.memory import MemoryRestoreRequest, MemoryReviseRequest
from app.security import AuthPrincipal, safe_actor_id
from app.services.memory_change_service import MemoryChangeService
from app.services.memory_evidence_service import MemoryEvidenceService


class MemoryRevisionService:
    def __init__(self, memory_repository: MemoryRepository, project_repository: ProjectRepository):
        self.memory_repository = memory_repository
        self.project_repository = project_repository

    def revise(
        self,
        entry_id: uuid.UUID,
        payload: MemoryReviseRequest,
        *,
        principal: AuthPrincipal | None,
        now: datetime | None = None,
        operation_source: str = "api",
    ) -> tuple[MemoryEntry, MemoryEntry, str]:
        old = self.memory_repository.get(entry_id)
        if not old:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        self._ensure_access(old, principal)
        successor = self._successor(old.id)
        if old.archived or old.valid_to is not None or successor:
            raise HTTPException(status_code=409, detail={"code": "memory_revision_not_current", "successor_id": str(successor.id) if successor else None})
        reason = MemoryEvidenceService.validate_reason(payload.reason)
        allowed = {"title", "content", "source_agent", "importance", "provenance", "confidence"}
        forbidden = set(payload.changes) - allowed
        if forbidden:
            raise HTTPException(status_code=422, detail={"code": "immutable_memory_fields", "fields": sorted(forbidden)})
        changes = dict(payload.changes)
        provenance = changes.get("provenance", old.provenance)
        metadata = dict(old.metadata_ or {})
        metadata.update(payload.metadata_patch)
        principal = principal or AuthPrincipal(name="anonymous", scopes={"read", "write", "import", "admin"}, api_key="")
        validation_metadata = dict(payload.metadata_patch)
        if provenance is MemoryProvenance.validated and "validation_evidence" not in validation_metadata:
            validation_metadata["validation_evidence"] = metadata.get("validation_evidence", [])
        MemoryEvidenceService.validate_provenance(provenance, principal=principal, metadata=validation_metadata, operation_source=operation_source)
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            raise ValueError("revision clock must be timezone-aware")
        old.valid_to = clock
        old.archived = True
        new = MemoryEntry(
            type=old.type,
            title=changes.get("title", old.title),
            content=changes.get("content", old.content),
            source_agent=changes.get("source_agent", old.source_agent),
            project_id=old.project_id,
            importance=changes.get("importance", old.importance),
            metadata_=metadata,
            provenance=MemoryProvenance.imported if operation_source == "import" else provenance,
            confidence=changes.get("confidence", old.confidence),
            valid_from=clock,
            supersedes_id=old.id,
            search_vector=None if self.memory_repository.is_postgresql() else self._search_payload(changes.get("title", old.title), changes.get("content", old.content)),
        )
        self.memory_repository.db.add(old)
        created = self.memory_repository.create(new)
        self.memory_repository.sync_search_vector(created, self._search_payload(created.title, created.content))
        if created.project_id:
            project = self.project_repository.get(created.project_id)
            if project:
                MemoryChangeService(self.memory_repository.db).emit(
                    project=project,
                    entry_id=created.id,
                    previous_entry_id=old.id,
                    event_kind=MemoryChangeEventKind.revised,
                    principal=principal,
                    reason=reason,
                )
        return created, old, reason

    def history(self, entry_id: uuid.UUID, *, principal: AuthPrincipal | None) -> list[MemoryEntry]:
        entry = self.memory_repository.get(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        self._ensure_access(entry, principal)
        items: list[MemoryEntry] = []
        current = entry
        seen: set[uuid.UUID] = set()
        while current and current.id not in seen:
            seen.add(current.id)
            items.append(current)
            current = self.memory_repository.db.get(MemoryEntry, current.supersedes_id) if current.supersedes_id else None
        current = entry
        while current:
            successor = self._successor(current.id)
            if not successor or successor.id in seen:
                break
            seen.add(successor.id)
            items.append(successor)
            current = successor
        return sorted(items, key=lambda item: item.valid_from)

    def restore(
        self,
        entry_id: uuid.UUID,
        payload: MemoryRestoreRequest,
        *,
        principal: AuthPrincipal | None,
        now: datetime | None = None,
    ) -> MemoryEntry:
        source = self.memory_repository.get(payload.source_entry_id or entry_id)
        if not source:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        self._ensure_access(source, principal)
        leaf = source
        while True:
            successor = self._successor(leaf.id)
            if not successor:
                break
            leaf = successor
        clock = now or datetime.now(timezone.utc)
        if leaf.valid_to is None:
            leaf.valid_to = clock
            leaf.archived = True
            self.memory_repository.db.add(leaf)
        restored = MemoryEntry(
            type=source.type,
            title=source.title,
            content=source.content,
            source_agent=source.source_agent,
            project_id=source.project_id,
            importance=source.importance,
            metadata_=dict(source.metadata_ or {}),
            provenance=source.provenance,
            confidence=source.confidence,
            valid_from=clock,
            supersedes_id=leaf.id,
            search_vector=None if self.memory_repository.is_postgresql() else self._search_payload(source.title, source.content),
        )
        created = self.memory_repository.create(restored)
        self.memory_repository.sync_search_vector(created, self._search_payload(created.title, created.content))
        project = self.project_repository.get(created.project_id) if created.project_id else None
        if project:
            MemoryChangeService(self.memory_repository.db).emit(
                project=project,
                entry_id=created.id,
                previous_entry_id=leaf.id,
                event_kind=MemoryChangeEventKind.restored,
                principal=principal,
                reason=f"restored_from_entry_id={source.id}; {MemoryEvidenceService.validate_reason(payload.reason)}",
            )
        return created

    def _successor(self, entry_id: uuid.UUID) -> MemoryEntry | None:
        return self.memory_repository.db.scalar(select(MemoryEntry).where(MemoryEntry.supersedes_id == entry_id))

    def _ensure_access(self, entry: MemoryEntry, principal: AuthPrincipal | None) -> None:
        if principal and principal.tenant_ids is not None:
            project = self.project_repository.get(entry.project_id) if entry.project_id else None
            if not project or project.tenant_id not in principal.tenant_ids:
                raise HTTPException(status_code=403, detail="Project access denied")

    @staticmethod
    def _search_payload(title: str | None, content: str) -> str:
        return " ".join(value.strip() for value in (title or "", content) if value and value.strip())
