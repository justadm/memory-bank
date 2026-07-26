from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.enums import MemoryChangeEventKind, MemoryProvenance
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.memory import MemoryRestoreRequest, MemoryReviseRequest
from app.security import AuthPrincipal, safe_actor_id
from app.services.memory_change_service import MemoryChangeService
from app.services.decision_authority_service import DecisionAuthorityService
from app.services.memory_evidence_service import MemoryEvidenceService
from app.services.memory_quality_service import MemoryQualityService


class MemoryRevisionService:
    def __init__(self, memory_repository: MemoryRepository, project_repository: ProjectRepository):
        self.memory_repository = memory_repository
        self.project_repository = project_repository
        self.link_repository = LinkRepository(memory_repository.db)

    def revise(
        self,
        entry_id: uuid.UUID,
        payload: MemoryReviseRequest,
        *,
        principal: AuthPrincipal | None,
        now: datetime | None = None,
        operation_source: str = "api",
        enforce_quality_gate: bool = True,
    ) -> tuple[MemoryEntry, MemoryEntry, str]:
        old = self.memory_repository.get_for_update(entry_id)
        if not old:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        self._ensure_access(old, principal)
        successor = self._successor(old.id)
        if old.archived or old.valid_to is not None or successor:
            raise HTTPException(status_code=409, detail={"code": "memory_revision_not_current", "successor_id": str(successor.id) if successor else None})
        reason = MemoryEvidenceService.validate_reason(payload.reason)
        changes = payload.changes.model_dump(exclude_unset=True)
        provenance = changes.get("provenance", old.provenance)
        metadata = dict(old.metadata_ or {})
        metadata.update(payload.metadata_patch)
        principal = principal or AuthPrincipal(name="anonymous", scopes={"read", "write", "import", "admin"}, api_key="")
        validation_metadata = dict(payload.metadata_patch)
        if provenance is MemoryProvenance.validated and "validation_evidence" not in validation_metadata:
            validation_metadata["validation_evidence"] = metadata.get("validation_evidence", [])
        MemoryEvidenceService.validate_provenance(provenance, principal=principal, metadata=validation_metadata, operation_source=operation_source)
        quality_service = MemoryQualityService(self.memory_repository)
        quality = quality_service.assess(
            memory_type=old.type,
            title=changes.get("title", old.title),
            content=changes.get("content", old.content),
            metadata=metadata,
            project_id=old.project_id,
            existing_entry_id=old.id,
        )
        metadata["quality"] = quality.as_metadata()
        if quality.review_required:
            metadata["quality_review_required"] = True
        else:
            metadata.pop("quality_review_required", None)
        metadata = DecisionAuthorityService(self.memory_repository).enrich_metadata(
            entry_id=old.id,
            memory_type=old.type,
            project_id=old.project_id,
            title=changes.get("title", old.title),
            content=changes.get("content", old.content),
            metadata=metadata,
        )
        if quality.reject and enforce_quality_gate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Memory entry did not pass quality validation",
                    "quality": quality.as_metadata(),
                },
            )
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            raise ValueError("revision clock must be timezone-aware")
        try:
            with self.memory_repository.db.begin_nested():
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
                    history_available=True,
                    supersedes_id=old.id,
                    search_vector=None if self.memory_repository.is_postgresql() else self._search_payload(changes.get("title", old.title), changes.get("content", old.content)),
                )
                self.memory_repository.db.add(old)
                created = self.memory_repository.create(new)
                self.memory_repository.sync_search_vector(created, self._search_payload(created.title, created.content))
                self.link_repository.inherit_for_revision(
                    previous_entry_id=old.id,
                    revision_entry_id=created.id,
                    inherited_at=clock,
                )
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
                            occurred_at=clock,
                        )
        except IntegrityError as exc:
            self.memory_repository.db.expire_all()
            winner = self._successor(old.id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "memory_revision_conflict",
                    "successor_id": str(winner.id) if winner else None,
                },
            ) from exc
        self._set_lineage(created)
        return created, old, reason

    def history(self, entry_id: uuid.UUID, *, principal: AuthPrincipal | None) -> list[MemoryEntry]:
        entry = self.memory_repository.get(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        self._ensure_access(entry, principal)
        if not entry.history_available:
            raise HTTPException(
                status_code=409,
                detail={"code": "memory_history_unavailable"},
            )
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
        result = sorted(items, key=lambda item: item.valid_from)
        for item in result:
            self._set_lineage(item)
        return result

    def restore(
        self,
        entry_id: uuid.UUID,
        payload: MemoryRestoreRequest,
        *,
        principal: AuthPrincipal | None,
        now: datetime | None = None,
    ) -> MemoryEntry:
        target = self.memory_repository.get_for_update(entry_id)
        source = self.memory_repository.get(payload.source_entry_id or entry_id)
        if not target or not source:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        if not source.history_available or not target.history_available:
            raise HTTPException(status_code=409, detail={"code": "memory_history_unavailable"})
        target_chain = {item.id for item in self.history(target.id, principal=principal)}
        if source.id not in target_chain:
            raise HTTPException(status_code=409, detail={"code": "memory_restore_chain_mismatch"})
        self._ensure_access(source, principal)
        leaf = target
        while True:
            successor = self._successor(leaf.id)
            if not successor:
                break
            leaf = successor
        leaf = self.memory_repository.get_for_update(leaf.id)
        if leaf is None:
            raise HTTPException(status_code=404, detail="Memory entry not found")
        winner = self._successor(leaf.id)
        if winner is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "memory_restore_conflict",
                    "successor_id": str(winner.id),
                },
            )
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            raise ValueError("restore clock must be timezone-aware")
        leaf_is_current = leaf.valid_to is None and not leaf.archived
        leaf_is_archived = leaf.valid_to is not None and leaf.archived
        if not leaf_is_current and not leaf_is_archived:
            raise HTTPException(
                status_code=409,
                detail={"code": "memory_restore_chain_state_invalid"},
            )
        if leaf_is_current and source.id == leaf.id:
            raise HTTPException(
                status_code=409,
                detail={"code": "memory_restore_chain_is_current", "current_entry_id": str(leaf.id)},
            )
        try:
            with self.memory_repository.db.begin_nested():
                if leaf_is_current:
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
                    history_available=True,
                    supersedes_id=leaf.id,
                    search_vector=None if self.memory_repository.is_postgresql() else self._search_payload(source.title, source.content),
                )
                created = self.memory_repository.create(restored)
                self.memory_repository.sync_search_vector(created, self._search_payload(created.title, created.content))
                self.link_repository.inherit_for_revision(
                    previous_entry_id=leaf.id,
                    revision_entry_id=created.id,
                    inherited_at=clock,
                )
                project = self.project_repository.get(created.project_id) if created.project_id else None
                if project:
                    MemoryChangeService(self.memory_repository.db).emit(
                        project=project,
                        entry_id=created.id,
                        previous_entry_id=leaf.id,
                        restored_from_entry_id=source.id,
                        event_kind=MemoryChangeEventKind.restored,
                        principal=principal,
                        reason=MemoryEvidenceService.validate_reason(payload.reason),
                        occurred_at=clock,
                    )
        except IntegrityError as exc:
            self.memory_repository.db.expire_all()
            winner = self._successor(leaf.id)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "memory_restore_conflict",
                    "successor_id": str(winner.id) if winner else None,
                },
            ) from exc
        self._set_lineage(created)
        return created

    def _successor(self, entry_id: uuid.UUID) -> MemoryEntry | None:
        return self.memory_repository.get_successor(entry_id)

    def _set_lineage(self, entry: MemoryEntry) -> MemoryEntry:
        successor = self._successor(entry.id)
        entry.successor_id = successor.id if successor else None
        entry.is_current = self.memory_repository.entry_is_current(
            entry,
            successor=successor,
        )
        return entry

    def _ensure_access(self, entry: MemoryEntry, principal: AuthPrincipal | None) -> None:
        if principal and principal.tenant_ids is not None:
            project = self.project_repository.get(entry.project_id) if entry.project_id else None
            if not project or project.tenant_id not in principal.tenant_ids:
                raise HTTPException(status_code=403, detail="Project access denied")

    @staticmethod
    def _search_payload(title: str | None, content: str) -> str:
        return " ".join(value.strip() for value in (title or "", content) if value and value.strip())
