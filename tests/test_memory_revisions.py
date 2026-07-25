from datetime import datetime, timedelta, timezone


def test_revision_closes_old_entry_and_creates_one_change_event(client):
    project = client.post("/projects", json={"name": "Temporal API"}).json()
    created = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()
    before = client.get("/memory/changes", params={"project_id": project["id"]}).json()
    revised = client.post(
        f"/memory/{created['id']}/revise",
        json={"changes": {"content": "after"}, "reason": "corrected after read-back"},
    )

    assert revised.status_code == 200
    assert revised.json()["entry"]["content"] == "after"
    old = client.get(f"/memory/{created['id']}").json()
    assert old["archived"] is True
    assert old["valid_to"] is not None
    history = client.get(f"/memory/{created['id']}/history")
    assert history.status_code == 200
    assert [item["content"] for item in history.json()["items"]] == ["before", "after"]
    changes = client.get("/memory/changes", params={"project_id": project["id"], "after_sequence": before["committed_high_watermark"]}).json()
    assert [item["event_kind"] for item in changes["items"]] == ["revised"]
    assert changes["items"][0]["actor"] == "anonymous"


def test_changes_cursor_is_exclusive_and_tamper_safe(client):
    project = client.post("/projects", json={"name": "Cursor API"}).json()
    client.post("/memory", json={"type": "note", "content": "one", "project_id": project["id"]})
    client.post("/memory", json={"type": "note", "content": "two", "project_id": project["id"]})
    first = client.get("/memory/changes", params={"project_id": project["id"], "limit": 1}).json()
    second = client.get("/memory/changes", params={"project_id": project["id"], "cursor": first["next_cursor"], "limit": 10})
    assert second.status_code == 200
    assert all(item["sequence"] > first["items"][-1]["sequence"] for item in second.json()["items"])
    tampered = first["next_cursor"][:-8] + ("a" if first["next_cursor"][-8] != "a" else "b") + first["next_cursor"][-7:]
    assert client.get("/memory/changes", params={"project_id": project["id"], "cursor": tampered}).status_code == 422


def test_archive_and_restore_create_temporal_leaf(client):
    project = client.post("/projects", json={"name": "Restore API"}).json()
    created = client.post("/memory", json={"type": "note", "content": "original", "project_id": project["id"]}).json()
    archived = client.post(f"/memory/{created['id']}/archive")
    assert archived.status_code == 200
    restored = client.post(f"/memory/{created['id']}/restore", json={"reason": "restore after review"})
    assert restored.status_code == 200
    assert restored.json()["content"] == "original"
    listed = client.get("/memory", params={"project_id": project["id"]}).json()["items"]
    assert [item["id"] for item in listed] == [restored.json()["id"]]
