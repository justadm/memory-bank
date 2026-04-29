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
