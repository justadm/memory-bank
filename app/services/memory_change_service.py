from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.models.enums import MemoryChangeEventKind
from app.models.memory_change_feed import MemoryChangeEvent
from app.models.project import Project
from app.repositories.memory_change_repository import MemoryChangeRepository
from app.repositories.memory_repository import MemoryRepository
from app.security import AuthPrincipal, ensure_tenant_access, safe_actor_id
from app.services.memory_evidence_service import MemoryEvidenceService


class _CursorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: int = Field(ge=1, le=1)
    project_id: uuid.UUID
    tenant_key: str
    feed_epoch: uuid.UUID
    sequence: int = Field(ge=0)


class MemoryChangeService:
    def __init__(self, db):
        self.db = db
        self.repository = MemoryChangeRepository(db)

    @staticmethod
    def tenant_key(project: Project) -> str:
        return project.tenant_id or "__global__"

    def emit(
        self,
        *,
        project: Project,
        entry_id: uuid.UUID,
        event_kind: MemoryChangeEventKind,
        principal: AuthPrincipal | None,
        previous_entry_id: uuid.UUID | None = None,
        restored_from_entry_id: uuid.UUID | None = None,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> MemoryChangeEvent:
        if not self.db.in_transaction():
            raise RuntimeError("change events require an active semantic transaction")
        state = self.repository.get_or_create_state(project.id, lock=True)
        state.sequence += 1
        clock = occurred_at or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            raise ValueError("change event clock must be timezone-aware")
        safe_reason = MemoryEvidenceService.validate_reason(reason) if reason else None
        event = MemoryChangeEvent(
            project_id=project.id,
            sequence=state.sequence,
            feed_epoch=state.feed_epoch,
            event_kind=event_kind,
            occurred_at=clock,
            normalized_tenant_key=self.tenant_key(project),
            entry_id=entry_id,
            previous_entry_id=previous_entry_id,
            restored_from_entry_id=restored_from_entry_id,
            actor=safe_actor_id(principal or AuthPrincipal(name="system", scopes={"admin"}, api_key="")),
            reason=safe_reason,
        )
        self.db.add(state)
        return self.repository.append(event)

    @staticmethod
    def _sign(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(
            get_settings().memory_change_cursor_signing_key.encode(),
            raw,
            hashlib.sha256,
        ).digest()
        encoded_raw = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return "v1." + encoded_raw + "." + encoded_signature

    @staticmethod
    def _decode(cursor: str) -> _CursorPayload:
        if not cursor.startswith("v1."):
            raise ValueError("unsupported cursor")
        encoded_raw, encoded_signature = cursor[3:].split(".", 1)
        raw = base64.urlsafe_b64decode((encoded_raw + "=" * (-len(encoded_raw) % 4)).encode())
        signature = base64.urlsafe_b64decode((encoded_signature + "=" * (-len(encoded_signature) % 4)).encode())
        expected = hmac.new(
            get_settings().memory_change_cursor_signing_key.encode(),
            raw,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid cursor signature")
        try:
            return _CursorPayload.model_validate_json(raw)
        except ValidationError as exc:
            raise ValueError("invalid cursor payload") from exc

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
        state = self.repository.get_or_create_state(project.id)
        sequence = 0 if after_sequence is None else after_sequence
        if sequence < 0:
            raise HTTPException(status_code=422, detail="after_sequence must be non-negative")
        if cursor:
            try:
                payload = self._decode(cursor)
            except (ValueError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=422, detail="invalid cursor") from exc
            if (
                payload.project_id != project.id
                or payload.tenant_key != self.tenant_key(project)
                or payload.feed_epoch != state.feed_epoch
            ):
                raise HTTPException(status_code=422, detail="cursor scope mismatch")
            sequence = payload.sequence
        high_watermark = state.sequence
        if sequence > high_watermark:
            raise HTTPException(status_code=422, detail="cursor exceeds committed high watermark")
        events = self.repository.list_page(
            project_id=project.id,
            feed_epoch=state.feed_epoch,
            after_sequence=sequence,
            high_watermark=high_watermark,
            limit=limit,
        )
        last = events[-1].sequence if events else sequence
        next_cursor = self._sign(
            {
                "v": 1,
                "project_id": str(project.id),
                "tenant_key": self.tenant_key(project),
                "feed_epoch": str(state.feed_epoch),
                "sequence": last,
            }
        )
        return {
            "items": events,
            "has_more": last < high_watermark,
            "next_cursor": next_cursor,
            "committed_high_watermark": high_watermark,
            "feed_epoch": state.feed_epoch,
            "feed_started_at": state.created_at,
        }
