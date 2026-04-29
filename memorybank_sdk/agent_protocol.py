from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from memorybank_sdk.client import MemoryBankClient, MemoryBankError, MemoryType


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
    log_task_runs: bool = True
    evaluate_task_runs: bool = True
    experiment_id: str | None = None
    group_name: str | None = None

    def run(
        self,
        task: str,
        handler: Callable[[str, list[dict[str, Any]]], str | dict[str, Any]],
        *,
        result_type: MemoryType = "artifact",
        result_title: str | None = None,
        importance: int = 3,
    ) -> dict[str, Any]:
        started_at = perf_counter()
        relevant_response = self.memory.get_relevant_memory(
            query=task,
            agent_id=self.agent_id,
            project_id=self.project_id,
            limit=self.default_limit,
        )

        context = relevant_response.get("context") or relevant_response.get("items") or []
        handler_output = handler(task, context)
        normalized_output = self._normalize_handler_output(handler_output)
        result = normalized_output["answer"]
        reasoning = normalized_output["reasoning"]
        extra_metadata = normalized_output["metadata"]

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
                **extra_metadata,
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

        duration_seconds = round(perf_counter() - started_at, 4)
        evaluation = self._evaluate_task(task=task, context=context, reasoning=reasoning, answer=result)
        task_log = self._log_task_run(
            task=task,
            context=context,
            duration_seconds=duration_seconds,
            evaluation=evaluation,
            memory_entry_id=saved["id"],
            linked_ids=linked_ids,
        )

        return {
            "task": task,
            "result": result,
            "reasoning": reasoning,
            "memory_entry": saved,
            "linked_to": linked_ids,
            "evaluation": evaluation,
            "task_log": task_log,
        }

    @staticmethod
    def _normalize_handler_output(handler_output: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(handler_output, str):
            return {"answer": handler_output, "reasoning": "", "metadata": {}}
        return {
            "answer": str(handler_output.get("answer", "")),
            "reasoning": str(handler_output.get("reasoning", "")),
            "metadata": dict(handler_output.get("metadata", {})),
        }

    def _evaluate_task(
        self,
        *,
        task: str,
        context: list[dict[str, Any]],
        reasoning: str,
        answer: str,
    ) -> dict[str, Any] | None:
        if not self.evaluate_task_runs:
            return None
        try:
            return self.memory.evaluate_memory_usage(
                task=task,
                memory=context,
                reasoning=reasoning,
                answer=answer,
            )
        except MemoryBankError:
            return None

    def _log_task_run(
        self,
        *,
        task: str,
        context: list[dict[str, Any]],
        duration_seconds: float,
        evaluation: dict[str, Any] | None,
        memory_entry_id: str,
        linked_ids: list[str],
    ) -> dict[str, Any] | None:
        if not self.log_task_runs:
            return None
        try:
            return self.memory.create_task_log(
                experiment_id=self.experiment_id,
                group_name=self.group_name,
                agent_id=self.agent_id,
                task_description=task,
                used_memory=bool(context),
                memory_entries_count=len(context),
                duration_seconds=duration_seconds,
                result_quality_score=(evaluation or {}).get("quality_score"),
                consistency_score=(evaluation or {}).get("consistency_score"),
                duplicate_count=0,
                metadata={
                    "result_entry_id": memory_entry_id,
                    "linked_ids": linked_ids,
                    "used_memory_ids": [item.get("id") for item in context if item.get("id")],
                },
            )
        except MemoryBankError:
            return None
