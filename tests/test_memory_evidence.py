from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.models.enums import MemoryProvenance
from app.schemas.memory import ValidationEvidence
from app.security import AuthPrincipal, safe_actor_id
from app.services.memory_evidence_service import MemoryEvidenceService, scan_privacy_safe


def principal(*scopes):
    return AuthPrincipal(name="reviewer@example.com", scopes=set(scopes), api_key="never-expose")


def evidence():
    return {
        "kind": "read_back",
        "summary": "Sanitized read-back confirmed the expected state.",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "redacted": True,
        "contains_sensitive_data": False,
    }


def test_validated_provenance_requires_scope_and_safe_evidence():
    with pytest.raises(HTTPException):
        MemoryEvidenceService.validate_provenance(
            MemoryProvenance.validated,
            principal=principal("write"),
            metadata={"validation_evidence": [evidence()]},
        )
    result = MemoryEvidenceService.validate_provenance(
        MemoryProvenance.validated,
        principal=principal("validate"),
        metadata={"validation_evidence": [evidence()]},
    )
    assert result[0]["redacted"] is True


@pytest.mark.parametrize("payload", [
    {"authorization": "Bearer secret"},
    {"api_key": "sensitive-value"},
    {"customer_payload": "private customer record"},
    {"raw_output": "stdout"},
    {"private_key": "-----BEGIN PRIVATE KEY-----"},
    {"password": "value"},
    "api_key=sensitive-value",
])
def test_privacy_scanner_fails_closed(payload):
    assert scan_privacy_safe(payload) is False


def test_actor_is_safe_and_not_an_api_key():
    actor = safe_actor_id(principal("write"))
    assert actor.startswith("principal-")
    assert "never-expose" not in actor
    assert ValidationEvidence.model_validate(evidence()).contains_sensitive_data is False


def test_redacted_marker_does_not_bypass_remaining_sensitive_text():
    assert scan_privacy_safe("[REDACTED] token=still-secret") is False


def test_provenance_is_normalized_and_generic_api_cannot_claim_imported():
    with pytest.raises(HTTPException):
        MemoryEvidenceService.validate_provenance(
            "imported",
            principal=principal("import", "admin"),
            metadata={},
            operation_source="api",
        )

    assert (
        MemoryEvidenceService.validate_provenance(
            "imported",
            principal=principal("import"),
            metadata={},
            operation_source="import",
        )
        == []
    )


def test_generic_api_rejects_all_service_owned_metadata():
    for key in (
        "quality_review_required",
        "requires_review",
        "decision_conflicts",
        "review_history",
    ):
        with pytest.raises(HTTPException):
            MemoryEvidenceService.validate_provenance(
                "unspecified",
                principal=principal("write"),
                metadata={key: True},
                operation_source="api",
            )
