import uuid

from sqlalchemy.orm import Session

from app.models.access_log import MemoryAccessLog
from app.models.memory_entry import MemoryEntry


def test_create_project(client):
    response = client.post("/projects", json={"name": "Memory Bank MVP", "description": "Simple memory layer"})
    assert response.status_code == 201
    assert response.json()["name"] == "Memory Bank MVP"


def test_project_crud_flow(client):
    created = client.post("/projects", json={"name": "Operations", "description": "Ops workspace"}).json()

    fetched = client.get(f"/projects/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Operations"

    updated = client.patch(f"/projects/{created['id']}", json={"description": "Updated ops workspace"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated ops workspace"

    deleted = client.delete(f"/projects/{created['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/projects/{created['id']}")
    assert missing.status_code == 404


def test_create_memory_entry(client):
    project = client.post("/projects", json={"name": "Core"}).json()
    response = client.post(
        "/memory",
        json={
            "type": "decision",
            "title": "Use PostgreSQL",
            "content": "Roadmap says PostgreSQL for MVP.",
            "project_id": project["id"],
            "importance": 4,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Use PostgreSQL"
    assert body["importance"] == 4
    assert body["metadata"] == {}


def test_update_memory_entry(client):
    created = client.post("/memory", json={"type": "note", "content": "draft"}).json()
    response = client.patch(f"/memory/{created['id']}", json={"title": "Updated", "content": "Updated content"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["content"] == "Updated content"

    detail = client.get(f"/memory/{created['id']}")
    assert detail.status_code == 200
    assert "Updated content" in (detail.json().get("content") or "")


def test_archive_memory_entry(client):
    created = client.post("/memory", json={"type": "note", "content": "archive me"}).json()
    response = client.post(f"/memory/{created['id']}/archive")
    assert response.status_code == 200
    assert response.json()["archived"] is True


def test_create_memory_link(client):
    first = client.post("/memory", json={"type": "task", "content": "Task A"}).json()
    second = client.post("/memory", json={"type": "decision", "content": "Decision B"}).json()
    response = client.post(
        "/memory-links",
        json={"from_entry_id": first["id"], "to_entry_id": second["id"], "type": "depends_on"},
    )
    assert response.status_code == 201
    links = client.get(f"/memory/{first['id']}/links")
    assert links.status_code == 200
    assert len(links.json()["outgoing"]) == 1


def test_list_memory_with_filters(client):
    project_a = client.post("/projects", json={"name": "A"}).json()
    project_b = client.post("/projects", json={"name": "B"}).json()
    active = client.post(
        "/memory",
        json={"type": "decision", "content": "Active A", "project_id": project_a["id"]},
    ).json()
    archived = client.post(
        "/memory",
        json={"type": "note", "content": "Archived B", "project_id": project_b["id"]},
    ).json()
    client.post(f"/memory/{archived['id']}/archive")

    response = client.get("/memory", params={"project_id": project_a["id"], "type": "decision", "archived": "false"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == active["id"]


def test_search_memory(client):
    client.post("/memory", json={"type": "decision", "title": "Use PostgreSQL", "content": "Architecture decision"})
    client.post("/memory", json={"type": "note", "title": "Unrelated", "content": "Something else"})
    response = client.get("/memory/search", params={"query": "PostgreSQL"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Use PostgreSQL"


def test_get_relevant_memory(client):
    created = client.post(
        "/memory",
        json={"type": "artifact", "title": "DB layer", "content": "Implement database layer for memory bank"},
    ).json()
    response = client.post(
        "/memory/relevant",
        json={"query": "Implement database layer for memory bank", "agent_id": "backend-agent"},
    )
    assert response.status_code == 200
    items = response.json()["context"]
    assert items[0]["id"] == created["id"]

    updated = client.get(f"/memory/{created['id']}")
    assert updated.status_code == 200
    assert updated.json()["usage_count"] == 1
    assert updated.json()["last_used_at"] is not None


def test_graph_endpoint(client):
    root = client.post("/memory", json={"type": "task", "title": "Task root", "content": "root"}).json()
    decision = client.post("/memory", json={"type": "decision", "title": "Decision", "content": "decide"}).json()
    artifact = client.post("/memory", json={"type": "artifact", "title": "Artifact", "content": "artifact"}).json()

    client.post(
        "/memory-links",
        json={"from_entry_id": root["id"], "to_entry_id": decision["id"], "type": "depends_on"},
    )
    client.post(
        "/memory-links",
        json={"from_entry_id": decision["id"], "to_entry_id": artifact["id"], "type": "derived_from"},
    )

    response = client.get(f"/memory/{root['id']}/graph", params={"depth": 2})
    assert response.status_code == 200
    graph = response.json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2


def test_archive_stale_memory(client, db_session: Session):
    created = client.post("/memory", json={"type": "note", "content": "old note", "importance": 1}).json()
    entry = db_session.get(MemoryEntry, uuid.UUID(created["id"]))
    entry.created_at = entry.created_at.replace(year=entry.created_at.year - 1)
    db_session.add(entry)
    db_session.commit()

    response = client.post(
        "/maintenance/archive-stale",
        json={"older_than_days": 30, "max_usage_count": 0, "max_importance": 2},
    )
    assert response.status_code == 200
    assert response.json()["archived_count"] == 1

    detail = client.get(f"/memory/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["archived"] is True


def test_rebuild_search_vectors(client):
    client.post("/memory", json={"type": "decision", "title": "FTS", "content": "search vector rebuild"})
    client.post("/memory", json={"type": "note", "title": "Other", "content": "another search vector"})

    response = client.post("/maintenance/rebuild-search-vectors", json={})
    assert response.status_code == 200
    assert response.json()["rebuilt_count"] == 2


def test_task_logs_and_summary(client):
    created = client.post(
        "/task-logs",
        json={
            "experiment_id": "exp-1",
            "group_name": "B_WITH_MEMORY",
            "agent_id": "eval-agent",
            "task_description": "Implement endpoint",
            "used_memory": True,
            "memory_entries_count": 3,
            "duration_seconds": 12.5,
            "result_quality_score": 0.9,
            "duplicate_count": 0,
            "consistency_score": 0.95,
            "metadata": {"source": "test"},
        },
    )
    assert created.status_code == 201
    assert created.json()["agent_id"] == "eval-agent"

    listed = client.get("/task-logs", params={"experiment_id": "exp-1"})
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    summary = client.get("/task-logs/summary", params={"experiment_id": "exp-1"})
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_tasks"] == 1
    assert body["memory_usage_rate"] == 1.0
    assert body["avg_quality_score"] == 0.9


def test_task_logs_import(client):
    response = client.post(
        "/task-logs/import",
        json={
            "items": [
                {
                    "experiment_id": "exp-import",
                    "agent_id": "agent-a",
                    "task_description": "Task A",
                    "used_memory": True,
                    "memory_entries_count": 2,
                },
                {
                    "experiment_id": "exp-import",
                    "agent_id": "agent-b",
                    "task_description": "Task B",
                    "used_memory": False,
                    "memory_entries_count": 0,
                },
            ]
        },
    )
    assert response.status_code == 201
    assert response.json()["created_count"] == 2

    listed = client.get("/task-logs", params={"experiment_id": "exp-import"})
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2


def test_evaluation_endpoint(client):
    response = client.post(
        "/evaluation/evaluate",
        json={
            "task": "Implement endpoint using previous decision",
            "memory": [{"id": "m1", "title": "Use PostgreSQL", "content": "Prefer PostgreSQL for MVP"}],
            "reasoning": "According to memory, we keep PostgreSQL.",
            "answer": "Based on memory and previous decision, we keep PostgreSQL.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["used_memory"] is True
    assert body["referenced_memory_in_answer"] is True
    assert body["quality_score"] >= 0.8


def test_evaluation_batch_endpoint(client):
    response = client.post(
        "/evaluation/evaluate-batch",
        json={
            "items": [
                {
                    "task": "Implement endpoint using previous decision",
                    "memory": [{"id": "m1", "title": "Use PostgreSQL", "content": "Prefer PostgreSQL for MVP"}],
                    "reasoning": "According to memory, we keep PostgreSQL.",
                    "answer": "Based on memory we keep PostgreSQL.",
                },
                {
                    "task": "Write draft",
                    "memory": [],
                    "reasoning": "No memory used.",
                    "answer": "Fresh draft.",
                },
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["summary"]["total_items"] == 2
    assert body["summary"]["used_memory_rate"] == 0.5


def test_metrics_overview_endpoint(client):
    project = client.post("/projects", json={"name": "Metrics Project"}).json()
    first = client.post(
        "/memory",
        json={"type": "decision", "title": "Use PostgreSQL", "content": "Architecture memory", "project_id": project["id"]},
    ).json()
    second = client.post(
        "/memory",
        json={"type": "artifact", "title": "Implementation", "content": "Derived work", "project_id": project["id"]},
    ).json()
    client.post(
        "/memory-links",
        json={"from_entry_id": second["id"], "to_entry_id": first["id"], "type": "derived_from", "strength": 0.8},
    )
    client.post(
        "/task-logs",
        json={
            "experiment_id": "metrics-exp",
            "agent_id": "metrics-agent",
            "task_description": "Check metrics",
            "used_memory": True,
            "memory_entries_count": 2,
            "duration_seconds": 8.0,
            "result_quality_score": 0.75,
            "duplicate_count": 0,
            "consistency_score": 0.9,
        },
    )

    response = client.get(
        "/metrics/overview",
        params={"project_id": project["id"], "agent_id": "metrics-agent", "experiment_id": "metrics-exp"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["memory"]["total_entries"] == 2
    assert body["memory"]["active_entries"] == 2
    assert body["graph"]["total_links"] == 1
    assert body["tasks"]["total_tasks"] == 1
    assert body["tasks"]["memory_usage_rate"] == 1.0


def test_admin_observability_summary_endpoint(client):
    client.post("/memory", json={"type": "decision", "title": "Memory A", "content": "Observe this memory"})
    client.post("/memory", json={"type": "note", "title": "Memory B", "content": "Another observed memory"})
    client.post(
        "/task-logs",
        json={
            "experiment_id": "obs-exp-a",
            "agent_id": "obs-agent-a",
            "task_description": "Inspect observability",
            "used_memory": True,
            "memory_entries_count": 2,
            "duration_seconds": 5.0,
            "result_quality_score": 0.8,
            "duplicate_count": 0,
            "consistency_score": 0.9,
        },
    )
    client.post(
        "/task-logs",
        json={
            "experiment_id": "obs-exp-a",
            "agent_id": "obs-agent-a",
            "task_description": "Inspect observability again",
            "used_memory": False,
            "memory_entries_count": 0,
            "duration_seconds": 6.0,
            "result_quality_score": 0.7,
            "duplicate_count": 0,
            "consistency_score": 0.85,
        },
    )
    client.post(
        "/task-logs",
        json={
            "experiment_id": "obs-exp-b",
            "agent_id": "obs-agent-b",
            "task_description": "Secondary agent task",
            "used_memory": True,
            "memory_entries_count": 1,
            "duration_seconds": 4.0,
            "result_quality_score": 0.95,
            "duplicate_count": 0,
            "consistency_score": 1.0,
        },
    )

    response = client.get("/admin/observability/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "development"
    assert body["memory"]["total_entries"] == 2
    assert body["tasks"]["total_tasks"] == 3
    assert body["recent_activity"]["memory_entries_created"] == 2
    assert body["recent_activity"]["task_logs_created"] == 3
    assert body["top_agents"][0]["key"] == "obs-agent-a"
    assert body["top_agents"][0]["total_tasks"] == 2
    assert body["top_experiments"][0]["key"] == "obs-exp-a"
    assert body["top_experiments"][0]["total_tasks"] == 2


def test_project_import_scan_endpoint(client):
    response = client.post(
        "/imports/project-scan",
        json={
            "project": {
                "name": "Imported Repo",
                "description": "Imported from analyzer",
            },
            "entries": [
                {
                    "ref": "decision-db",
                    "type": "decision",
                    "title": "Use PostgreSQL",
                    "content": "Primary database is PostgreSQL.",
                    "importance": 4,
                    "metadata": {"evidence": ["docker-compose.yml"]},
                },
                {
                    "ref": "risk-secrets",
                    "type": "risk",
                    "title": "Secrets leak risk",
                    "content": "Never store api_key=super-secret-value in imported memory.",
                    "importance": 5,
                    "metadata": {"note": "token=abc123"},
                },
                {
                    "ref": "constraint-stack",
                    "type": "constraint",
                    "title": "FastAPI stack",
                    "content": "Service must stay on FastAPI and PostgreSQL.",
                    "importance": 4,
                },
            ],
            "links": [
                {
                    "from_ref": "risk-secrets",
                    "to_ref": "decision-db",
                    "type": "affects",
                },
                {
                    "from_ref": "constraint-stack",
                    "to_ref": "decision-db",
                    "type": "depends_on",
                },
            ],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["entries_created"] == 3
    assert body["links_created"] == 2
    assert "decision-db" in body["entry_refs"]

    project_id = body["project"]["id"]
    listed = client.get("/memory", params={"project_id": project_id})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 4
    imported_risk = next(item for item in items if item["type"] == "risk")
    assert "[REDACTED]" in imported_risk["content"]
    assert "super-secret-value" not in imported_risk["content"]


def test_project_import_detects_conflicting_decisions(client):
    project = client.post("/projects", json={"name": "Conflict Project"}).json()
    client.post(
        "/memory",
        json={
            "type": "decision",
            "title": "Use PostgreSQL",
            "content": "We use PostgreSQL as the main database.",
            "project_id": project["id"],
        },
    )

    response = client.post(
        "/imports/project-scan",
        json={
            "project_id": project["id"],
            "entries": [
                {
                    "ref": "decision-db",
                    "type": "decision",
                    "title": "Use MongoDB",
                    "content": "We should replace PostgreSQL with MongoDB for the main database.",
                    "importance": 4,
                }
            ],
            "links": [],
            "detect_conflicts": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["conflicts_detected"] >= 1
    assert body["conflicts"][0]["entry_ref"] == "decision-db"
    assert "postgresql" in body["conflicts"][0]["reason"].lower()

    listed = client.get("/memory", params={"project_id": project["id"]})
    assert listed.status_code == 200
    imported = next(item for item in listed.json()["items"] if item["title"] == "Use MongoDB")
    assert imported["metadata"]["requires_review"] is True
    assert imported["metadata"]["import_conflicts"]


def test_admin_import_conflicts_endpoint(client):
    project = client.post("/projects", json={"name": "Admin Conflict Project"}).json()
    client.post(
        "/memory",
        json={
            "type": "decision",
            "title": "Use PostgreSQL",
            "content": "Keep PostgreSQL as the database.",
            "project_id": project["id"],
        },
    )
    client.post(
        "/imports/project-scan",
        json={
            "project_id": project["id"],
            "entries": [
                {
                    "ref": "decision-db",
                    "type": "decision",
                    "title": "Use MySQL",
                    "content": "Move from PostgreSQL to MySQL.",
                }
            ],
            "links": [],
            "detect_conflicts": True,
        },
    )

    response = client.get("/admin/import-conflicts", params={"project_id": project["id"], "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["requires_review"] is True
    assert body["items"][0]["conflicts"]


def test_admin_import_summary_endpoint(client):
    project = client.post(
        "/projects",
        json={"name": "Imported Summary Project", "metadata": {"source_path": "/tmp/imported-summary-project"}},
    ).json()
    client.post(
        "/memory",
        json={
            "type": "event",
            "title": "Initial project import",
            "content": "Imported existing project into MemoryBank.",
            "source_agent": "memorybank-import-agent",
            "project_id": project["id"],
            "metadata": {"import_type": "initial_project_scan"},
        },
    )
    client.post(
        "/memory",
        json={
            "type": "artifact",
            "title": "README.md",
            "content": "Imported artifact",
            "source_agent": "memorybank-import-agent",
            "project_id": project["id"],
            "metadata": {},
        },
    )

    response = client.get("/admin/imports/summary", params={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    match = next(item for item in body["items"] if item["project_id"] == project["id"])
    assert match["project_name"] == "Imported Summary Project"
    assert match["source_path"] == "/tmp/imported-summary-project"
    assert match["import_events_count"] == 1
    assert match["imported_entries_count"] == 2


def test_project_import_update_existing_mode(client):
    project = client.post("/projects", json={"name": "Reimport Project"}).json()
    first = client.post(
        "/imports/project-scan",
        json={
            "project_id": project["id"],
            "entries": [
                {
                    "ref": "artifact-readme",
                    "type": "artifact",
                    "title": "README.md",
                    "content": "First imported content",
                }
            ],
            "links": [],
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/imports/project-scan",
        json={
            "project_id": project["id"],
            "existing_entry_mode": "update",
            "entries": [
                {
                    "ref": "artifact-readme",
                    "type": "artifact",
                    "title": "README.md",
                    "content": "Updated imported content",
                    "metadata": {"sync": "second-pass"},
                }
            ],
            "links": [],
        },
    )
    assert second.status_code == 201
    body = second.json()
    assert body["entries_created"] == 0
    assert body["entries_updated"] == 1
    assert body["entries_skipped"] == 0

    listed = client.get("/memory", params={"project_id": project["id"], "type": "artifact"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["content"] == "Updated imported content"
    assert items[0]["metadata"]["sync"] == "second-pass"


def test_auth_protects_write_endpoints_when_enabled(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_API_KEYS", "writer-key:write|import,admin-key:write|import|admin")

    unauthorized = client.post("/projects", json={"name": "Secured"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/projects",
        json={"name": "Secured"},
        headers={"Authorization": "Bearer writer-key"},
    )
    assert authorized.status_code == 201

    public_read = client.get("/projects")
    assert public_read.status_code == 200


def test_auth_requires_admin_scope_for_admin_endpoints(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_API_KEYS", "writer-key:write|import,admin-key:write|import|admin")

    forbidden = client.get("/admin/observability/summary", headers={"X-API-Key": "writer-key"})
    assert forbidden.status_code == 403

    allowed = client.get("/admin/observability/summary", headers={"X-API-Key": "admin-key"})
    assert allowed.status_code == 200


def test_auth_requires_import_scope_for_import_endpoint(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_API_KEYS", "writer-key:write,import-key:write|import")

    project = client.post(
        "/projects",
        json={"name": "Import Auth Project"},
        headers={"Authorization": "Bearer writer-key"},
    ).json()

    forbidden = client.post(
        "/imports/project-scan",
        json={"project_id": project["id"], "entries": [], "links": []},
        headers={"Authorization": "Bearer writer-key"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/imports/project-scan",
        json={"project_id": project["id"], "entries": [], "links": []},
        headers={"Authorization": "Bearer import-key"},
    )
    assert allowed.status_code == 201


def test_relevant_memory_creates_access_log(client, db_session: Session):
    created = client.post(
        "/memory",
        json={"type": "decision", "title": "Store facts", "content": "Agents should store useful facts"},
    ).json()

    response = client.post(
        "/memory/relevant",
        json={"query": "store useful facts", "agent_id": "retriever-agent", "metadata": {"trace_id": "abc-123"}},
    )
    assert response.status_code == 200

    logs = db_session.query(MemoryAccessLog).filter(MemoryAccessLog.entry_id == uuid.UUID(created["id"])).all()
    assert len(logs) == 1
    assert logs[0].agent_id == "retriever-agent"
    assert logs[0].metadata_ == {"trace_id": "abc-123"}


def test_auto_link_on_create(client, monkeypatch):
    monkeypatch.setenv("AUTO_LINK_ON_CREATE", "true")
    monkeypatch.setenv("AUTO_LINK_MIN_SIMILARITY", "0.2")

    first = client.post(
        "/memory",
        json={
            "type": "decision",
            "title": "PostgreSQL search design",
            "content": "Use PostgreSQL full text search for architecture and search tasks",
        },
    ).json()
    second = client.post(
        "/memory",
        json={
            "type": "artifact",
            "title": "Search implementation notes",
            "content": "Implement PostgreSQL search tasks and architecture notes",
        },
    ).json()

    links = client.get(f"/memory/{second['id']}/links")
    assert links.status_code == 200
    outgoing = links.json()["outgoing"]
    assert len(outgoing) == 1
    assert outgoing[0]["to_entry_id"] == first["id"]
    assert outgoing[0]["type"] == "related_to"
