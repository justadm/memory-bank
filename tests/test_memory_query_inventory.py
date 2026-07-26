from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.lint_memory_query_inventory import check_inventory, scan_memory_queries


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_query_fingerprint_ignores_line_number_but_changes_with_query_shape(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    source = """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry

def lookup(db):
    return db.scalar(select(MemoryEntry).where(MemoryEntry.id == value))
"""
    target = app_root / "sample.py"
    target.write_text(source)
    first = scan_memory_queries(app_root)

    target.write_text("\n\n" + source)
    shifted = scan_memory_queries(app_root)
    assert [item.key for item in shifted] == [item.key for item in first]

    target.write_text(source.replace("MemoryEntry.id == value", "MemoryEntry.project_id == value"))
    changed = scan_memory_queries(app_root)
    assert [item.key for item in changed] != [item.key for item in first]


def test_inventory_check_fails_for_new_unclassified_query(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry

def lookup(db):
    return db.scalar(select(MemoryEntry).where(MemoryEntry.id == value))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps({"schema_version": 1, "queries": []}))

    findings = check_inventory(app_root=app_root, inventory_path=inventory_path)

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_aliased_memory_entry_query(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry as Entry

def lookup(db):
    return db.scalar(select(Entry).where(Entry.project_id == value))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_memory_entry_reexport_alias(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models import MemoryEntry as Entry

def lookup(db):
    return db.scalar(select(Entry).where(Entry.project_id == value))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_module_attribute_assignment_alias(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
import app.models.memory_entry as memory_model
from sqlalchemy import select

Entry = memory_model.MemoryEntry

def lookup(db):
    return db.scalar(select(Entry).where(Entry.project_id == value))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_package_module_alias(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
import app.models as models
from sqlalchemy import select

def lookup(db):
    return db.scalar(
        select(models.MemoryEntry).where(models.MemoryEntry.project_id == value)
    )
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_from_app_models_alias(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from app import models
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(models.MemoryEntry))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_unaliased_package_import(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
import app.models
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(app.models.MemoryEntry))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_inventory_detects_propagated_module_assignment_alias(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from app import models
from sqlalchemy import select

model_namespace = models
Entry = model_namespace.MemoryEntry

def lookup(db):
    return db.scalar(select(Entry))
"""
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


@pytest.mark.parametrize(
    "source",
    [
        """
import app.models as models
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(models.memory_entry.MemoryEntry))
""",
        """
from .models import MemoryEntry as Entry
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(Entry))
""",
        """
from . import models
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(models.MemoryEntry))
""",
        """
from .models import memory_entry as memory_model
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(memory_model.MemoryEntry))
""",
        """
import app.models as models
from sqlalchemy import select

memory_module = models.memory_entry
Entry = memory_module.MemoryEntry

def lookup(db):
    return db.scalar(select(Entry))
""",
    ],
)
def test_inventory_detects_child_and_relative_module_aliases(
    tmp_path: Path,
    source: str,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(source)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


@pytest.mark.parametrize(
    "source",
    [
        """
from app.models import MemoryEntry
from sqlalchemy import select as query_select

def lookup(db):
    return query_select(MemoryEntry)
""",
        """
from app.models import MemoryEntry
from sqlalchemy import select

query_select = select

def lookup(db):
    return query_select(MemoryEntry)
""",
        """
from app.models import MemoryEntry

def lookup(db):
    query_for = db.query
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry

def lookup(db, value):
    fetch_one = db.get
    return fetch_one(MemoryEntry, value)
""",
    ],
)
def test_inventory_detects_static_query_callable_aliases(
    tmp_path: Path,
    source: str,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(source)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


@pytest.mark.parametrize(
    "source",
    [
        """
from . import memory_entry as memory_model
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(memory_model.MemoryEntry))
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast

def lookup(db):
    query_for = cast(Callable[..., Any], db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast as typed_cast

def lookup(db):
    query_for = typed_cast(Callable[..., Any], db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
import typing

def lookup(db):
    query_for = typing.cast(typing.Any, db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
import typing as t

def lookup(db):
    query_for = t.cast(t.Any, db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast

typed_cast = cast

def lookup(db):
    query_for = typed_cast(Callable[..., Any], db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
import typing as t

typing_api = t

def lookup(db):
    query_for = typing_api.cast(typing_api.Any, db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast

def lookup(db):
    return cast(Callable[..., Any], db.query)(MemoryEntry)
""",
    ],
)
def test_inventory_detects_relative_child_and_typed_aliases(
    tmp_path: Path,
    source: str,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(source)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


@pytest.mark.parametrize(
    "source",
    [
        """
from .memory_entry import MemoryEntry as Entry
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(Entry))
""",
        """
from ..memory_entry import MemoryEntry as Entry
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(Entry))
""",
        """
from . import MemoryEntry as Entry
from sqlalchemy import select

def lookup(db):
    return db.scalar(select(Entry))
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast

def lookup(db):
    query_for = cast(typ=Callable[..., Any], val=db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
from typing import Any, Callable, cast

def lookup(db):
    query_for = cast(Callable[..., Any], val=db.query)
    return query_for(MemoryEntry)
""",
        """
from app.models import MemoryEntry
import typing

def lookup(db):
    return typing.cast(
        typ=typing.Any,
        val=db.query,
    )(MemoryEntry)
""",
        """
from app.models import MemoryEntry
import typing_extensions

def lookup(db):
    return typing_extensions.cast(
        typ=typing_extensions.Any,
        val=db.query,
    )(MemoryEntry)
""",
    ],
)
def test_inventory_detects_relative_model_and_keyword_cast_aliases(
    tmp_path: Path,
    source: str,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(source)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": []})
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert len(findings) == 1
    assert "missing inventory row" in findings[0]


def test_current_view_requires_central_predicate_call(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry

def current_items(db):
    return db.scalars(select(MemoryEntry))
"""
    )
    detected = scan_memory_queries(app_root)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queries": [
                    {
                        "key": detected[0].key,
                        "classification": "current-view",
                        "required_guard": "current_predicate",
                        "owner": detected[0].owner,
                    }
                ],
            }
        )
    )

    findings = check_inventory(app_root=app_root, inventory_path=inventory_path)

    assert findings == [
        f"{detected[0].key}: current-view owner does not call current_predicate"
    ]


def test_unrelated_guard_does_not_cover_an_unguarded_query(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository

def mixed_queries(db):
    guarded_stmt = select(MemoryEntry).where(MemoryRepository.current_predicate())
    guarded = list(db.scalars(guarded_stmt))
    unguarded_stmt = select(MemoryEntry)
    unguarded = list(db.scalars(unguarded_stmt))
    return guarded, unguarded
"""
    )

    detected = scan_memory_queries(app_root)

    assert len(detected) == 2
    guarded, unguarded = sorted(detected, key=lambda item: item.line)
    assert guarded.guard_calls == frozenset({"current_predicate"})
    assert unguarded.guard_calls == frozenset()


def test_reused_query_variable_does_not_inherit_guard_from_previous_query(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository

def mixed_queries(db):
    stmt = select(MemoryEntry).where(MemoryRepository.current_predicate())
    guarded = list(db.scalars(stmt))
    stmt = select(MemoryEntry)
    unguarded = list(db.scalars(stmt))
    return guarded, unguarded
"""
    )

    detected = scan_memory_queries(app_root)

    assert len(detected) == 2
    guarded, unguarded = sorted(detected, key=lambda item: item.line)
    assert guarded.guard_calls == frozenset({"current_predicate"})
    assert unguarded.guard_calls == frozenset()


def test_mixed_view_requires_every_declared_guard(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    source = """
from sqlalchemy import func, select
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository

def mixed_view(db):
    current = MemoryRepository.current_predicate()
    historical = MemoryRepository.historical_rows_predicate()
    stmt = select(
        func.count(MemoryEntry.id).filter(current),
        func.count(MemoryEntry.id).filter(historical),
    )
    return list(db.scalars(stmt))
"""
    target = app_root / "sample.py"
    target.write_text(source)
    detected = scan_memory_queries(app_root)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queries": [
                    {
                        "key": detected[0].key,
                        "classification": "mixed-view",
                        "required_guards": [
                            "current_predicate",
                            "historical_rows_predicate",
                        ],
                        "owner": detected[0].owner,
                    }
                ],
            }
        )
    )
    assert check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    ) == []

    target.write_text(
        source.replace(
            "func.count(MemoryEntry.id).filter(current),",
            "func.count(MemoryEntry.id),",
        )
    )
    changed = scan_memory_queries(app_root)
    inventory = json.loads(inventory_path.read_text())
    inventory["queries"][0]["key"] = changed[0].key
    inventory_path.write_text(json.dumps(inventory))

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )
    assert findings == [
        f"{changed[0].key}: mixed-view guard coverage mismatch"
    ]


def test_mixed_view_rejects_guards_only_applied_downstream_in_one_branch(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "sample.py").write_text(
        """
from sqlalchemy import select
from app.models.memory_entry import MemoryEntry
from app.repositories.memory_repository import MemoryRepository

def mixed_view(db, guarded=False):
    stmt = select(MemoryEntry)
    if guarded:
        stmt = stmt.where(
            MemoryRepository.current_predicate(),
            MemoryRepository.historical_predicate(moment),
        )
    return list(db.scalars(stmt))
"""
    )
    detected = scan_memory_queries(app_root)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queries": [
                    {
                        "key": detected[0].key,
                        "classification": "mixed-view",
                        "required_guards": [
                            "current_predicate",
                            "historical_predicate",
                        ],
                        "owner": detected[0].owner,
                    }
                ],
            }
        )
    )

    findings = check_inventory(
        app_root=app_root,
        inventory_path=inventory_path,
    )

    assert findings == [
        f"{detected[0].key}: mixed-view guard coverage mismatch"
    ]


def test_tracked_repository_inventory_is_complete() -> None:
    findings = check_inventory(
        app_root=REPO_ROOT / "app",
        inventory_path=REPO_ROOT / "docs/current-memory-query-inventory.json",
    )

    assert findings == []
