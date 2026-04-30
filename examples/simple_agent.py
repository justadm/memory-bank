from __future__ import annotations

import os

from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryAwareAgent, MemoryBankClient


def fake_llm_handler(task: str, memory_context: list[dict]) -> str:
    decisions = [item for item in memory_context if item.get("type") == "decision"]
    context_text = "\n".join(
        f"- [{item.get('type')}] {item.get('title')}: {item.get('content', '')[:200]}"
        for item in memory_context
    )

    return {
        "reasoning": f"Used {len(memory_context)} memory items before producing the answer.",
        "answer": f"""
Task completed: {task}

Relevant memory used:
{context_text or '- No relevant memory found'}

Decision handling:
{f'Followed {len(decisions)} previous decisions.' if decisions else 'No prior decisions found.'}

Result:
Implemented according to available Memory Bank context.
""".strip(),
        "metadata": {"example": True},
    }


def main() -> None:
    base_url = os.getenv("MEMORYBANK_URL", DEFAULT_MEMORYBANK_URL)
    project_id = os.getenv("MEMORYBANK_PROJECT_ID")
    api_key = os.getenv("MEMORYBANK_API_KEY")

    with MemoryBankClient(base_url=base_url, api_key=api_key) as client:
        agent = MemoryAwareAgent(
            agent_id="example-agent",
            memory=client,
            project_id=project_id,
            experiment_id="sdk-example",
            group_name="WITH_MEMORY",
        )
        result = agent.run(
            "Implement search endpoint for Memory Bank",
            fake_llm_handler,
            result_type="artifact",
            result_title="Search endpoint implementation notes",
            importance=3,
        )

    print("Saved memory:", result["memory_entry"])
    print("Linked to:", result["linked_to"])
    print("Evaluation:", result["evaluation"])
    print("Task log:", result["task_log"])


if __name__ == "__main__":
    main()
