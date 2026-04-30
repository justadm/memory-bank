from __future__ import annotations

import os

from memorybank_sdk import DEFAULT_MEMORYBANK_URL, MemoryBankClient


def build_import_payload() -> dict:
    return {
        "project": {
            "name": "Sample Imported Project",
            "description": "Imported through the embedded SDK example importer.",
            "metadata": {"source": "examples/project_importer.py"},
        },
        "entries": [
            {
                "ref": "decision-db",
                "type": "decision",
                "title": "Use PostgreSQL as primary database",
                "content": "docker-compose and runtime config point to PostgreSQL as the main database.",
                "importance": 4,
                "metadata": {"evidence": ["docker-compose.yml"], "confidence": 0.95},
            },
            {
                "ref": "artifact-compose",
                "type": "artifact",
                "title": "docker-compose.yml",
                "content": "Defines api and db services, with the API waiting for PostgreSQL health readiness.",
                "importance": 4,
                "metadata": {"path": "docker-compose.yml", "artifact_type": "infrastructure"},
            },
            {
                "ref": "constraint-stack",
                "type": "constraint",
                "title": "FastAPI + PostgreSQL stack",
                "content": "Current service behavior depends on FastAPI, SQLAlchemy, Alembic, and PostgreSQL.",
                "importance": 4,
                "metadata": {"confidence": 0.9},
            },
            {
                "ref": "risk-secrets",
                "type": "risk",
                "title": "Secret leakage during import",
                "content": "Imported notes must never keep api_key=demo-secret-value or other credentials.",
                "importance": 5,
                "metadata": {"confidence": 0.9},
            },
        ],
        "links": [
            {
                "from_ref": "artifact-compose",
                "to_ref": "decision-db",
                "type": "derived_from",
                "strength": 0.8,
            },
            {
                "from_ref": "constraint-stack",
                "to_ref": "decision-db",
                "type": "depends_on",
                "strength": 0.7,
            },
            {
                "from_ref": "risk-secrets",
                "to_ref": "artifact-compose",
                "type": "affects",
                "strength": 0.9,
            },
        ],
    }


def main() -> None:
    base_url = os.getenv("MEMORYBANK_URL", DEFAULT_MEMORYBANK_URL)
    api_key = os.getenv("MEMORYBANK_API_KEY")

    with MemoryBankClient(base_url=base_url, api_key=api_key) as client:
        result = client.import_project_scan(**build_import_payload())

    print("Project:", result["project"])
    print("Import event:", result["import_event_id"])
    print("Entries created:", result["entries_created"])
    print("Links created:", result["links_created"])
    print("Entry refs:", result["entry_refs"])


if __name__ == "__main__":
    main()
