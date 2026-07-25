from datetime import datetime, timedelta, timezone


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
