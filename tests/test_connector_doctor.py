import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from memlayer_connector.doctor import DoctorService, _fresh, _ordered_timestamps
from memlayer_connector.service import ConnectorService


class FakeApi:
    def health(self):
        return {"status": "ok", "secret": "do-not-leak"}

    def auth_status(self):
        return {"authenticated": True, "scopes": ["read", "write"], "body": "private"}

    def get_project(self, project_id):
        return {"id": project_id, "tenant_id": "tenant-a", "content": "private payload"}

    def verify_project_connector(
        self,
        project_id,
        *,
        agent,
        connector_identity,
        tenant_id,
    ):
        return {
            "project_id": project_id,
            "agent": agent,
            "connector_identity": connector_identity,
            "tenant_id": tenant_id,
            "bound": True,
        }


class UnreachableApi:
    def health(self):
        raise OSError("offline")

    def auth_status(self):
        raise OSError("offline")

    def verify_project_connector(self, *args, **kwargs):
        raise OSError("offline")


def test_write_scope_is_authorized_not_verified(tmp_path: Path):
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    manifest.project_id = UUID("d8399b69-82ff-46ec-8e03-1930f1c84735")
    from memlayer_connector.manifest import write_manifest_atomic
    write_manifest_atomic(service.manifest_path, manifest)
    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text())
    config["project_id"] = str(manifest.project_id)
    config["tenant_id"] = "tenant-a"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    from memlayer_connector.service import _digest

    config_spec = next(
        spec
        for path, spec in service.registry.items()
        if str(path) == ".memlayer/memlayer.config.json"
    )
    managed = {key: config.get(key) for key in config_spec.managed_keys}
    for record in manifest.managed_files:
        if record.path == ".memlayer/memlayer.config.json":
            record.content_sha256 = _digest(
                (
                    json.dumps(
                        managed,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
    write_manifest_atomic(service.manifest_path, manifest)

    report = DoctorService(tmp_path, FakeApi()).check()

    assert report.api_reachable is True
    assert report.live_read_authorized is True
    assert report.live_read_verified is True
    assert report.live_write_authorized is True
    assert report.live_write_verified == "unknown"


def test_live_identity_rejects_tenant_scope_mismatch(tmp_path: Path):
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    manifest.project_id = UUID("d8399b69-82ff-46ec-8e03-1930f1c84735")
    from memlayer_connector.manifest import write_manifest_atomic
    from memlayer_connector.service import _digest

    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text())
    config["project_id"] = str(manifest.project_id)
    config["tenant_id"] = "tenant-b"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    config_spec = next(
        spec
        for path, spec in service.registry.items()
        if str(path) == ".memlayer/memlayer.config.json"
    )
    managed = {key: config.get(key) for key in config_spec.managed_keys}
    for record in manifest.managed_files:
        if record.path == ".memlayer/memlayer.config.json":
            record.content_sha256 = _digest(
                (
                    json.dumps(
                        managed,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
    write_manifest_atomic(service.manifest_path, manifest)

    report = DoctorService(tmp_path, FakeApi()).check()

    assert report.live_read_verified is False
    assert report.live_identity_ready is False
    assert any(
        finding.code == "project_tenant_mismatch"
        for finding in report.findings
    )


def test_live_identity_requires_matching_server_binding(tmp_path: Path):
    class MissingBindingApi(FakeApi):
        def verify_project_connector(self, *args, **kwargs):
            return {"bound": False}

    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    manifest.project_id = UUID("d8399b69-82ff-46ec-8e03-1930f1c84735")
    from memlayer_connector.manifest import write_manifest_atomic
    from memlayer_connector.service import _digest

    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text())
    config["project_id"] = str(manifest.project_id)
    config["tenant_id"] = "tenant-a"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    config_spec = next(
        spec
        for path, spec in service.registry.items()
        if str(path) == ".memlayer/memlayer.config.json"
    )
    managed = {key: config.get(key) for key in config_spec.managed_keys}
    for record in manifest.managed_files:
        if record.path == ".memlayer/memlayer.config.json":
            record.content_sha256 = _digest(
                (
                    json.dumps(
                        managed,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
    write_manifest_atomic(service.manifest_path, manifest)

    report = DoctorService(tmp_path, MissingBindingApi()).check()

    assert report.live_read_verified is False
    assert report.live_identity_ready is False
    assert any(
        finding.code == "project_binding_mismatch"
        for finding in report.findings
    )


def test_live_identity_requires_authenticated_project_read_back(tmp_path: Path):
    service = ConnectorService(tmp_path)
    manifest = service.apply_connect(service.plan_connect())
    manifest.project_id = UUID("d8399b69-82ff-46ec-8e03-1930f1c84735")
    from memlayer_connector.manifest import write_manifest_atomic
    from memlayer_connector.service import _digest

    config_path = tmp_path / ".memlayer/memlayer.config.json"
    config = json.loads(config_path.read_text())
    config["project_id"] = str(manifest.project_id)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    config_spec = next(
        spec
        for path, spec in service.registry.items()
        if str(path) == ".memlayer/memlayer.config.json"
    )
    managed = {key: config.get(key) for key in config_spec.managed_keys}
    for record in manifest.managed_files:
        if record.path == ".memlayer/memlayer.config.json":
            record.content_sha256 = _digest(
                (
                    json.dumps(
                        managed,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
    write_manifest_atomic(service.manifest_path, manifest)

    report = DoctorService(tmp_path, UnreachableApi()).check()

    assert report.local_connected is True
    assert report.live_identity_ready is False
    assert report.live_read_verified is False


def test_doctor_reports_queue_and_stale_snapshot_without_secrets(tmp_path: Path):
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    (tmp_path / ".memlayer/memlayer.offline.queue.jsonl").write_text(
        '{"endpoint":"/memory","payload":{"content":"abc"}}\n',
        encoding="utf-8",
    )
    (tmp_path / ".memlayer/memlayer.snapshot.json").write_text('{"generated_at":"2000-01-01T00:00:00+00:00", "content":"private"}', encoding="utf-8")

    output = DoctorService(tmp_path, FakeApi()).check().as_dict()
    serialized = json.dumps(output)

    assert output["queue_pending"] == 1
    assert any(item["code"] == "stale_snapshot" for item in output["findings"])
    assert "abc" not in serialized
    assert "private" not in serialized


def test_doctor_counts_only_valid_queue_records_and_reports_invalid_lines(tmp_path: Path):
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    (tmp_path / ".memlayer/memlayer.offline.queue.jsonl").write_text(
        '{"endpoint":"/memory","payload":{"type":"note"}}\n'
        'not-json\n["not", "an", "object"]\n{}\n',
        encoding="utf-8",
    )

    output = DoctorService(tmp_path, FakeApi()).check().as_dict()

    assert output["queue_pending"] == 1
    invalid = [
        item for item in output["findings"] if item["code"] == "invalid_queue_entry"
    ]
    assert [item["path"] for item in invalid] == [
        ".memlayer/memlayer.offline.queue.jsonl:2",
        ".memlayer/memlayer.offline.queue.jsonl:3",
        ".memlayer/memlayer.offline.queue.jsonl:4",
    ]


def test_doctor_does_not_report_local_connected_when_managed_file_drifted(tmp_path: Path):
    service = ConnectorService(tmp_path)
    service.apply_connect(service.plan_connect())
    (tmp_path / ".agents/skills/memlayer/SKILL.md").write_text("modified\n", encoding="utf-8")

    output = DoctorService(tmp_path, FakeApi()).check().as_dict()

    assert output["local_connected"] is False
    assert any(item["code"] == "managed_artifact_drift" for item in output["findings"])


def test_doctor_freshness_rejects_far_future_and_reversed_receipt_timestamps():
    now = datetime.now(timezone.utc)

    assert _fresh((now + timedelta(minutes=4)).isoformat()) is True
    assert _fresh((now + timedelta(minutes=6)).isoformat()) is False
    assert _ordered_timestamps(now.isoformat(), (now + timedelta(seconds=1)).isoformat())
    assert not _ordered_timestamps(
        now.isoformat(),
        (now - timedelta(seconds=1)).isoformat(),
    )
