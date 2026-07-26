import base64
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.config import LOCAL_CURSOR_SIGNING_KEY, Settings
from app.models.memory_change_feed import MemoryChangeEvent
from app.services.memory_change_service import MemoryChangeService


def test_production_requires_non_default_change_cursor_key():
    for invalid_key in (LOCAL_CURSOR_SIGNING_KEY, "", "   "):
        with pytest.raises(
            ValidationError,
            match="MEMORY_CHANGE_CURSOR_SIGNING_KEY",
        ):
            Settings(
                app_env="production",
                memory_change_cursor_signing_key=invalid_key,
            )

    settings = Settings(
        app_env="production",
        memory_change_cursor_signing_key="synthetic-non-default-signing-key",
    )
    assert settings.memory_change_cursor_signing_key != LOCAL_CURSOR_SIGNING_KEY


def test_cursor_payload_rejects_extra_fields_and_future_sequence(client):
    project = client.post("/projects", json={"name": "Strict cursor"}).json()
    client.post(
        "/memory",
        json={"type": "note", "content": "one", "project_id": project["id"]},
    )
    page = client.get("/memory/changes", params={"project_id": project["id"]}).json()
    decoded = MemoryChangeService._decode(page["next_cursor"])

    forged_extra = MemoryChangeService._sign(
        {
            **decoded.model_dump(mode="json"),
            "extra": "not-allowed",
        }
    )
    assert (
        client.get(
            "/memory/changes",
            params={"project_id": project["id"], "cursor": forged_extra},
        ).status_code
        == 422
    )

    forged_future = MemoryChangeService._sign(
        {
            **decoded.model_dump(mode="json"),
            "sequence": page["committed_high_watermark"] + 1,
        }
    )
    assert (
        client.get(
            "/memory/changes",
            params={"project_id": project["id"], "cursor": forged_future},
        ).status_code
        == 422
    )


def test_change_feed_orders_by_sequence_not_occurred_at(client, db_session):
    project = client.post("/projects", json={"name": "Sequence order"}).json()
    first = client.post(
        "/memory",
        json={"type": "note", "content": "first", "project_id": project["id"]},
    ).json()
    second = client.post(
        "/memory",
        json={"type": "note", "content": "second", "project_id": project["id"]},
    ).json()

    events = db_session.query(MemoryChangeEvent).order_by(MemoryChangeEvent.sequence).all()
    events[0].occurred_at = datetime.now(timezone.utc) + timedelta(days=1)
    events[1].occurred_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    page = client.get("/memory/changes", params={"project_id": project["id"]}).json()
    assert [item["entry_id"] for item in page["items"]] == [first["id"], second["id"]]
    assert [item["sequence"] for item in page["items"]] == sorted(
        item["sequence"] for item in page["items"]
    )


def test_negative_after_sequence_is_rejected(client):
    project = client.post("/projects", json={"name": "Negative sequence"}).json()

    response = client.get(
        "/memory/changes",
        params={"project_id": project["id"], "after_sequence": -1},
    )

    assert response.status_code == 422


def test_change_feed_pseudonymizes_tenant_in_event_and_cursor(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "AUTH_API_KEYS",
        "tenant-a-writer:tenant-a-key:read|write:tenant-a",
    )
    project = client.post(
        "/projects",
        json={"name": "Tenant cursor privacy"},
        headers={"Authorization": "Bearer tenant-a-key"},
    ).json()
    client.post(
        "/memory",
        json={
            "type": "note",
            "content": "tenant-safe event",
            "project_id": project["id"],
        },
        headers={"Authorization": "Bearer tenant-a-key"},
    )

    page = client.get(
        "/memory/changes",
        params={"project_id": project["id"]},
        headers={"Authorization": "Bearer tenant-a-key"},
    ).json()
    event = db_session.query(MemoryChangeEvent).one()
    encoded_payload = page["next_cursor"].split(".", 2)[1]
    cursor_payload = base64.urlsafe_b64decode(
        encoded_payload + "=" * (-len(encoded_payload) % 4)
    )

    assert event.normalized_tenant_key != "tenant-a"
    assert len(event.normalized_tenant_key) == 64
    assert b"tenant-a" not in cursor_payload
    assert MemoryChangeService._decode(
        page["next_cursor"]
    ).tenant_key == event.normalized_tenant_key
