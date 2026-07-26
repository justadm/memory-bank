from __future__ import annotations

import json
from pathlib import Path

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


def test_tracked_repository_inventory_is_complete() -> None:
    findings = check_inventory(
        app_root=REPO_ROOT / "app",
        inventory_path=REPO_ROOT / "docs/current-memory-query-inventory.json",
    )

    assert findings == []
