from datetime import datetime, timedelta, timezone

from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.project_repository import ProjectRepository


def test_as_of_search_sees_historical_revision_but_current_search_does_not(client):
    project = client.post("/projects", json={"name": "As Of"}).json()
    created = client.post("/memory", json={"type": "note", "content": "old architecture", "project_id": project["id"]}).json()
    created_at = datetime.fromisoformat(created["valid_from"].replace("Z", "+00:00"))
    revised = client.post(
        f"/memory/{created['id']}/revise",
        json={"changes": {"content": "new architecture"}, "reason": "newer state"},
    ).json()
    current = client.get("/memory/search", params={"project_id": project["id"], "query": "old architecture"}).json()["items"]
    historical = client.get(
        "/memory/search",
        params={"project_id": project["id"], "query": "old architecture", "as_of": created_at.isoformat()},
    ).json()["items"]
    assert all(item["id"] != created["id"] for item in current)
    assert any(item["id"] == created["id"] for item in historical)


def test_project_counts_and_metrics_exclude_future_and_superseded_rows(db_session):
    now = datetime.now(timezone.utc)
    project = Project(name="Temporal visibility", metadata_={})
    db_session.add(project)
    db_session.flush()
    db_session.add_all(
        [
            MemoryEntry(
                type=MemoryType.note,
                content="current",
                project_id=project.id,
                valid_from=now - timedelta(hours=1),
            ),
            MemoryEntry(
                type=MemoryType.note,
                content="superseded",
                project_id=project.id,
                valid_from=now - timedelta(days=2),
                valid_to=now - timedelta(days=1),
                archived=True,
            ),
            MemoryEntry(
                type=MemoryType.note,
                content="future",
                project_id=project.id,
                valid_from=now + timedelta(days=1),
            ),
        ]
    )
    db_session.flush()

    project_counts = dict(ProjectRepository(db_session).list_with_entry_counts(at=now))
    metrics = MetricsRepository(db_session).memory_overview(project_id=project.id)

    assert project_counts[project] == 1
    assert metrics["active_entries"] == 1
