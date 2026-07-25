from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status

from app.models.enums import MemoryProvenance
from app.schemas.memory import ValidationEvidence
from app.security import AuthPrincipal, safe_actor_id


SERVICE_OWNED_METADATA_KEYS = frozenset(
    {
        "quality",
        "quality_review_required",
        "review_overdue",
        "review_status",
        "review_history",
        "requires_review",
        "import_runs_count",
        "last_imported_at",
        "import_history",
        "import_conflicts",
        "decision_conflicts",
        "decision_status",
        "supersedes_entry_id",
        "deprecated_by_entry_id",
    }
)
LEGACY_COMPATIBILITY_METADATA_KEYS = frozenset({"quality_review_required", "requires_review", "decision_conflicts"})

_FORBIDDEN = re.compile(
    r"(?i)(authorization\s*:\s*bearer|x-api-key\s*:|-----begin .*private key-----|\b(?:sk|ghp|gho|xoxb|xoxp)-[a-z0-9_-]{8,}|\b(?:password|passwd|secret|token)\s*[:=]|\b(?:stdout|stderr|response_body|raw_output|customer_payload)\b)"
)
def scan_privacy_safe(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"authorization", "x-api-key", "password", "secret", "token", "stdout", "stderr", "raw_output", "response_body"}:
                return False
            if not scan_privacy_safe(item):
                return False
        return True
    if isinstance(value, (list, tuple)):
        return all(scan_privacy_safe(item) for item in value)
    if value is None:
        return True
    text = str(value)
    if "[REDACTED]" in text:
        return True
    return not _FORBIDDEN.search(text)


class MemoryEvidenceService:
    @staticmethod
    def validate_provenance(
        provenance: MemoryProvenance,
        *,
        principal: AuthPrincipal,
        metadata: dict[str, Any],
        operation_source: str = "api",
    ) -> list[dict[str, Any]]:
        forbidden_metadata = (SERVICE_OWNED_METADATA_KEYS - LEGACY_COMPATIBILITY_METADATA_KEYS).intersection(metadata)
        if operation_source == "api" and forbidden_metadata:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="service-owned metadata is not client writable")
        if not scan_privacy_safe(metadata):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="metadata contains sensitive evidence")
        if provenance is MemoryProvenance.imported and operation_source != "import" and not ({"import", "admin"} & principal.scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="imported provenance requires import scope")
        if provenance is MemoryProvenance.validated:
            if not ({"validate", "admin"} & principal.scopes):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="validated provenance requires validate scope")
            raw_evidence = metadata.get("validation_evidence")
            if not isinstance(raw_evidence, list) or not raw_evidence:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="validated provenance requires validation_evidence")
            try:
                evidence = [ValidationEvidence.model_validate(item) for item in raw_evidence]
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid validation evidence") from exc
            if not all(scan_privacy_safe(item.model_dump(mode="json")) for item in evidence):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="validation evidence is not privacy safe")
            return [item.model_dump(mode="json") for item in evidence]
        return []

    @staticmethod
    def validate_reason(reason: str) -> str:
        if not reason or len(reason) > 500 or not scan_privacy_safe(reason):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reason is invalid or contains sensitive data")
        return reason
