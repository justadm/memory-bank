#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


QUERY_CALLS = {"select", "query", "get", "execute", "scalars", "scalar", "update", "delete"}
CLASSIFICATIONS = {
    "current-view",
    "historical-view",
    "exact-id-view",
    "operational-row-update",
}
OPERATIONAL_OWNER_ALLOWLIST = {
    "MemoryRepository.sync_search_vector",
}
EXACT_ID_OWNER_ALLOWLIST = {
    "LinkRepository.get_graph",
    "LinkRepository.traverse",
    "MemoryRepository.get",
    "MemoryRevisionService._successor",
    "MemoryRevisionService.history",
}


@dataclass(frozen=True)
class DetectedQuery:
    key: str
    path: str
    owner: str
    line: int
    guard_calls: frozenset[str]
    exact_id_lookup: bool


def _call_name(node: ast.Call) -> str | None:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _references_memory_entry(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id == "MemoryEntry"
        for child in ast.walk(node)
    )


def _has_query_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child)
        if name not in QUERY_CALLS:
            continue
        if name == "get":
            if child.args and isinstance(child.args[0], ast.Name) and child.args[0].id == "MemoryEntry":
                return True
            continue
        if _references_memory_entry(child):
            return True
    return False


def _function_guard_calls(node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    return frozenset(
        name
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for name in [_call_name(child)]
        if name in {"current_predicate", "historical_predicate"}
    )


def _is_exact_id_lookup(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "MemoryEntry"
            and child.attr in {"id", "supersedes_id"}
        ):
            return True
        if isinstance(child, ast.Call) and _call_name(child) == "get":
            if child.args and isinstance(child.args[0], ast.Name) and child.args[0].id == "MemoryEntry":
                return True
    return False


def _query_statements(node: ast.AST) -> Iterable[ast.stmt]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.stmt):
            if _references_memory_entry(child) and _has_query_call(child):
                yield child
            yield from _query_statements(child)


def _scan_file(path: Path, *, relative_path: str) -> list[DetectedQuery]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    detected: list[DetectedQuery] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.classes: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.classes.append(node.name)
            self.generic_visit(node)
            self.classes.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function(node)

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            owner = ".".join([*self.classes, node.name])
            guards = _function_guard_calls(node)
            for statement in _query_statements(node):
                normalized = ast.dump(statement, annotate_fields=True, include_attributes=False)
                fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                detected.append(
                    DetectedQuery(
                        key=f"{relative_path}:{owner}:{fingerprint}",
                        path=relative_path,
                        owner=owner,
                        line=statement.lineno,
                        guard_calls=guards,
                        exact_id_lookup=_is_exact_id_lookup(statement),
                    )
                )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.visit(child)

    Visitor().visit(tree)
    return detected


def scan_memory_queries(app_root: Path) -> list[DetectedQuery]:
    app_root = app_root.resolve()
    repository_root = app_root.parent
    detected = [
        query
        for path in sorted(app_root.rglob("*.py"))
        for query in _scan_file(
            path,
            relative_path=path.relative_to(repository_root).as_posix(),
        )
    ]
    return sorted(detected, key=lambda item: item.key)


def _load_inventory(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema_version": 1, "queries": []}
    if payload.get("schema_version") != 1 or not isinstance(payload.get("queries"), list):
        raise ValueError("invalid current-memory query inventory")
    return payload


def _row_map(payload: dict) -> tuple[dict[str, dict], list[str]]:
    rows: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in payload["queries"]:
        key = row.get("key")
        if not isinstance(key, str):
            duplicates.append("inventory row has no string key")
            continue
        if key in rows:
            duplicates.append(f"duplicate inventory key: {key}")
        rows[key] = row
    return rows, duplicates


def check_inventory(*, app_root: Path, inventory_path: Path) -> list[str]:
    detected = scan_memory_queries(app_root)
    detected_by_key = {item.key: item for item in detected}
    findings: list[str] = []
    if len(detected_by_key) != len(detected):
        findings.append("detector produced duplicate query keys")
    payload = _load_inventory(inventory_path)
    rows, row_findings = _row_map(payload)
    findings.extend(row_findings)

    for key in sorted(detected_by_key.keys() - rows.keys()):
        findings.append(f"missing inventory row: {key}")
    for key in sorted(rows.keys() - detected_by_key.keys()):
        findings.append(f"stale inventory row: {key}")

    for key in sorted(detected_by_key.keys() & rows.keys()):
        query = detected_by_key[key]
        row = rows[key]
        classification = row.get("classification")
        required_guard = row.get("required_guard")
        if classification not in CLASSIFICATIONS:
            findings.append(f"{key}: invalid classification")
            continue
        if row.get("owner") != query.owner:
            findings.append(f"{key}: owner mismatch")
        if classification == "current-view":
            if required_guard != "current_predicate":
                findings.append(f"{key}: current-view required_guard mismatch")
            elif "current_predicate" not in query.guard_calls:
                findings.append(f"{key}: current-view owner does not call current_predicate")
        elif classification == "historical-view":
            if required_guard != "historical_predicate":
                findings.append(f"{key}: historical-view required_guard mismatch")
            elif "historical_predicate" not in query.guard_calls:
                findings.append(f"{key}: historical-view owner does not call historical_predicate")
        elif classification == "exact-id-view":
            if required_guard != "exact_id":
                findings.append(f"{key}: exact-id-view required_guard mismatch")
            elif not query.exact_id_lookup or query.owner not in EXACT_ID_OWNER_ALLOWLIST:
                findings.append(f"{key}: exact-id-view is not an allowlisted exact lookup")
        elif classification == "operational-row-update":
            if required_guard != "operational_allowlist":
                findings.append(f"{key}: operational-row-update required_guard mismatch")
            elif query.owner not in OPERATIONAL_OWNER_ALLOWLIST:
                findings.append(f"{key}: operational-row-update owner is not allowlisted")
    return findings


def _suggest_row(query: DetectedQuery, existing: dict | None) -> dict:
    if existing:
        return {
            "key": query.key,
            "classification": existing["classification"],
            "required_guard": existing["required_guard"],
            "owner": query.owner,
        }
    if query.owner in OPERATIONAL_OWNER_ALLOWLIST:
        classification, guard = "operational-row-update", "operational_allowlist"
    elif query.owner in EXACT_ID_OWNER_ALLOWLIST and query.exact_id_lookup:
        classification, guard = "exact-id-view", "exact_id"
    elif "historical_predicate" in query.guard_calls:
        classification, guard = "historical-view", "historical_predicate"
    else:
        classification, guard = "current-view", "current_predicate"
    return {
        "key": query.key,
        "classification": classification,
        "required_guard": guard,
        "owner": query.owner,
    }


def write_inventory(*, app_root: Path, inventory_path: Path) -> None:
    old_payload = _load_inventory(inventory_path)
    old_rows, _ = _row_map(old_payload)
    rows = [
        _suggest_row(query, old_rows.get(query.key))
        for query in scan_memory_queries(app_root)
    ]
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(
        json.dumps({"schema_version": 1, "queries": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check direct MemoryEntry query ownership.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    app_root = repository_root / "app"
    inventory_path = repository_root / "docs/current-memory-query-inventory.json"
    if args.write:
        write_inventory(app_root=app_root, inventory_path=inventory_path)
        return 0
    findings = check_inventory(app_root=app_root, inventory_path=inventory_path)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
