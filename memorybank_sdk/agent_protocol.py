from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from memorybank_sdk.client import MemoryBankClient, MemoryType


@dataclass
class MemoryAwareAgent:
    """
    Minimal agent wrapper following the Memory Bank loop:
    READ -> ACT -> WRITE -> LINK
    """

    agent_id: str
    memory: MemoryBankClient
    project_id: str | None = None
    default_limit: int = 8

    def run(
        self,
        task: str,
        handler: Callable[[str, list[dict[str, Any]]], str],
        *,
        result_type: MemoryType = "artifact",
        result_title: str | None = None,
        importance: int = 3,
    ) -> dict[str, Any]:
        relevant_response = self.memory.get_relevant_memory(
            query=task,
            agent_id=self.agent_id,
            project_id=self.project_id,
            limit=self.default_limit,
        )

        context = relevant_response.get("context") or relevant_response.get("items") or []
        result = handler(task, context)

        saved = self.memory.add_memory(
            type=result_type,
            title=result_title or f"Result: {task[:80]}",
            content=result,
            source_agent=self.agent_id,
            project_id=self.project_id,
            importance=importance,
            metadata={
                "task": task,
                "used_memory_ids": [item.get("id") for item in context if item.get("id")],
            },
        )

        new_id = saved["id"]
        linked_ids: list[str] = []
        for item in context[:5]:
            old_id = item.get("id")
            if not old_id:
                continue
            self.memory.create_link(
                from_entry_id=new_id,
                to_entry_id=old_id,
                type="derived_from",
                strength=float(item.get("relevance_score", item.get("score", 0.7))),
                created_by_agent=self.agent_id,
            )
            linked_ids.append(old_id)

        return {
            "task": task,
            "result": result,
            "memory_entry": saved,
            "linked_to": linked_ids,
        }

