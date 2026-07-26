def test_semantic_patch_creates_revision_and_exact_compatibility_reason(client):
    project = client.post("/projects", json={"name": "PATCH compatibility"}).json()
    created = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()
    before = client.get("/memory/changes", params={"project_id": project["id"]}).json()

    response = client.patch(
        f"/memory/{created['id']}",
        json={"content": "after"},
    )

    assert response.status_code == 200
    assert response.json()["id"] != created["id"]
    changes = client.get(
        "/memory/changes",
        params={
            "project_id": project["id"],
            "after_sequence": before["committed_high_watermark"],
        },
    ).json()["items"]
    assert len(changes) == 1
    assert changes[0]["event_kind"] == "revised"
    assert changes[0]["reason"] == "legacy PATCH compatibility"


def test_generic_patch_rejects_identity_and_operational_fields(client):
    project = client.post("/projects", json={"name": "PATCH forbidden"}).json()
    created = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()

    for patch in (
        {"project_id": project["id"]},
        {"archived": True},
    ):
        response = client.patch(f"/memory/{created['id']}", json=patch)
        assert response.status_code == 422


def test_operational_update_emits_no_semantic_event(
    client,
    db_session,
):
    from app.repositories.link_repository import LinkRepository
    from app.repositories.memory_repository import MemoryRepository
    from app.repositories.project_repository import ProjectRepository
    from app.services.memory_service import MemoryService

    project = client.post("/projects", json={"name": "Operational update"}).json()
    created = client.post(
        "/memory",
        json={"type": "note", "content": "before", "project_id": project["id"]},
    ).json()
    before = client.get("/memory/changes", params={"project_id": project["id"]}).json()
    service = MemoryService(
        MemoryRepository(db_session),
        ProjectRepository(db_session),
        LinkRepository(db_session),
    )

    updated = service.update_operational_fields(
        __import__("uuid").UUID(created["id"]),
        fields={"usage_count": 4},
        operation="test_usage_accounting",
    )
    db_session.commit()

    assert updated.usage_count == 4
    after = client.get(
        "/memory/changes",
        params={
            "project_id": project["id"],
            "after_sequence": before["committed_high_watermark"],
        },
    ).json()
    assert after["items"] == []
