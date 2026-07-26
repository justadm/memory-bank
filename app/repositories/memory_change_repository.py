from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.memory_change_feed import MemoryChangeEvent, MemoryChangeFeedState


class MemoryChangeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_state(
        self,
        project_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> MemoryChangeFeedState:
        statement = select(MemoryChangeFeedState).where(
            MemoryChangeFeedState.project_id == project_id
        )
        if lock and self.db.bind and self.db.bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        state = self.db.scalar(statement)
        if state is not None:
            return state
        try:
            with self.db.begin_nested():
                state = MemoryChangeFeedState(project_id=project_id, sequence=0)
                self.db.add(state)
                self.db.flush()
        except IntegrityError:
            self.db.expire_all()
            state = self.db.scalar(statement)
            if state is None:
                raise
        return state

    def append(self, event: MemoryChangeEvent) -> MemoryChangeEvent:
        if not self.db.in_transaction():
            raise RuntimeError("change events require an active semantic transaction")
        self.db.add(event)
        self.db.flush()
        return event

    def list_page(
        self,
        *,
        project_id: uuid.UUID,
        feed_epoch: uuid.UUID,
        after_sequence: int,
        high_watermark: int,
        limit: int,
    ) -> list[MemoryChangeEvent]:
        return list(
            self.db.scalars(
                select(MemoryChangeEvent)
                .where(
                    MemoryChangeEvent.project_id == project_id,
                    MemoryChangeEvent.feed_epoch == feed_epoch,
                    MemoryChangeEvent.sequence > after_sequence,
                    MemoryChangeEvent.sequence <= high_watermark,
                )
                .order_by(MemoryChangeEvent.sequence)
                .limit(limit)
            )
        )
