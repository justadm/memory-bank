from memorybank_sdk import MemoryAwareAgent


class FakeMemoryClient:
    def __init__(self) -> None:
        self.created_links: list[dict] = []
        self.saved_payloads: list[dict] = []
        self.task_logs: list[dict] = []
        self.import_payloads: list[dict] = []

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

    def evaluate_memory_usage(self, **kwargs):
        return {
            "used_memory": True,
            "memory_entries_count": len(kwargs.get("memory", [])),
            "referenced_memory_in_answer": True,
            "likely_influenced_decision": True,
            "possible_conflict": False,
            "quality_score": 0.9,
            "consistency_score": 0.95,
            "notes": ["Memory appears to be used meaningfully."],
        }

    def create_task_log(self, **kwargs):
        self.task_logs.append(kwargs)
        return {"id": "task-log-1", **kwargs}

    def import_project_scan(self, **kwargs):
        self.import_payloads.append(kwargs)
        return {
            "project": {"id": "project-1", "name": kwargs["project"]["name"]},
            "import_event_id": "event-1",
            "entries_created": len(kwargs.get("entries", [])),
            "links_created": len(kwargs.get("links", [])),
            "entry_refs": {item["ref"]: f"memory-{index}" for index, item in enumerate(kwargs.get("entries", []), start=1)},
        }


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
    assert result["evaluation"]["quality_score"] == 0.9
    assert result["task_log"]["task_description"] == "Implement DB layer"
    assert client.task_logs[0]["memory_entries_count"] == 1


def test_memory_aware_agent_supports_structured_handler_output():
    client = FakeMemoryClient()
    agent = MemoryAwareAgent(agent_id="sdk-agent", memory=client, project_id="project-1")

    result = agent.run(
        "Review architecture",
        lambda task, context: {
            "answer": f"{task} using {len(context)} memories",
            "reasoning": "According to memory, keep PostgreSQL.",
            "metadata": {"mode": "review"},
        },
        result_type="artifact",
        result_title="Architecture review",
        importance=4,
    )

    assert result["reasoning"] == "According to memory, keep PostgreSQL."
    assert result["memory_entry"]["metadata"]["mode"] == "review"
    assert result["task_log"]["result_quality_score"] == 0.9


def test_sdk_project_import_helper():
    client = FakeMemoryClient()

    result = client.import_project_scan(
        project={"name": "Imported Project", "description": "SDK import"},
        entries=[
            {"ref": "decision-db", "type": "decision", "content": "Use PostgreSQL."},
            {"ref": "risk-secrets", "type": "risk", "content": "Never keep token=abc."},
        ],
        links=[{"from_ref": "risk-secrets", "to_ref": "decision-db", "type": "affects"}],
    )

    assert result["project"]["name"] == "Imported Project"
    assert result["entries_created"] == 2
    assert result["links_created"] == 1
    assert client.import_payloads[0]["entries"][1]["type"] == "risk"
