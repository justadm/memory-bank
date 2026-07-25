from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import MemoryProvenance, MemoryType
from app.models.memory_entry import MemoryEntry
from app.models.project import Project


def make_entry(project_id=None, **kwargs):
    return MemoryEntry(
        type=MemoryType.note,
        title="temporal",
        content="temporal content",
        project_id=project_id,
        **kwargs,
    )


def test_memory_entry_defaults_to_unspecified_current_revision(db_session):
    entry = make_entry()
    db_session.add(entry)
    db_session.flush()

    assert entry.provenance is MemoryProvenance.unspecified
    assert entry.confidence is None
    assert entry.valid_from is not None
    assert entry.valid_to is None
    assert entry.supersedes_id is None


@pytest.mark.parametrize("field", ["confidence"])
def test_memory_entry_rejects_invalid_confidence(db_session, field):
    entry = make_entry(**{field: 1.5})
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_memory_entry_rejects_invalid_interval_and_self_successor(db_session):
    now = datetime.now(timezone.utc)
    invalid = make_entry(valid_from=now, valid_to=now - timedelta(seconds=1))
    db_session.add(invalid)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    entry = make_entry()
    db_session.add(entry)
    db_session.flush()
    entry.supersedes_id = entry.id
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_memory_entry_allows_one_successor_only(db_session):
    original = make_entry()
    db_session.add(original)
    db_session.flush()
    first = make_entry(supersedes_id=original.id)
    second = make_entry(supersedes_id=original.id)
    db_session.add_all([first, second])
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
