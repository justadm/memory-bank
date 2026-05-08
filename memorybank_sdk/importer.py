from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


IMPORTANT_FILENAMES = [
    "README.md",
    "README.txt",
    "COMMITS.md",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "requirements.txt",
    "package.json",
    "pyproject.toml",
    "go.mod",
    "pnpm-workspace.yaml",
    "turbo.json",
    "Makefile",
    ".env.example",
    "openspec/config.yaml",
]

IMPORTANT_DOC_DIRS = (".docs", "docs", "mvp-handoff")

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
COMMON_ENTRYPOINTS = [
    "app/main.py",
    "src/main.py",
    "src/index.ts",
    "src/main.ts",
    "main.go",
    "cmd/server/main.go",
]


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
    entries.extend(_derive_risks(files))
    entries.extend(_derive_notes(files, root))
    entries.extend(_derive_tasks(root))
    entries.extend(_derive_doc_backlog_tasks(files))

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
    if "artifact-package-json" in refs and "constraint-nodejs-runtime" in refs:
        links.append(
            {
                "from_ref": "artifact-package-json",
                "to_ref": "constraint-nodejs-runtime",
                "type": "derived_from",
                "strength": 0.7,
            }
        )
    if "artifact-go-mod" in refs and "constraint-go-runtime" in refs:
        links.append(
            {
                "from_ref": "artifact-go-mod",
                "to_ref": "constraint-go-runtime",
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

    for candidate in COMMON_ENTRYPOINTS:
        entrypoint = root / candidate
        if entrypoint.exists() and entrypoint.is_file():
            files[candidate] = _read_text(entrypoint)

    tests_dir = root / "tests"
    if tests_dir.exists():
        files["tests/"] = _summarize_tests_dir(tests_dir)

    for directory in IMPORTANT_DOC_DIRS:
        doc_dir = root / directory
        if not doc_dir.exists() or not doc_dir.is_dir():
            continue
        for path in sorted(doc_dir.rglob("*.md")):
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            relative = str(path.relative_to(root))
            files[relative] = _read_text(path)

    return files


def _looks_like_project(path: Path) -> bool:
    for candidate in IMPORTANT_FILENAMES:
        if (path / candidate).exists():
            return True
    for candidate in COMMON_ENTRYPOINTS:
        if (path / candidate).exists():
            return True
    if (path / "tests").exists():
        return True
    for directory in IMPORTANT_DOC_DIRS:
        if any((path / directory).rglob("*.md")):
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
    elif name.endswith(".ts") or name.endswith(".go"):
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
    package_json = _load_package_json(files.get("package.json"))
    if package_json:
        package_manager = _guess_package_manager(files)
        framework = _guess_node_framework(package_json, combined)
        decisions.append(
            {
                "ref": "decision-nodejs-runtime",
                "type": "decision",
                "title": "Use Node.js application runtime",
                "content": f"Project includes a package-managed JavaScript/TypeScript runtime{f' with {framework}' if framework else ''}{f' and {package_manager}' if package_manager else ''}.",
                "importance": 4,
                "metadata": {"evidence": _evidence(files, ["package.json", "pnpm-workspace.yaml", "turbo.json"]), "confidence": 0.88},
            }
        )
    if "go.mod" in files:
        module_name = _first_nonempty_line(files["go.mod"], prefix="module ")
        decisions.append(
            {
                "ref": "decision-go-runtime",
                "type": "decision",
                "title": "Use Go application runtime",
                "content": f"Project includes Go module configuration{f' for {module_name}' if module_name else ''}.",
                "importance": 4,
                "metadata": {"evidence": _evidence(files, ["go.mod"]), "confidence": 0.88},
            }
        )
    if "pre-build decision engine" in combined or "not an ai pm" in combined:
        decisions.append(
            {
                "ref": "decision-prebuild-decision-engine",
                "type": "decision",
                "title": "Position BuildGuard as a pre-build decision engine",
                "content": "Project docs position the product as a pre-build decision engine that stress-tests ideas before generating implementation artifacts, explicitly not as an AI PM or generic PRD generator.",
                "importance": 5,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/decision-log.md", "docs/v1-technical-blueprint.md", "mvp-handoff/03-mvp-development-spec.md"]), "confidence": 0.95},
            }
        )
    if "stress_test -> questions -> refine -> prd -> tasks -> markdown" in combined:
        decisions.append(
            {
                "ref": "decision-staged-llm-pipeline",
                "type": "decision",
                "title": "Use a staged LLM pipeline",
                "content": "Project docs define a staged pipeline `stress_test -> questions -> refine -> prd -> tasks -> markdown` instead of one large generation call.",
                "importance": 5,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/decision-log.md", "docs/v1-technical-blueprint.md"]), "confidence": 0.94},
            }
        )
    if "structured output is mandatory" in combined or ("zod" in combined and "schema" in combined):
        decisions.append(
            {
                "ref": "decision-schema-first-runtime",
                "type": "decision",
                "title": "Use a schema-first runtime",
                "content": "Every LLM stage is expected to parse against dedicated schemas with structured output treated as mandatory rather than best-effort.",
                "importance": 5,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/decision-log.md", "docs/v1-technical-blueprint.md"]), "confidence": 0.93},
            }
        )
    if "single guided flow" in combined or "one main screen" in combined:
        decisions.append(
            {
                "ref": "decision-single-screen-guided-ux",
                "type": "decision",
                "title": "Prefer a single-screen guided UX",
                "content": "The docs recommend one guided flow with progressive steps instead of splitting the product into multiple disconnected pages.",
                "importance": 4,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/decision-log.md", "docs/v1-technical-blueprint.md", "mvp-handoff/03-mvp-development-spec.md"]), "confidence": 0.9},
            }
        )
    if "use sqlite first" in combined or ("sqlite" in combined and "drizzle" in combined):
        decisions.append(
            {
                "ref": "decision-sqlite-first-mvp",
                "type": "decision",
                "title": "Start MVP storage with SQLite",
                "content": "Current handoff docs prefer SQLite first for the MVP to reduce operational overhead, with Drizzle as the ORM layer.",
                "importance": 4,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/decision-log.md", "docs/v1-technical-blueprint.md"]), "confidence": 0.9},
            }
        )
    if "next.js" in combined and "app router" in combined:
        decisions.append(
            {
                "ref": "decision-nextjs-app-router",
                "type": "decision",
                "title": "Use Next.js App Router as the application shell",
                "content": "The recommended V1 architecture is a Next.js App Router application with TypeScript, Tailwind, and route-driven analysis flows.",
                "importance": 4,
                "metadata": {"evidence": _evidence_prefix(files, ["docs/v1-technical-blueprint.md", "mvp-handoff/03-mvp-development-spec.md"]), "confidence": 0.9},
            }
        )
    if "в mvp создается обычный список битрикс24" in combined or "обычный список битрикс24" in combined:
        decisions.append(
            {
                "ref": "decision-bitrix-list-mvp",
                "type": "decision",
                "title": "Use a standard Bitrix24 list for the MVP",
                "content": "The current MVP direction explicitly prefers a standard Bitrix24 list over a smart process to reduce delivery risk and avoid extra CRM/SPA dependencies.",
                "importance": 5,
                "metadata": {"evidence": _evidence_prefix(files, [".docs/CONTRACTOR_CHECK_TZ.md"]), "confidence": 0.95},
            }
        )
    if "schema: spec-driven" in combined:
        decisions.append(
            {
                "ref": "decision-spec-driven-artifacts",
                "type": "decision",
                "title": "Use a spec-driven delivery workflow",
                "content": "The repository ships with an OpenSpec configuration that declares a spec-driven workflow for creating and evolving project artifacts.",
                "importance": 4,
                "metadata": {"evidence": _evidence_prefix(files, ["openspec/config.yaml"]), "confidence": 0.9},
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
    if "package.json" in files:
        constraints.append(
            {
                "ref": "constraint-nodejs-runtime",
                "type": "constraint",
                "title": "Node.js package-managed runtime",
                "content": "Project runtime and scripts depend on package.json-managed JavaScript or TypeScript tooling.",
                "importance": 4,
                "metadata": {"confidence": 0.88},
            }
        )
    if "go.mod" in files:
        constraints.append(
            {
                "ref": "constraint-go-runtime",
                "type": "constraint",
                "title": "Go module runtime",
                "content": "Project build and execution depend on Go module tooling.",
                "importance": 4,
                "metadata": {"confidence": 0.88},
            }
        )
    if "pnpm-workspace.yaml" in files or "turbo.json" in files:
        constraints.append(
            {
                "ref": "constraint-monorepo-layout",
                "type": "constraint",
                "title": "Monorepo workspace layout",
                "content": "Project structure appears to be multi-package and should be handled as a monorepo during tooling and imports.",
                "importance": 4,
                "metadata": {"confidence": 0.85},
            }
        )
    if "do not add authentication in v1" in combined or "anonymous session persistence" in combined:
        constraints.append(
            {
                "ref": "constraint-anonymous-session-v1",
                "type": "constraint",
                "title": "Keep V1 authentication-free",
                "content": "Current MVP direction favors anonymous session persistence and explicitly avoids full authentication in V1.",
                "importance": 4,
                "metadata": {"confidence": 0.92},
            }
        )
    if "buildguard.loc" in combined:
        constraints.append(
            {
                "ref": "constraint-local-loc-domain",
                "type": "constraint",
                "title": "Develop behind a local .loc HTTPS domain",
                "content": "The project is expected to run behind `BuildGuard.loc` using the existing machine-wide `.loc` nginx and dnsmasq setup.",
                "importance": 3,
                "metadata": {"confidence": 0.88},
            }
        )
    if "use docker early" in combined or "keep docker early" in combined or "docker compose" in combined:
        constraints.append(
            {
                "ref": "constraint-docker-early",
                "type": "constraint",
                "title": "Keep the application container-friendly from the start",
                "content": "The handoff docs expect Docker and Docker Compose to be introduced early so local and future staging environments stay aligned.",
                "importance": 3,
                "metadata": {"confidence": 0.86},
            }
        )
    if "только административная часть битрикс24" in combined or "без доступа к серверу" in combined:
        constraints.append(
            {
                "ref": "constraint-admin-only-bitrix-access",
                "type": "constraint",
                "title": "Operate through Bitrix24 admin access only",
                "content": "Implementation is constrained to Bitrix24 administrative access without direct server access, so delivery must rely on UI-configurable settings, migrations, and safe admin-side tooling.",
                "importance": 5,
                "metadata": {"confidence": 0.94},
            }
        )
    if "через git и миграции" in combined:
        constraints.append(
            {
                "ref": "constraint-git-migrations-delivery",
                "type": "constraint",
                "title": "Deliver environment changes through git and migrations",
                "content": "Changes should be reproducible through versioned code and migrations, with manual admin actions limited to environment-specific settings that cannot be safely automated.",
                "importance": 4,
                "metadata": {"confidence": 0.92},
            }
        )
    if "sharepoint" in combined and "историчес" in combined:
        constraints.append(
            {
                "ref": "constraint-sharepoint-history-source",
                "type": "constraint",
                "title": "Keep SharePoint as the historical source during MVP",
                "content": "Historical data and attachments stay anchored in SharePoint until the customer provides a reliable export path, so MVP scope should not assume full archival migration is available.",
                "importance": 4,
                "metadata": {"confidence": 0.9},
            }
        )
    return constraints


def _derive_risks(files: dict[str, str]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    combined = _compact_text("\n".join(files.values())).lower()
    env_example = files.get(".env.example", "")
    if env_example:
        risks.append(
            {
                "ref": "risk-env-secrets",
                "type": "risk",
                "title": "Environment secret handling",
                "content": "Project exposes environment-variable configuration and imported knowledge should avoid storing real credentials or tokens.",
                "importance": 4,
                "metadata": {"evidence": _evidence(files, [".env.example"]), "confidence": 0.9},
            }
        )
    if "0.0.0.0" in combined or "ports:" in combined:
        risks.append(
            {
                "ref": "risk-public-runtime-surface",
                "type": "risk",
                "title": "Published runtime surface",
                "content": "Project configuration publishes network services and should be reviewed for accidental port exposure or permissive defaults.",
                "importance": 3,
                "metadata": {"confidence": 0.82},
            }
        )
    if "unstable json" in combined or "malformed json" in combined or "structured output is mandatory" in combined:
        risks.append(
            {
                "ref": "risk-structured-output-failures",
                "type": "risk",
                "title": "Structured LLM output can fail parsing",
                "content": "The handoff docs explicitly call unstable or malformed JSON the main technical risk, so parse/repair behavior must stay observable and recoverable.",
                "importance": 5,
                "metadata": {"confidence": 0.94},
            }
        )
    if "fatal assumptions" in combined or "missing data" in combined or ("raw idea" in combined and "clarification questions" in combined):
        risks.append(
            {
                "ref": "risk-founder-input-ambiguity",
                "type": "risk",
                "title": "Raw founder input may be incomplete or misleading",
                "content": "The product flow depends on surfacing fatal assumptions, missing data, and clarification questions before downstream PRD generation.",
                "importance": 4,
                "metadata": {"confidence": 0.88},
            }
        )
    if "персональные данные" in combined and "вложени" in combined:
        risks.append(
            {
                "ref": "risk-personal-data-attachments",
                "type": "risk",
                "title": "Historical attachments may contain personal data",
                "content": "Attachment migration and storage are constrained by personal-data handling requirements, so bulk import cannot be treated as a guaranteed MVP capability.",
                "importance": 5,
                "metadata": {"confidence": 0.94},
            }
        )
    return risks


def _derive_notes(files: dict[str, str], root: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    package_json = _load_package_json(files.get("package.json"))
    if package_json:
        scripts = sorted((package_json.get("scripts") or {}).keys())
        if scripts:
            notes.append(
                {
                    "ref": "note-package-scripts",
                    "type": "note",
                    "title": "Package scripts snapshot",
                    "content": _truncate(f"package.json scripts: {', '.join(scripts)}"),
                    "importance": 3,
                    "metadata": {"path": "package.json", "confidence": 0.9},
                }
            )
    if "go.mod" in files:
        module_name = _first_nonempty_line(files["go.mod"], prefix="module ")
        if module_name:
            notes.append(
                {
                    "ref": "note-go-module",
                    "type": "note",
                    "title": "Go module path",
                    "content": f"Detected Go module path: {module_name}",
                    "importance": 3,
                    "metadata": {"path": "go.mod", "confidence": 0.9},
                }
            )
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
    openspec_config = files.get("openspec/config.yaml", "")
    if "schema: spec-driven" in openspec_config.lower():
        notes.append(
            {
                "ref": "note-openspec-schema-driven",
                "type": "note",
                "title": "OpenSpec schema mode",
                "content": "Detected `openspec/config.yaml` with `schema: spec-driven`, indicating a spec-first artifact workflow.",
                "importance": 3,
                "metadata": {"path": "openspec/config.yaml", "confidence": 0.9},
            }
        )
    commits_doc = files.get("COMMITS.md", "")
    lowered_commits = commits_doc.lower()
    if "conventional commits" in lowered_commits and "task:" in lowered_commits:
        notes.append(
            {
                "ref": "note-commit-convention-task-link",
                "type": "note",
                "title": "Commit messages require task-linked conventional format",
                "content": "Project commit policy uses Russian Conventional Commits and requires a separate `Task: <id>` line for every logical change.",
                "importance": 3,
                "metadata": {"path": "COMMITS.md", "confidence": 0.92},
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


def _derive_doc_backlog_tasks(files: dict[str, str]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    for path, content in files.items():
        if not path.endswith(".md"):
            continue
        for ref, title, body in _extract_epics_from_markdown(path, content):
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            tasks.append(
                {
                    "ref": ref,
                    "type": "task",
                    "title": title,
                    "content": body,
                    "importance": 4,
                    "metadata": {"path": path, "confidence": 0.88},
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


def _load_package_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _guess_package_manager(files: dict[str, str]) -> str | None:
    if "pnpm-workspace.yaml" in files:
        return "pnpm workspaces"
    if "turbo.json" in files:
        return "turbo monorepo tooling"
    return "npm-compatible package management" if "package.json" in files else None


def _guess_node_framework(package_json: dict[str, Any], combined: str) -> str | None:
    deps = {
        *list((package_json.get("dependencies") or {}).keys()),
        *list((package_json.get("devDependencies") or {}).keys()),
    }
    lowered = {item.lower() for item in deps}
    if "next" in lowered:
        return "Next.js"
    if "react" in lowered:
        return "React"
    if "vue" in lowered:
        return "Vue"
    if "express" in lowered or "express" in combined:
        return "Express"
    if "nestjs" in lowered or "@nestjs/core" in lowered:
        return "NestJS"
    return None


def _first_nonempty_line(text: str, *, prefix: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return None


def _summarize_tests_dir(tests_dir: Path) -> str:
    test_files = sorted(str(path.relative_to(tests_dir.parent)) for path in tests_dir.rglob("test_*.py") if path.is_file())
    if not test_files:
        return "Tests directory exists but no test files were detected."
    return _truncate(f"Detected test files: {', '.join(test_files)}", 500)


def _evidence(files: dict[str, str], candidates: list[str]) -> list[str]:
    return [name for name in candidates if name in files]


def _evidence_prefix(files: dict[str, str], candidates: list[str]) -> list[str]:
    available = set(files)
    return [name for name in candidates if name in available]


def _ref(prefix: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{prefix}-{slug}"


def _compact_text(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _extract_epics_from_markdown(path: str, content: str) -> list[tuple[str, str, str]]:
    lines = content.splitlines()
    epics: list[tuple[str, str, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_heading, buffer
        if not current_heading:
            return
        body_lines = [line.strip() for line in buffer if line.strip()]
        body = _truncate(" ".join(body_lines), 500)
        ref = _ref("task", f"{path}-{current_heading}")
        epics.append((ref, current_heading, body or f"Backlog item imported from {path}."))
        current_heading = None
        buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### EPIC-"):
            flush()
            current_heading = stripped.lstrip("#").strip()
            continue
        if current_heading:
            if stripped.startswith("### ") or stripped.startswith("## "):
                flush()
                continue
            buffer.append(stripped)

    flush()
    return epics


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
