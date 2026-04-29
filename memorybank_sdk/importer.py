from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


IMPORTANT_FILENAMES = [
    "README.md",
    "README.txt",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    ".env.example",
]

TEXT_FILE_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".env",
    ".ini",
    ".cfg",
}

EXCLUDED_DIRS = {".git", ".venv", ".venv313", "__pycache__", "node_modules", ".pytest_cache"}


def build_project_import_payload(
    project_root: str | Path,
    *,
    project_name: str | None = None,
    project_description: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    files = _read_important_files(root)

    project = {
        "name": project_name or root.name,
        "description": project_description or _derive_project_description(files),
        "metadata": {"source_path": str(root)},
    }
    entries: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for name, content in files.items():
        entry = _artifact_entry_for_file(name, content)
        if entry:
            entries.append(entry)

    entries.extend(_derive_decisions(files))
    entries.extend(_derive_constraints(files))
    entries.extend(_derive_notes(files, root))
    entries.extend(_derive_tasks(root))

    refs = {item["ref"] for item in entries}
    if "artifact-docker-compose-yml" in refs and "decision-postgresql-primary" in refs:
        links.append(
            {
                "from_ref": "artifact-docker-compose-yml",
                "to_ref": "decision-postgresql-primary",
                "type": "derived_from",
                "strength": 0.8,
            }
        )
    if "artifact-app-main-py" in refs and "constraint-fastapi-stack" in refs:
        links.append(
            {
                "from_ref": "artifact-app-main-py",
                "to_ref": "constraint-fastapi-stack",
                "type": "derived_from",
                "strength": 0.7,
            }
        )
    for item in entries:
        if item["type"] == "task" and "decision-postgresql-primary" in refs:
            links.append(
                {
                    "from_ref": item["ref"],
                    "to_ref": "decision-postgresql-primary",
                    "type": "depends_on",
                    "strength": 0.5,
                }
            )

    return {
        "project": project,
        "entries": _dedupe_by_ref(entries),
        "links": _dedupe_links(links),
        "detect_conflicts": True,
    }


def build_directory_import_payloads(
    projects_root: str | Path,
    *,
    names: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    root = Path(projects_root).resolve()
    candidates = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith(".") or path.name in EXCLUDED_DIRS:
            continue
        if names and path.name not in set(names):
            continue
        if _looks_like_project(path):
            candidates.append(path)
    if limit is not None:
        candidates = candidates[:limit]

    return [build_project_import_payload(path, project_name=path.name) for path in candidates]


def _read_important_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for candidate in IMPORTANT_FILENAMES:
        path = root / candidate
        if path.exists() and path.is_file():
            files[candidate] = _read_text(path)

    entrypoint = root / "app" / "main.py"
    if entrypoint.exists():
        files["app/main.py"] = _read_text(entrypoint)

    tests_dir = root / "tests"
    if tests_dir.exists():
        files["tests/"] = _summarize_tests_dir(tests_dir)

    return files


def _looks_like_project(path: Path) -> bool:
    for candidate in IMPORTANT_FILENAMES:
        if (path / candidate).exists():
            return True
    if (path / "app" / "main.py").exists():
        return True
    if (path / "tests").exists():
        return True
    return False


def _derive_project_description(files: dict[str, str]) -> str:
    readme = files.get("README.md") or files.get("README.txt")
    if readme:
        first_meaningful = next((line.strip("# ").strip() for line in readme.splitlines() if line.strip()), None)
        if first_meaningful:
            return first_meaningful[:255]
    return "Project imported from existing repository"


def _artifact_entry_for_file(name: str, content: str) -> dict[str, Any] | None:
    if name == "tests/":
        return None
    title = name
    artifact_type = "documentation"
    if "docker" in name.lower():
        artifact_type = "infrastructure"
    elif name.endswith(".py"):
        artifact_type = "source"
    elif name.endswith(".json") or name.endswith(".toml") or name.endswith(".txt"):
        artifact_type = "configuration"
    return {
        "ref": _ref("artifact", name),
        "type": "artifact",
        "title": title,
        "content": _truncate(f"{name} summary:\n{_compact_text(content)}"),
        "importance": 4 if artifact_type in {"infrastructure", "source"} else 3,
        "metadata": {"path": name, "artifact_type": artifact_type, "confidence": 0.9},
    }


def _derive_decisions(files: dict[str, str]) -> list[dict[str, Any]]:
    combined = _compact_text("\n".join(files.values())).lower()
    decisions: list[dict[str, Any]] = []
    if "postgresql" in combined or "psycopg" in combined:
        decisions.append(
            {
                "ref": "decision-postgresql-primary",
                "type": "decision",
                "title": "Use PostgreSQL as primary database",
                "content": "Project configuration and dependencies indicate PostgreSQL as the primary database.",
                "importance": 4,
                "metadata": {"evidence": _evidence(files, ["docker-compose.yml", "requirements.txt", "README.md"]), "confidence": 0.9},
            }
        )
    return decisions


def _derive_constraints(files: dict[str, str]) -> list[dict[str, Any]]:
    combined = _compact_text("\n".join(files.values())).lower()
    constraints: list[dict[str, Any]] = []
    if "fastapi" in combined:
        constraints.append(
            {
                "ref": "constraint-fastapi-stack",
                "type": "constraint",
                "title": "FastAPI service stack",
                "content": "Project currently depends on FastAPI-based HTTP endpoints and should preserve that runtime shape.",
                "importance": 4,
                "metadata": {"confidence": 0.9},
            }
        )
    if "docker compose" in combined or "docker-compose" in combined:
        constraints.append(
            {
                "ref": "constraint-docker-runtime",
                "type": "constraint",
                "title": "Docker Compose runtime",
                "content": "Project startup and local verification depend on Docker Compose orchestration.",
                "importance": 3,
                "metadata": {"confidence": 0.85},
            }
        )
    return constraints


def _derive_notes(files: dict[str, str], root: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if "tests/" in files:
        notes.append(
            {
                "ref": "note-tests-coverage",
                "type": "note",
                "title": "Test suite coverage snapshot",
                "content": files["tests/"],
                "importance": 3,
                "metadata": {"path": "tests/", "confidence": 0.85},
            }
        )
    notes.append(
        {
            "ref": "event-import-source",
            "type": "note",
            "title": "Import source path",
            "content": f"Imported from local path {root}",
            "importance": 2,
            "metadata": {"confidence": 1.0},
        }
    )
    return notes


def _derive_tasks(root: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index, item in enumerate(_scan_todos(root), start=1):
        tasks.append(
            {
                "ref": f"task-todo-{index}",
                "type": "task",
                "title": f"Follow up TODO in {item['path']}",
                "content": item["content"],
                "importance": 3,
                "metadata": {"path": item["path"], "line": item["line"], "confidence": 0.8},
            }
        )
    return tasks


def _scan_todos(root: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(findings) >= limit:
            break
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if "TODO" in line or "FIXME" in line:
                    findings.append(
                        {
                            "path": str(path.relative_to(root)),
                            "line": line_no,
                            "content": _truncate(f"{path.relative_to(root)}:{line_no} {line.strip()}", 240),
                        }
                    )
                    if len(findings) >= limit:
                        break
        except OSError:
            continue
    return findings


def _summarize_tests_dir(tests_dir: Path) -> str:
    test_files = sorted(str(path.relative_to(tests_dir.parent)) for path in tests_dir.rglob("test_*.py") if path.is_file())
    if not test_files:
        return "Tests directory exists but no test files were detected."
    return _truncate(f"Detected test files: {', '.join(test_files)}", 500)


def _evidence(files: dict[str, str], candidates: list[str]) -> list[str]:
    return [name for name in candidates if name in files]


def _ref(prefix: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{prefix}-{slug}"


def _compact_text(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _dedupe_by_ref(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in entries:
        ref = item["ref"]
        if ref in seen:
            continue
        seen.add(ref)
        deduped.append(item)
    return deduped


def _dedupe_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in links:
        key = json.dumps([item["from_ref"], item["to_ref"], item["type"]])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
