from datetime import datetime, timedelta, timezone

from app.models.enums import MemoryType
from app.models.memory_entry import MemoryEntry
from app.models.project import Project


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


def test_archived_list_excludes_superseded_revisions(client):
    project = client.post(
        "/projects",
        json={"name": "Archive closure listing"},
    ).json()
    revised_source = client.post(
        "/memory",
        json={
            "type": "note",
            "content": "revision source",
            "project_id": project["id"],
        },
    ).json()
    client.post(
        f"/memory/{revised_source['id']}/revise",
        json={
            "changes": {"content": "revision successor"},
            "reason": "verified newer state",
        },
    )
    archived_leaf = client.post(
        "/memory",
        json={
            "type": "note",
            "content": "explicit archive leaf",
            "project_id": project["id"],
        },
    ).json()
    client.post(f"/memory/{archived_leaf['id']}/archive")

    archived = client.get(
        "/memory",
        params={"project_id": project["id"], "archived": True},
    ).json()["items"]

    assert [item["id"] for item in archived] == [archived_leaf["id"]]


def test_revision_schema_rejects_identity_and_archive_changes(client):
    project = client.post("/projects", json={"name": "Immutable revision"}).json()
    entry = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()

    for forbidden in (
        {"project_id": project["id"]},
        {"archived": True},
        {"valid_to": datetime.now(timezone.utc).isoformat()},
    ):
        response = client.post(
            f"/memory/{entry['id']}/revise",
            json={"changes": forbidden, "reason": "invalid identity mutation"},
        )
        assert response.status_code == 422


def test_restore_schema_rejects_unknown_identity_fields(client):
    project = client.post("/projects", json={"name": "Strict restore schema"}).json()
    entry = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()

    response = client.post(
        f"/memory/{entry['id']}/restore",
        json={
            "reason": "invalid restore identity override",
            "project_id": project["id"],
        },
    )

    assert response.status_code == 422


def test_revision_inherits_links_once_and_exposes_lineage(client):
    project = client.post("/projects", json={"name": "Link inheritance"}).json()
    source = client.post(
        "/memory",
        json={"type": "note", "content": "source", "project_id": project["id"]},
    ).json()
    target = client.post(
        "/memory",
        json={"type": "decision", "content": "target", "project_id": project["id"]},
    ).json()
    original_link = client.post(
        "/memory-links",
        json={
            "from_entry_id": source["id"],
            "to_entry_id": target["id"],
            "type": "depends_on",
            "metadata": {"origin": "synthetic"},
        },
    ).json()

    revised = client.post(
        f"/memory/{source['id']}/revise",
        json={"changes": {"content": "source v2"}, "reason": "verified correction"},
    ).json()["entry"]
    inherited = client.get(f"/memory/{revised['id']}/links").json()["outgoing"]
    old = client.get(f"/memory/{source['id']}").json()

    assert len(inherited) == 1
    assert inherited[0]["to_entry_id"] == target["id"]
    assert inherited[0]["metadata"]["inherited_from_link_id"] == original_link["id"]
    assert inherited[0]["metadata"]["revision_id"] == revised["id"]
    assert old["is_current"] is False
    assert old["successor_id"] == revised["id"]
    assert revised["is_current"] is True


def test_restore_rejects_current_chain_and_unrelated_source(client):
    project = client.post("/projects", json={"name": "Restore guards"}).json()
    first = client.post(
        "/memory",
        json={"type": "note", "content": "first", "project_id": project["id"]},
    ).json()
    unrelated = client.post(
        "/memory",
        json={"type": "note", "content": "unrelated", "project_id": project["id"]},
    ).json()

    assert (
        client.post(
            f"/memory/{first['id']}/restore",
            json={"reason": "must not duplicate current state"},
        ).status_code
        == 409
    )
    client.post(f"/memory/{first['id']}/archive")
    assert (
        client.post(
            f"/memory/{first['id']}/restore",
            json={
                "source_entry_id": unrelated["id"],
                "reason": "must not cross chains",
            },
        ).status_code
        == 409
    )


def test_restore_historical_source_closes_current_leaf(client):
    project = client.post("/projects", json={"name": "Restore current chain"}).json()
    first = client.post(
        "/memory",
        json={"type": "note", "content": "first", "project_id": project["id"]},
    ).json()
    second = client.post(
        f"/memory/{first['id']}/revise",
        json={"changes": {"content": "second"}, "reason": "newer verified value"},
    ).json()["entry"]

    restored = client.post(
        f"/memory/{first['id']}/restore",
        json={"reason": "restore verified historical value"},
    )

    assert restored.status_code == 200
    assert restored.json()["content"] == "first"
    closed_leaf = client.get(f"/memory/{second['id']}").json()
    assert closed_leaf["is_current"] is False
    assert closed_leaf["successor_id"] == restored.json()["id"]
    assert closed_leaf["archived"] is True
    assert closed_leaf["valid_to"] is not None
    changes = client.get(
        "/memory/changes",
        params={"project_id": project["id"]},
    ).json()["items"]
    assert [item["event_kind"] for item in changes] == [
        "created",
        "revised",
        "restored",
    ]
    assert changes[-1]["restored_from_entry_id"] == first["id"]
    assert changes[-1]["previous_entry_id"] == second["id"]


def test_legacy_archived_history_is_fail_closed(client, db_session):
    project = Project(name="Legacy history unavailable", metadata_={})
    db_session.add(project)
    db_session.flush()
    now = datetime.now(timezone.utc)
    entry = MemoryEntry(
        type=MemoryType.note,
        content="legacy archived",
        project_id=project.id,
        valid_from=now - timedelta(days=1),
        valid_to=now,
        archived=True,
        history_available=False,
    )
    db_session.add(entry)
    db_session.commit()

    response = client.get(f"/memory/{entry.id}/history")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "memory_history_unavailable"
