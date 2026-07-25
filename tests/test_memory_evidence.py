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
    {"raw_output": "stdout"},
    {"private_key": "-----BEGIN PRIVATE KEY-----"},
    {"password": "value"},
])
def test_privacy_scanner_fails_closed(payload):
    assert scan_privacy_safe(payload) is False


def test_actor_is_safe_and_not_an_api_key():
    actor = safe_actor_id(principal("write"))
    assert actor == "reviewer-example.com"
    assert "never-expose" not in actor
    assert ValidationEvidence.model_validate(evidence()).contains_sensitive_data is False
