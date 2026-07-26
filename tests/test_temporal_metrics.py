from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.repositories.metrics_repository import MetricsRepository


def test_temporal_metrics_separate_current_history_provenance_and_feed(
    client,
    db_session,
):
    project = client.post("/projects", json={"name": "Temporal metrics"}).json()
    created = client.post(
        "/memory",
        json={
            "type": "note",
            "content": "before",
            "project_id": project["id"],
            "provenance": "observed",
        },
    ).json()
    revised = client.post(
        f"/memory/{created['id']}/revise",
        json={"changes": {"content": "after"}, "reason": "verified correction"},
    ).json()["entry"]

    metrics = MetricsRepository(db_session).memory_overview(
        project_id=__import__("uuid").UUID(project["id"])
    )

    assert metrics["active_entries"] == 1
    assert metrics["current_revision_count"] == 1
    assert metrics["historical_revision_count"] == 2
    assert metrics["provenance_distribution"]["observed"] == 2
    assert metrics["missing_provenance_rate"] == 0.0
    assert metrics["feed_high_watermark"] == 2
    assert metrics["stale_revision_conflicts"] == 0
