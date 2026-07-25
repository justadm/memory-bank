from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from memorybank_sdk import DEFAULT_MEMORYBANK_URL

from .client import api_key_from_process_environment, make_client, resolve_and_verify
from .doctor import DoctorService
from .manifest import write_manifest_atomic
from .service import ConnectorConflict, ConnectorPlan, ConnectorService, _write_atomic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memlayer")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("connect", "disconnect"):
        sub = commands.add_parser(command)
        sub.add_argument("agent", choices=("codex",))
        sub.add_argument("--project-root", required=True)
        sub.add_argument("--apply", action="store_true")
        sub.add_argument("--json", action="store_true")
        if command == "connect":
            sub.add_argument("--register-project", action="store_true")
            sub.add_argument("--api-url", default=DEFAULT_MEMORYBANK_URL)
            sub.add_argument("--tenant-id")
            sub.add_argument("--existing-project-id")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("agent", choices=("codex",))
    doctor.add_argument("--project-root", required=True)
    doctor.add_argument("--json", action="store_true")
    return parser


def _plan_payload(plan: ConnectorPlan) -> dict[str, Any]:
    return {
        "operation": plan.operation,
        "project_root": plan.project_root,
        "ready": plan.ready,
        "actions": [
            {"kind": action.kind, "path": action.path, "ownership": action.ownership.value, "reason": action.reason}
            for action in plan.actions
        ],
        "conflicts": [{"code": item.code, "path": item.path, "reason": item.reason} for item in plan.conflicts],
    }


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    else:
        status = payload.get("status", "ready" if payload.get("ready") else "conflict")
        print(f"memlayer {payload.get('operation', 'operation')}: {status}")
        for conflict in payload.get("conflicts", []):
            print(f"- {conflict.get('code')}: {conflict.get('path')}: {conflict.get('reason')}")


def _persist_registration(service: ConnectorService, manifest: Any, resolved: dict[str, Any]) -> None:
    config_path = service._path(next(path for path in service.registry if str(path) == ".memlayer/memlayer.config.json"))
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config["connector_identity"] = str(manifest.connector_identity)
    config["project_id"] = str(resolved["project_id"])
    config["last_verified_write"] = {
        "status": "verified",
        "agent": "codex",
        "project_id": str(resolved["project_id"]),
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_atomic(config_path, (json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    manifest.project_id = UUID(str(resolved["project_id"]))
    write_manifest_atomic(service.manifest_path, manifest)


def run_connect(
    project_root: str | Path,
    *,
    apply: bool = False,
    register_project: bool = False,
    api_url: str = DEFAULT_MEMORYBANK_URL,
    tenant_id: str | None = None,
    existing_project_id: str | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    service = ConnectorService(project_root)
    if register_project and not apply:
        raise ValueError("--register-project requires --apply")
    plan = service.plan_connect()
    result = {"status": "ready" if plan.ready else "conflict", "mode": "apply" if apply else "dry_run", **_plan_payload(plan)}
    if not plan.ready:
        return result
    if not apply:
        return result
    manifest = service.apply_connect(plan)
    result["status"] = "applied"
    result["connector_identity"] = str(manifest.connector_identity)
    if register_project:
        client = (client_factory or make_client)(base_url=api_url, api_key=api_key_from_process_environment())
        try:
            resolved, project = resolve_and_verify(
                client,
                connector_identity=str(manifest.connector_identity),
                project_name=Path(project_root).resolve().name,
                tenant_id=tenant_id,
                existing_project_id=existing_project_id,
            )
        finally:
            close = getattr(client, "close", None)
            if close:
                close()
        _persist_registration(service, manifest, resolved)
        result["status"] = "registered"
        result["registration"] = {"resolved": resolved, "project": project}
    return result


def run_disconnect(project_root: str | Path, *, apply: bool = False) -> dict[str, Any]:
    service = ConnectorService(project_root)
    plan = service.plan_disconnect()
    result = {"status": "ready" if plan.ready else "conflict", "mode": "apply" if apply else "dry_run", **_plan_payload(plan)}
    if plan.ready and apply:
        service.apply_disconnect(plan)
        result["status"] = "disconnected"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "connect":
            if args.register_project and not args.apply:
                print("--register-project requires --apply", file=__import__("sys").stderr)
                return 2
            result = run_connect(
                args.project_root,
                apply=args.apply,
                register_project=args.register_project,
                api_url=args.api_url,
                tenant_id=args.tenant_id,
                existing_project_id=args.existing_project_id,
            )
        elif args.command == "disconnect":
            result = run_disconnect(args.project_root, apply=args.apply)
        else:
            result = {"status": "checked", "operation": "doctor", "project_root": str(Path(args.project_root).expanduser().resolve()), **DoctorService(args.project_root).check().as_dict()}
    except (ConnectorConflict, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2
    _emit(result, args.json)
    return 0 if result["status"] not in {"conflict"} else 1
