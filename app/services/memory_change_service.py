from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select

from app.config import get_settings
from app.models.enums import MemoryChangeEventKind
from app.models.memory_change_feed import MemoryChangeEvent, MemoryChangeFeedState
from app.models.project import Project
from app.repositories.memory_repository import MemoryRepository
from app.security import AuthPrincipal, ensure_tenant_access, safe_actor_id


class MemoryChangeService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def tenant_key(project: Project) -> str:
        return project.tenant_id or "__global__"

    def _state(self, project_id: uuid.UUID, *, lock: bool = False) -> MemoryChangeFeedState:
        statement = select(MemoryChangeFeedState).where(MemoryChangeFeedState.project_id == project_id)
        if lock:
            statement = statement.with_for_update()
        state = self.db.scalar(statement)
        if state:
            return state
        state = MemoryChangeFeedState(project_id=project_id, sequence=0)
        self.db.add(state)
        self.db.flush()
        return state

    def emit(
        self,
        *,
        project: Project,
        entry_id: uuid.UUID,
        event_kind: MemoryChangeEventKind,
        principal: AuthPrincipal | None,
        previous_entry_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> MemoryChangeEvent:
        state = self._state(project.id, lock=True)
        state.sequence += 1
        event = MemoryChangeEvent(
            project_id=project.id,
            sequence=state.sequence,
            feed_epoch=state.feed_epoch,
            event_kind=event_kind,
            occurred_at=datetime.now(timezone.utc),
            normalized_tenant_key=self.tenant_key(project),
            entry_id=entry_id,
            previous_entry_id=previous_entry_id,
            actor=safe_actor_id(principal or AuthPrincipal(name="system", scopes={"admin"}, api_key="")),
            reason=reason[:500] if reason else None,
        )
        self.db.add(state)
        self.db.add(event)
        self.db.flush()
        return event

    @staticmethod
    def _sign(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(get_settings().cursor_secret.encode(), raw, hashlib.sha256).digest()
        encoded_raw = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return "v1." + encoded_raw + "." + encoded_signature

    @staticmethod
    def _decode(cursor: str) -> dict[str, Any]:
        if not cursor.startswith("v1."):
            raise ValueError("unsupported cursor")
        encoded_raw, encoded_signature = cursor[3:].split(".", 1)
        raw = base64.urlsafe_b64decode((encoded_raw + "=" * (-len(encoded_raw) % 4)).encode())
        signature = base64.urlsafe_b64decode((encoded_signature + "=" * (-len(encoded_signature) % 4)).encode())
        expected = hmac.new(get_settings().cursor_secret.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid cursor signature")
        payload = json.loads(raw.decode())
        if payload.get("version") != 1:
            raise ValueError("unsupported cursor")
        return payload

    def list_changes(
        self,
        *,
        project: Project,
        principal: AuthPrincipal | None,
        cursor: str | None = None,
        after_sequence: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        ensure_tenant_access(principal, project.tenant_id) if principal else None
        if cursor and after_sequence is not None:
            raise HTTPException(status_code=422, detail="cursor and after_sequence are mutually exclusive")
        limit = min(max(limit, 1), 500)
        state = self._state(project.id)
        sequence = 0 if after_sequence is None else after_sequence
        if cursor:
            try:
                payload = self._decode(cursor)
            except (ValueError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=422, detail="invalid cursor") from exc
            if str(payload.get("project_id")) != str(project.id) or payload.get("tenant_key") != self.tenant_key(project) or str(payload.get("feed_epoch")) != str(state.feed_epoch):
                raise HTTPException(status_code=422, detail="cursor scope mismatch")
            sequence = int(payload.get("sequence", 0))
        high_watermark = state.sequence
        events = list(
            self.db.scalars(
                select(MemoryChangeEvent)
                .where(
                    MemoryChangeEvent.project_id == project.id,
                    MemoryChangeEvent.feed_epoch == state.feed_epoch,
                    MemoryChangeEvent.sequence > sequence,
                    MemoryChangeEvent.sequence <= high_watermark,
                )
                .order_by(MemoryChangeEvent.sequence)
                .limit(limit)
            )
        )
        last = events[-1].sequence if events else sequence
        next_cursor = self._sign({"version": 1, "project_id": str(project.id), "tenant_key": self.tenant_key(project), "feed_epoch": str(state.feed_epoch), "sequence": last})
        return {
            "items": events,
            "has_more": last < high_watermark,
            "next_cursor": next_cursor,
            "committed_high_watermark": high_watermark,
            "feed_epoch": state.feed_epoch,
            "feed_started_at": state.created_at,
        }
