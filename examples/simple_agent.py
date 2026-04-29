from __future__ import annotations

import os

from memorybank_sdk import MemoryAwareAgent, MemoryBankClient


def fake_llm_handler(task: str, memory_context: list[dict]) -> str:
    decisions = [item for item in memory_context if item.get("type") == "decision"]
    context_text = "\n".join(
        f"- [{item.get('type')}] {item.get('title')}: {item.get('content', '')[:200]}"
        for item in memory_context
    )

    return f"""
Task completed: {task}

Relevant memory used:
{context_text or '- No relevant memory found'}

Decision handling:
{f'Followed {len(decisions)} previous decisions.' if decisions else 'No prior decisions found.'}

Result:
Implemented according to available Memory Bank context.
""".strip()


def main() -> None:
    base_url = os.getenv("MEMORYBANK_URL", "http://localhost:8000")
    project_id = os.getenv("MEMORYBANK_PROJECT_ID")

    with MemoryBankClient(base_url=base_url) as client:
        agent = MemoryAwareAgent(
            agent_id="example-agent",
            memory=client,
            project_id=project_id,
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


if __name__ == "__main__":
    main()

