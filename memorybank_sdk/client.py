from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

DEFAULT_MEMORYBANK_URL = "http://127.0.0.1:18100"
DEFAULT_MEMORYBANK_FALLBACK_URL = "https://memlayer.loc/api"
SearchScope = Literal["project", "related", "global"]

MemoryType = Literal["decision", "task", "artifact", "event", "note", "constraint", "risk"]
LinkType = Literal[
    "depends_on",
    "related_to",
    "created_after",
    "affects",
    "derived_from",
    "blocks",
    "resolves",
]


class MemoryBankError(RuntimeError):
    pass


@dataclass
class MemoryBankClient:
    base_url: str
    api_key: str | None = None
    timeout: float = 15.0
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.Client(
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise MemoryBankError(f"MemoryBank error {response.status_code}: {response.text}")
        if response.text:
            return response.json()
        return None

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def auth_status(self) -> dict[str, Any]:
        return self._request("GET", "/auth/me")

    def create_project(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/projects",
            json={"name": name, "description": description, "metadata": metadata or {}},
        )

    def resolve_project(
        self,
        *,
        agent: Literal["codex"],
        connector_identity: str,
        project_name: str,
        tenant_id: str | None = None,
        existing_project_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent": agent,
            "connector_identity": connector_identity,
            "project_name": project_name,
        }
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        if existing_project_id is not None:
            payload["existing_project_id"] = existing_project_id
        return self._request("POST", "/projects/resolve", json=payload)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}")

    def verify_project_connector(
        self,
        project_id: str,
        *,
        agent: str,
        connector_identity: str,
        tenant_id: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "agent": agent,
            "connector_identity": connector_identity,
        }
        if tenant_id is not None:
            params["tenant_id"] = tenant_id
        return self._request(
            "GET",
            f"/projects/{project_id}/connector-binding",
            params=params,
        )

    def import_project_scan(
        self,
        *,
        project: dict[str, Any] | None = None,
        project_id: str | None = None,
        import_event: dict[str, Any] | None = None,
        entries: list[dict[str, Any]] | None = None,
        links: list[dict[str, Any]] | None = None,
        detect_conflicts: bool = True,
        existing_entry_mode: Literal["create", "skip", "update"] = "create",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/imports/project-scan",
            json={
                "project": project,
                "project_id": project_id,
                "import_event": import_event
                or {
                    "title": "Initial project import",
                    "content": "Imported existing project into MemoryBank.",
                    "source_agent": "memorybank-import-agent",
                    "importance": 3,
                    "metadata": {"import_type": "initial_project_scan"},
                },
                "entries": entries or [],
                "links": links or [],
                "detect_conflicts": detect_conflicts,
                "existing_entry_mode": existing_entry_mode,
            },
        )

    def add_memory(
        self,
        *,
        type: MemoryType,
        content: str,
        title: str | None = None,
        source_agent: str | None = None,
        project_id: str | None = None,
        importance: int = 3,
        metadata: dict[str, Any] | None = None,
        provenance: str = "unspecified",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/memory",
            json={
                "type": type,
                "title": title,
                "content": content,
                "source_agent": source_agent,
                "project_id": project_id,
                "importance": importance,
                "metadata": metadata or {},
                "provenance": provenance,
                "confidence": confidence,
            },
        )

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/memory/{memory_id}")

    def revise_memory(
        self,
        memory_id: str,
        *,
        changes: dict[str, Any],
        reason: str,
        metadata_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/memory/{memory_id}/revise",
            json={"changes": changes, "metadata_patch": metadata_patch or {}, "reason": reason},
        )

    def memory_history(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/memory/{memory_id}/history")

    def restore_memory(self, memory_id: str, *, source_entry_id: str | None = None, reason: str = "restored historical memory") -> dict[str, Any]:
        payload: dict[str, Any] = {"reason": reason}
        if source_entry_id is not None:
            payload["source_entry_id"] = source_entry_id
        return self._request("POST", f"/memory/{memory_id}/restore", json=payload)

    def memory_changes(
        self,
        *,
        project_id: str,
        cursor: str | None = None,
        after_sequence: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"project_id": project_id, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if after_sequence is not None:
            params["after_sequence"] = after_sequence
        return self._request("GET", "/memory/changes", params=params)

    def list_memory(
        self,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
        archived: bool | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id
        if memory_type:
            params["type"] = memory_type
        if archived is not None:
            params["archived"] = str(archived).lower()
        if as_of is not None:
            params["as_of"] = as_of
        return self._request("GET", "/memory", params=params)

    def update_memory(self, memory_id: str, **patch: Any) -> dict[str, Any]:
        clean_patch = {key: value for key, value in patch.items() if value is not None}
        return self._request("PATCH", f"/memory/{memory_id}", json=clean_patch)

    def archive_memory(self, memory_id: str) -> dict[str, Any]:
        return self._request("POST", f"/memory/{memory_id}/archive")

    def search_memory(
        self,
        query: str,
        *,
        project_id: str | None = None,
        limit: int = 10,
        scope: SearchScope = "project",
        mode: Literal["lexical", "semantic", "hybrid"] = "hybrid",
        as_of: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "limit": limit, "scope": scope, "mode": mode}
        if project_id:
            params["project_id"] = project_id
        if as_of is not None:
            params["as_of"] = as_of
        return self._request("GET", "/memory/search", params=params)

    def get_relevant_memory(
        self,
        *,
        query: str,
        agent_id: str,
        project_id: str | None = None,
        types: list[str] | None = None,
        limit: int = 8,
        scope: SearchScope = "project",
        search_mode: Literal["lexical", "semantic", "hybrid"] = "hybrid",
        metadata: dict[str, Any] | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/memory/relevant",
            json={
                "query": query,
                "agent_id": agent_id,
                "project_id": project_id,
                "types": types or ["decision", "task", "artifact", "note"],
                "scope": scope,
                "limit": limit,
                "search_mode": search_mode,
                "metadata": metadata or {},
                "as_of": as_of,
            },
        )

    def build_context(
        self,
        *,
        query: str,
        project_id: str | None = None,
        agent_id: str | None = None,
        scope: SearchScope = "project",
        mode: Literal["lexical", "semantic", "hybrid"] = "hybrid",
        limit: int = 12,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/context/build",
            json={
                "query": query,
                "project_id": project_id,
                "agent_id": agent_id,
                "scope": scope,
                "mode": mode,
                "limit": limit,
            },
        )

    def runtime_self_check(
        self,
        *,
        project_id: str | None = None,
        search_query: str = "architecture",
        limit: int = 5,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"search_query": search_query, "limit": limit}
        if project_id:
            params["project_id"] = project_id
        return self._request("GET", "/admin/runtime/self-check", params=params)

    def create_link(
        self,
        *,
        from_entry_id: str,
        to_entry_id: str,
        type: LinkType = "related_to",
        strength: float = 1.0,
        created_by_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/memory-links",
            json={
                "from_entry_id": from_entry_id,
                "to_entry_id": to_entry_id,
                "type": type,
                "strength": strength,
                "created_by_agent": created_by_agent,
                "metadata": metadata or {},
            },
        )

    def get_links(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/memory/{memory_id}/links")

    def get_graph(self, memory_id: str, depth: int = 2) -> dict[str, Any]:
        return self._request("GET", f"/memory/{memory_id}/graph", params={"depth": depth})

    def evaluate_memory_usage(
        self,
        *,
        task: str,
        memory: list[dict[str, Any]],
        reasoning: str = "",
        answer: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/evaluation/evaluate",
            json={"task": task, "memory": memory, "reasoning": reasoning, "answer": answer},
        )

    def evaluate_memory_usage_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", "/evaluation/evaluate-batch", json={"items": items})

    def create_task_log(
        self,
        *,
        task_description: str,
        used_memory: bool,
        memory_entries_count: int,
        experiment_id: str | None = None,
        group_name: str | None = None,
        agent_id: str | None = None,
        duration_seconds: float | None = None,
        result_quality_score: float | None = None,
        duplicate_count: int = 0,
        consistency_score: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/task-logs",
            json={
                "experiment_id": experiment_id,
                "group_name": group_name,
                "agent_id": agent_id,
                "task_description": task_description,
                "used_memory": used_memory,
                "memory_entries_count": memory_entries_count,
                "duration_seconds": duration_seconds,
                "result_quality_score": result_quality_score,
                "duplicate_count": duplicate_count,
                "consistency_score": consistency_score,
                "metadata": metadata or {},
            },
        )

    def import_task_logs(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request("POST", "/task-logs/import", json={"items": items})

    def __enter__(self) -> MemoryBankClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
