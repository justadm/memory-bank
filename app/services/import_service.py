import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from app.models.enums import MemoryType
from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.security import AuthPrincipal
from app.schemas.imports import ProjectImportRequest
from app.schemas.links import LinkCreate
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.conflict_detector import ConflictDetector
from app.services.memory_service import MemoryService, ProjectService
from memorybank_sdk.importer import build_project_import_payload


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s,;]+)"),
]


@dataclass
class ImportDecisionCandidate:
    id: str
    type: str
    title: str | None
    content: str
    project_id: str | None
    metadata: dict


class ImportService:
    def __init__(
        self,
        memory_repository: MemoryRepository,
        project_repository: ProjectRepository,
        link_repository: LinkRepository,
    ):
        self.memory_service = MemoryService(memory_repository, project_repository, link_repository)
        self.project_service = ProjectService(project_repository)
        self.project_repository = project_repository
        self.memory_repository = memory_repository
        self.conflict_detector = ConflictDetector()

    def import_project_scan(self, payload: ProjectImportRequest, *, principal: AuthPrincipal | None = None) -> dict:
        project = self._resolve_project(payload.project, payload.project_id, principal=principal)
        conflicts = self._detect_conflicts(project, payload) if payload.detect_conflicts else []
        conflicts_by_ref: dict[str, list[dict]] = {}
        for item in conflicts:
            conflicts_by_ref.setdefault(item["entry_ref"], []).append(item)
        import_event = self._record_import_event(project=project, payload=payload, principal=principal)

        entry_refs: dict[str, uuid.UUID] = {}
        entries_created = 0
        entries_updated = 0
        entries_skipped = 0
        quality_review_required_count = 0
        for item in payload.entries:
            if item.ref in entry_refs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate entry ref: {item.ref}",
                )
            title = self._mask_text(item.title)
            content = self._mask_text(item.content) or ""
            metadata = self._mask_metadata(item.metadata)
            if item.ref in conflicts_by_ref:
                metadata["requires_review"] = True
                metadata["import_conflicts"] = [
                    {
                        "reason": conflict["reason"],
                        "confidence": conflict["confidence"],
                        "conflicting_entry_id": str(conflict["conflicting_entry_id"])
                        if conflict["conflicting_entry_id"]
                        else None,
                        "conflicting_ref": conflict["conflicting_ref"],
                    }
                    for conflict in conflicts_by_ref[item.ref]
                ]
            existing = self.memory_repository.find_import_match(
                project_id=project.id,
                memory_type=item.type,
                title=title,
                content=content,
            )
            if existing and payload.existing_entry_mode == "skip":
                entry_refs[item.ref] = existing.id
                entries_skipped += 1
                continue
            if existing and payload.existing_entry_mode == "update":
                updated = self.memory_service.update_memory(
                    existing.id,
                    MemoryUpdate(
                        title=title,
                        content=content,
                        source_agent=item.source_agent,
                        project_id=project.id,
                        importance=item.importance,
                        metadata=metadata,
                        archived=False,
                    ),
                    principal=principal,
                    enforce_quality_gate=False,
                )
                entry_refs[item.ref] = updated.id
                if updated.metadata_.get("quality_review_required"):
                    quality_review_required_count += 1
                entries_updated += 1
                continue

            created = self.memory_service.create_memory(
                MemoryCreate(
                    type=item.type,
                    title=title,
                    content=content,
                    source_agent=item.source_agent,
                    project_id=project.id,
                    importance=item.importance,
                    metadata=metadata,
                ),
                principal=principal,
                enforce_quality_gate=False,
            )
            entry_refs[item.ref] = created.id
            if created.metadata_.get("quality_review_required"):
                quality_review_required_count += 1
            entries_created += 1

        created_links = 0
        skipped_links = 0
        for item in payload.links:
            from_entry_id = entry_refs.get(item.from_ref)
            to_entry_id = entry_refs.get(item.to_ref)
            if not from_entry_id or not to_entry_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Link references unknown refs: {item.from_ref} -> {item.to_ref}",
                )
            if self.memory_service.link_repository.find_by_pair(from_entry_id, to_entry_id, item.type):
                skipped_links += 1
                continue
            self.memory_service.create_link(
                LinkCreate(
                    from_entry_id=from_entry_id,
                    to_entry_id=to_entry_id,
                    type=item.type,
                    strength=item.strength,
                    created_by_agent=item.created_by_agent,
                    metadata=self._mask_metadata(item.metadata),
                ),
                principal=principal,
            )
            created_links += 1

        return {
            "project": project,
            "import_event_id": import_event.id,
            "entries_created": entries_created,
            "entries_updated": entries_updated,
            "entries_skipped": entries_skipped,
            "quality_review_required_count": quality_review_required_count,
            "links_created": created_links,
            "links_skipped": skipped_links,
            "entry_refs": entry_refs,
            "conflicts_detected": len(conflicts),
            "conflicts": conflicts,
        }

    def _record_import_event(
        self,
        *,
        project: Project,
        payload: ProjectImportRequest,
        principal: AuthPrincipal | None,
    ):
        title = self._mask_text(payload.import_event.title)
        content = self._mask_text(payload.import_event.content)
        metadata = self._build_import_event_metadata(payload=payload)
        existing = None
        if payload.existing_entry_mode == "update":
            existing = self._find_active_import_event(
                project_id=project.id,
                source_agent=payload.import_event.source_agent,
                import_type=metadata.get("import_type"),
            )
        if existing:
            metadata = self._build_import_event_metadata(payload=payload, previous_metadata=existing.metadata_)
            return self.memory_service.update_memory(
                existing.id,
                MemoryUpdate(
                    title=title,
                    content=content,
                    source_agent=payload.import_event.source_agent,
                    project_id=project.id,
                    importance=payload.import_event.importance,
                    metadata=metadata,
                    archived=False,
                ),
                principal=principal,
                enforce_quality_gate=False,
            )

        return self.memory_service.create_memory(
            MemoryCreate(
                type="event",
                title=title,
                content=content,
                source_agent=payload.import_event.source_agent,
                project_id=project.id,
                importance=payload.import_event.importance,
                metadata=metadata,
            ),
            principal=principal,
            enforce_quality_gate=False,
        )

    def _find_active_import_event(
        self,
        *,
        project_id: uuid.UUID,
        source_agent: str,
        import_type: object,
    ):
        if not import_type:
            return None
        for entry in self.memory_repository.list(project_id=project_id, memory_type=MemoryType.event, archived=False):
            metadata = entry.metadata_ if isinstance(entry.metadata_, dict) else {}
            if (
                entry.source_agent == source_agent
                and metadata.get("import_type") == import_type
            ):
                return entry
        return None

    def _build_import_event_metadata(
        self,
        *,
        payload: ProjectImportRequest,
        previous_metadata: dict | None = None,
    ) -> dict:
        previous = dict(previous_metadata or {})
        metadata = {
            key: value
            for key, value in previous.items()
            if key not in {"quality", "quality_review_required", "review_overdue"}
        }
        metadata.update(self._mask_metadata(payload.import_event.metadata))
        now = datetime.now(timezone.utc).isoformat()
        previous_runs_count = int(previous.get("import_runs_count", 0) or 0)
        metadata["import_runs_count"] = previous_runs_count + 1
        metadata["last_imported_at"] = now
        metadata["evidence"] = {
            "kind": "project_import_event",
            "existing_entry_mode": payload.existing_entry_mode,
            "entries_count": len(payload.entries),
            "links_count": len(payload.links),
        }
        history = previous.get("import_history", [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "imported_at": now,
                "existing_entry_mode": payload.existing_entry_mode,
                "entries_count": len(payload.entries),
                "links_count": len(payload.links),
            }
        )
        metadata["import_history"] = history[-10:]
        return metadata

    def reimport_project_scan(
        self,
        *,
        project_id: uuid.UUID,
        source_path: str | None = None,
        existing_entry_mode: str = "update",
        detect_conflicts: bool = True,
        principal: AuthPrincipal | None = None,
    ) -> dict:
        project = self.project_service.get_project(project_id, principal=principal)
        resolved_source_path = source_path or (
            project.metadata_.get("source_path") if isinstance(project.metadata_, dict) else None
        )
        if not resolved_source_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project source_path is not configured")

        root = Path(resolved_source_path).expanduser()
        if not root.exists() or not root.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project source_path is not accessible to the server: {resolved_source_path}",
            )

        payload = build_project_import_payload(
            root,
            project_name=project.name,
            project_description=project.description,
        )
        payload["project_id"] = project.id
        payload.pop("project", None)
        payload["existing_entry_mode"] = existing_entry_mode
        payload["detect_conflicts"] = detect_conflicts

        return self.import_project_scan(ProjectImportRequest.model_validate(payload), principal=principal)

    def _resolve_project(
        self,
        project_payload: ProjectCreate | None,
        project_id: uuid.UUID | None,
        *,
        principal: AuthPrincipal | None = None,
    ) -> Project:
        if project_payload:
            existing = self._find_existing_project_for_import(project_payload, principal=principal)
            if existing:
                desired_metadata = dict(project_payload.metadata)
                existing_metadata = dict(existing.metadata_ or {})
                changed = False
                for key, value in desired_metadata.items():
                    if existing_metadata.get(key) != value:
                        existing_metadata[key] = value
                        changed = True
                description = project_payload.description
                if changed or (description and description != existing.description):
                    return self.project_service.update_project(
                        existing.id,
                        ProjectUpdate(description=description or existing.description, metadata=existing_metadata),
                        principal=principal,
                    )
                return existing
            return self.project_service.create_project(project_payload, principal=principal)
        return self.project_service.get_project(project_id, principal=principal)

    def _find_existing_project_for_import(
        self,
        project_payload: ProjectCreate,
        *,
        principal: AuthPrincipal | None = None,
    ) -> Project | None:
        source_path = None
        if isinstance(project_payload.metadata, dict):
            raw_source_path = project_payload.metadata.get("source_path")
            source_path = str(raw_source_path) if raw_source_path else None

        candidates = self.project_service.list_projects(principal=principal)

        if source_path:
            for project in candidates:
                metadata = project.metadata_ if isinstance(project.metadata_, dict) else {}
                if str(metadata.get("source_path") or "") == source_path:
                    return project

        for project in candidates:
            if project.name == project_payload.name:
                return project

        return None

    def _mask_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        masked = value
        for pattern in SECRET_PATTERNS:
            masked = pattern.sub(r"\1[REDACTED]", masked)
        return masked

    def _mask_metadata(self, metadata: dict) -> dict:
        masked = deepcopy(metadata)
        for key, value in list(masked.items()):
            if isinstance(value, str):
                masked[key] = self._mask_text(value)
            elif isinstance(value, dict):
                masked[key] = self._mask_metadata(value)
            elif isinstance(value, list):
                masked[key] = [self._mask_text(item) if isinstance(item, str) else item for item in value]
        return masked

    def _detect_conflicts(self, project: Project, payload: ProjectImportRequest) -> list[dict]:
        existing_decisions = self.memory_repository.list(
            project_id=project.id,
            memory_type=MemoryType.decision,
            archived=False,
        )
        seen_batch_decisions: list[ImportDecisionCandidate] = []
        conflicts: list[dict] = []

        for item in payload.entries:
            if item.type != MemoryType.decision:
                continue

            candidate = ImportDecisionCandidate(
                id=item.ref,
                type=item.type.value,
                title=self._mask_text(item.title),
                content=self._mask_text(item.content) or "",
                project_id=str(project.id),
                metadata=self._mask_metadata(item.metadata),
            )
            detected = self.conflict_detector.detect(candidate, [*existing_decisions, *seen_batch_decisions])
            for match in detected:
                conflict_payload = {
                    "entry_ref": item.ref,
                    "conflicting_entry_id": None,
                    "conflicting_ref": None,
                    "reason": match.reason,
                    "confidence": match.confidence,
                }
                try:
                    conflict_payload["conflicting_entry_id"] = uuid.UUID(match.existing_entry_id)
                except ValueError:
                    conflict_payload["conflicting_ref"] = match.existing_entry_id
                conflicts.append(conflict_payload)
            seen_batch_decisions.append(candidate)

        return conflicts
