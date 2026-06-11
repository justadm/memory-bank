import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "docs" / "schemas"
EXAMPLE_DIR = ROOT / "docs" / "examples"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_required_fields_present(schema: dict, example: dict) -> None:
    missing = [field for field in schema["required"] if field not in example]
    assert missing == []


def test_revision_pass_schema_and_example_contract():
    schema = load_json(SCHEMA_DIR / "revision_pass.v0.schema.json")
    example = load_json(EXAMPLE_DIR / "revision_pass.v0.example.json")

    assert schema["properties"]["schema_version"]["const"] == "revision_pass.v0"
    assert schema["properties"]["artifact"]["const"] == "local.agent.revision_pass_before_production_write.v0"
    assert_required_fields_present(schema, example)

    assert example["schema_version"] == "revision_pass.v0"
    assert example["artifact"] == "local.agent.revision_pass_before_production_write.v0"
    assert example["mode"] in {"lite", "standard", "full"}
    assert example["go_no_go"]["decision"] in {"GO", "NO-GO", "EMERGENCY-ROLLBACK"}
    assert set(example["roles_completed"]).issubset(set(example["roles_required"]))
    assert example["state_sync"]["git_status_checked"] is True
    assert example["state_sync"]["latest_handoff_checked"] is True
    assert example["go_no_go"]["required_verification"]
    assert example["go_no_go"]["forbidden_changes"]


def test_post_action_evidence_schema_and_example_contract():
    schema = load_json(SCHEMA_DIR / "post_action_evidence.v0.schema.json")
    example = load_json(EXAMPLE_DIR / "post_action_evidence.v0.example.json")

    assert schema["properties"]["schema_version"]["const"] == "post_action_evidence.v0"
    assert_required_fields_present(schema, example)

    assert example["schema_version"] == "post_action_evidence.v0"
    assert example["action_type"] in {
        "deploy",
        "rollback",
        "cleanup",
        "reimport",
        "crm_write",
        "flag_change",
        "data_write",
        "smoke_only",
    }
    assert example["approved_in_current_thread"] is True
    assert example["target"]["environment"] in {"local", "staging", "production"}
    assert example["changes"]
    assert example["read_back"]
    assert example["not_changed"]
    assert example["evidence_written_to"]
    assert example["privacy_check"]["secrets_exposed"] is False
    assert example["privacy_check"]["raw_payloads_included"] is False


def test_examples_do_not_contain_secret_like_literals():
    forbidden_fragments = [
        "sk-",
        "api_key=",
        "token=",
        "password=",
        "bearer ",
        "webhook",
    ]

    for path in sorted(EXAMPLE_DIR.glob("*.v0.example.json")):
        text = path.read_text(encoding="utf-8").lower()
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{path.name} contains {fragment}"
