from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx


MemoryType = Literal["decision", "task", "artifact", "event", "note"]
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
            },
        )

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        return self._request("GET", f"/memory/{memory_id}")

    def list_memory(
        self,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id
        if memory_type:
            params["type"] = memory_type
        if archived is not None:
            params["archived"] = str(archived).lower()
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
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "limit": limit}
        if project_id:
            params["project_id"] = project_id
        return self._request("GET", "/memory/search", params=params)

    def get_relevant_memory(
        self,
        *,
        query: str,
        agent_id: str,
        project_id: str | None = None,
        types: list[str] | None = None,
        limit: int = 8,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/memory/relevant",
            json={
                "query": query,
                "agent_id": agent_id,
                "project_id": project_id,
                "types": types or ["decision", "task", "artifact", "note"],
                "limit": limit,
                "metadata": metadata or {},
            },
        )

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

    def __enter__(self) -> MemoryBankClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

