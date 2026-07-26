from __future__ import annotations

import os
from typing import Any

from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient


def api_key_from_process_environment() -> str | None:
    """Read credentials only at the explicit registration boundary."""
    return os.getenv("MEMORYBANK_API_KEY") or os.getenv("MEMLAYER_WRITE_API_KEY")


def make_client(*, base_url: str, api_key: str | None = None, timeout: float = 15.0) -> MemoryBankClient:
    return MemoryBankClient(base_url=base_url or DEFAULT_MEMORYBANK_URL, api_key=api_key, timeout=timeout)


def resolve_and_verify(
    client: Any,
    *,
    connector_identity: str,
    project_name: str,
    tenant_id: str | None = None,
    existing_project_id: str | None = None,
    retries: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            resolved = client.resolve_project(
                agent="codex",
                connector_identity=connector_identity,
                project_name=project_name,
                tenant_id=tenant_id,
                existing_project_id=existing_project_id,
            )
            project = client.get_project(resolved["project_id"])
            if str(project.get("id")) != str(resolved["project_id"]):
                raise ValueError("project registration read-back id mismatch")
            if str(resolved.get("connector_identity")) != connector_identity:
                raise ValueError("project registration connector identity mismatch")
            resolved_tenant = resolved.get("tenant_id")
            project_tenant = project.get("tenant_id")
            if resolved_tenant != project_tenant:
                raise ValueError("project registration tenant read-back mismatch")
            if tenant_id is not None and resolved_tenant != tenant_id:
                raise ValueError("project registration tenant scope mismatch")
            return resolved, project
        except TimeoutError as exc:
            last_error = exc
    raise last_error or TimeoutError("project registration timed out")
