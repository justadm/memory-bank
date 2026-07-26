from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.config import LOCAL_CURSOR_SIGNING_KEY, Settings
from app.models.memory_change_feed import MemoryChangeEvent
from app.services.memory_change_service import MemoryChangeService


def test_production_requires_non_default_change_cursor_key():
    with pytest.raises(ValidationError, match="MEMORY_CHANGE_CURSOR_SIGNING_KEY"):
        Settings(
            app_env="production",
            memory_change_cursor_signing_key=LOCAL_CURSOR_SIGNING_KEY,
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
