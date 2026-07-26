from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from memorybank_sdk import DEFAULT_MEMORYBANK_URL

from .client import api_key_from_process_environment, make_client
from .manifest import ManifestConflict, validate_manifest_identity
from .service import ConnectorService


@dataclass(frozen=True)
class DoctorFinding:
    code: str
    path: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    local_connected: bool
    live_identity_ready: bool
    api_reachable: bool
    auth_authenticated: bool
    live_read_authorized: bool
    live_read_verified: bool
    live_write_authorized: bool
    live_write_verified: Literal["true", "false", "unknown"]
    snapshot_ready: bool
    queue_pending: int
    findings: tuple[DoctorFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        return payload


def _fresh(timestamp: Any, *, max_age: timedelta = timedelta(hours=24)) -> bool:
    if not timestamp:
        return False
    try:
        value = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - value
    return -timedelta(minutes=5) <= age <= max_age


def _ordered_timestamps(earlier: Any, later: Any) -> bool:
    try:
        earlier_value = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
        later_value = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
    except ValueError:
        return False
    if earlier_value.tzinfo is None:
        earlier_value = earlier_value.replace(tzinfo=timezone.utc)
    if later_value.tzinfo is None:
        later_value = later_value.replace(tzinfo=timezone.utc)
    return later_value >= earlier_value


class DoctorService:
    def __init__(self, project_root: str | Path, client: Any | None = None):
        self.service = ConnectorService(project_root)
        self.client = client

    def check(self) -> DoctorReport:
        findings: list[DoctorFinding] = []
        config_path = self.service._path(next(path for path in self.service.registry if str(path) == ".memlayer/memlayer.config.json"))
        snapshot_path = self.service._path(next(path for path in self.service.registry if str(path) == ".memlayer/memlayer.snapshot.json"))
        queue_path = self.service._path(next(path for path in self.service.registry if str(path) == ".memlayer/memlayer.offline.queue.jsonl"))
        try:
            manifest = self.service._manifest()
            local_connected = manifest is not None
        except ManifestConflict:
            manifest = None
            local_connected = False
            findings.append(DoctorFinding("invalid_manifest", ".memlayer/connection-manifest.json"))
        if manifest:
            integrity_findings = self.service.local_integrity_findings(manifest)
            if integrity_findings:
                local_connected = False
                findings.extend(
                    DoctorFinding(
                        item.code,
                        item.path,
                    )
                    for item in integrity_findings
                )

        config: dict[str, Any] = {}
        if config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                config = raw if isinstance(raw, dict) else {}
            except (OSError, UnicodeError, json.JSONDecodeError):
                findings.append(DoctorFinding("invalid_config", ".memlayer/memlayer.config.json"))
        if manifest:
            try:
                validate_manifest_identity(manifest, config=config)
            except ManifestConflict:
                findings.append(DoctorFinding("identity_mismatch", ".memlayer/memlayer.config.json"))
        local_identity_ready = bool(
            manifest
            and manifest.project_id
            and not any(item.code == "identity_mismatch" for item in findings)
        )

        queue_pending = 0
        if queue_path.exists():
            try:
                for line_number, line in enumerate(
                    queue_path.read_text(encoding="utf-8").splitlines(),
                    start=1,
                ):
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        item = None
                    if (
                        not isinstance(item, dict)
                        or not isinstance(item.get("endpoint"), str)
                        or not item["endpoint"].startswith("/")
                        or not isinstance(item.get("payload"), dict)
                    ):
                        findings.append(
                            DoctorFinding(
                                "invalid_queue_entry",
                                f".memlayer/memlayer.offline.queue.jsonl:{line_number}",
                            )
                        )
                        continue
                    queue_pending += 1
            except (OSError, UnicodeError):
                findings.append(DoctorFinding("queue_unreadable", ".memlayer/memlayer.offline.queue.jsonl"))

        snapshot_ready = False
        if snapshot_path.exists():
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                snapshot_ready = _fresh(snapshot.get("generated_at"))
                if not snapshot_ready:
                    findings.append(DoctorFinding("stale_snapshot", ".memlayer/memlayer.snapshot.json"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                findings.append(DoctorFinding("invalid_snapshot", ".memlayer/memlayer.snapshot.json"))
        else:
            findings.append(DoctorFinding("missing_snapshot", ".memlayer/memlayer.snapshot.json"))
        if queue_pending:
            findings.append(DoctorFinding("pending_queue", ".memlayer/memlayer.offline.queue.jsonl"))

        api_reachable = False
        auth_authenticated = False
        live_read_authorized = False
        live_read_verified = False
        live_write_authorized = False
        client = self.client
        owns_client = client is None
        if client is None:
            client = make_client(base_url=DEFAULT_MEMORYBANK_URL, api_key=api_key_from_process_environment())
        try:
            try:
                client.health()
                api_reachable = True
            except Exception:
                findings.append(DoctorFinding("api_unreachable"))
            try:
                auth = client.auth_status()
                auth_authenticated = bool(auth.get("authenticated"))
                scopes = set(auth.get("scopes") or [])
                live_read_authorized = bool({"read", "write", "import", "admin"} & scopes)
                live_write_authorized = "write" in scopes or "admin" in scopes
            except Exception:
                findings.append(DoctorFinding("auth_unavailable"))
            if local_identity_ready and live_read_authorized:
                try:
                    project = client.get_project(str(manifest.project_id))
                    live_read_verified = str(project.get("id")) == str(manifest.project_id)
                    if not live_read_verified:
                        findings.append(DoctorFinding("project_read_mismatch"))
                except Exception:
                    findings.append(DoctorFinding("project_read_failed"))
            elif local_identity_ready:
                findings.append(DoctorFinding("read_not_authorized"))
        finally:
            if owns_client:
                close = getattr(client, "close", None)
                if close:
                    close()

        write_check = config.get("last_write_check") if isinstance(config.get("last_write_check"), dict) else {}
        successful_receipt = (
            write_check.get("status") == "success"
            and write_check.get("operation") in {"project_registration", "memory_write"}
            and write_check.get("target_type") == "project"
            and manifest is not None
            and str(write_check.get("target_id")) == str(manifest.project_id)
            and bool(write_check.get("receipt_id"))
            and _fresh(write_check.get("attempted_at"))
            and _fresh(write_check.get("read_back_at"))
            and _ordered_timestamps(
                write_check.get("attempted_at"),
                write_check.get("read_back_at"),
            )
        )
        live_identity_ready = local_identity_ready and live_read_verified
        if successful_receipt and live_read_verified:
            live_write_verified: Literal["true", "false", "unknown"] = "true"
        elif _fresh(write_check.get("attempted_at")) and write_check.get("status") == "failed":
            live_write_verified = "false"
        else:
            live_write_verified = "unknown"

        return DoctorReport(
            local_connected=local_connected,
            live_identity_ready=live_identity_ready,
            api_reachable=api_reachable,
            auth_authenticated=auth_authenticated,
            live_read_authorized=live_read_authorized,
            live_read_verified=live_read_verified,
            live_write_authorized=live_write_authorized,
            live_write_verified=live_write_verified,
            snapshot_ready=snapshot_ready,
            queue_pending=queue_pending,
            findings=tuple(findings),
        )
