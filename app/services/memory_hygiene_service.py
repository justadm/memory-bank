from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from app.config import Settings
from app.models.enums import MemoryLinkType
from app.models.memory_entry import MemoryEntry
from app.models.memory_link import MemoryLink
from app.models.project import Project
from app.repositories.link_repository import LinkRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.project_repository import ProjectRepository
from app.services.auto_link_service import AutoLinkService


@dataclass(frozen=True)
class ProjectAssignmentCandidate:
    entry_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    evidence: str


@dataclass(frozen=True)
class LinkCandidate:
    from_entry_id: uuid.UUID
    to_entry_id: uuid.UUID
    project_id: uuid.UUID | None
    similarity: float


@dataclass
class MemoryHygieneResult:
    project_assignments_count: int = 0
    links_created_count: int = 0
    project_assignment_candidates: list[ProjectAssignmentCandidate] = field(default_factory=list)
    link_candidates: list[LinkCandidate] = field(default_factory=list)
    dry_run: bool = True


@dataclass(frozen=True)
class _ProjectPath:
    project: Project
    source_path: str
    normalized_source_path: str


class MemoryHygieneService:
    def __init__(
        self,
        *,
        memory_repository: MemoryRepository,
        project_repository: ProjectRepository,
        link_repository: LinkRepository,
        settings: Settings,
    ):
        self.memory_repository = memory_repository
        self.project_repository = project_repository
        self.link_repository = link_repository
        self.settings = settings

    def run(
        self,
        *,
        project_id: uuid.UUID | None = None,
        assign_project_ids: bool = True,
        relink: bool = True,
        dry_run: bool = True,
        min_similarity: float | None = None,
        max_links_per_entry: int = 2,
        max_candidates_per_entry: int = 30,
        min_existing_links: int = 1,
    ) -> MemoryHygieneResult:
        result = MemoryHygieneResult(dry_run=dry_run)
        if assign_project_ids:
            self._assign_project_ids(result, project_id=project_id, dry_run=dry_run)
        if relink:
            self._relink(
                result,
                project_id=project_id,
                dry_run=dry_run,
                min_similarity=min_similarity if min_similarity is not None else self.settings.auto_link_min_similarity,
                max_links_per_entry=max_links_per_entry,
                max_candidates_per_entry=max_candidates_per_entry,
                min_existing_links=min_existing_links,
            )
        return result

    def _assign_project_ids(
        self,
        result: MemoryHygieneResult,
        *,
        project_id: uuid.UUID | None,
        dry_run: bool,
    ) -> None:
        project_paths = self._project_paths(project_id=project_id)
        if not project_paths:
            return

        entries = self.memory_repository.list(archived=False)
        for entry in entries:
            if entry.project_id is not None:
                continue
            match = self._match_project(entry, project_paths)
            if match is None:
                continue

            project_path, evidence = match
            candidate = ProjectAssignmentCandidate(
                entry_id=entry.id,
                project_id=project_path.project.id,
                project_name=project_path.project.name,
                evidence=evidence,
            )
            result.project_assignment_candidates.append(candidate)
            result.project_assignments_count += 1
            if dry_run:
                continue

            entry.project_id = project_path.project.id
            metadata = dict(entry.metadata_ or {})
            metadata["project_id_hygiene"] = {
                "assigned_by": "source_path",
                "project_name": project_path.project.name,
                "evidence": evidence,
            }
            entry.metadata_ = metadata

    def _relink(
        self,
        result: MemoryHygieneResult,
        *,
        project_id: uuid.UUID | None,
        dry_run: bool,
        min_similarity: float,
        max_links_per_entry: int,
        max_candidates_per_entry: int,
        min_existing_links: int,
    ) -> None:
        if max_links_per_entry <= 0:
            return

        entries = self.memory_repository.list(project_id=project_id, archived=False)
        entries = [entry for entry in entries if entry.project_id is not None]
        vectors = {
            entry.id: AutoLinkService._embed(AutoLinkService._compose_text(entry.title, entry.content)) for entry in entries
        }

        for entry in entries:
            if self._link_count(entry) > min_existing_links:
                continue

            candidates = [candidate for candidate in entries if candidate.id != entry.id and candidate.project_id == entry.project_id]
            candidates.sort(key=lambda candidate: candidate.created_at, reverse=True)
            created_for_entry = 0
            for candidate in candidates[:max_candidates_per_entry]:
                if self._related_link_exists(entry.id, candidate.id):
                    continue

                similarity = AutoLinkService._cosine(vectors[entry.id], vectors[candidate.id])
                if similarity < min_similarity:
                    continue

                link_candidate = LinkCandidate(
                    from_entry_id=entry.id,
                    to_entry_id=candidate.id,
                    project_id=entry.project_id,
                    similarity=round(similarity, 4),
                )
                result.link_candidates.append(link_candidate)
                result.links_created_count += 1
                created_for_entry += 1

                if not dry_run:
                    self.link_repository.create(
                        MemoryLink(
                            from_entry_id=entry.id,
                            to_entry_id=candidate.id,
                            type=MemoryLinkType.related_to,
                            strength=link_candidate.similarity,
                            created_by_agent="memory-hygiene",
                            metadata_={"method": "maintenance_relink"},
                        )
                    )

                if created_for_entry >= max_links_per_entry:
                    break

    def _project_paths(self, *, project_id: uuid.UUID | None) -> list[_ProjectPath]:
        projects = [self.project_repository.get(project_id)] if project_id else self.project_repository.list()
        paths: list[_ProjectPath] = []
        for project in projects:
            if project is None or not isinstance(project.metadata_, dict):
                continue
            source_path = project.metadata_.get("source_path")
            if not source_path:
                continue
            source_path_text = str(source_path).strip()
            if not source_path_text:
                continue
            paths.append(
                _ProjectPath(
                    project=project,
                    source_path=source_path_text,
                    normalized_source_path=self._normalize_path(source_path_text),
                )
            )
        paths.sort(key=lambda item: len(item.normalized_source_path), reverse=True)
        return paths

    def _match_project(
        self, entry: MemoryEntry, project_paths: list[_ProjectPath]
    ) -> tuple[_ProjectPath, str] | None:
        text_values = self._collect_text_values(
            {
                "title": entry.title,
                "content": entry.content,
                "metadata": entry.metadata_,
            }
        )
        normalized_values = [self._normalize_path(value) for value in text_values if "/" in value]
        haystack = "\n".join(text_values)

        for project_path in project_paths:
            if project_path.source_path in haystack:
                return project_path, project_path.source_path
            for value in normalized_values:
                if self._path_is_under(value, project_path.normalized_source_path):
                    return project_path, value
        return None

    def _related_link_exists(self, first_id: uuid.UUID, second_id: uuid.UUID) -> bool:
        return bool(
            self.link_repository.find_by_pair(first_id, second_id, MemoryLinkType.related_to)
            or self.link_repository.find_by_pair(second_id, first_id, MemoryLinkType.related_to)
        )

    def _link_count(self, entry: MemoryEntry) -> int:
        outgoing, incoming = self.link_repository.get_for_entry(entry.id)
        return len(outgoing) + len(incoming)

    def _collect_text_values(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            values: list[str] = []
            for item in value.values():
                values.extend(self._collect_text_values(item))
            return values
        if isinstance(value, list | tuple | set):
            values = []
            for item in value:
                values.extend(self._collect_text_values(item))
            return values
        return [str(value)]

    @staticmethod
    def _normalize_path(value: str) -> str:
        return "/" + str(PurePosixPath(value.strip()).as_posix()).strip("/")

    @staticmethod
    def _path_is_under(path: str, parent: str) -> bool:
        return path == parent or path.startswith(f"{parent}/")
