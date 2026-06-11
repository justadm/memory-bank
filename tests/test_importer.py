from memorybank_sdk.importer import build_directory_import_payloads, build_project_import_payload


def test_build_project_import_payload_extracts_entries_and_tasks(tmp_path):
    (tmp_path / "README.md").write_text("# Demo Project\n\nFastAPI service with PostgreSQL.\n", encoding="utf-8")
    (tmp_path / "docker-compose.yml").write_text("services:\n  db:\n    image: postgres:16\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\npsycopg[binary]\n", encoding="utf-8")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("from fastapi import FastAPI\n# TODO: add auth\napp = FastAPI()\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")

    payload = build_project_import_payload(tmp_path, project_name="Demo Import")

    assert payload["project"]["name"] == "Demo Import"
    refs = {item["ref"] for item in payload["entries"]}
    assert "decision-postgresql-primary" in refs
    assert "constraint-fastapi-stack" in refs
    assert "artifact-app-main-py" in refs
    assert "note-tests-coverage" in refs
    assert any(item["type"] == "task" for item in payload["entries"])
    assert any(link["type"] == "derived_from" for link in payload["links"])


def test_build_directory_import_payloads_collects_child_projects(tmp_path):
    first = tmp_path / "alpha"
    first.mkdir()
    (first / "README.md").write_text("# Alpha\n", encoding="utf-8")

    second = tmp_path / "beta"
    second.mkdir()
    (second / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    ignored = tmp_path / "notes"
    ignored.mkdir()

    payloads = build_directory_import_payloads(tmp_path)

    names = [item["project"]["name"] for item in payloads]
    assert names == ["alpha", "beta"]


def test_build_project_import_payload_detects_node_go_and_monorepo_signals(tmp_path):
    (tmp_path / "README.md").write_text("# Poly Repo\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"name":"poly","scripts":{"dev":"next dev"},"dependencies":{"next":"15.0.0","react":"19.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "go.mod").write_text("module github.com/example/poly\n\ngo 1.24\n", encoding="utf-8")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - apps/*\n", encoding="utf-8")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.ts").write_text("console.log('hello')\n", encoding="utf-8")

    payload = build_project_import_payload(tmp_path, project_name="Poly Repo")
    refs = {item["ref"] for item in payload["entries"]}

    assert "decision-nodejs-runtime" in refs
    assert "decision-go-runtime" in refs
    assert "constraint-monorepo-layout" in refs
    assert "constraint-nodejs-runtime" in refs
    assert "constraint-go-runtime" in refs
    assert "note-package-scripts" in refs
    assert "note-go-module" in refs
    assert "risk-env-secrets" not in refs
    assert "artifact-src-index-ts" in refs


def test_build_project_import_payload_extracts_doc_driven_handoff_signals(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    handoff_dir = tmp_path / "mvp-handoff"
    handoff_dir.mkdir()

    (docs_dir / "decision-log.md").write_text(
        "# Decision Log\n\n"
        "- BuildGuard is a pre-build decision engine, not an AI PM.\n"
        "- Use a staged pipeline: stress_test -> questions -> refine -> prd -> tasks -> markdown.\n"
        "- Use SQLite first, not Postgres.\n"
        "- Do not add authentication in V1.\n",
        encoding="utf-8",
    )
    (docs_dir / "v1-technical-blueprint.md").write_text(
        "# Blueprint\n\n"
        "Use Next.js App Router with TypeScript, Tailwind, SQLite, Drizzle, and Zod.\n"
        "Structured output is mandatory.\n"
        "Develop behind BuildGuard.loc and keep Docker early.\n",
        encoding="utf-8",
    )
    (handoff_dir / "03-mvp-development-spec.md").write_text(
        "The user starts from a raw idea and answers clarification questions before PRD generation.\n\n"
        "### EPIC-001: Project setup\n"
        "- Initialize Next.js TypeScript app\n"
        "- Add Tailwind\n\n"
        "### EPIC-002: Idea intake\n"
        "- Create homepage input form\n"
        "- Redirect to analysis page\n",
        encoding="utf-8",
    )

    payload = build_project_import_payload(tmp_path, project_name="BuildGuard")
    refs = {item["ref"] for item in payload["entries"]}

    assert "artifact-docs-decision-log-md" in refs
    assert "artifact-docs-v1-technical-blueprint-md" in refs
    assert "artifact-mvp-handoff-03-mvp-development-spec-md" in refs
    assert "decision-prebuild-decision-engine" in refs
    assert "decision-staged-llm-pipeline" in refs
    assert "decision-schema-first-runtime" in refs
    assert "decision-nextjs-app-router" in refs
    assert "constraint-anonymous-session-v1" in refs
    assert "constraint-local-loc-domain" in refs
    assert "constraint-docker-early" in refs
    assert "risk-structured-output-failures" in refs
    assert "risk-founder-input-ambiguity" in refs
    assert any(item["title"] == "EPIC-001: Project setup" for item in payload["entries"])
    assert any(item["title"] == "EPIC-002: Idea intake" for item in payload["entries"])


def test_build_project_import_payload_extracts_hidden_docs_and_spec_signals(tmp_path):
    hidden_docs_dir = tmp_path / ".docs"
    hidden_docs_dir.mkdir()
    openspec_dir = tmp_path / "openspec"
    openspec_dir.mkdir()

    (hidden_docs_dir / "CONTRACTOR_CHECK_TZ.md").write_text(
        "# ТЗ\n\n"
        "В MVP создается обычный список Битрикс24.\n"
        "Смарт-процесс в MVP не используется.\n"
        "Доступ исполнителя: только административная часть Битрикс24, без доступа к серверу.\n"
        "Перенос на тестовый контур выполняется через git и миграции.\n"
        "Текущий SharePoint остается источником исторических данных.\n"
        "Вложения содержат персональные данные.\n",
        encoding="utf-8",
    )
    (hidden_docs_dir / "WORKLOG.md").write_text(
        "# Worklog\n\n"
        "- Project context for lk.loc imported from hidden docs.\n",
        encoding="utf-8",
    )
    (openspec_dir / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    (tmp_path / "COMMITS.md").write_text(
        "Используется формат Conventional Commits.\n"
        "Обязательная строка: Task: 13244\n",
        encoding="utf-8",
    )

    payload = build_project_import_payload(tmp_path, project_name="lk.loc")
    refs = {item["ref"] for item in payload["entries"]}

    assert "artifact-docs-contractor-check-tz-md" in refs
    assert "artifact-docs-worklog-md" in refs
    assert "artifact-openspec-config-yaml" in refs
    assert "artifact-commits-md" in refs
    assert "decision-bitrix-list-mvp" in refs
    assert "decision-spec-driven-artifacts" in refs
    assert "constraint-admin-only-bitrix-access" in refs
    assert "constraint-git-migrations-delivery" in refs
    assert "constraint-sharepoint-history-source" in refs
    assert "risk-personal-data-attachments" in refs
    assert "note-openspec-schema-driven" in refs
    assert "note-commit-convention-task-link" in refs


def test_artifact_entries_include_source_path_evidence(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n\nUseful project documentation.\n", encoding="utf-8")

    payload = build_project_import_payload(tmp_path, project_name="Evidence Project")

    readme_entry = next(item for item in payload["entries"] if item["ref"] == "artifact-readme-md")
    assert readme_entry["metadata"]["path"] == "README.md"
    assert readme_entry["metadata"]["evidence"] == ["README.md"]


def test_fastapi_constraint_requires_runtime_signal_not_doc_mention(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Project\n\nThis document mentions FastAPI only as an example from a product idea log.\n",
        encoding="utf-8",
    )

    payload = build_project_import_payload(tmp_path, project_name="Docs Only Project")

    refs = {item["ref"] for item in payload["entries"]}
    assert "constraint-fastapi-stack" not in refs


def test_fastapi_constraint_uses_source_evidence_when_runtime_is_present(tmp_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    main = app_dir / "main.py"
    main.write_text("from fastapi import FastAPI\n\napp = FastAPI()\n", encoding="utf-8")

    payload = build_project_import_payload(tmp_path, project_name="FastAPI Project")

    constraint = next(item for item in payload["entries"] if item["ref"] == "constraint-fastapi-stack")
    assert constraint["metadata"]["evidence"] == ["app/main.py"]


def test_importer_quality_gated_entries_include_evidence(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    handoff_dir = tmp_path / "mvp-handoff"
    handoff_dir.mkdir()
    hidden_docs_dir = tmp_path / ".docs"
    hidden_docs_dir.mkdir()

    (tmp_path / "README.md").write_text(
        "# Project\n\nFastAPI service with PostgreSQL, ports: 8000, Docker Compose, and malformed JSON handling.\n",
        encoding="utf-8",
    )
    (tmp_path / "docker-compose.yml").write_text("services:\n  app:\n    ports:\n      - '8000:8000'\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\npsycopg[binary]\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"scripts":{"dev":"next dev"}}', encoding="utf-8")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - apps/*\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module example.com/app\n", encoding="utf-8")
    (docs_dir / "decision-log.md").write_text(
        "Use a staged pipeline: stress_test -> questions -> refine -> prd -> tasks -> markdown.\n"
        "Do not add authentication in V1. Fatal assumptions and missing data must be surfaced.\n",
        encoding="utf-8",
    )
    (docs_dir / "v1-technical-blueprint.md").write_text(
        "Use Next.js App Router. Structured output is mandatory. Develop behind BuildGuard.loc and keep Docker early.\n",
        encoding="utf-8",
    )
    (handoff_dir / "03-mvp-development-spec.md").write_text("Raw idea intake starts with clarification questions.\n", encoding="utf-8")
    (hidden_docs_dir / "CONTRACTOR_CHECK_TZ.md").write_text(
        "Доступ исполнителя: только административная часть Битрикс24, без доступа к серверу.\n"
        "Перенос на тестовый контур выполняется через git и миграции.\n"
        "Текущий SharePoint остается источником исторических данных.\n"
        "Вложения содержат персональные данные.\n",
        encoding="utf-8",
    )

    payload = build_project_import_payload(tmp_path, project_name="Quality Evidence Project")

    quality_gated_types = {"artifact", "decision", "constraint", "risk"}
    missing_evidence = [
        item["ref"]
        for item in payload["entries"]
        if item["type"] in quality_gated_types and not item["metadata"].get("evidence")
    ]
    assert missing_evidence == []
