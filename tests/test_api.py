import uuid

from sqlalchemy.orm import Session

from app.models.memory_entry import MemoryEntry
from app.models.enums import MemoryType


def test_create_project(client):
    response = client.post("/projects", json={"name": "Memory Bank MVP", "description": "Simple memory layer"})
    assert response.status_code == 201
    assert response.json()["name"] == "Memory Bank MVP"


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


def test_update_memory_entry(client):
    created = client.post("/memory", json={"type": "note", "content": "draft"}).json()
    response = client.patch(f"/memory/{created['id']}", json={"title": "Updated", "content": "Updated content"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


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
