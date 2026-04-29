from memorybank_sdk import MemoryAwareAgent


class FakeMemoryClient:
    def __init__(self) -> None:
        self.created_links: list[dict] = []
        self.saved_payloads: list[dict] = []

    def get_relevant_memory(self, **kwargs):
        return {
            "context": [
                {
                    "id": "old-1",
                    "type": "decision",
                    "title": "Use PostgreSQL",
                    "content": "Prefer PostgreSQL for MVP",
                    "relevance_score": 0.91,
                }
            ]
        }

    def add_memory(self, **kwargs):
        self.saved_payloads.append(kwargs)
        return {"id": "new-1", **kwargs}

    def create_link(self, **kwargs):
        self.created_links.append(kwargs)
        return kwargs


def test_memory_aware_agent_run_links_used_context():
    client = FakeMemoryClient()
    agent = MemoryAwareAgent(agent_id="sdk-agent", memory=client, project_id="project-1")

    result = agent.run(
        "Implement DB layer",
        lambda task, context: f"{task} using {len(context)} memories",
        result_type="artifact",
        result_title="DB layer notes",
        importance=4,
    )

    assert result["memory_entry"]["id"] == "new-1"
    assert result["linked_to"] == ["old-1"]
    assert client.saved_payloads[0]["metadata"]["used_memory_ids"] == ["old-1"]
    assert client.created_links[0]["from_entry_id"] == "new-1"
    assert client.created_links[0]["to_entry_id"] == "old-1"

